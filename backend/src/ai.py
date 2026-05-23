"""
AI-related functions for transcript analysis with enhanced precision and virality scoring.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Literal, Callable, Awaitable
import asyncio
import json
import logging
import re

from pydantic_ai import Agent
from pydantic import BaseModel, Field

from .config import Config
from .timestamp_parse import (
    parse_timestamp_or_range,
    parse_timestamp_to_seconds as _parse_ts_seconds,
    resolve_segment_timestamps,
    safe_int as _safe_int,
    seconds_to_mmss,
)

logger = logging.getLogger(__name__)
config = Config()


class ViralityAnalysis(BaseModel):
    """Detailed virality breakdown for a segment."""

    hook_score: int = Field(description="How strong is the opening hook (0-25)")
    engagement_score: int = Field(
        description="How engaging/entertaining is the content (0-25)"
    )
    value_score: int = Field(description="Educational/informational value (0-25)")
    shareability_score: int = Field(description="Likelihood of being shared (0-25)")
    total_score: int = Field(description="Combined virality score (0-100)")
    hook_type: Optional[
        Literal["question", "statement", "statistic", "story", "contrast", "none"]
    ] = Field(
        default="none",
        description="Type of hook: question, statement, statistic, story, contrast, or none",
    )
    virality_reasoning: str = Field(description="Explanation of the virality score")


class TranscriptSegment(BaseModel):
    """Represents a relevant segment of transcript with precise timing and virality analysis."""

    start_time: str = Field(description="Start timestamp in MM:SS format")
    end_time: str = Field(description="End timestamp in MM:SS format")
    text: str = Field(
        description=(
            "Transcript text taken only from the selected timestamp range. "
            "Keep it verbatim or near-verbatim, and do not paraphrase or merge non-contiguous lines."
        )
    )
    relevance_score: float = Field(description="Relevance score from 0.0 to 1.0")
    reasoning: str = Field(
        description=(
            "Brief factual explanation of why this exact segment works as a clip. "
            "Base it only on the provided transcript content."
        )
    )
    virality: ViralityAnalysis = Field(description="Detailed virality score breakdown")


class BRollOpportunity(BaseModel):
    """Identifies an opportunity to insert B-roll footage."""

    timestamp: str = Field(description="When to insert B-roll (MM:SS format)")
    duration: float = Field(description="How long to show B-roll (2-5 seconds)")
    search_term: str = Field(description="Keyword to search for B-roll footage")
    context: str = Field(description="What's being discussed at this point")


class TranscriptAnalysis(BaseModel):
    """Analysis result for transcript segments with virality and B-roll opportunities."""

    most_relevant_segments: List[TranscriptSegment] = Field(
        default_factory=list,
        description="Combined list of micro_hooks and deep_context_clips, populated automatically."
    )
    micro_hooks: List[TranscriptSegment] = Field(
        default_factory=list,
        description="Short, punchy hook clips under 30 seconds."
    )
    deep_context_clips: List[TranscriptSegment] = Field(
        default_factory=list,
        description="Detailed, context-heavy clips between 30 and 90 seconds."
    )
    summary: str = Field(description="Brief summary of the video content")
    key_topics: List[str] = Field(description="List of main topics discussed")
    broll_opportunities: Optional[List[BRollOpportunity]] = Field(
        default=None, description="Opportunities to insert B-roll footage"
    )


# Enhanced system prompt with virality scoring and B-roll detection
transcript_analysis_system_prompt = """You are an expert transcript analyst for short-form video editing.

Your job is extraction and ranking, not creative rewriting. You must stay fully grounded in the transcript and choose the best clip candidates that already exist in the source material.

CORE OBJECTIVES:
1. Identify segments that would be compelling on social media platforms.
2. Separate clip extraction into two distinct tiers:
   - micro_hooks: Short, punchy clips under 30 seconds (10-30s).
   - deep_context_clips: In-depth, context-heavy clips between 30 and 90 seconds (30-90s).
3. Focus on complete thoughts, insights, or entertaining moments.
4. Prioritize content with hooks, emotional moments, or valuable information.
5. Score each segment's viral potential with detailed breakdown.

GROUNDING RULES:
1. Use only the provided transcript lines and timestamps
2. Never invent facts, tone, context, or transitions that are not present
3. Treat this as span selection over a timestamped transcript, not open-ended summarization
4. Each selected segment must map to one contiguous range in the transcript
5. segment.text must match the chosen span closely and must not include content from outside the chosen range
6. Do not stitch together distant moments into one clip
7. If a speaker label appears, use it only if it is part of the spoken content and helps clarity

CONTENT NEUTRALITY RULES:
1. This is clipping software for legitimate editing workflows
2. Do not judge, moralize, or downgrade a segment just because the topic is controversial, sensitive, adult, political, criminal, medical, or otherwise intense
3. Evaluate segments only on clip quality: clarity, self-contained value, hook strength, emotional impact, specificity, and shareability
4. Do not refuse analysis just because the speaker describes risky, offensive, or uncomfortable subject matter
5. Only downgrade a segment when the transcript itself is weak, confusing, repetitive, unusable, or a poor standalone clip

