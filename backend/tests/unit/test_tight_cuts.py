import unittest

from src.tight_cuts import (
    KeepSpan,
    TightCutsConfig,
    compute_keep_spans,
    is_filler_word,
    output_duration_ms,
    remap_words_to_output,
    should_apply_tight_cuts,
)


def word(text: str, start: int, end: int) -> dict:
    return {"text": text, "start": start, "end": end}


class TightCutsTests(unittest.TestCase):
    def test_is_filler_word(self):
        self.assertTrue(is_filler_word("um"))
        self.assertTrue(is_filler_word("Uh,"))
        self.assertFalse(is_filler_word("punchline"))

    def test_filler_words_removed_from_spans(self):
        words = [
            word("um", 1000, 1200),
            word("hello", 1300, 1600),
            word("world", 1700, 2000),
        ]
        spans = compute_keep_spans(words, 1000, 2200)
        self.assertEqual(len(spans), 1)
        self.assertLess(spans[0].src_start_ms, 1300)

    def test_long_gap_splits_spans(self):
        words = [
            word("first", 1000, 1400),
            word("second", 2400, 2800),
        ]
        spans = compute_keep_spans(words, 1000, 3000, TightCutsConfig(max_silence_ms=350))
        self.assertGreaterEqual(len(spans), 2)

    def test_short_gap_merges_spans(self):
        words = [
            word("first", 1000, 1400),
            word("second", 1600, 1900),
        ]
        spans = compute_keep_spans(words, 1000, 2000, TightCutsConfig(max_silence_ms=350))
        self.assertEqual(len(spans), 1)

    def test_laughter_preserves_reaction_window(self):
        words = [word("funny", 1000, 1400)]
        utterances = [{"text": "haha that's great", "start": 1400, "end": 2200}]
        spans = compute_keep_spans(
            words,
            1000,
            2500,
            utterances=utterances,
        )
        self.assertEqual(len(spans), 1)
        self.assertGreaterEqual(spans[0].src_end_ms, 2000)

    def test_remap_words_to_output_is_monotonic(self):
        words = [
            word("hello", 1000, 1300),
            word("world", 2400, 2700),
        ]
        spans = [
            KeepSpan(980, 1350),
            KeepSpan(2380, 2750),
        ]
        remapped = remap_words_to_output(words, spans, 900)
        self.assertEqual(len(remapped), 2)
        self.assertEqual(remapped[0]["text"], "hello")
        self.assertLess(remapped[0]["end"], remapped[1]["start"])
        total_s = output_duration_ms(spans) / 1000.0
        self.assertLessEqual(remapped[-1]["end"], total_s + 0.05)

    def test_remap_words_uses_encoded_span_durations(self):
        words = [
            word("hello", 1000, 1300),
            word("world", 3000, 3300),
        ]
        spans = [
            KeepSpan(1000, 3000),
            KeepSpan(3000, 4500),
        ]
        remapped = remap_words_to_output(
            words,
            spans,
            1000,
            span_output_durations_ms=[2800, 1500],
        )
        self.assertAlmostEqual(remapped[0]["start"], 0.0, places=2)
        self.assertAlmostEqual(remapped[1]["start"], 2.8, places=2)

    def test_should_apply_false_when_negligible_cut(self):
        spans = [KeepSpan(1000, 5000)]
        self.assertFalse(should_apply_tight_cuts(spans, 1000, 5000))


if __name__ == "__main__":
    unittest.main()
