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
    ):
        # Distance thresholds in normalized coordinates (0..1)
        self.brush_finger_threshold = brush_finger_threshold
        self.brush_wrist_threshold = brush_wrist_threshold
        self.face_finger_threshold = face_finger_threshold
        self.face_wrist_threshold = face_wrist_threshold
        self.min_fingers_for_facewash = min_fingers_for_facewash
        self.break_seconds = break_seconds

        self.state = BehaviorState.IDLE
        self.state_start_time: float = 0.0
        self.last_detection_time: float = 0.0

        self.brush_segments: list[Tuple[float, float]] = []  # list of (start, end)
        self.facewash_segments: list[Tuple[float, float]] = []

        self.current_brush_start: Optional[float] = None
        self.current_facewash_start: Optional[float] = None

    def update(
        self,
        relative_time: float,
        mouth: Optional[Tuple[float, float]],
        face: Optional[Tuple[float, float]],
        left_wrist: Optional[Tuple[float, float]],
        right_wrist: Optional[Tuple[float, float]],
        finger_tips: Optional[List[Tuple[float, float]]] = None,
    ):
        """
        relative_time: seconds since window start.
        finger_tips: list of (x, y) for all detected finger tips.
        """
        finger_tips = finger_tips or []

        # Determine instantaneous actions
        is_brushing = self._detect_brushing(mouth, left_wrist, right_wrist, finger_tips)
        is_facewashing = self._detect_facewashing(face, left_wrist, right_wrist, finger_tips)

        self._update_state(relative_time, is_brushing, is_facewashing)

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

        # Fallback: wrists near mouth
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
    ) -> bool:
        if face is None:
            return False

        # Primary: multiple finger tips near face (both hands scrubbing)
        if finger_tips:
            nearby_count = count_nearby(finger_tips, face, self.face_finger_threshold)
            if nearby_count >= self.min_fingers_for_facewash:
                return True
            # Also accept if at least 2 tips are very close (one hand actively washing)
            very_close = count_nearby(finger_tips, face, self.face_finger_threshold * 0.7)
            if very_close >= 2:
                return True

        # Fallback: both wrists near face
        d_left = distance(left_wrist, face)
        d_right = distance(right_wrist, face)
        if d_left < self.face_wrist_threshold and d_right < self.face_wrist_threshold:
            return True
        elif d_left < self.face_wrist_threshold * 0.6 or d_right < self.face_wrist_threshold * 0.6:
            return True

        return False

    def _update_state(self, t: float, is_brushing: bool, is_facewashing: bool):
        # Hysteresis: require break_seconds of absence to end a segment
        gap = t - self.last_detection_time
        self.last_detection_time = t

        if gap > self.break_seconds:
            # Force end any ongoing segment due to long gap
            if self.current_brush_start is not None:
                self.brush_segments.append((self.current_brush_start, self.last_detection_time - gap))
                self.current_brush_start = None
            if self.current_facewash_start is not None:
                self.facewash_segments.append((self.current_facewash_start, self.last_detection_time - gap))
                self.current_facewash_start = None

        # Update brushing
        if is_brushing:
            if self.current_brush_start is None:
                self.current_brush_start = t
        else:
            if self.current_brush_start is not None and gap > self.break_seconds:
                self.brush_segments.append((self.current_brush_start, self.last_detection_time - gap))
                self.current_brush_start = None

        # Update face washing
        if is_facewashing:
            if self.current_facewash_start is None:
                self.current_facewash_start = t
        else:
            if self.current_facewash_start is not None and gap > self.break_seconds:
                self.facewash_segments.append((self.current_facewash_start, self.last_detection_time - gap))
                self.current_facewash_start = None

    def finalize(self, end_time: float):
        """Call at window end to close any open segments."""
        if self.current_brush_start is not None:
            self.brush_segments.append((self.current_brush_start, end_time))
            self.current_brush_start = None
        if self.current_facewash_start is not None:
            self.facewash_segments.append((self.current_facewash_start, end_time))
            self.current_facewash_start = None

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
