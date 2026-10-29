"""The interface offers block and tool renderers only.

The template-and-session reporter class is gone, and with it the database dependency: a report
plugin receives its data from the renderer, never a database session.
"""
import importlib.util
import tomllib
from pathlib import Path

import pytest

import aisc_report_plugin_interface

ROOT = Path(__file__).resolve().parents[1]


def test_the_session_based_reporter_class_is_not_exported():
    assert "BaseReporterPlugin" not in aisc_report_plugin_interface.__all__
    with pytest.raises(AttributeError):
        aisc_report_plugin_interface.BaseReporterPlugin  # noqa: B018


def test_the_session_based_reporter_module_is_gone():
    assert importlib.util.find_spec("aisc_report_plugin_interface.base_report_plugin") is None


def test_the_package_does_not_depend_on_a_database_library():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert not [d for d in project["dependencies"] if d.lower().startswith("sqlalchemy")]


def test_no_source_file_mentions_a_shared_session_or_render_template():
    for path in (ROOT / "aisc_report_plugin_interface").rglob("*.py"):
        text = path.read_text()
        assert "shared_session" not in text, path
        assert "def render_template" not in text, path
        assert "BaseReporterPlugin" not in text, path
