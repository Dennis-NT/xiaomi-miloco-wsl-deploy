import unittest

from analyzer.behavior_rules import BehaviorAccumulator


class BehaviorAccumulatorTests(unittest.TestCase):
    def test_single_false_positive_does_not_extend_to_window_end(self):
        acc = BehaviorAccumulator(break_seconds=2.0, min_segment_seconds=2.0)

        acc.update(
            1.0,
            mouth=(0.5, 0.5),
            face=(0.5, 0.45),
            left_wrist=None,
            right_wrist=None,
            finger_tips=[(0.51, 0.5)],
        )
        for t in (1.5, 2.0, 3.5, 4.0):
            acc.update(t, mouth=(0.5, 0.5), face=(0.5, 0.45), left_wrist=None, right_wrist=None)

        acc.finalize(60.0)

        self.assertEqual(acc.brush_segments, [])
        self.assertEqual(acc.total_brush_seconds(), 0)

    def test_facewash_suppresses_brushing_for_same_frame(self):
        acc = BehaviorAccumulator(break_seconds=2.0, min_segment_seconds=0.0)
        hand_tip_groups = [
            [(0.50, 0.45), (0.51, 0.46), (0.52, 0.47)],
            [(0.49, 0.45), (0.48, 0.46), (0.47, 0.47)],
        ]

        is_brushing, is_facewashing = acc.update(
            1.0,
            mouth=(0.5, 0.5),
            face=(0.5, 0.45),
            left_wrist=None,
            right_wrist=None,
            finger_tips=[tip for group in hand_tip_groups for tip in group],
            hand_tip_groups=hand_tip_groups,
        )
        acc.finalize(2.0)

        self.assertFalse(is_brushing)
        self.assertTrue(is_facewashing)
        self.assertEqual(acc.brush_segments, [])
        self.assertEqual(acc.facewash_segments, [(1.0, 1.0)])


if __name__ == "__main__":
    unittest.main()
