import logging
import math
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)


def distance(p1: Optional[Tuple[float, float]], p2: Optional[Tuple[float, float]]) -> float:
    if p1 is None or p2 is None:
        return float("inf")
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def min_distance(points: List[Tuple[float, float]], target: Optional[Tuple[float, float]]) -> float:
    if not points or target is None:
        return float("inf")
    return min(distance(p, target) for p in points)


def count_nearby(points: List[Tuple[float, float]], target: Optional[Tuple[float, float]], threshold: float) -> int:
    if not points or target is None:
        return 0
    return sum(1 for p in points if distance(p, target) < threshold)


def count_nearby_by_group(
    point_groups: List[List[Tuple[float, float]]],
    target: Optional[Tuple[float, float]],
    threshold: float,
) -> List[int]:
    if not point_groups or target is None:
        return []
    return [count_nearby(points, target, threshold) for points in point_groups]


def point_range(points: List[Tuple[float, float]]) -> float:
    if len(points) < 2:
        return 0.0
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return max(max(xs) - min(xs), max(ys) - min(ys))


def path_length(points: List[Tuple[float, float]]) -> float:
    if len(points) < 2:
        return 0.0
    return sum(distance(a, b) for a, b in zip(points, points[1:]))


class BehaviorState:
    IDLE = "idle"
    BRUSHING = "brushing"
    FACEWASHING = "facewashing"


