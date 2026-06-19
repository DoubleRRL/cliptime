from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src import video_utils
from src.layout_director import LayoutSegment, fill_layout_timeline_gaps, remap_layout_timeline_to_output
from src.tight_cuts import KeepSpan


class FakeSpanClip:
    def __init__(self, size=(1920, 1080), duration=2.0):
        self.size = size
        self.fps = 30
        self.duration = duration

    def subclipped(self, start, end):
        return FakeSpanClip()

    def cropped(self, **kwargs):
        return FakeSpanClip(size=(1080, 1920))

    def resized(self, size):
        return FakeSpanClip(size=size)

    def write_videofile(self, *args, **kwargs):
        return None

    def close(self):
        return None


def test_remap_layout_timeline_to_output_offsets_spans():
    span_timelines = [
        [LayoutSegment(0, 500, "solo", "A"), LayoutSegment(500, 2000, "dual", None)],
        [LayoutSegment(0, 1500, "solo", "B")],
    ]
    remapped = remap_layout_timeline_to_output([2000, 1500], span_timelines)

    assert remapped == [
        LayoutSegment(0, 500, "solo", "A"),
        LayoutSegment(500, 2000, "dual", None),
        LayoutSegment(2000, 3500, "solo", "B"),
    ]


def test_process_vertical_span_face_crop_does_not_import_layout_director():
    video = FakeSpanClip()
    with patch(
        "src.video_utils.detect_optimal_crop_region",
        return_value=(0, 0, 1080, 1920),
    ) as mock_crop:
        result, rendered_timeline = video_utils._process_vertical_span(
            video,
            None,
            0.0,
            2.0,
            1080,
            1920,
            1080,
            1920,
            Path("/tmp/source.mp4"),
            use_directed_layout=False,
        )

    mock_crop.assert_called_once()
    assert rendered_timeline is None
    assert result.size == (1080, 1920)


def test_process_vertical_span_directed_layout_uses_video_utils_helpers():
    video = FakeSpanClip()
    layout_ctx = MagicMock()
    layout_ctx.timeline = []
    layout_ctx.clip_start_ms = 1000
    rendered_timeline = [LayoutSegment(0, 2000, "solo", "A")]
    directed = FakeSpanClip(size=(1080, 1920))

    with (
        patch("src.video_utils.prepare_directed_layout", return_value=layout_ctx) as mock_prepare,
        patch(
            "src.video_utils.create_directed_clip",
            return_value=(directed, rendered_timeline),
        ) as mock_directed,
        patch("src.layout_director.create_directed_clip", create=True) as wrong_import,
    ):
        result, returned_timeline = video_utils._process_vertical_span(
            video,
            {"utterances": [{"speaker": "A", "start": 0, "end": 1000}]},
            1.0,
            3.0,
            1080,
            1920,
            1080,
            1920,
            Path("/tmp/source.mp4"),
            use_directed_layout=True,
        )

    mock_prepare.assert_called_once()
    mock_directed.assert_called_once()
    wrong_import.assert_not_called()
    assert returned_timeline is rendered_timeline
    assert result.size == (1080, 1920)


def test_create_optimized_clip_tight_cuts_multi_span_uses_directed_layout():
    keep_spans = [
        KeepSpan(src_start_ms=1000, src_end_ms=2000),
        KeepSpan(src_start_ms=3000, src_end_ms=4000),
    ]
    processed = FakeSpanClip(size=(1080, 1920), duration=2.0)
    span_timeline = [LayoutSegment(0, 1000, "solo", "A")]

    with (
        patch(
            "src.video_utils._resolve_tight_cut_plan",
            return_value=(True, keep_spans, []),
        ),
        patch(
            "src.video_utils._process_vertical_span",
            return_value=(processed, span_timeline),
        ) as mock_span,
        patch("src.video_utils.VideoFileClip") as mock_video_file,
        patch("moviepy.concatenate_videoclips", return_value=processed),
        patch(
            "src.video_utils.load_cached_transcript_data",
            return_value={"utterances": [{"speaker": "A", "start": 0, "end": 5000}]},
        ),
        patch(
            "src.video_utils.create_assemblyai_subtitles",
            return_value=[],
        ) as mock_subs,
    ):
        mock_clip = MagicMock()
        mock_clip.fps = 30
        mock_clip.duration = 10
        mock_clip.size = (1920, 1080)
        mock_clip.subclipped.return_value = mock_clip
        mock_video_file.return_value = mock_clip

        ok = video_utils.create_optimized_clip(
            Path("/tmp/source.mp4"),
            1.0,
            5.0,
            Path("/tmp/out.mp4"),
            add_subtitles=True,
            tight_cuts=True,
        )

    assert ok is True
    assert mock_span.call_count == 2
    assert all(
        call.kwargs.get("use_directed_layout") is True for call in mock_span.call_args_list
    )
    subs_kwargs = mock_subs.call_args.kwargs
    assert subs_kwargs["layout_timeline"] is not None
    filled = subs_kwargs["layout_timeline"]
    assert filled[0].start_ms == 0
    assert filled[-1].end_ms == 2000