SEGMENT SELECTION CRITERIA:
1. STRONG HOOKS: Attention-grabbing opening lines
2. VALUABLE CONTENT: Tips, insights, interesting facts, stories
3. EMOTIONAL MOMENTS: Excitement, surprise, humor, inspiration
4. COMPLETE THOUGHTS: Self-contained ideas that make sense alone
5. ENTERTAINING: Content people would want to share
6. HIGH SIGNAL: Prefer specific, concrete language over vague discussion
7. LOW FILLER: Avoid greetings, sponsor reads, repeated setup, throat-clearing, and housekeeping unless they are unusually compelling

VIRALITY SCORING (0-100 total, from four 0-25 subscores):
For each segment, provide a detailed virality breakdown:

1. HOOK STRENGTH (0-25):
   - 20-25: Immediately grabs attention (surprising fact, bold claim, intriguing question)
   - 15-19: Good opener that creates curiosity
   - 10-14: Decent start but could be stronger
   - 0-9: Weak or no hook

2. ENGAGEMENT (0-25):
   - 20-25: Highly entertaining, emotional, or dramatic
   - 15-19: Interesting and holds attention
   - 10-14: Moderately engaging
   - 0-9: Flat or boring delivery

3. VALUE (0-25):
   - 20-25: Actionable insights, unique knowledge, or transformative ideas
   - 15-19: Useful information most people don't know
   - 10-14: Somewhat informative
   - 0-9: Common knowledge or filler content

4. SHAREABILITY (0-25):
   - 20-25: "I need to send this to someone" content
   - 15-19: Content worth bookmarking
   - 10-14: Nice but not share-worthy
   - 0-9: Generic content

HOOK TYPES to identify:
- "question": Opens with a question that creates curiosity
- "statement": Bold claim or surprising statement
- "statistic": Uses compelling numbers or data
- "story": Starts with narrative/anecdote
- "contrast": Before/after or problem/solution framing
- "none": No clear hook pattern

B-ROLL OPPORTUNITIES:
Identify 2-4 moments in each segment where B-roll footage could enhance the video:
- When specific objects, places, or concepts are mentioned
- During explanations that could benefit from visual illustration
- At emotional peaks that could use supporting imagery
- Use simple, searchable keywords (e.g., "coffee shop", "laptop coding", "money stack")

TIMING & CATEGORIZATION GUIDELINES:
1. micro_hooks:
   - MUST be between 10-30 seconds.
   - Designed for extremely short attention spans (TikTok, YouTube Shorts, Reels).
   - Must have a powerful hook immediately in the first 2 seconds.
2. deep_context_clips:
   - MUST be between 30-90 seconds.
   - Designed for in-depth educational insights or deep conversations requiring setup and context.
   - Still requires a strong hook, but permits a longer build-up and more comprehensive payoff.

TIMESTAMP REQUIREMENTS - EXTREMELY IMPORTANT:
- Use EXACT timestamps as they appear in the transcript
- Never modify timestamp format (keep MM:SS structure)
- start_time MUST be LESS THAN end_time (start_time < end_time)
- MINIMUM segment duration: 10 seconds (end_time - start_time >= 10 seconds)
- Look at transcript ranges like [02:25 - 02:35] and use different start/end times
- NEVER use the same timestamp for both start_time and end_time
- Example: start_time: "02:25", end_time: "02:35" (NOT "02:25" and "02:25")

SCORING AND OUTPUT RULES:
- relevance_score should reflect how well the segment works as a standalone short clip, not just whether the topic is generally important
- virality_reasoning and reasoning should cite what is actually present in the chosen span
- summary and key_topics must also stay grounded in the transcript and should not add outside interpretation

