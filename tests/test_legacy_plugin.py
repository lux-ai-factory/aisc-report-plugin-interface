"""The legacy BaseReporterPlugin keeps its behaviour.

The report renderer's legacy adapter relies on this class unchanged.
"""
import pytest

from aisc_report_plugin_interface import BaseReporterPlugin


class Legacy(BaseReporterPlugin):
    def get_template_relative_path(self):
        return "templates/missing.html.j2"

    def build_template_context(self, **kwargs):
        return {"x": kwargs.get("x")}


def test_legacy_plugins_are_constructed_with_a_session_argument():
    p = Legacy(db_session=None)
    assert p.session is None


@pytest.mark.parametrize("path", ["", "/abs.html.j2", "../x.html.j2"])
def test_template_paths_are_still_validated(path):
    with pytest.raises(ValueError):
        BaseReporterPlugin._validate_relative_template_path(path)


def test_template_errors_are_still_swallowed_into_an_error_string():
    out = Legacy(None).generate_content(x=1)
    assert out.startswith("[ERROR]")


def test_a_swallowed_template_error_is_logged_with_its_traceback(caplog):
    with caplog.at_level("ERROR"):
        out = Legacy(None).generate_content(x=1)
    assert "Check logs for details" in out
    errors = [r for r in caplog.records if r.levelname == "ERROR"]
    assert len(errors) == 1
    assert "Legacy" in errors[0].getMessage()
    assert errors[0].exc_info is not None
    assert "missing.html.j2" in caplog.text
