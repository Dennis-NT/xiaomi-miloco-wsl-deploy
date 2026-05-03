import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class RoiConfig:
    def __init__(self, config_dict: Optional[dict] = None):
        d = config_dict or {}
        self.enabled = d.get("enabled", False)
        # Normalized rectangle [x1, y1, x2, y2] in 0..1 range
        self.sink_area: Optional[Tuple[float, float, float, float]] = d.get("sink_area")
        self.mirror_area: Optional[Tuple[float, float, float, float]] = d.get("mirror_area")
        self.body_area: Optional[Tuple[float, float, float, float]] = d.get("body_area")

    def is_point_in_rect(self, x: float, y: float, rect: Optional[Tuple[float, float, float, float]]) -> bool:
        if rect is None:
            return True
        x1, y1, x2, y2 = rect
        return x1 <= x <= x2 and y1 <= y <= y2

    def is_in_roi(self, x: float, y: float) -> bool:
        if not self.enabled:
            return True
        # Consider in ROI if in any defined area
        areas = [self.sink_area, self.mirror_area, self.body_area]
        for area in areas:
            if area and self.is_point_in_rect(x, y, area):
                return True
        return False

    def filter_landmarks(self, landmarks: list) -> list:
        """Return only landmarks that fall inside ROI."""
        if not self.enabled:
            return landmarks
        return [lm for lm in landmarks if self.is_in_roi(lm.x, lm.y)]
