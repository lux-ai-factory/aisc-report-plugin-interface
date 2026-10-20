"""The block-renderer contract.

Module `aisc_report_plugin_interface`: BaseBlockRenderer, BlockResult, InvalidBlockType, SOURCES.
"""
import inspect

import pytest

from conftest import need

M = "aisc_report_plugin_interface"


def _block_class(**overrides):
    Base = need(M, "BaseBlockRenderer")
    BlockResult = need(M, "BlockResult")
    attrs = dict(
        type_id="demo_block",
        title="Demo",
        contract_version=1,
        options_schema={
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 10}},
            "additionalProperties": False,
        },
        default_options={"limit": 3},
        reads=("platform",),
        load=lambda self, ctx, options: {"n": options["limit"]},
        render=lambda self, data, options, ctx: BlockResult(html="<p>x</p>", status="ok", notices=[]),
    )
    attrs.update(overrides)
    return type("DemoBlock", (Base,), attrs)


def test_a_block_type_declares_its_contract():
    """type_id, title, contract_version, options_schema, default_options, reads."""
    cls = _block_class()
    cls.validate_declaration()  # a correct declaration passes
    for attr in ("type_id", "title", "contract_version", "options_schema", "default_options", "reads"):
        assert hasattr(cls, attr), attr


@pytest.mark.parametrize(
    "overrides",
    [
        {"type_id": "Not A Slug"},
        {"type_id": ""},
        {"contract_version": 0},
        {"contract_version": "1"},
        {"options_schema": {"type": "no-such-type"}},
        {"default_options": {"limit": 99}},
        {"reads": ("catalogue",)},
    ],
    ids=["slug-spaces", "slug-empty", "version-0", "version-str", "bad-schema", "defaults-invalid", "unknown-source"],
)
def test_a_bad_declaration_is_refused(overrides):
    """Lowercase slug, integer contract version from 1, a valid draft 2020-12 schema,
    defaults valid against it, reads from the known sources only (never the catalogue)."""
    InvalidBlockType = need(M, "InvalidBlockType")
    with pytest.raises(InvalidBlockType):
        _block_class(**overrides).validate_declaration()


def test_sources_are_the_six_data_sources_without_the_catalogue():
    SOURCES = need(M, "SOURCES")
    assert set(SOURCES) == {"platform", "qualification", "control_objectives", "engine", "controls", "superset"}
    assert "catalogue" not in SOURCES


def test_load_and_render_are_abstract():
    """Load(ctx, options) and render(data, options, ctx) must be implemented."""
    Base = need(M, "BaseBlockRenderer")
    assert inspect.isabstract(Base)
    incomplete = type("Incomplete", (Base,), {"type_id": "x", "title": "X", "contract_version": 1,
                                              "options_schema": {"type": "object"}, "default_options": {},
                                              "reads": ()})
    with pytest.raises(TypeError):
        incomplete()
    assert list(inspect.signature(Base.load).parameters) == ["self", "ctx", "options"]
    assert list(inspect.signature(Base.render).parameters) == ["self", "data", "options", "ctx"]


def test_choices_is_optional_and_empty_by_default():
    cls = _block_class()
    assert cls().choices(ctx=None, option_name="limit") == []


def test_block_result_carries_html_status_and_notices():
    BlockResult = need(M, "BlockResult")
    r = BlockResult(html="<p>ok</p>", status="stale", notices=["Newer results exist for version 3."])
    assert (r.html, r.status, r.notices) == ("<p>ok</p>", "stale", ["Newer results exist for version 3."])
    assert BlockResult(html="", status="empty").notices == []


@pytest.mark.parametrize("status", ["ok", "empty", "stale", "error"])
def test_the_four_statuses_are_accepted(status):
    need(M, "BlockResult")(html="", status=status)


def test_any_other_status_is_refused():
    BlockResult = need(M, "BlockResult")
    with pytest.raises(ValueError):
        BlockResult(html="", status="done")


