"""The tool-renderer contract inside Test results.

Module `aisc_report_plugin_interface`: BaseToolRenderer, ToolRun, normalise_tool_name, tool_keys.
"""
import dataclasses
import inspect

import pytest

from conftest import need

M = "aisc_report_plugin_interface"

MLA = {"display_name": "MLA-Reject", "name": "MLARejectEvaluationPlugin", "package_name": "aisc-plugin-mlareject"}
LANGBITE = {"display_name": "LangBiTe", "name": "LangBiTeEvaluationPlugin", "package_name": "aisc-plugin-langbite"}


@pytest.mark.parametrize(
    "raw,expected",
    [("MLA-Reject", "MLAREJECT"), ("mla_reject", "MLAREJECT"), ("MLA Reject", "MLAREJECT"), ("LangBiTe", "LANGBITE")],
)
def test_tool_names_are_normalised(raw, expected):
    """Uppercase, spaces, dashes and underscores removed."""
    assert need(M, "normalise_tool_name")(raw) == expected


def test_an_engine_plugin_is_known_by_four_keys():
    """display_name, name, name without a trailing EvaluationPlugin/Plugin, package_name
    without the aisc-plugin- prefix, all normalised."""
    keys = need(M, "tool_keys")(**MLA)
    assert keys == {"MLAREJECT", "MLAREJECTEVALUATIONPLUGIN"}
    keys = need(M, "tool_keys")(display_name="Garak", name="GarakPlugin", package_name="aisc-plugin-garak-probe")
    assert keys == {"GARAK", "GARAKPLUGIN", "GARAKPROBE"}


def _tool_class(names=("MLAREJECT",), **extra):
    Base = need(M, "BaseToolRenderer")
    attrs = {"tool_names": names, "render": lambda self, run, ctx: "<p>tool</p>"}
    attrs.update(extra)
    return type("DemoTool", (Base,), attrs)


def test_a_renderer_matches_on_any_key():
    cls = _tool_class(("mla-reject",))
    assert cls.matches(MLA)
    assert not cls.matches(LANGBITE)
    assert _tool_class(("MLARejectEvaluationPlugin",)).matches(MLA)


def test_render_is_abstract_and_verdict_optional():
    Base = need(M, "BaseToolRenderer")
    assert inspect.isabstract(Base)
    with pytest.raises(TypeError):
        type("NoRender", (Base,), {"tool_names": ("X",)})()
    assert list(inspect.signature(Base.render).parameters) == ["self", "run", "ctx"]
    assert _tool_class()().verdict(run=None) is None


def test_verdict_may_say_pass_or_fail():
    cls = _tool_class(verdict=lambda self, run: "fail")
    assert cls().verdict(None) == "fail"


def _run():
    ToolRun = need(M, "ToolRun")
    return ToolRun(
        evaluation={"pid": "e1", "status": "Done", "created_at": "2026-09-10T09:00:00+00:00"},
        evaluation_plugin={"pid": "ep1", "name": "MLARejectEvaluationPlugin", "status": "Done"},
        tool={"display_name": "MLA-Reject", "name": "MLARejectEvaluationPlugin", "package_name": "aisc-plugin-mlareject", "version": "1.0"},
        components=[{"name": "Scoring model endpoint", "component_type": "model"}],
        observations=[{"id": 1, "tool": "aisc-plugin-mlareject::MLARejectEvaluationPlugin (v1.0)"}],
        measurements=[{"name": "score", "metric": "score", "score": 4.0, "unit": None, "uncertainty": 0.0,
                       "dimensions": {"language": "en"}}],
        artifacts=[{"name": "report.csv", "file_size": 10}],
    )


def test_a_run_holds_what_the_renderer_needs():
    run = _run()
    assert run.evaluation["pid"] == "e1"
    assert run.tool["display_name"] == "MLA-Reject"
    assert run.components[0]["name"] == "Scoring model endpoint"
    assert run.measurements[0]["metric"] == "score"
    assert run.measurements[0]["dimensions"]["language"] == "en"
    assert run.artifacts[0] == {"name": "report.csv", "file_size": 10}


def test_a_run_is_read_only():
    run = _run()
    with pytest.raises(dataclasses.FrozenInstanceError):
        run.measurements = ()
    with pytest.raises(TypeError):
        run.measurements[0]["score"] = 0.0
    with pytest.raises((TypeError, AttributeError)):
        run.measurements.append({})
    with pytest.raises(TypeError):
        run.measurements[0]["dimensions"]["language"] = "fr"


def test_a_run_has_no_database_session():
    """Tool renderers get no database session."""
    run = _run()
    names = {f.name for f in dataclasses.fields(run)}
    assert not names & {"session", "db_session", "connection", "engine"}
