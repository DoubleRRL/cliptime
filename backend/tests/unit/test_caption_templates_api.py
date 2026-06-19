from src.caption_templates import get_template, get_template_info
from src.ass_captions import generate_ass_from_words


def test_get_template_info_includes_background_flag():
    templates = {item["id"]: item for item in get_template_info()}
    assert templates["riverside"]["background"] is True
    assert templates["riverside"]["pill_style"] is True
    assert templates["podcast"]["background"] is True
    assert templates["tiktok"]["background"] is False
    assert templates["tiktok"]["emphasis_callouts"] is True
    assert templates["minimal"]["emphasis_callouts"] is True


def _ass_style_line(ass: str) -> str:
    for line in ass.split("\n"):
        if line.startswith("Style: Default"):
            return line
    raise AssertionError("Style line not found")


def test_ass_uses_opaque_box_for_background_templates():
    template = {
        **get_template("hormozi"),
        "background_color": "#000000AA",
    }
    ass = generate_ass_from_words(
        [{"text": "hello", "start": 0.0, "end": 0.5}],
        template,
        1080,
        1920,
    )
    style_line = _ass_style_line(ass)
    assert ",3," in style_line
    assert "&H55000000" in style_line


def test_ass_outline_style_for_templates_without_background():
    template = get_template("tiktok")
    ass = generate_ass_from_words(
        [{"text": "hello", "start": 0.0, "end": 0.5}],
        template,
        1080,
        1920,
    )
    style_line = _ass_style_line(ass)
    assert ",1," in style_line
    assert "&H00000000" in style_line