@pytest.mark.parametrize("html", ["<html><p>x</p></html>", "<body>x</body>", "<!DOCTYPE html><p>x</p>"])
def test_the_html_is_a_fragment(html):
    """A fragment, no <html>/<body>."""
    BlockResult = need(M, "BlockResult")
    with pytest.raises(ValueError):
        BlockResult(html=html, status="ok")


def test_every_block_accepts_title_and_page_break_before():
    cls = _block_class()
    schema = cls.full_options_schema()
    props = schema["properties"]
    assert props["title"]["type"] == "string" and props["title"]["maxLength"] == 200
    assert props["title"].get("minLength", 0) == 0
    assert props["page_break_before"]["type"] == "boolean"
    assert "limit" in props  # its own options stay
    assert cls.full_default_options() == {"title": "", "page_break_before": False, "commentary": "",
                                         "commentary_position": "after", "limit": 3}


def test_the_common_options_validate():
    cls = _block_class()
    assert cls.options_problems({"title": "", "page_break_before": True, "limit": 2}) == []
    problems = cls.options_problems({"title": "x" * 201, "page_break_before": False, "limit": 2})
    assert [p["pointer"] for p in problems] == ["/title"]


def test_option_problems_name_the_field_and_the_reason():
    """The renderer prints "Invalid options: {field}: {reason}" from these."""
    cls = _block_class()
    problems = cls.options_problems({"title": "", "page_break_before": False, "limit": 99})
    assert len(problems) == 1
    assert problems[0]["pointer"] == "/limit"
    assert problems[0]["message"]  # a reason, in words


def test_block_templates_are_autoescaped_even_as_html_j2():
    """Autoescape is on. The legacy machinery keys autoescape on the .html extension, so a
    `.html.j2` template (every template in these repos) would not be escaped there: here it must be."""
    render_package_template = need(f"{M}.templating", "render_package_template")
    out = render_package_template("fake_block_pkg", "templates/block.html.j2", value="<script>alert(1)</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out


def test_a_block_renders_its_own_package_templates():
    """BaseBlockRenderer.render_package_template renders from the plugin's own package."""
    need(M, "BaseBlockRenderer")
    import fake_block_pkg

    cls = _block_class()
    cls.__module__ = fake_block_pkg.__name__ + ".blocks"
    out = cls().render_package_template("templates/block.html.j2", value="<b>")
    assert out.strip() == '<p class="v">&lt;b&gt;</p>'


@pytest.mark.parametrize("path", ["", "/etc/passwd", "../secrets.html.j2", "templates/../../x.html.j2"])
def test_template_paths_are_relative_and_stay_inside(path):
    render_package_template = need(f"{M}.templating", "render_package_template")
    with pytest.raises(ValueError):
        render_package_template("fake_block_pkg", path, value="x")


def test_a_one_file_plugin_renders_the_templates_beside_it(tmp_path):
    """A one-file plugin loaded from REPORT_PLUGIN_PATH ('report_plugin_0_myblock') is no package, so
    its templates cannot be found from the module's dotted name ('package ... cannot be found'). The
    template folder is the folder the module's file is in."""
    import importlib.util
    import sys

    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "x.html.j2").write_text("<i>{{ value }}</i>")
    (tmp_path / "myblock.py").write_text("X = 1\n")
    spec = importlib.util.spec_from_file_location("report_plugin_0_myblock", tmp_path / "myblock.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    try:
        cls = _block_class()
        cls.__module__ = spec.name
        assert cls().render_package_template("templates/x.html.j2", value="<b>").strip() == "<i>&lt;b&gt;</i>"
    finally:
        sys.modules.pop(spec.name, None)


def test_a_class_in_a_package_itself_renders_that_packages_templates():
    """A class in pkg/__init__.py looked in pkg's parent for its templates."""
    import fake_block_pkg

    cls = _block_class()
    cls.__module__ = fake_block_pkg.__name__
    out = cls().render_package_template("templates/block.html.j2", value="<b>")
    assert out.strip() == '<p class="v">&lt;b&gt;</p>'
