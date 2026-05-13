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
        acc = BehaviorAccumulator(break_seconds=2.0, min_segment_seconds=0.0, min_segment_hits=1)
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

    def test_static_hand_near_mouth_is_rejected(self):
        acc = BehaviorAccumulator(
            break_seconds=2.0,
            min_segment_seconds=5.0,
            min_segment_hits=8,
            brush_min_motion=0.020,
        )

        for i in range(12):
            t = i * 0.5
            acc.update(
                t,
                mouth=(0.5, 0.5),
                face=(0.5, 0.45),
                left_wrist=None,
                right_wrist=None,
                finger_tips=[(0.505, 0.502)],
            )
        acc.finalize(6.0)

        self.assertEqual(acc.brush_segments, [])
        self.assertEqual(acc.rejected_brush_segments[0][2], "too_static")

    def test_moving_hand_near_mouth_is_accepted_as_brushing(self):
        acc = BehaviorAccumulator(
            break_seconds=2.0,
            min_segment_seconds=5.0,
            min_segment_hits=8,
            brush_min_motion=0.020,
        )

        for i in range(12):
            t = i * 0.5
            offset = 0.025 if i % 2 else -0.005
            acc.update(
                t,
                mouth=(0.5, 0.5),
                face=(0.5, 0.45),
                left_wrist=None,
                right_wrist=None,
                finger_tips=[(0.5 + offset, 0.5)],
            )
        acc.finalize(6.0)

        self.assertEqual(acc.brush_segments, [(0.0, 5.5)])


if __name__ == "__main__":
    unittest.main()
