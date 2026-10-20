"""A run's target: what the run assessed, the AI system or one
component of its AI card. `ToolRun.target` is optional: None for runs made before targets, and every
constructor written before it keeps working."""
import dataclasses
import tomllib
from pathlib import Path

import pytest

from conftest import need

M = "aisc_report_plugin_interface"
ROOT = Path(__file__).resolve().parents[1]

COMPONENT = {"key": "component:5b0c3a52-0000-4000-8000-000000000001", "kind": "component",
             "component_kind": "model", "label": "Scoring model", "card_version": 2, "status": "current"}


def _fields(**extra):
    return dict(
        evaluation={"pid": "e1", "status": "Done"},
        evaluation_plugin={"pid": "ep1", "name": "OldToolPlugin", "status": "Done"},
        tool={"display_name": "Old tool", "name": "OldToolPlugin", "package_name": "aisc-plugin-old"},
        components=[{"name": "Scoring model", "component_type": "resource"}],
        observations=[], measurements=[], artifacts=[], **extra)


def test_a_run_made_before_targets_has_none():
    run = need(M, "ToolRun")(**_fields())
    assert run.target is None


def test_positional_construction_of_the_seven_old_fields_still_works():
    ToolRun = need(M, "ToolRun")
    f = _fields()
    run = ToolRun(f["evaluation"], f["evaluation_plugin"], f["tool"], f["components"], f["observations"],
                  f["measurements"], f["artifacts"])
    assert run.target is None and run.tool["display_name"] == "Old tool"


def test_a_run_carries_its_target_read_only():
    run = need(M, "ToolRun")(**_fields(target=COMPONENT))
    assert run.target["label"] == "Scoring model" and run.target["kind"] == "component"
    assert run.target["component_kind"] == "model" and run.target["card_version"] == 2
    assert run.target["status"] == "current"
    with pytest.raises(TypeError):
        run.target["label"] = "x"
    with pytest.raises(dataclasses.FrozenInstanceError):
        run.target = None


def test_a_system_target():
    run = need(M, "ToolRun")(**_fields(target={"key": "system", "kind": "system", "component_kind": None,
                                               "label": "Example Assistant", "card_version": 1, "status": "current"}))
    assert run.target["kind"] == "system" and run.target["component_kind"] is None


@pytest.mark.parametrize("target", [None, COMPONENT])
def test_the_target_round_trips(target):
    ToolRun = need(M, "ToolRun")
    run = ToolRun(**_fields(target=target))
    again = ToolRun(**{f.name: getattr(run, f.name) for f in dataclasses.fields(ToolRun)})
    assert again == run and again.target == run.target
    assert dataclasses.replace(run) == run
    if target is not None:
        assert dict(run.target) == target


def test_the_package_version_says_the_contract_grew():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert tuple(int(x) for x in version.split(".")) >= (0, 2, 0)
