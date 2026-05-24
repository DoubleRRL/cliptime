import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ai import TranscriptSegment, ViralityAnalysis
from src.transcript_windows import (
    deduplicate_segments,
    select_final_segments,
    split_transcript_into_windows,
)


def _segment(start: str, end: str, score: int) -> TranscriptSegment:
    return TranscriptSegment(
        start_time=start,
        end_time=end,
        text="This is a sample transcript segment with enough words.",
        relevance_score=score / 100,
        reasoning="test",
        virality=ViralityAnalysis(
            hook_score=score // 4,
            engagement_score=score // 4,
            value_score=score // 4,
            shareability_score=score // 4,
            total_score=score,
            hook_type="statement",
            virality_reasoning="test",
        ),
    )


class TranscriptWindowTests(unittest.TestCase):
    def test_split_transcript_into_windows_respects_overlap(self):
        lines = []
        for minute in range(6):
            start = f"{minute:02d}:00"
            end = f"{minute:02d}:30"
            lines.append(f"[{start} - {end}] Speaker A: Segment {minute}.")

        transcript = "\n".join(lines)
        windows = split_transcript_into_windows(
            transcript, window_seconds=300, overlap_seconds=30, max_windows=3
        )

        self.assertGreaterEqual(len(windows), 2)
        self.assertIn("Segment 0.", windows[0].text)

    def test_deduplicate_segments_keeps_higher_score_on_overlap(self):
        low = _segment("01:00", "01:20", 40)
        high = _segment("01:05", "01:25", 90)
        result = deduplicate_segments([low, high])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].start_time, "01:05")

    def test_select_final_segments_caps_each_tier(self):
        micro = [_segment(f"{i * 6:02d}:00", f"{i * 6:02d}:20", 80 + i) for i in range(5)]
        deep = [_segment(f"{5 + i:02d}:00", f"{6 + i:02d}:00", 70 + i) for i in range(4)]
        final_micro, final_deep = select_final_segments(
            micro, deep, max_micro=2, max_deep=2
        )
        self.assertEqual(len(final_micro), 2)
        self.assertEqual(len(final_deep), 2)


if __name__ == "__main__":
    unittest.main()
