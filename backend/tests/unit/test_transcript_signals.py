import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ai import _parse_patch_analysis
from src.transcript_signals import (
    build_patch_for_anchor,
    build_signal_first_patches,
    compute_anchor_count,
    rank_transcript_utterances,
    score_utterance,
    select_anchor_moments,
)
from src.transcript_windows import TranscriptLine, parse_transcript_lines


def _build_sample_transcript(minutes: int = 15) -> str:
    lines = []
    for minute in range(minutes):
        start = f"{minute:02d}:00"
        end = f"{minute:02d}:25"
        if minute % 4 == 0:
            body = f"Speaker A: Why does this actually matter for creators in 2026?"
        elif minute % 4 == 1:
            body = f"Speaker B: Um, like, you know, it is kind of fine I guess."
        elif minute % 4 == 2:
            body = (
                f"Speaker A: The secret is 3 steps: record, rank, and ship clips fast."
            )
        else:
            body = f"Speaker B: That is the best framework we have tested so far."
        lines.append(f"[{start} - {end}] {body}")
    return "\n".join(lines)


class TranscriptSignalTests(unittest.TestCase):
    def test_question_scores_higher_than_filler(self):
        question = TranscriptLine(
            start_seconds=60,
            end_seconds=85,
            text="Why does this framework change everything for creators?",
            raw="[01:00 - 01:25] Speaker A: Why does this framework change everything for creators?",
        )
        filler = TranscriptLine(
            start_seconds=120,
            end_seconds=145,
            text="Um, like, you know, it is kind of fine I guess.",
            raw="[02:00 - 02:25] Speaker B: Um, like, you know, it is kind of fine I guess.",
        )
        self.assertGreater(score_utterance(question), score_utterance(filler))

    def test_ranking_prefers_hooks_over_filler(self):
        transcript = _build_sample_transcript(minutes=12)
        ranked = rank_transcript_utterances(transcript)
        self.assertGreaterEqual(len(ranked), 4)
        top_text = ranked[0].text.lower()
        self.assertTrue(
            "why" in top_text
            or "secret" in top_text
            or "best" in top_text
            or "3 steps" in top_text
        )

    def test_select_anchor_moments_applies_timeline_diversity(self):
        transcript = _build_sample_transcript(minutes=20)
        ranked = rank_transcript_utterances(transcript)
        anchors = select_anchor_moments(
            ranked,
            max_anchors=12,
            bucket_seconds=300,
            max_per_bucket=3,
        )
        buckets = [anchor.start_seconds // 300 for anchor in anchors]
        for bucket in set(buckets):
            self.assertLessEqual(buckets.count(bucket), 3)

    def test_compute_anchor_count_scales_with_duration(self):
        short = _build_sample_transcript(minutes=5)
        long = _build_sample_transcript(minutes=30)
        self.assertLess(compute_anchor_count(short), compute_anchor_count(long))
        self.assertGreaterEqual(compute_anchor_count(long), 12)

    def test_patch_size_stays_within_char_budget(self):
        transcript = _build_sample_transcript(minutes=15)
        anchors, patches = build_signal_first_patches(
            transcript,
            max_anchors=8,
            pad_seconds=45,
            max_chars=1500,
        )
        self.assertGreaterEqual(len(anchors), 4)
        self.assertEqual(len(anchors), len(patches))
        for patch in patches:
            self.assertGreater(len(patch), 0)
            self.assertLessEqual(len(patch), 1500)

    def test_build_patch_for_anchor_includes_anchor_context(self):
        transcript = _build_sample_transcript(minutes=8)
        lines = parse_transcript_lines(transcript)
        ranked = rank_transcript_utterances(transcript)
        anchor = ranked[0]
        patch = build_patch_for_anchor(
            anchor,
            lines,
            pad_seconds=45,
            max_chars=1500,
        )
        self.assertIn(anchor.raw, patch)

    def test_sentiment_cache_boosts_emotional_lines(self):
        transcript = "[01:00 - 01:20] Speaker A: This launch changed everything for us."
        cache = {
            "sentiment_analysis": [
                {
                    "text": "This launch changed everything for us.",
                    "start": 60000,
                    "end": 80000,
                    "sentiment": "POSITIVE",
                    "confidence": 0.9,
                }
            ]
        }
        with_boost = rank_transcript_utterances(transcript, cache=cache)
        without_boost = rank_transcript_utterances(transcript)
        self.assertGreater(with_boost[0].signal_score, without_boost[0].signal_score)

    def test_riverside_anchor_density_matches_reference_range(self):
        """~15-min sample should yield ~10-12 patches (Riverside-style pre-filter budget)."""
        transcript = _build_sample_transcript(minutes=15)
        anchor_count = compute_anchor_count(transcript)
        self.assertGreaterEqual(anchor_count, 10)
        self.assertLessEqual(anchor_count, 18)
        anchors, _ = build_signal_first_patches(transcript, max_anchors=anchor_count)
        self.assertGreaterEqual(len(anchors), 6)

    def test_parse_patch_analysis_accepts_optional_both_tiers(self):
        raw = {
            "micro_hook": {
                "start_time": "01:00",
                "end_time": "01:18",
                "text": "Why does this framework change everything?",
                "relevance_score": 0.9,
                "reasoning": "Strong curiosity hook",
                "virality": {
                    "hook_score": 22,
                    "engagement_score": 20,
                    "value_score": 18,
                    "shareability_score": 19,
                    "total_score": 79,
                    "hook_type": "question",
                    "virality_reasoning": "Opens with a question",
                },
            },
            "deep_context_clip": {
                "start_time": "01:00",
                "end_time": "01:55",
                "text": "Why does this framework change everything? Here is the full arc.",
                "relevance_score": 0.85,
                "reasoning": "Complete narrative",
                "virality": {
                    "hook_score": 18,
                    "engagement_score": 21,
                    "value_score": 22,
                    "shareability_score": 17,
                    "total_score": 78,
                    "hook_type": "story",
                    "virality_reasoning": "Setup and payoff",
                },
            },
        }
        micro, deep = _parse_patch_analysis(raw)
        self.assertIsNotNone(micro)
        self.assertIsNotNone(deep)
        self.assertEqual(micro.start_time, "01:00")
        self.assertEqual(deep.end_time, "01:55")


if __name__ == "__main__":
    unittest.main()
