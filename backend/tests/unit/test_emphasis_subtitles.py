"""Tests for emphasis highlight pills in subtitle compositor."""

from src.subtitle_compositor import (
    _is_transparent_background,
    _should_show_active_highlight_pill,
    render_pill_phrase_image,
)


def test_is_transparent_background_detects_full_alpha_zero():
    assert _is_transparent_background("#00000000") is True
    assert _is_transparent_background("transparent") is True
    assert _is_transparent_background("#1A1A1ACC") is False


def test_should_show_active_highlight_pill_only_for_emphasis_words_when_enabled():
    template = {
        "emphasis_callouts": True,
        "emphasis_words": ["laugh"],
    }
    assert _should_show_active_highlight_pill(template, "laugh") is True
    assert _should_show_active_highlight_pill(template, "here") is False


def test_should_show_active_highlight_pill_for_all_words_when_disabled():
    template = {
        "emphasis_callouts": False,
        "emphasis_words": ["laugh"],
    }
    assert _should_show_active_highlight_pill(template, "here") is True


def test_render_pill_phrase_image_uses_width_scaled_font_size():
    template_small = {
        "font_size": 24,
        "font_color": "#FFFFFF",
        "highlight_color": "#8B5CF6",
        "background_color": "#1A1A1ACC",
        "emphasis_callouts": False,
    }
    template_large = {
        **template_small,
        "font_size": 48,
    }
    small = render_pill_phrase_image(
        ["hello", "world"],
        0,
        template_small,
        "/nonexistent/font.ttf",
        1080,
        900,
    )
    large = render_pill_phrase_image(
        ["hello", "world"],
        0,
        template_large,
        "/nonexistent/font.ttf",
        1080,
        900,
    )
    assert large.size[1] > small.size[1]


def test_render_pill_phrase_image_skips_line_backdrop_when_transparent(tmp_path):
    font_path = tmp_path / "font.ttf"
    # Use default font fallback — render should not raise.
    template = {
        "font_size": 24,
        "font_color": "#FFFFFF",
        "highlight_color": "#8B5CF6",
        "background_color": "#00000000",
        "emphasis_callouts": False,
    }
    image = render_pill_phrase_image(
        ["hello", "world"],
        0,
        template,
        str(font_path),
        360,
        320,
    )
    assert image.mode == "RGBA"
    # Transparent line backdrop: corners should stay fully transparent.
    assert image.getpixel((0, 0))[3] == 0
