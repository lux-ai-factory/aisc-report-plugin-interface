"""Contract additions of version 2. Everything is backwards compatible: a block or tool renderer of
contract 1 keeps working."""
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from v2_helpers import want

M = "aisc_report_plugin_interface"
B = "aisc_report_plugin_interface.blocks"
ROOT = Path(__file__).resolve().parents[1]


def old_block_class(**overrides):
    """A block type written against contract 1 (contract_version 1, no new attributes)."""
    Base = want(M, "BaseBlockRenderer")
    BlockResult = want(M, "BlockResult")
    attrs = dict(type_id="old_block", title="Old", contract_version=1,
                 options_schema={"type": "object", "properties": {"limit": {"type": "integer"}},
                                 "additionalProperties": False},
                 default_options={"limit": 3}, reads=("platform",),
                 load=lambda self, ctx, options: None,
                 render=lambda self, data, options, ctx: BlockResult(html="<p>x</p>", status="ok"))
    attrs.update(overrides)
    return type("OldBlock", (Base,), attrs)


def old_tool_class():
    """A tool renderer of contract 1: no contract_version, no headline/charts/chart_ids."""
    Base = want(M, "BaseToolRenderer")
    return type("OldTool", (Base,), {"tool_names": ("OLDTOOL",), "render": lambda self, run, ctx: "<p>old</p>"})


def run(**evaluation):
    ToolRun = want(M, "ToolRun")
    return ToolRun(evaluation={"pid": "e1", "status": "Done", **evaluation},
                   evaluation_plugin={"pid": "ep1", "name": "OldToolPlugin", "status": "Done"},
                   tool={"display_name": "Old tool", "name": "OldToolPlugin", "package_name": "aisc-plugin-old"},
                   components=[], observations=[],
                   measurements=[{"name": "m", "metric": "m", "score": 0.5, "unit": None, "uncertainty": 0.0,
                                  "dimensions": None, "description": "why", "error": None}],
                   artifacts=[{"name": "a.csv", "file_size": 10}])



def test_interface_version_is_2():
    assert want(M, "INTERFACE_VERSION") == 2


def test_new_dependencies_are_declared():
    deps = " ".join(tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]).lower()
    assert "markdown-it-py" in deps and "nh3" in deps


# commentary on every block

def test_common_properties_gain_commentary():
    props = want(B, "COMMON_PROPERTIES")
    assert "commentary" in props, "missing feature: COMMON_PROPERTIES.commentary"
    c = props["commentary"]
    assert c["type"] == "string" and c.get("minLength", 0) == 0 and c["maxLength"] == 10000
    assert props["commentary_position"]["enum"] == ["after", "before"]


def test_every_block_accepts_commentary_through_the_full_schema():
    cls = old_block_class()
    schema = cls.full_options_schema()
    assert "commentary" in schema["properties"] and "commentary_position" in schema["properties"]
    defaults = cls.full_default_options()
    assert defaults["commentary"] == "" and defaults["commentary_position"] == "after"
    assert cls.options_problems(defaults) == []


def test_commentary_limits_are_checked():
    cls = old_block_class()
    base = cls.full_default_options()
    assert "commentary" in base, "missing feature: commentary in full_default_options"
    assert cls.options_problems({**base, "commentary": "x" * 10001}) == \
        [{"pointer": "/commentary", "message": "must be at most 10000 characters"}]
    assert cls.options_problems({**base, "commentary_position": "middle"}) == \
        [{"pointer": "/commentary_position", "message": "must be one of after, before"}]



def test_new_instance_options_default_empty():
    Base = want(M, "BaseBlockRenderer")
    assert getattr(Base, "new_instance_options", None) == {}, "missing feature: BaseBlockRenderer.new_instance_options"
    cls = old_block_class(new_instance_options={"limit": 5})
    cls.validate_declaration()
    assert cls.new_instance_options == {"limit": 5}


def test_description_default_empty():
    Base = want(M, "BaseBlockRenderer")
    assert getattr(Base, "description", None) == "", "missing feature: BaseBlockRenderer.description"
    cls = old_block_class(description="Shows old things.")
    cls.validate_declaration()



def test_common_properties_carry_title_and_description():
    props = want(B, "COMMON_PROPERTIES")
    for name in ("title", "page_break_before", "commentary", "commentary_position"):
        assert name in props, f"missing feature: COMMON_PROPERTIES.{name}"
        assert isinstance(props[name].get("title"), str) and props[name]["title"].strip(), name
        assert isinstance(props[name].get("description"), str) and props[name]["description"].strip(), name


def test_common_enum_values_carry_labels():
    props = want(B, "COMMON_PROPERTIES")
    assert "commentary_position" in props, "missing feature: COMMON_PROPERTIES.commentary_position"
    labels = props["commentary_position"].get("x-aisc-enum-labels", {})
    assert labels == {"after": "After the section", "before": "Before the section"}


def test_title_page_break_and_commentary_position_are_more_options():
    props = want(B, "COMMON_PROPERTIES")
    for name in ("title", "page_break_before", "commentary_position"):
        assert props.get(name, {}).get("x-aisc-more") is True, name
    assert props.get("commentary", {"x-aisc-more": True}).get("x-aisc-more") is not True