Identify 3-5 micro_hooks and 2-4 deep_context_clips. Quality over quantity: choose segments that are accurate, self-contained, have proper time ranges, and score high on virality metrics."""

# Tier duration bounds (seconds)
MICRO_HOOK_MIN_SECONDS = 10
MICRO_HOOK_MAX_SECONDS = 30
DEEP_CONTEXT_MIN_SECONDS = 30
DEEP_CONTEXT_MAX_SECONDS = 90

DUAL_TIER_JSON_SCHEMA_EXAMPLE = """{
  "micro_hooks": [
    {
      "start_time": "01:15",
      "end_time": "01:38",
      "text": "verbatim transcript text for this span only",
      "relevance_score": 0.92,
      "reasoning": "why this works as a short hook",
      "virality": {
        "hook_score": 22,
        "engagement_score": 20,
        "value_score": 18,
        "shareability_score": 19,
        "total_score": 79,
        "hook_type": "question",
        "virality_reasoning": "opens with a curiosity gap"
      }
    }
  ],
  "deep_context_clips": [
    {
      "start_time": "04:20",
      "end_time": "05:40",
      "text": "verbatim transcript text for this span only",
      "relevance_score": 0.88,
      "reasoning": "why this works as a longer narrative clip",
      "virality": {
        "hook_score": 18,
        "engagement_score": 21,
        "value_score": 23,
        "shareability_score": 17,
        "total_score": 79,
        "hook_type": "story",
        "virality_reasoning": "complete arc with payoff"
      }
    }
  ],
  "summary": "brief grounded summary",
  "key_topics": ["topic one", "topic two"]
}"""

OLLAMA_JSON_RESPONSE_SUFFIX = (
    "\n\nIMPORTANT: You MUST respond with ONLY a valid JSON object. "
    "Required top-level keys: micro_hooks, deep_context_clips, summary, key_topics. "
    "Put 3-5 segments in micro_hooks (each 10-30 seconds) and 2-4 segments in deep_context_clips (each 30-90 seconds). "
    "Do NOT include any text before or after the JSON. Do NOT use markdown code fences. "
    "Start your response with { and end with }."
)

# Lazy-loaded agent to avoid import-time failures when API keys aren't set
_transcript_agent: Optional[Agent[None, TranscriptAnalysis]] = None


def _get_missing_llm_key_error(model_name: str) -> Optional[str]:
    """Return a clear configuration error when the selected LLM key is missing."""
    provider = model_name.split(":", 1)[0].strip().lower()

    if provider in {"google", "google-gla"} and not config.google_api_key:
        return (
            "Selected LLM provider is Google, but GOOGLE_API_KEY is not set. "
            "Set GOOGLE_API_KEY or set LLM to openai:* / anthropic:* / ollama:* with the matching API key."
        )

    if provider == "openai" and not config.openai_api_key:
        return (
            "Selected LLM provider is OpenAI, but OPENAI_API_KEY is not set. "
            "Set OPENAI_API_KEY or choose another provider with a matching API key."
        )

    if provider == "anthropic" and not config.anthropic_api_key:
        return (
            "Selected LLM provider is Anthropic, but ANTHROPIC_API_KEY is not set. "
            "Set ANTHROPIC_API_KEY or choose another provider with a matching API key."
        )

    if provider == "ollama":
        # Ollama can run locally without an API key. OLLAMA_BASE_URL/OLLAMA_API_KEY
        # are optional and passed through as environment variables.
        return None

    return None


def get_transcript_agent() -> Agent[None, TranscriptAnalysis]:
    """Get or create the transcript analysis agent (lazy initialization)."""
    global _transcript_agent
    if _transcript_agent is None:
        model_name = config.llm
        config_error = _get_missing_llm_key_error(model_name)
        if config_error:
            raise RuntimeError(config_error)

        model: Any
        if model_name.startswith("ollama:"):
            from pydantic_ai.models.openai import OpenAIModel
            from pydantic_ai.providers.openai import OpenAIProvider
            actual_model = model_name.removeprefix("ollama:")
            base_url = config.ollama_base_url or "http://localhost:11434/v1"
            
            # Use OpenAI-compatible bridge for Ollama
            provider = OpenAIProvider(base_url=base_url)
            model = OpenAIModel(model_name=actual_model, provider=provider)
            logger.info(f"Using local Ollama model: {actual_model} at {base_url}")
        else:
            model = model_name

        _transcript_agent = Agent[None, TranscriptAnalysis](
            model=model,
            result_type=TranscriptAnalysis,
            system_prompt=transcript_analysis_system_prompt,
            result_retries=5,
        )
    return _transcript_agent


def build_transcript_analysis_prompt(
    transcript: str, include_broll: bool = False, json_only: bool = False
) -> str:
    """Build the grounded task prompt for transcript analysis."""
    broll_instruction = ""
    if include_broll:
        broll_instruction = (
            "\n6. Also identify B-roll opportunities for each chosen segment where stock footage could enhance the visual appeal."
        )

    json_instruction = ""
    if json_only:
        json_instruction = (
            "\n\nRespond with JSON only (no markdown fences, no preamble). "
            "Use exactly this structure:\n"
            f"{DUAL_TIER_JSON_SCHEMA_EXAMPLE}"
        )

    return f"""Analyze this video transcript and identify the most engaging segments for short-form content.

The transcript is formatted as one line per timestamped span, for example:
[00:12 - 00:21] Spoken text here
[00:21 - 00:35] More spoken text here

Follow this workflow:
1. Read the transcript as a sequence of timestamped spans.
2. Select only contiguous ranges that already exist in the transcript.
3. Prefer moments with a strong hook, clear payoff, emotional charge, or concrete value.
4. For each chosen segment, use the earliest timestamp in the selected range as start_time and the latest timestamp in the selected range as end_time.
5. Return results in two tiers:
   - micro_hooks: 3-5 clips, each 10-30 seconds, punchy standalone hooks.
   - deep_context_clips: 2-4 clips, each 30-90 seconds, richer narrative arcs.{broll_instruction}

Required JSON output keys:
- micro_hooks (array of segment objects)
- deep_context_clips (array of segment objects)
- summary (string)
- key_topics (array of strings)

Each segment object must include: start_time, end_time, text, relevance_score, reasoning, virality (with hook_score, engagement_score, value_score, shareability_score, total_score, hook_type, virality_reasoning).

Example output shape:
{DUAL_TIER_JSON_SCHEMA_EXAMPLE}

Critical accuracy requirements:
- Do not fabricate or embellish content.
- Do not use timestamps that are not present in the transcript.
- Do not merge separate non-contiguous moments into one segment.
- segment.text must reflect only the spoken content inside the selected time range.
- If a span lacks enough context to stand alone, expand to nearby contiguous lines rather than guessing.
- If there is a tradeoff between "viral" and "accurate", choose accuracy.
- Do not reject or penalize a segment simply because of the subject matter; stay content-neutral and assess clip quality only.{json_instruction}