class BehaviorAccumulator:
    """
    Accumulates behavior evidence over time from per-frame detections.
    Uses finger tips (from Hands model) for primary detection, with wrist fallback.
    """
    def __init__(
        self,
        brush_finger_threshold: float = 0.10,
        brush_wrist_threshold: float = 0.15,
        face_finger_threshold: float = 0.12,
        face_wrist_threshold: float = 0.18,
        min_fingers_for_facewash: int = 4,
        break_seconds: float = 2.0,
        min_segment_seconds: float = 2.0,
        min_segment_hits: int = 6,
        brush_min_motion: float = 0.020,
        facewash_min_motion: float = 0.025,
    ):
        # Distance thresholds in normalized coordinates (0..1)
        self.brush_finger_threshold = brush_finger_threshold
        self.brush_wrist_threshold = brush_wrist_threshold
        self.face_finger_threshold = face_finger_threshold
        self.face_wrist_threshold = face_wrist_threshold
        self.min_fingers_for_facewash = min_fingers_for_facewash
        self.break_seconds = break_seconds
        self.min_segment_seconds = min_segment_seconds
        self.min_segment_hits = min_segment_hits
        self.brush_min_motion = brush_min_motion
        self.facewash_min_motion = facewash_min_motion

        self.state = BehaviorState.IDLE
        self.state_start_time: float = 0.0

        self.brush_segments: list[Tuple[float, float]] = []  # list of (start, end)
        self.facewash_segments: list[Tuple[float, float]] = []
        self.rejected_brush_segments: list[Tuple[float, float, str]] = []
        self.rejected_facewash_segments: list[Tuple[float, float, str]] = []

        self.current_brush_start: Optional[float] = None
        self.current_facewash_start: Optional[float] = None
        self.last_brush_seen: Optional[float] = None
        self.last_facewash_seen: Optional[float] = None
        self.current_brush_samples: list[Tuple[float, Tuple[float, float]]] = []
        self.current_facewash_samples: list[Tuple[float, Tuple[float, float]]] = []

    def update(
        self,
        relative_time: float,
        mouth: Optional[Tuple[float, float]],
        face: Optional[Tuple[float, float]],
        left_wrist: Optional[Tuple[float, float]],
        right_wrist: Optional[Tuple[float, float]],
        finger_tips: Optional[List[Tuple[float, float]]] = None,
        hand_tip_groups: Optional[List[List[Tuple[float, float]]]] = None,
    ) -> tuple[bool, bool]:
        """
        relative_time: seconds since window start.
        finger_tips: list of (x, y) for all detected finger tips.
        """
        finger_tips = finger_tips or []
        hand_tip_groups = hand_tip_groups or []

        # Determine instantaneous actions
        is_facewashing = self._detect_facewashing(face, left_wrist, right_wrist, finger_tips, hand_tip_groups)
        # Washing the face also puts fingers near the mouth, so give it priority.
        is_brushing = False if is_facewashing else self._detect_brushing(mouth, left_wrist, right_wrist, finger_tips)

        brush_point = self._brush_motion_point(mouth, left_wrist, right_wrist, finger_tips) if is_brushing else None
        facewash_point = self._facewash_motion_point(face, left_wrist, right_wrist, finger_tips) if is_facewashing else None

        self._update_state(relative_time, is_brushing, is_facewashing, brush_point, facewash_point)
        return is_brushing, is_facewashing

    def _detect_brushing(
        self,
        mouth: Optional[Tuple[float, float]],
        left_wrist: Optional[Tuple[float, float]],
        right_wrist: Optional[Tuple[float, float]],
        finger_tips: List[Tuple[float, float]],
    ) -> bool:
        if mouth is None:
            return False

        # Primary: finger tips near mouth (more precise)
        if finger_tips:
            d_tip = min_distance(finger_tips, mouth)
            if d_tip < self.brush_finger_threshold:
                return True
            return False

        # Fallback when hands are not detected: wrists near mouth.
        d_left = distance(left_wrist, mouth)
        d_right = distance(right_wrist, mouth)
        if d_left < self.brush_wrist_threshold or d_right < self.brush_wrist_threshold:
            return True

        return False

    def _detect_facewashing(
        self,
        face: Optional[Tuple[float, float]],
        left_wrist: Optional[Tuple[float, float]],
        right_wrist: Optional[Tuple[float, float]],
        finger_tips: List[Tuple[float, float]],
        hand_tip_groups: List[List[Tuple[float, float]]],
    ) -> bool:
        if face is None:
            return False

        # Primary: both hands near face. This avoids treating one hand near
        # the mouth (brushing, drinking, touching the face) as face washing.
        if hand_tip_groups:
            nearby_by_hand = count_nearby_by_group(hand_tip_groups, face, self.face_finger_threshold)
            active_hands = sum(1 for count in nearby_by_hand if count >= 2)
            if active_hands >= 2:
                return True

        # Fallback when only flattened tips are available.
        if finger_tips:
            nearby_count = count_nearby(finger_tips, face, self.face_finger_threshold)
            if nearby_count >= max(self.min_fingers_for_facewash + 2, 6):
                return True

        # Last fallback: both wrists near face. A single wrist is too noisy.
        d_left = distance(left_wrist, face)
        d_right = distance(right_wrist, face)
        if d_left < self.face_wrist_threshold and d_right < self.face_wrist_threshold:
            return True

        return False

    def _brush_motion_point(
        self,
        mouth: Optional[Tuple[float, float]],
        left_wrist: Optional[Tuple[float, float]],
        right_wrist: Optional[Tuple[float, float]],
        finger_tips: List[Tuple[float, float]],
    ) -> Optional[Tuple[float, float]]:
        if finger_tips and mouth is not None:
            return min(finger_tips, key=lambda p: distance(p, mouth))
        wrist_points = [p for p in (left_wrist, right_wrist) if p is not None]
        if wrist_points and mouth is not None:
            return min(wrist_points, key=lambda p: distance(p, mouth))
        return None

    def _facewash_motion_point(
        self,
        face: Optional[Tuple[float, float]],
        left_wrist: Optional[Tuple[float, float]],
        right_wrist: Optional[Tuple[float, float]],
        finger_tips: List[Tuple[float, float]],
    ) -> Optional[Tuple[float, float]]:
        if finger_tips and face is not None:
            near = [p for p in finger_tips if distance(p, face) < self.face_finger_threshold]
            points = near or finger_tips
            return (
                sum(p[0] for p in points) / len(points),
                sum(p[1] for p in points) / len(points),
            )
        wrist_points = [p for p in (left_wrist, right_wrist) if p is not None]
        if wrist_points:
            return (
                sum(p[0] for p in wrist_points) / len(wrist_points),
                sum(p[1] for p in wrist_points) / len(wrist_points),
            )
        return None

    def _update_state(
        self,
        t: float,
        is_brushing: bool,
        is_facewashing: bool,
        brush_point: Optional[Tuple[float, float]],
        facewash_point: Optional[Tuple[float, float]],
    ):
        if is_brushing:
            if self.current_brush_start is None:
                self.current_brush_start = t
                self.current_brush_samples = []
            self.last_brush_seen = t
            if brush_point is not None:
                self.current_brush_samples.append((t, brush_point))
        else:
            self._close_if_stale(
                t,
                "brush",
                self.current_brush_start,
                self.last_brush_seen,
                self.brush_segments,
                self.current_brush_samples,
            )

        if is_facewashing:
            if self.current_facewash_start is None:
                self.current_facewash_start = t
                self.current_facewash_samples = []
            self.last_facewash_seen = t
            if facewash_point is not None:
                self.current_facewash_samples.append((t, facewash_point))
        else:
            self._close_if_stale(
                t,
                "facewash",
                self.current_facewash_start,
                self.last_facewash_seen,
                self.facewash_segments,
                self.current_facewash_samples,
            )

    def _close_if_stale(
        self,
        t: float,
        behavior: str,
        start: Optional[float],
        last_seen: Optional[float],
        segments: list[Tuple[float, float]],
        samples: list[Tuple[float, Tuple[float, float]]],
    ):
        if start is None or last_seen is None or t - last_seen <= self.break_seconds:
            return
        self._append_segment(behavior, segments, start, last_seen, samples)
        if behavior == "brush":
            self.current_brush_start = None
            self.last_brush_seen = None
            self.current_brush_samples = []
        else:
            self.current_facewash_start = None
            self.last_facewash_seen = None
            self.current_facewash_samples = []

    def _append_segment(
        self,
        behavior: str,
        segments: list[Tuple[float, float]],
        start: float,
        end: float,
        samples: list[Tuple[float, Tuple[float, float]]],
    ):
        ok, reason = self._validate_segment(behavior, start, end, samples)
        if ok:
            segments.append((start, end))
            return
        if behavior == "brush":
            self.rejected_brush_segments.append((start, end, reason))
        else:
            self.rejected_facewash_segments.append((start, end, reason))

    def _validate_segment(
        self,
        behavior: str,
        start: float,
        end: float,
        samples: list[Tuple[float, Tuple[float, float]]],
    ) -> tuple[bool, str]:
        duration = end - start
        if duration < self.min_segment_seconds:
            return False, "too_short"
        if len(samples) < self.min_segment_hits:
            return False, "too_few_hits"

        points = [p for _, p in samples]
        motion_range = point_range(points)
        motion_path = path_length(points)
        min_motion = self.brush_min_motion if behavior == "brush" else self.facewash_min_motion
        if motion_range < min_motion and motion_path < min_motion * 2.0:
            return False, "too_static"

        return True, "accepted"

    def finalize(self, end_time: float):
        """Call at window end to close any open segments."""
        if self.current_brush_start is not None and self.last_brush_seen is not None:
            self._append_segment(
                "brush",
                self.brush_segments,
                self.current_brush_start,
                min(self.last_brush_seen, end_time),
                self.current_brush_samples,
            )
            self.current_brush_start = None
            self.last_brush_seen = None
            self.current_brush_samples = []
        if self.current_facewash_start is not None and self.last_facewash_seen is not None:
            self._append_segment(
                "facewash",
                self.facewash_segments,
                self.current_facewash_start,
                min(self.last_facewash_seen, end_time),
                self.current_facewash_samples,
            )
            self.current_facewash_start = None
            self.last_facewash_seen = None
            self.current_facewash_samples = []

    def total_brush_seconds(self) -> float:
        return sum(end - start for start, end in self.brush_segments)

    def total_facewash_seconds(self) -> float:
        return sum(end - start for start, end in self.facewash_segments)

    def longest_brush_segment(self) -> float:
        if not self.brush_segments:
            return 0.0
        return max(end - start for start, end in self.brush_segments)

    def longest_facewash_segment(self) -> float:
        if not self.facewash_segments:
            return 0.0
        return max(end - start for start, end in self.facewash_segments)

    def brush_continuity_ratio(self) -> float:
        """Ratio of longest continuous segment to total time."""
        total = self.total_brush_seconds()
        if total <= 0:
            return 0.0
        return self.longest_brush_segment() / total

    def facewash_continuity_ratio(self) -> float:
        total = self.total_facewash_seconds()
        if total <= 0:
            return 0.0
        return self.longest_facewash_segment() / total
