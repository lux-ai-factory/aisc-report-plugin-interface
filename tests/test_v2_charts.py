"""Charts drawn by the renderer.

`aisc_report_plugin_interface.charts.svg(spec, colours) -> Markup`, a pure function.
"""
import re

import pytest

from v2_helpers import want

M = "aisc_report_plugin_interface.charts"
COLOURS = {"primary": "#000fdf", "text": "#000000", "grid": "#cccccc"}


def spec(**over):
    s = {"id": "demo", "title": "Pass rate by concern", "kind": "hbar", "value_format": "percent",
         "axis_min": 0, "axis_max": 1,
         "series": [{"label": "ageism", "value": 0.75}, {"label": "gender", "value": 0.25},
                    {"label": "religion", "value": 0.5}]}
    s.update(over)
    return s


def svg(s, colours=COLOURS) -> str:
    out = want(M, "svg")(s, colours)
    assert hasattr(out, "__html__"), "svg must return Markup"
    return str(out)


def bars(html: str, colour=COLOURS["primary"]) -> int:
    return len(re.findall(rf'fill="{colour}"', html, flags=re.I))


def test_the_same_chart_spec_gives_the_same_bytes():
    assert svg(spec()) == svg(spec())


def test_drawing_a_chart_does_no_io(monkeypatch):
    import builtins
    import socket

    def boom(*a, **k):
        raise AssertionError("charts.svg did I/O")

    want(M, "svg")  # import before blocking
    monkeypatch.setattr(builtins, "open", boom)
    monkeypatch.setattr(socket, "socket", boom)
    svg(spec())


# bars use the primary colour only, never a red/amber/green scale
def test_bars_use_primary_only():
    html = svg(spec(kind="bar"))
    assert bars(html) == 3
    for bad in ("red", "green", "orange", "amber", "#ff0000", "#00ff00", "#ffa500", "#f00", "#0f0"):
        assert not re.search(rf'(fill|stroke)="{bad}"', html, flags=re.I), bad


def test_other_colours_follow_the_argument():
    html = svg(spec(), {"primary": "#123456", "text": "#222222", "grid": "#dddddd"})
    assert bars(html, "#123456") == 3
    assert "#000fdf" not in html.lower()


def test_percent_values_print_as_0_to_100():
    html = svg(spec())
    assert re.search(r"75(\.0+)?\s?%", html)
    assert re.search(r"100(\.0+)?\s?%", html)       # axis tick at axis_max 1


def test_number_format_prints_plain_numbers():
    html = svg(spec(value_format="number", axis_max=None,
                    series=[{"label": "a", "value": 3}, {"label": "b", "value": 7.5}]))
    assert "7.5" in html and "%" not in re.sub(r"<title>.*?</title>", "", html)


def test_null_value_draws_no_bar_and_says_n_a():
    html = svg(spec(kind="bar", series=[{"label": "a", "value": 0.5}, {"label": "b", "value": None}]))
    assert bars(html) == 1
    assert "n/a" in html


def test_a_chart_note_is_optional():
    svg(spec(note="Estimated."))
    s = spec()
    s.pop("axis_min")
    s["axis_max"] = None
    svg(s)


def test_accessible_svg_with_title():
    html = svg(spec())
    root = re.search(r"<svg[^>]*>", html).group(0)
    assert 'role="img"' in root
    assert 'aria-label="Pass rate by concern"' in root
    assert "<title>Pass rate by concern</title>" in html


def test_explicit_size_at_most_160mm():
    root = re.search(r"<svg[^>]*>", svg(spec())).group(0)
    w = re.search(r'\swidth="([\d.]+)(mm|px)?"', root)
    h = re.search(r'\sheight="([\d.]+)(mm|px)?"', root)
    assert w and h, root
    width_mm = float(w.group(1)) if w.group(2) == "mm" else float(w.group(1)) * 25.4 / 96
    assert width_mm <= 160.0001


def test_value_labels_at_the_bars():
    html = svg(spec())
    for v in ("75", "25", "50"):
        assert re.search(rf">\s*{v}(\.0+)?\s?%\s*<", html), v


def test_chart_labels_are_escaped():
    html = svg(spec(title='<b>"t"</b>', series=[{"label": "<script>x</script>", "value": 0.1}]))
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "<b>" not in html


def test_long_labels_are_cut_to_39_plus_dots():
    long = "A" * 30 + "B" * 20
    html = svg(spec(series=[{"label": long, "value": 0.1}]))
    assert long not in html
    assert long[:39] + "..." in html


@pytest.mark.parametrize("bad", [
    {"kind": "pie"},
    {"series": [{"label": "a", "value": "abc"}]},
    {"series": [{"label": str(i), "value": 0.1} for i in range(61)]},
])
def test_invalid_chart_specs_raise_value_error(bad):
    with pytest.raises(ValueError):
        svg(spec(**bad))


def test_a_chart_with_sixty_items_is_fine():
    svg(spec(series=[{"label": str(i), "value": 0.1} for i in range(60)]))


@pytest.mark.parametrize("kind", ["hbar", "bar"])
def test_negative_values_draw_bars_on_an_axis_that_reaches_them(kind):
    """Negative values must not draw as empty bars that still print their value, which is what a
    ratio() clamped to [0, 1] on an axis starting at 0 would give. Without axis_min the axis starts
    below the lowest value, and a bar goes from zero to its value."""
    s = spec(kind=kind, value_format="number", series=[{"label": "a", "value": -0.4}, {"label": "b", "value": -0.1}])
    del s["axis_min"], s["axis_max"]
    html = svg(s)
    rects = re.findall(r'<rect x="[^"]+" y="[^"]+" width="([0-9.]+)" height="([0-9.]+)"', html)
    extent = [float(w) if kind == "hbar" else float(h) for w, h in rects]
    assert len(extent) == 2 and all(e > 0 for e in extent), extent
    assert extent[0] > extent[1]                                   # -0.4 is the longer bar
    assert re.search(r">-0\.\d", html)                              # the axis shows negative ticks