Transcript:
{transcript}"""


def _timestamp_to_seconds(ts: str) -> int:
    """Convert a timestamp string to total seconds."""
    return int(_parse_ts_seconds(ts))


def _normalize_timestamp(ts: str) -> str:
    """Normalize any timestamp format to MM:SS."""
    try:
        start, end = parse_timestamp_or_range(ts)
        if end is not None:
            return seconds_to_mmss(start)
        return seconds_to_mmss(start)
    except (ValueError, IndexError):
        return ts


def _normalize_segment_times(start_time: str, end_time: str) -> tuple[str, str]:
    """Normalize start/end, splitting combined range strings from LLM output."""
    start_s, end_s = resolve_segment_timestamps(start_time, end_time)
    return seconds_to_mmss(start_s), seconds_to_mmss(end_s)


def _segment_duration_seconds(segment: TranscriptSegment) -> Optional[int]:
    """Return segment duration in seconds, or None if timestamps are invalid."""
    try:
        start_seconds = _timestamp_to_seconds(segment.start_time)
        end_seconds = _timestamp_to_seconds(segment.end_time)
        duration = end_seconds - start_seconds
        if duration <= 0:
            return None
        return duration
    except (ValueError, IndexError):
        return None


def _classify_segment_tier(duration: int) -> Optional[str]:
    """Classify a segment into micro_hook or deep_context by duration."""
    if MICRO_HOOK_MIN_SECONDS <= duration <= MICRO_HOOK_MAX_SECONDS:
        return "micro_hook"
    if DEEP_CONTEXT_MIN_SECONDS <= duration <= DEEP_CONTEXT_MAX_SECONDS:
        return "deep_context"
    return None


def _extract_json_from_text(text: str) -> Optional[dict]:
    """Extract a JSON object from raw LLM text output, tolerating markdown fences and preamble."""
    # Try to find JSON within ```json ... ``` fences first
    fence_match = re.search(r'```(?:json)?\s*\n?(\{.*?\})\s*```', text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find the outermost { ... } in the text
    brace_start = text.find('{')
    if brace_start == -1:
        return None

    # Find matching closing brace
    depth = 0
    for i in range(brace_start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[brace_start:i + 1])
                except json.JSONDecodeError:
                    pass
                break
    return None


def _build_default_virality() -> ViralityAnalysis:
    """Build a default virality analysis for segments parsed from raw JSON."""
    return ViralityAnalysis(
        hook_score=10,
        engagement_score=10,
        value_score=10,
        shareability_score=10,
        total_score=40,
        hook_type="none",
        virality_reasoning="Parsed from raw model output",
    )


def _parse_segment_list(raw_segments: list) -> List[TranscriptSegment]:
    """Parse a list of raw segments from JSON dicts, tolerating malformed items."""
    segments = []
    for seg in raw_segments:
        if not isinstance(seg, dict):
            continue
        try:
            start_time = str(seg.get("start_time") or seg.get("start") or seg.get("start_timestamp") or "00:00")
            end_time = str(seg.get("end_time") or seg.get("end") or seg.get("end_timestamp") or "00:00")
            start_time, end_time = _normalize_segment_times(start_time, end_time)
            text = str(seg.get("text") or seg.get("content") or seg.get("transcript") or "")
            reasoning = str(seg.get("reasoning") or seg.get("reason") or seg.get("explanation") or "Selected by AI")
            relevance = seg.get("relevance_score") or seg.get("relevance") or seg.get("score") or 0.5

            virality_data = seg.get("virality") or seg.get("virality_analysis")
            if isinstance(virality_data, dict):
                virality_data["hook_score"] = _safe_int(
                    virality_data.get("hook_score", 10), default=10, min_val=0, max_val=25
                )
                virality_data["engagement_score"] = _safe_int(
                    virality_data.get("engagement_score", 10), default=10, min_val=0, max_val=25
                )
                virality_data["value_score"] = _safe_int(
                    virality_data.get("value_score", 10), default=10, min_val=0, max_val=25
                )
                virality_data["shareability_score"] = _safe_int(
                    virality_data.get("shareability_score", 10), default=10, min_val=0, max_val=25
                )
                virality_data["total_score"] = (
                    virality_data["hook_score"] + virality_data["engagement_score"]
                    + virality_data["value_score"] + virality_data["shareability_score"]
                )
                hook_type = virality_data.get("hook_type", "none")
                if hook_type not in ("question", "statement", "statistic", "story", "contrast", "none"):
                    hook_type = "none"
                virality_data["hook_type"] = hook_type
                virality_data.setdefault("virality_reasoning", "Parsed from model output")
                virality = ViralityAnalysis(**virality_data)
            else:
                virality = _build_default_virality()

            segment = TranscriptSegment(
                start_time=start_time,
                end_time=end_time,
                text=text,
                relevance_score=max(0.0, min(1.0, float(relevance))),
                reasoning=reasoning,
                virality=virality,
            )
            segments.append(segment)
            logger.info(f"Raw parse: parsed segment {segment.start_time}-{segment.end_time}")
        except Exception as parse_err:
            logger.warning(f"Skipping malformed segment during raw parse: {parse_err}")
            continue
    return segments


def _parse_raw_analysis(raw: dict) -> TranscriptAnalysis:
    """Parse a raw dict from the LLM into a TranscriptAnalysis, tolerating missing/malformed fields."""
    micro_hooks_raw = raw.get("micro_hooks") or []
    deep_context_clips_raw = raw.get("deep_context_clips") or []

    micro_hooks = _parse_segment_list(micro_hooks_raw) if isinstance(micro_hooks_raw, list) else []
    deep_context_clips = _parse_segment_list(deep_context_clips_raw) if isinstance(deep_context_clips_raw, list) else []

    # Try standard parse for backward compatibility if micro/deep not found or if we want to check other keys
    segments = []
    for key in ("most_relevant_segments", "segments", "clips", "relevant_segments", "results", "most_relevant"):
        if key in raw and isinstance(raw[key], list):
            segments = _parse_segment_list(raw[key])
            break

    # If segments list is empty, combine them for backward compatibility
    if not segments:
        segments = list(micro_hooks) + list(deep_context_clips)

    logger.info(f"Raw parse: total {len(segments)} segments parsed successfully ({len(micro_hooks)} micro hooks, {len(deep_context_clips)} deep context)")

    summary = str(raw.get("summary") or raw.get("video_summary") or raw.get("description") or "Video content analysis")
    key_topics = raw.get("key_topics") or raw.get("topics") or raw.get("main_topics") or ["general"]

    return TranscriptAnalysis(
        most_relevant_segments=segments,
        micro_hooks=micro_hooks,
        deep_context_clips=deep_context_clips,
        summary=summary,
        key_topics=key_topics if isinstance(key_topics, list) else [str(key_topics)],
        broll_opportunities=None,
    )


async def _ollama_raw_json_call(transcript: str, include_broll: bool = False) -> Optional[TranscriptAnalysis]:
    """Call Ollama directly via HTTP and manually parse the dual-tier JSON response."""
    import httpx

    base_url = (config.ollama_base_url or "http://localhost:11434/v1").rstrip("/v1").rstrip("/")
    model_name = config.llm.removeprefix("ollama:")

    prompt = build_transcript_analysis_prompt(
        transcript=transcript, include_broll=include_broll, json_only=True
    )
    system = transcript_analysis_system_prompt + OLLAMA_JSON_RESPONSE_SUFFIX

    logger.info(
        f"Calling Ollama directly at {base_url}/api/chat "
        f"(model={model_name}, temperature=0.1, num_predict=8192)"
    )

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 8192,
                    }
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            logger.info(f"Ollama: got {len(content)} chars from model")

            parsed = _extract_json_from_text(content)
            if not parsed:
                # The content might already be valid JSON since we asked for format=json
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError:
                    logger.error("Ollama: could not extract JSON from response")
                    return None

            return _parse_raw_analysis(parsed)
    except Exception as e:
        logger.error(f"Ollama direct call failed: {e}")
        return None


# Backward-compatible alias
async def _fallback_raw_ollama_call(transcript: str, include_broll: bool = False) -> Optional[TranscriptAnalysis]:
    return await _ollama_raw_json_call(transcript, include_broll)


def _segment_key(segment: TranscriptSegment) -> tuple[str, str]:
    return (segment.start_time, segment.end_time)


def _validate_and_finalize_analysis(
    analysis: TranscriptAnalysis, include_broll: bool = False
) -> TranscriptAnalysis:
    """Validate segments, enforce tier durations, and build the final analysis."""
    validated_micro_hooks: List[TranscriptSegment] = []
    validated_deep_context_clips: List[TranscriptSegment] = []
    seen_keys: set[tuple[str, str]] = set()

    def validate_base_segment(segment: TranscriptSegment) -> Optional[TranscriptSegment]:
        if not segment.text.strip() or len(segment.text.split()) < 3:
            logger.warning(
                f"Skipping segment with insufficient content: '{segment.text[:50]}...'"
            )
            return None

        if segment.start_time == segment.end_time:
            logger.warning(
                f"Skipping segment with identical start/end times: {segment.start_time}"
            )
            return None

        duration = _segment_duration_seconds(segment)
        if duration is None:
            logger.warning(
                f"Skipping segment with invalid timestamps: "
                f"{segment.start_time}-{segment.end_time}"
            )
            return None

        if segment.virality:
            calculated_total = (
                segment.virality.hook_score
                + segment.virality.engagement_score
                + segment.virality.value_score
                + segment.virality.shareability_score
            )
            if segment.virality.total_score != calculated_total:
                logger.warning(
                    f"Correcting virality total: {segment.virality.total_score} -> {calculated_total}"
                )
                segment.virality.total_score = calculated_total

        virality_info = (
            f", virality={segment.virality.total_score}" if segment.virality else ""
        )
        logger.info(
            f"Validated segment: {segment.start_time}-{segment.end_time} "
            f"({duration}s){virality_info}"
        )
        return segment

    def validate_micro_hook(segment: TranscriptSegment) -> Optional[TranscriptSegment]:
        validated = validate_base_segment(segment)
        if validated is None:
            return None
        duration = _segment_duration_seconds(validated)
        if duration is None:
            return None
        if duration < MICRO_HOOK_MIN_SECONDS or duration > MICRO_HOOK_MAX_SECONDS:
            logger.warning(
                f"Skipping micro_hook out of tier range ({duration}s): "
                f"{validated.start_time}-{validated.end_time} "
                f"(expected {MICRO_HOOK_MIN_SECONDS}-{MICRO_HOOK_MAX_SECONDS}s)"
            )
            return None
        return validated

    def validate_deep_context_clip(segment: TranscriptSegment) -> Optional[TranscriptSegment]:
        validated = validate_base_segment(segment)
        if validated is None:
            return None
        duration = _segment_duration_seconds(validated)
        if duration is None:
            return None
        if duration < DEEP_CONTEXT_MIN_SECONDS or duration > DEEP_CONTEXT_MAX_SECONDS:
            logger.warning(
                f"Skipping deep_context_clip out of tier range ({duration}s): "
                f"{validated.start_time}-{validated.end_time} "
                f"(expected {DEEP_CONTEXT_MIN_SECONDS}-{DEEP_CONTEXT_MAX_SECONDS}s)"
            )
            return None
        return validated

    def add_to_tier(
        segment: TranscriptSegment,
        declared_tier: str,
    ) -> None:
        key = _segment_key(segment)
        if key in seen_keys:
            return

        duration = _segment_duration_seconds(segment)
        if duration is None:
            return

        validated: Optional[TranscriptSegment] = None
        target_bucket: Optional[str] = None

        if declared_tier == "micro_hook":
            validated = validate_micro_hook(segment)
            target_bucket = "micro_hook"
            if validated is None:
                reclassified = _classify_segment_tier(duration)
                if reclassified == "deep_context":
                    logger.info(
                        f"Re-bucketing mislabeled micro_hook ({duration}s) into deep_context_clips"
                    )
                    validated = validate_deep_context_clip(segment)
                    target_bucket = "deep_context"
        elif declared_tier == "deep_context":
            validated = validate_deep_context_clip(segment)
            target_bucket = "deep_context"
            if validated is None:
                reclassified = _classify_segment_tier(duration)
                if reclassified == "micro_hook":
                    logger.info(
                        f"Re-bucketing mislabeled deep_context_clip ({duration}s) into micro_hooks"
                    )
                    validated = validate_micro_hook(segment)
                    target_bucket = "micro_hook"
        else:
            tier = _classify_segment_tier(duration)
            if tier == "micro_hook":
                validated = validate_micro_hook(segment)
                target_bucket = "micro_hook"
            elif tier == "deep_context":
                validated = validate_deep_context_clip(segment)
                target_bucket = "deep_context"
            else:
                logger.warning(
                    f"Skipping segment with duration outside both tiers ({duration}s): "
                    f"{segment.start_time}-{segment.end_time}"
                )
                return

        if validated is None:
            return

        seen_keys.add(key)
        if target_bucket == "micro_hook":
            validated_micro_hooks.append(validated)
        elif target_bucket == "deep_context":
            validated_deep_context_clips.append(validated)

    for segment in analysis.micro_hooks:
        add_to_tier(segment, "micro_hook")

    for segment in analysis.deep_context_clips:
        add_to_tier(segment, "deep_context")

    for segment in analysis.most_relevant_segments:
        if _segment_key(segment) in seen_keys:
            continue
        add_to_tier(segment, "auto")

    combined_segments = validated_micro_hooks + validated_deep_context_clips

    combined_segments.sort(
        key=lambda x: (
            x.virality.total_score if x.virality else 0,
            x.relevance_score,
        ),
        reverse=True,
    )

    final_analysis = TranscriptAnalysis(
        most_relevant_segments=combined_segments,
        micro_hooks=validated_micro_hooks,
        deep_context_clips=validated_deep_context_clips,
        summary=analysis.summary,
        key_topics=analysis.key_topics,
        broll_opportunities=analysis.broll_opportunities if include_broll else None,
    )

    logger.info(
        f"Selected {len(combined_segments)} total segments "
        f"({len(validated_micro_hooks)} micro hooks, "
        f"{len(validated_deep_context_clips)} deep context) for processing"
    )
    if combined_segments:
        top = combined_segments[0]
        logger.info(
            f"Top segment - relevance: {top.relevance_score:.2f}, "
            f"virality: {top.virality.total_score if top.virality else 'N/A'}"
        )

    return final_analysis


async def _ollama_json_request(
    system: str,
    prompt: str,
    *,
    num_predict: Optional[int] = None,
) -> Optional[dict]:
    """Call Ollama and return parsed JSON dict."""
    import httpx

    base_url = (config.ollama_base_url or "http://localhost:11434/v1").rstrip("/v1").rstrip("/")
    model_name = config.llm.removeprefix("ollama:")
    predict_tokens = num_predict or config.ollama_num_predict

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.1,
                        "num_predict": predict_tokens,
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            parsed = _extract_json_from_text(content)
            if parsed:
                return parsed
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                logger.error("Ollama: could not extract JSON from response")
                return None
    except Exception as exc:
        logger.error(f"Ollama request failed: {exc}")
        return None


def build_window_micro_prompt(
    window_text: str,
    window_index: int,
    total_windows: int,
    hints: Optional[List[str]] = None,
) -> str:
    hint_block = ""
    if hints:
        hint_block = (
            "\nCandidate hook timestamps to consider: "
            + ", ".join(hints)
            + "\n"
        )
    return f"""Analyze ONLY this transcript window ({window_index + 1}/{total_windows}) and find punchy micro hooks.

