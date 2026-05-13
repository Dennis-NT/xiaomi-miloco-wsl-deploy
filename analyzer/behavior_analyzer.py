import logging
import threading
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from analyzer.config import Config
from analyzer.pose_detector import PoseDetector
from analyzer.hands_detector import HandsDetector
from analyzer.roi import RoiConfig
from analyzer.behavior_rules import BehaviorAccumulator
from analyzer.scoring import ScoringEngine

logger = logging.getLogger(__name__)


def _brush_score(finger_tips, mouth):
    """Higher score = finger closer to mouth."""
    if not finger_tips or mouth is None:
        return 0.0
    import math
    min_d = min(math.hypot(t[0] - mouth[0], t[1] - mouth[1]) for t in finger_tips)
    return 1.0 / (min_d + 0.01)


def _facewash_score(finger_tips, face, face_threshold=0.12):
    """Higher score = more fingers near face."""
    if not finger_tips or face is None:
        return 0
    import math
    count = sum(1 for t in finger_tips if math.hypot(t[0] - face[0], t[1] - face[1]) < face_threshold)
    return count


class BehaviorAnalyzer:
    def __init__(self, config: Config):
        self.config = config

        # Pose model
        pose_model = f"pose_landmarker_{config.analysis_pose_model}.task"
        pose_path = str(Path(__file__).resolve().parent / "models" / pose_model)
        self.pose_detector = PoseDetector(model_path=pose_path)

        # Hands model
        hands_model = config.get("hands", "model", default="hand_landmarker.task")
        hands_path = str(Path(__file__).resolve().parent / "models" / hands_model)
        self.hands_detector = HandsDetector(model_path=hands_path)

        self.roi = RoiConfig(config.get("roi"))
        self.scoring = ScoringEngine(
            toothbrush_min_done=config.analysis_threshold("toothbrush_min_seconds_done"),
            toothbrush_min_medium=config.analysis_threshold("toothbrush_min_seconds_medium"),
            toothbrush_min_good=config.analysis_threshold("toothbrush_min_seconds_good"),
            facewash_min_done=config.analysis_threshold("facewash_min_seconds_done"),
            facewash_min_medium=config.analysis_threshold("facewash_min_seconds_medium"),
            facewash_min_good=config.analysis_threshold("facewash_min_seconds_good"),
        )
        self.accumulator = BehaviorAccumulator(
            brush_finger_threshold=config.get("hands", "brush_finger_threshold", default=0.10),
            brush_wrist_threshold=config.get("hands", "brush_wrist_threshold", default=0.15),
            face_finger_threshold=config.get("hands", "face_finger_threshold", default=0.12),
            face_wrist_threshold=config.get("hands", "face_wrist_threshold", default=0.18),
            min_fingers_for_facewash=config.get("hands", "min_fingers_for_facewash", default=4),
            min_segment_seconds=config.get("analysis", "min_segment_seconds", default=2.0),
            min_segment_hits=config.get("analysis", "min_segment_hits", default=6),
            brush_min_motion=config.get("analysis", "brush_min_motion", default=0.020),
            facewash_min_motion=config.get("analysis", "facewash_min_motion", default=0.025),
        )
        self.frame_count = 0
        self.pose_detection_count = 0
        self.hands_detection_count = 0
        self._lock = threading.Lock()

        # Best frames tracking
        self.best_brush_frame: Optional[np.ndarray] = None
        self.best_brush_score = 0.0
        self.best_facewash_frame: Optional[np.ndarray] = None
        self.best_facewash_score = 0
        self.brush_frame_candidates: list[tuple[float, float, np.ndarray]] = []
        self.facewash_frame_candidates: list[tuple[float, float, np.ndarray]] = []
        self.accepted_brush_segments: list[tuple[float, float]] = []
        self.accepted_facewash_segments: list[tuple[float, float]] = []

        logger.info(
            "BehaviorAnalyzer initialized. Pose=%s, ROI=%s, Hands enabled",
            config.analysis_pose_model,
            self.roi.enabled,
        )

    def process_frame(self, frame_bgr: np.ndarray, relative_time: float):
        """Process a single frame and update internal state. Thread-safe."""
        with self._lock:
            self.frame_count += 1

            # 1. Pose detection
            landmarks = self.pose_detector.detect(frame_bgr)
            mouth = None
            face = None
            left_wrist = None
            right_wrist = None

            if landmarks is not None:
                # Filter out false positives (e.g. empty scene detected as person)
                if not self.pose_detector.is_valid_pose(landmarks):
                    return

                self.pose_detection_count += 1
                mouth = self.pose_detector.get_mouth_center(landmarks)
                face = self.pose_detector.get_face_center(landmarks)
                left_wrist, right_wrist = self.pose_detector.get_wrists(landmarks)
                if self.roi.enabled:
                    mouth = mouth if mouth is not None and self.roi.is_in_roi(mouth[0], mouth[1]) else None
                    face = face if face is not None and self.roi.is_in_roi(face[0], face[1]) else None
                if self.roi.enabled and mouth is None and face is None:
                    return

            # 2. Hands detection
            finger_tips = None
            hand_tip_groups = None
            hand_landmarks = self.hands_detector.detect(frame_bgr)
            if hand_landmarks:
                self.hands_detection_count += 1
                hand_tip_groups = self.hands_detector.get_finger_tip_groups(hand_landmarks)
                finger_tips = [tip for group in hand_tip_groups for tip in group]

            # 3. Update behavior rules
            is_brushing, is_facewashing = self.accumulator.update(
                relative_time,
                mouth,
                face,
                left_wrist,
                right_wrist,
                finger_tips=finger_tips,
                hand_tip_groups=hand_tip_groups,
            )

            # 4. Track best evidence frames
            # Use only frames that actually triggered an action.
            if is_brushing and mouth is not None:
                if finger_tips:
                    b_score = _brush_score(finger_tips, mouth)
                elif left_wrist is not None or right_wrist is not None:
                    # Fallback: use wrist distance as score
                    import math
                    d_left = math.hypot(left_wrist[0] - mouth[0], left_wrist[1] - mouth[1]) if left_wrist else float('inf')
                    d_right = math.hypot(right_wrist[0] - mouth[0], right_wrist[1] - mouth[1]) if right_wrist else float('inf')
                    b_score = 1.0 / (min(d_left, d_right) + 0.01)
                else:
                    b_score = 0.0

                if b_score > self.best_brush_score:
                    self.best_brush_score = b_score
                    self.best_brush_frame = frame_bgr.copy()
                self._remember_candidate(self.brush_frame_candidates, b_score, relative_time, frame_bgr)

            if is_facewashing and face is not None:
                if finger_tips:
                    fw_score = _facewash_score(finger_tips, face)
                elif left_wrist is not None and right_wrist is not None:
                    # Fallback: both wrists near face
                    import math
                    d_left = math.hypot(left_wrist[0] - face[0], left_wrist[1] - face[1])
                    d_right = math.hypot(right_wrist[0] - face[0], right_wrist[1] - face[1])
                    fw_score = int(d_left < 0.18 and d_right < 0.18)
                else:
                    fw_score = 0

                if fw_score > self.best_facewash_score:
                    self.best_facewash_score = fw_score
                    self.best_facewash_frame = frame_bgr.copy()
                self._remember_candidate(self.facewash_frame_candidates, float(fw_score), relative_time, frame_bgr)

    def _pose_in_roi(self, *points) -> bool:
        return any(point is not None and self.roi.is_in_roi(point[0], point[1]) for point in points)

    def _remember_candidate(
        self,
        candidates: list[tuple[float, float, np.ndarray]],
        score: float,
        relative_time: float,
        frame_bgr: np.ndarray,
        limit: int = 20,
    ):
        candidates.append((score, relative_time, frame_bgr.copy()))
        candidates.sort(key=lambda item: item[0], reverse=True)
        del candidates[limit:]

    def _best_candidate_in_segments(
        self,
        candidates: list[tuple[float, float, np.ndarray]],
        segments: list[tuple[float, float]],
    ) -> Optional[np.ndarray]:
        for _, t, frame in candidates:
            if any(start <= t <= end for start, end in segments):
                return frame
        return None

    def save_evidence_frames(self, tag: str, frames_dir: str) -> dict:
        """Save best frames to disk. Returns paths."""
        paths = {}
        out_dir = Path(frames_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        brush_frame = self._best_candidate_in_segments(self.brush_frame_candidates, self.accepted_brush_segments)
        facewash_frame = self._best_candidate_in_segments(self.facewash_frame_candidates, self.accepted_facewash_segments)

        if brush_frame is not None:
            path = out_dir / f"{tag}_best_brush.jpg"
            cv2.imwrite(str(path), brush_frame)
            paths["brush"] = str(path)
            logger.info("Saved best brush frame: %s", path)

        if facewash_frame is not None:
            path = out_dir / f"{tag}_best_facewash.jpg"
            cv2.imwrite(str(path), facewash_frame)
            paths["facewash"] = str(path)
            logger.info("Saved best facewash frame: %s", path)

        # Fallback: if no action detected, save a generic frame from processing
        if not paths and self.frame_count > 0:
            logger.info("No best frames to save")

        return paths

    def get_result(self, end_time: float) -> dict:
        """Finalize and return scoring result."""
        with self._lock:
            self.accumulator.finalize(end_time)

            tb_seconds = self.accumulator.total_brush_seconds()
            fw_seconds = self.accumulator.total_facewash_seconds()
            self.accepted_brush_segments = list(self.accumulator.brush_segments)
            self.accepted_facewash_segments = list(self.accumulator.facewash_segments)
            tb_cont = self.accumulator.brush_continuity_ratio()
            fw_cont = self.accumulator.facewash_continuity_ratio()

            # Phase 2 MVP: rinse detection is placeholder (always False)
            rinse = False

            tb_grade = self.scoring.score_toothbrush(tb_seconds, tb_cont, rinse)
            fw_grade = self.scoring.score_facewash(fw_seconds, fw_cont)
            summary = self.scoring.generate_summary(
                tb_grade, fw_grade, tb_seconds, fw_seconds, rinse
            )

            return {
                "toothbrush_grade": tb_grade,
                "facewash_grade": fw_grade,
                "toothbrush_seconds": int(tb_seconds),
                "facewash_seconds": int(fw_seconds),
                "rinse_detected": rinse,
                "summary_text": summary,
                "frame_count": self.frame_count,
                "pose_detection_count": self.pose_detection_count,
                "hands_detection_count": self.hands_detection_count,
                "brush_segments": self.accumulator.brush_segments,
                "facewash_segments": self.accumulator.facewash_segments,
                "rejected_brush_segments": self.accumulator.rejected_brush_segments,
                "rejected_facewash_segments": self.accumulator.rejected_facewash_segments,
            }

    def close(self):
        self.pose_detector.close()
        self.hands_detector.close()