def test_annotations_do_not_change_validation():
    cls = old_block_class()
    assert "commentary" in cls.full_options_schema()["properties"], "missing feature: commentary"
    assert cls.options_problems(cls.full_default_options()) == []
    assert cls.options_problems({**cls.full_default_options(), "title": "x" * 201})[0]["pointer"] == "/title"


# tool renderer additions

def test_tool_renderer_defaults():
    Base = want(M, "BaseToolRenderer")
    assert getattr(Base, "contract_version", None) == 1, "missing feature: BaseToolRenderer.contract_version"
    assert getattr(Base, "chart_ids", None) == {}, "missing feature: BaseToolRenderer.chart_ids"
    tool = old_tool_class()()
    assert tool.headline(run()) == []
    assert tool.charts(run()) == []
    assert tool.verdict(run()) is None


def test_a_renderer_may_declare_contract_2_and_charts():
    Base = want(M, "BaseToolRenderer")
    cls = type("NewTool", (Base,), {"tool_names": ("NEW",), "contract_version": 2,
                                    "chart_ids": {"c": "A chart"},
                                    "render": lambda self, r, ctx: "<p/>",
                                    "headline": lambda self, r: [{"label": "L", "value": "1"}]})
    assert cls().headline(run()) == [{"label": "L", "value": "1"}]
    assert cls().charts(run()) == [], "missing feature: BaseToolRenderer.charts"


# compatibility with contract 1

def test_tool_run_carries_the_new_keys_read_only():
    """ToolRun freezes any mapping, so the renderer's newer keys (evaluation name/number,
    measurement description/error) are accepted and read-only."""
    r = run(name="Evaluation 2: Old tool", number=2)
    assert r.evaluation["name"] == "Evaluation 2: Old tool" and r.evaluation["number"] == 2
    assert r.measurements[0]["description"] == "why" and r.measurements[0]["error"] is None
    with pytest.raises(TypeError):
        r.evaluation["name"] = "x"
    with pytest.raises(TypeError):
        r.measurements[0]["description"] = "x"


def test_a_contract_1_renderer_ignoring_tool_options_works():
    """A renderer that never reads ctx.tool_options renders."""
    ctx = SimpleNamespace(tool_options={"show_charts": False, "detail": "summary"}, language="fr")
    assert old_tool_class()().render(run(), ctx) == "<p>old</p>"


def test_an_old_block_declaration_still_validates():
    """A contract-1 block keeps loading."""
    cls = old_block_class()
    cls.validate_declaration()
    assert cls.full_default_options()["limit"] == 3


def test_an_old_tool_renderer_still_matches_and_renders():
    """A tool renderer without contract_version keeps working."""
    cls = old_tool_class()
    assert cls.matches({"display_name": "Old tool", "name": "OldToolPlugin", "package_name": "aisc-plugin-old"})
    assert cls().render(run(), None) == "<p>old</p>"


# headline values are formatted with the report's context

def test_base_headline_accepts_a_context():
    tool = old_tool_class()()
    assert tool.headline(run(), ctx=SimpleNamespace(language="fr")) == []


def test_headline_items_passes_the_context_to_a_renderer_that_takes_it():
    Base = want(M, "BaseToolRenderer")
    headline_items = want("aisc_report_plugin_interface.tools", "headline_items")
    seen = []

    def headline(self, r, ctx=None):
        seen.append(ctx)
        return [{"label": "L", "value": getattr(ctx, "language", "none")}]

    cls = type("NewTool", (Base,), {"tool_names": ("NEW",), "contract_version": 2,
                                    "render": lambda self, r, ctx: "<p/>", "headline": headline})
    c = SimpleNamespace(language="fr")
    assert headline_items(cls(), run(), c) == [{"label": "L", "value": "fr"}]
    assert seen == [c]


def test_headline_items_keeps_a_renderer_whose_headline_takes_only_the_run():
    """A contract-2 renderer whose headline() takes only the run is still called."""
    Base = want(M, "BaseToolRenderer")
    headline_items = want("aisc_report_plugin_interface.tools", "headline_items")
    cls = type("EarlyTool", (Base,), {"tool_names": ("EARLY",), "contract_version": 2,
                                      "render": lambda self, r, ctx: "<p/>",
                                      "headline": lambda self, r: [{"label": "L", "value": "1"}]})
    assert headline_items(cls(), run(), SimpleNamespace(language="fr")) == [{"label": "L", "value": "1"}]


def test_headline_items_accepts_keyword_catch_alls():
    Base = want(M, "BaseToolRenderer")
    headline_items = want("aisc_report_plugin_interface.tools", "headline_items")
    cls = type("KwTool", (Base,), {"tool_names": ("KW",), "contract_version": 2,
                                   "render": lambda self, r, ctx: "<p/>",
                                   "headline": lambda self, r, **kw: [{"label": "L", "value": str(kw.get("ctx"))}]})
    assert headline_items(cls(), run(), "C") == [{"label": "L", "value": "C"}]