Rules:
- Return ONLY micro_hooks (10-30 seconds each)
- Find {config.micro_per_window} strong standalone hooks in THIS window only
- Use timestamps that appear in this window
- Do not invent content outside the window
{hint_block}
Required JSON keys: micro_hooks (array), summary (string), key_topics (array)
Each segment needs: start_time, end_time, text, relevance_score, reasoning, virality

Window transcript:
{window_text}"""


def build_window_deep_prompt(
    window_text: str,
    window_index: int,
    total_windows: int,
) -> str:
    return f"""Analyze ONLY this transcript window ({window_index + 1}/{total_windows}) and find deep context clips.

Rules:
- Return ONLY deep_context_clips (30-90 seconds each)
- Find {config.deep_per_window} narrative arcs in THIS window only
- Use timestamps that appear in this window
- Do not invent content outside the window

Required JSON keys: deep_context_clips (array), summary (string), key_topics (array)
Each segment needs: start_time, end_time, text, relevance_score, reasoning, virality

Window transcript:
{window_text}"""


def build_rerank_prompt(candidates: List[TranscriptSegment]) -> str:
    lines = []
    for idx, segment in enumerate(candidates):
        score = segment.virality.total_score if segment.virality else 0
        preview = segment.text[:180].replace("\n", " ")
        lines.append(
            f'{idx}: {segment.start_time}-{segment.end_time} score={score} text="{preview}"'
        )
    candidate_block = "\n".join(lines)
    return f"""Rank these clip candidates for short-form virality (Hook, Flow, Value, Shareability).