def test_create_optimized_clip_tight_cuts_multi_span_calls_process_vertical_span():
    keep_spans = [
        KeepSpan(src_start_ms=1000, src_end_ms=2000),
        KeepSpan(src_start_ms=3000, src_end_ms=4000),
    ]
    processed = FakeSpanClip(size=(1080, 1920))

    with (
        patch(
            "src.video_utils._resolve_tight_cut_plan",
            return_value=(True, keep_spans, []),
        ),
        patch(
            "src.video_utils._process_vertical_span",
            return_value=(processed, None),
        ) as mock_span,
        patch("src.video_utils.VideoFileClip") as mock_video_file,
        patch("moviepy.concatenate_videoclips", return_value=processed),
        patch("src.video_utils.load_cached_transcript_data", return_value={"utterances": []}),
        patch(
            "src.video_utils.create_assemblyai_subtitles",
            return_value=[],
        ),
    ):
        mock_clip = MagicMock()
        mock_clip.fps = 30
        mock_clip.duration = 10
        mock_clip.size = (1920, 1080)
        mock_clip.subclipped.return_value = mock_clip
        mock_video_file.return_value = mock_clip

        ok = video_utils.create_optimized_clip(
            Path("/tmp/source.mp4"),
            1.0,
            5.0,
            Path("/tmp/out.mp4"),
            add_subtitles=False,
            tight_cuts=True,
        )

    assert ok is True
    assert mock_span.call_count == 2


@pytest.mark.asyncio
async def test_process_task_errors_when_all_clip_renders_fail():
    from unittest.mock import AsyncMock

    from src.config import Config
    from src.services.task_service import TaskService

    config = Config()
    service = TaskService(db=AsyncMock(), config=config)
    service.task_repo.get_task_by_id = AsyncMock(return_value={"status": "queued"})
    service.clip_repo.get_clips_by_task = AsyncMock(return_value=[])
    service.cache_repo.get_cache = AsyncMock(return_value=None)
    service.cache_repo.upsert_cache = AsyncMock()
    service.task_repo.update_task_runtime_metadata = AsyncMock()
    service.task_repo.update_task_status = AsyncMock()
    service.task_repo.update_task_clips = AsyncMock()
    service.video_service.create_single_clip = AsyncMock(return_value=None)
    service.video_service.process_video_complete = AsyncMock(
        return_value={
            "clips": [],
            "segments_to_render": [{"start_time": "00:00", "end_time": "00:10"}],
            "video_path": "/tmp/source.mp4",
            "segments": [],
            "summary": None,
            "key_topics": [],
            "transcript": "Transcript",
            "analysis_json": "{}",
        }
    )

    with pytest.raises(RuntimeError, match="All clip renders failed"):
        await service.process_task(
            task_id="task-1",
            url="upload://source.mp4",
            source_type="video_url",
        )

    error_calls = [
        call
        for call in service.task_repo.update_task_status.await_args_list
        if call.args[2] == "error"
    ]
    assert error_calls
    assert service.task_repo.update_task_runtime_metadata.await_args_list[-1].kwargs[
        "error_code"
    ] == "clip_render_failed"
