import logging
from typing import Tuple

logger = logging.getLogger(__name__)

GRADE_UNDONE = "未完成"
GRADE_POOR = "差"
GRADE_MEDIUM = "中"
GRADE_GOOD = "好"


class ScoringEngine:
    def __init__(
        self,
        toothbrush_min_done: int = 20,
        toothbrush_min_medium: int = 45,
        toothbrush_min_good: int = 90,
        facewash_min_done: int = 8,
        facewash_min_medium: int = 15,
        facewash_min_good: int = 30,
    ):
        self.toothbrush_min_done = toothbrush_min_done
        self.toothbrush_min_medium = toothbrush_min_medium
        self.toothbrush_min_good = toothbrush_min_good
        self.facewash_min_done = facewash_min_done
        self.facewash_min_medium = facewash_min_medium
        self.facewash_min_good = facewash_min_good

    def score_toothbrush(self, seconds: float, continuity_ratio: float, rinse_detected: bool = False) -> str:
        if seconds < self.toothbrush_min_done:
            return GRADE_UNDONE
        if seconds < self.toothbrush_min_medium:
            return GRADE_POOR
        if seconds < self.toothbrush_min_good:
            return GRADE_MEDIUM
        # Good: >= 90s, continuous, with rinse or area switching (simplified)
        if continuity_ratio >= 0.6 or rinse_detected:
            return GRADE_GOOD
        return GRADE_MEDIUM

    def score_facewash(self, seconds: float, continuity_ratio: float) -> str:
        if seconds < self.facewash_min_done:
            return GRADE_UNDONE
        if seconds < self.facewash_min_medium:
            return GRADE_POOR
        if seconds < self.facewash_min_good:
            return GRADE_MEDIUM
        if continuity_ratio >= 0.5:
            return GRADE_GOOD
        return GRADE_MEDIUM

    def generate_summary(
        self,
        toothbrush_grade: str,
        facewash_grade: str,
        toothbrush_seconds: float,
        facewash_seconds: float,
        rinse_detected: bool,
    ) -> str:
        parts = []
        if toothbrush_grade == GRADE_GOOD:
            parts.append(f"检测到约 {toothbrush_seconds:.0f} 秒连续刷牙动作")
            if rinse_detected:
                parts.append("并有漱口")
        elif toothbrush_grade == GRADE_MEDIUM:
            parts.append(f"检测到约 {toothbrush_seconds:.0f} 秒刷牙动作")
        elif toothbrush_grade == GRADE_POOR:
            parts.append("检测到短时刷牙动作，持续偏短")
        else:
            parts.append("未检测到明确刷牙行为")

        if facewash_grade == GRADE_GOOD:
            parts.append(f"检测到约 {facewash_seconds:.0f} 秒洗脸动作")
        elif facewash_grade == GRADE_MEDIUM:
            parts.append(f"检测到洗脸动作，持续约 {facewash_seconds:.0f} 秒")
        elif facewash_grade == GRADE_POOR:
            parts.append("检测到短时湿脸或擦拭动作")
        else:
            parts.append("未检测到明确洗脸行为")

        summary = "；".join(parts)
        if len(summary) > 60:
            summary = summary[:57] + "..."
        return summary
