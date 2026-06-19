from src.layout_director import (
    LayoutSegment,
    caption_position_y_at_time,
    fill_layout_timeline_gaps,
    remap_layout_timeline_to_output,
)


def test_remap_layout_timeline_uses_encoded_durations():
    span_timelines = [
        [LayoutSegment(0, 3000, "dual", None)],
        [LayoutSegment(0, 1500, "solo", "B")],
    ]
    remapped = remap_layout_timeline_to_output([2800, 1500], span_timelines)
    remapped = fill_layout_timeline_gaps(remapped, 4300)

    assert remapped[-1].end_ms == 4300
    assert caption_position_y_at_time(2.9, remapped) == 0.77


def test_remap_layout_timeline_total_matches_sum_encoded():
    span_timelines = [
        [LayoutSegment(0, 1000, "solo", "A")],
        [LayoutSegment(0, 800, "solo", "B")],
    ]
    encoded = [2800, 1500]
    remapped = remap_layout_timeline_to_output(encoded, span_timelines)
    remapped = fill_layout_timeline_gaps(remapped, sum(encoded))

    assert remapped[0].start_ms == 0
    assert remapped[-1].end_ms == sum(encoded)