Return JSON:
{{
  "ranked_ids": [0, 3, 1, ...],
  "scores": [
    {{"id": 0, "total_score": 85, "hook_score": 22, "engagement_score": 21, "value_score": 20, "shareability_score": 22}}
  ]
}}

Candidates:
{candidate_block}"""


async def analyze_window_micro(
    window_text: str,
    window_index: int,
    total_windows: int,
    hints: Optional[List[str]] = None,
) -> List[TranscriptSegment]:
    prompt = build_window_micro_prompt(window_text, window_index, total_windows, hints)
    system = transcript_analysis_system_prompt + OLLAMA_JSON_RESPONSE_SUFFIX
    raw = await _ollama_json_request(system, prompt)
    if not raw:
        return []
    parsed = _parse_raw_analysis(raw)
    return list(parsed.micro_hooks)


async def analyze_window_deep(
    window_text: str,
    window_index: int,
    total_windows: int,
) -> List[TranscriptSegment]:
    prompt = build_window_deep_prompt(window_text, window_index, total_windows)
    system = transcript_analysis_system_prompt + OLLAMA_JSON_RESPONSE_SUFFIX
    raw = await _ollama_json_request(system, prompt)
    if not raw:
        return []
    parsed = _parse_raw_analysis(raw)
    return list(parsed.deep_context_clips)


async def rerank_candidates(
    candidates: List[TranscriptSegment],
) -> List[TranscriptSegment]:
    if len(candidates) <= 1:
        return candidates

    try:
        prompt = build_rerank_prompt(candidates)
        system = (
            "You rank short-form video clip candidates. Respond with JSON only. "
            "Higher scores mean stronger viral potential."
        )
        raw = await _ollama_json_request(system, prompt, num_predict=2048)
        if not raw:
            return candidates

        ranked_ids = raw.get("ranked_ids") or []
        score_rows = raw.get("scores") or []
        score_by_id: dict[int, dict] = {}
        for row in score_rows:
            if not isinstance(row, dict) or "id" not in row:
                continue
            idx = _safe_int(row["id"], default=-1)
            if idx < 0:
                logger.warning("Skipping rerank score row with non-numeric id: %r", row.get("id"))
                continue
            score_by_id[idx] = row

        reranked: List[TranscriptSegment] = []
        seen: set[int] = set()
        for raw_id in ranked_ids:
            idx = _safe_int(raw_id, default=-1)
            if idx < 0 or idx >= len(candidates) or idx in seen:
                continue
            seen.add(idx)
            segment = candidates[idx]
            score_row = score_by_id.get(idx)
            if score_row and segment.virality:
                hook = _safe_int(
                    score_row.get("hook_score", segment.virality.hook_score),
                    default=segment.virality.hook_score,
                    min_val=0,
                    max_val=25,
                )
                engagement = _safe_int(
                    score_row.get("engagement_score", segment.virality.engagement_score),
                    default=segment.virality.engagement_score,
                    min_val=0,
                    max_val=25,
                )
                value = _safe_int(
                    score_row.get("value_score", segment.virality.value_score),
                    default=segment.virality.value_score,
                    min_val=0,
                    max_val=25,
                )
                share = _safe_int(
                    score_row.get("shareability_score", segment.virality.shareability_score),
                    default=segment.virality.shareability_score,
                    min_val=0,
                    max_val=25,
                )
                total = _safe_int(
                    score_row.get("total_score", hook + engagement + value + share),
                    default=hook + engagement + value + share,
                    min_val=0,
                    max_val=100,
                )
                segment.virality.hook_score = hook
                segment.virality.engagement_score = engagement
                segment.virality.value_score = value
                segment.virality.shareability_score = share
                segment.virality.total_score = total
            reranked.append(segment)

        for idx, segment in enumerate(candidates):
            if idx not in seen:
                reranked.append(segment)

        return reranked
    except Exception as err:
        logger.warning("Rerank failed, using original candidate order: %s", err)
        return candidates


async def analyze_transcript_map_reduce(
    transcript: str,
    processing_mode: str = "quality",
    progress_callback: Optional[Callable[[int, str, str], Awaitable[None]]] = None,
) -> TranscriptAnalysis:
    """Windowed dual-pass analysis with merge, dedup, and optional rerank."""
    from .transcript_windows import (
        extract_candidate_hints,
        select_final_segments,
        split_transcript_into_windows,
    )

    mode = (processing_mode or "quality").lower()
    if mode == "fast":
        max_windows = 3
        run_deep = False
        run_rerank = False
        max_micro = config.fast_mode_max_clips
        max_deep = 0
    elif mode == "balanced":
        max_windows = 5
        run_deep = True
        run_rerank = False
        max_micro = max(3, config.balanced_mode_max_clips // 2)
        max_deep = max(2, config.balanced_mode_max_clips - max_micro)
    else:
        max_windows = config.analysis_max_windows
        run_deep = True
        run_rerank = True
        max_micro = config.quality_mode_max_micro
        max_deep = config.quality_mode_max_deep

    windows = split_transcript_into_windows(
        transcript,
        window_seconds=config.transcript_window_seconds,
        overlap_seconds=config.transcript_window_overlap,
        max_windows=max_windows if mode != "quality" else None,
    )
    total_windows = len(windows)
    all_micro: List[TranscriptSegment] = []
    all_deep: List[TranscriptSegment] = []
    summaries: List[str] = []
    topics: set[str] = set()

    for window in windows:
        if progress_callback:
            await progress_callback(
                30 + int((window.index / max(total_windows, 1)) * 8),
                f"Analyzing hooks in part {window.index + 1}/{total_windows}...",
                "processing",
            )

        hints = extract_candidate_hints(window.text)
        micro_segments = await analyze_window_micro(
            window.text, window.index, total_windows, hints
        )
        all_micro.extend(micro_segments)

        if run_deep:
            if progress_callback:
                await progress_callback(
                    38 + int((window.index / max(total_windows, 1)) * 8),
                    f"Analyzing context clips in part {window.index + 1}/{total_windows}...",
                    "processing",
                )
            deep_segments = await analyze_window_deep(
                window.text, window.index, total_windows
            )
            all_deep.extend(deep_segments)

    final_micro, final_deep = select_final_segments(
        all_micro,
        all_deep,
        max_micro=max_micro,
        max_deep=max_deep if run_deep else 0,
        bucket_seconds=config.transcript_window_seconds,
        max_per_bucket=2,
    )

    combined = final_micro + final_deep
    if run_rerank and combined:
        if progress_callback:
            await progress_callback(
                48,
                f"Ranking top {min(len(combined), 25)} clip candidates...",
                "processing",
            )
        combined = await rerank_candidates(combined[:25])
        reranked_micro: List[TranscriptSegment] = []
        reranked_deep: List[TranscriptSegment] = []
        for segment in combined:
            duration = _segment_duration_seconds(segment)
            if duration is None:
                continue
            tier = _classify_segment_tier(duration)
            if tier == "micro_hook":
                reranked_micro.append(segment)
            elif tier == "deep_context":
                reranked_deep.append(segment)
        final_micro = reranked_micro[:max_micro]
        final_deep = reranked_deep[:max_deep]
        combined = final_micro + final_deep

    draft = TranscriptAnalysis(
        most_relevant_segments=final_micro + final_deep,
        micro_hooks=final_micro,
        deep_context_clips=final_deep,
        summary=summaries[0] if summaries else "Windowed transcript analysis",
        key_topics=sorted(topics) if topics else ["general"],
    )
    return _validate_and_finalize_analysis(draft, include_broll=False)


async def get_most_relevant_parts_by_transcript(
    transcript: str,
    include_broll: bool = False,
    processing_mode: str = "quality",
    progress_callback: Optional[Callable[[int, str, str], Awaitable[None]]] = None,
) -> TranscriptAnalysis:
    """Get the most relevant parts of a transcript with virality scoring and optional B-roll detection."""
    logger.info(
        f"Starting AI analysis of transcript ({len(transcript)} chars), "
        f"include_broll={include_broll}"
    )

    analysis: Optional[TranscriptAnalysis] = None
    use_map_reduce = len(transcript) > 8000 or processing_mode in ("balanced", "quality")

    if use_map_reduce and config.llm.startswith("ollama:"):
        logger.info(
            f"Using map-reduce analysis (mode={processing_mode}, chars={len(transcript)})"
        )
        return await analyze_transcript_map_reduce(
            transcript,
            processing_mode=processing_mode,
            progress_callback=progress_callback,
        )

    if config.llm.startswith("ollama:"):
        analysis = await _ollama_raw_json_call(transcript, include_broll)
        if analysis is None:
            raise RuntimeError(
                "Transcript analysis failed: Ollama returned no parseable JSON. "
                "Check OLLAMA_BASE_URL, model name (LLM=ollama:<tag>), and that the model is pulled."
            )
    else:
        try:
            agent = get_transcript_agent()
            result = await agent.run(
                build_transcript_analysis_prompt(
                    transcript=transcript, include_broll=include_broll
                ),
                model_settings={"temperature": 0.1, "max_tokens": 8192},
            )
            analysis = result.data
            logger.info(
                f"AI analysis found: {len(analysis.micro_hooks)} micro_hooks, "
                f"{len(analysis.deep_context_clips)} deep_context_clips"
            )
        except Exception as structured_err:
            logger.warning(f"Structured output failed: {structured_err}")
            raise RuntimeError(
                f"Transcript analysis failed: {structured_err}"
            ) from structured_err

    try:
        return _validate_and_finalize_analysis(analysis, include_broll=include_broll)
    except Exception as e:
        logger.error(f"Error in transcript analysis: {e}")
        raise RuntimeError(f"Transcript analysis failed: {str(e)}") from e


def get_most_relevant_parts_sync(transcript: str) -> TranscriptAnalysis:
    """Synchronous wrapper for the async function."""
    return asyncio.run(get_most_relevant_parts_by_transcript(transcript))
