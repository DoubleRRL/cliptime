from unittest.mock import patch

from src.layout_director import (
    DUAL_MIN_MS,
    LayoutSegment,
    caption_position_y_at_time,
    fill_layout_timeline_gaps,
    remap_layout_timeline_to_output,
)
from src.subtitle_compositor import create_premium_karaoke_clips, resolve_group_font_size


def test_fill_layout_timeline_gaps_covers_full_duration():
    timeline = [
        LayoutSegment(200, 800, "dual", None),
        LayoutSegment(1200, 1600, "solo", "A"),
    ]
    filled = fill_layout_timeline_gaps(timeline, 2000)

    assert filled[0].start_ms == 0
    assert filled[-1].end_ms == 2000
    cursor = 0
    for seg in filled:
        assert seg.start_ms == cursor
        cursor = seg.end_ms
    assert cursor == 2000


def test_remap_short_span_forces_solo_caption_mode():
    span_timelines = [
        [LayoutSegment(0, 400, "dual", None)],
        [LayoutSegment(0, 600, "dual", "B")],
    ]
    short_duration = DUAL_MIN_MS - 1
    remapped = remap_layout_timeline_to_output([short_duration, short_duration], span_timelines)

    assert remapped == [
        LayoutSegment(0, short_duration, "solo", None),
        LayoutSegment(short_duration, short_duration * 2, "solo", "B"),
    ]


def test_remap_solo_span_uses_solo_y_not_dual():
    span_timelines = [[LayoutSegment(0, 1200, "solo", "A")]]
    remapped = remap_layout_timeline_to_output([1200], span_timelines)
    remapped = fill_layout_timeline_gaps(remapped, 1200)

    assert caption_position_y_at_time(0.5, remapped) == 0.77


def test_build_rendered_layout_timeline_accounts_for_crossfade():
    from src.video_utils import _build_rendered_layout_timeline

    clip_a = type("Clip", (), {"duration": 2.0})()
    clip_b = type("Clip", (), {"duration": 1.5})()
    entries = [
        (clip_a, LayoutSegment(0, 2000, "solo", "A")),
        (clip_b, LayoutSegment(2000, 3500, "dual", None)),
    ]
    timeline = _build_rendered_layout_timeline(entries, crossfade_s=0.1)

    assert timeline == [
        LayoutSegment(0, 2000, "solo", "A"),
        LayoutSegment(2000, 3400, "dual", None),
    ]


def test_premium_karaoke_locks_group_y_and_font_size():
    words = [
        {"text": "one", "start": 0.0, "end": 0.2},
        {"text": "two", "start": 0.2, "end": 0.4},
        {"text": "three", "start": 0.4, "end": 0.6},
    ]
    template = {
        "name": "Riverside",
        "premium": True,
        "pill_style": True,
        "font_size": 32,
        "font_color": "#FFFFFF",
        "highlight_color": "#8B5CF6",
        "background_color": "#1A1A1ACC",
    }
    positions = []
    sizes = []

    def capture_render(words_arg, active_idx, tmpl, font_path, video_width, max_width, **kwargs):
        from PIL import Image

        sizes.append(kwargs.get("fixed_base_size"))
        image = Image.new("RGBA", (400, 80), (0, 0, 0, 0))
        return image

    with (
        patch(
            "src.subtitle_compositor.render_phrase_image",
            side_effect=capture_render,
        ),
        patch(
            "src.subtitle_compositor.resolve_group_font_size",
            return_value=42,
        ) as mock_resolve,
        patch("moviepy.ImageClip") as mock_image_clip,
    ):
        mock_image_clip.return_value.with_duration.return_value.with_start.return_value.with_position.side_effect = (
            lambda pos: (positions.append(pos), type("Clip", (), {})())[1]
        )
        create_premium_karaoke_clips(
            words,
            1080,
            1920,
            template,
            "/tmp/font.ttf",
            layout_timeline=[LayoutSegment(0, 1000, "solo", "A")],
        )

    mock_resolve.assert_called_once()
    assert len(sizes) == 3
    assert all(size == 42 for size in sizes)
    assert len(positions) == 3
    assert positions[0][1] == positions[1][1] == positions[2][1]


def test_premium_karaoke_splits_group_at_layout_mode_boundary():
    words = [
        {"text": "dual", "start": 0.0, "end": 0.2},
        {"text": "one", "start": 0.2, "end": 0.4},
        {"text": "solo", "start": 0.5, "end": 0.7},
        {"text": "two", "start": 0.7, "end": 0.9},
    ]
    template = {
        "name": "Riverside",
        "premium": True,
        "pill_style": True,
        "font_size": 32,
        "font_color": "#FFFFFF",
        "highlight_color": "#8B5CF6",
        "background_color": "#1A1A1ACC",
    }
    timeline = [
        LayoutSegment(0, 400, "dual", None),
        LayoutSegment(400, 1000, "solo", "A"),
    ]
    positions = []

    with (
        patch(
            "src.subtitle_compositor.render_phrase_image",
            return_value=__import__("PIL").Image.new("RGBA", (200, 60), (0, 0, 0, 0)),
        ),
        patch(
            "src.subtitle_compositor.resolve_group_font_size",
            return_value=42,
        ),
        patch("moviepy.ImageClip") as mock_image_clip,
    ):
        mock_image_clip.return_value.with_duration.return_value.with_start.return_value.with_position.side_effect = (
            lambda pos: (positions.append(pos), type("Clip", (), {})())[1]
        )
        create_premium_karaoke_clips(
            words,
            1080,
            1920,
            template,
            "/tmp/font.ttf",
            layout_timeline=timeline,
        )

    assert len(positions) == 4
    dual_y = positions[0][1]
    solo_y = positions[2][1]
    assert dual_y != solo_y
    assert solo_y > dual_y


def test_premium_karaoke_uses_word_midpoint_for_layout_y():
    words = [
        {"text": "but", "start": 7.0, "end": 7.4},
        {"text": "you", "start": 7.4, "end": 8.5},
    ]
    timeline = [
        LayoutSegment(0, 7283, "dual", None),
        LayoutSegment(7283, 10000, "solo", "A"),
    ]
    positions = []

    with (
        patch(
            "src.subtitle_compositor.render_phrase_image",
            return_value=__import__("PIL").Image.new("RGBA", (200, 60), (0, 0, 0, 0)),
        ),
        patch(
            "src.subtitle_compositor.resolve_group_font_size",
            return_value=42,
        ),
        patch("moviepy.ImageClip") as mock_image_clip,
    ):
        mock_image_clip.return_value.with_duration.return_value.with_start.return_value.with_position.side_effect = (
            lambda pos: (positions.append(pos), type("Clip", (), {})())[1]
        )
        create_premium_karaoke_clips(
            words,
            1080,
            1920,
            {"premium": True, "pill_style": True, "font_size": 32},
            "/tmp/font.ttf",
            layout_timeline=timeline,
        )

    assert len(positions) == 2
    assert positions[0][1] < positions[1][1]


def test_resolve_group_font_size_uses_scaled_size_when_phrase_fits():
    template = {
        "premium": True,
        "pill_style": True,
        "font_size": 32,
    }
    words = ["hello", "world"]

    with (
        patch(
            "src.subtitle_compositor._scaled_template_font_size",
            return_value=48,
        ),
        patch(
            "src.subtitle_compositor._measure_line",
            return_value=(300, 40, 30, []),
        ),
    ):
        size = resolve_group_font_size(
            words, template, "/tmp/font.ttf", 1080, 400
        )

    assert size == 48
