"""Catalogue loader for plugins.

API of `aisc_report_plugin_interface.i18n` under test:
    load_catalogue(path) -> Catalogue(code, name, messages, decimal_separator, percent_format);
        a bad file or a `_meta.code` not matching ^[a-z]{2}(-[A-Z]{2})?$ raises ValueError
    package_catalogue(package, code) -> Catalogue | None   (the package's own i18n/{code}.json)
    translator(*catalogues) -> t(msgid, **params): the first catalogue having msgid wins, else msgid;
        placeholders filled; a missing parameter leaves {name}; never raises
(BlockContext.language / .t / .translate_for live in the renderer and are tested there.)
"""
import json

import pytest

from v2_helpers import want

M = "aisc_report_plugin_interface.i18n"


def write(tmp_path, code="en", messages=None, name="x.json", meta=None):
    p = tmp_path / name
    m = {"code": code, "name": "English", "decimal_separator": ",", "percent_format": "{value} %"}
    m.update(meta or {})
    p.write_text(json.dumps({"_meta": m, "messages": messages or {}}), encoding="utf-8")
    return p


def test_a_catalogue_file_loads(tmp_path):
    c = want(M, "load_catalogue")(write(tmp_path, messages={"Contents": "Table of contents"}))
    assert c.code == "en" and c.name == "English"
    assert c.messages == {"Contents": "Table of contents"}
    assert c.decimal_separator == "," and c.percent_format == "{value} %"


@pytest.mark.parametrize("code", ["english", "EN", "en_GB", "en-gb", ""])
def test_a_bad_language_code_is_refused(tmp_path, code):
    with pytest.raises(ValueError):
        want(M, "load_catalogue")(write(tmp_path, code=code))


def test_a_language_code_with_a_region_is_fine(tmp_path):
    assert want(M, "load_catalogue")(write(tmp_path, code="en-GB")).code == "en-GB"


def test_not_a_catalogue_is_refused(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text('{"hello": 1}')
    with pytest.raises(ValueError):
        want(M, "load_catalogue")(p)


def test_translation_then_placeholders(tmp_path):
    c = want(M, "load_catalogue")(write(tmp_path, messages={
        "Newer results exist for version {number}.": "Version {number} has newer results."}))
    t = want(M, "translator")(c)
    assert t("Newer results exist for version {number}.", number=3) == "Version 3 has newer results."


def test_unknown_msgid_is_the_english_text(tmp_path):
    t = want(M, "translator")(want(M, "load_catalogue")(write(tmp_path)))
    assert t("Page {page} of {pages}", page=1, pages=2) == "Page 1 of 2"


def test_missing_parameter_leaves_the_placeholder():
    t = want(M, "translator")()
    assert t("Version {number} of {name}", number=2) == "Version 2 of {name}"


def test_lone_braces_never_raise():
    t = want(M, "translator")()
    assert t("50 { % and }", x=1) == "50 { % and }"


# the package's own catalogue first, then the renderer's
def test_package_catalogue_is_found():
    c = want(M, "package_catalogue")("fake_i18n_pkg", "en")
    assert c is not None and c.messages["Only in the package"] == "Found in the package"


def test_package_first_then_renderer(tmp_path):
    pkg = want(M, "package_catalogue")("fake_i18n_pkg", "en")
    renderer = want(M, "load_catalogue")(write(tmp_path, messages={
        "Overall pass rate": "Overall pass rate (renderer)", "Contents": "Table of contents"}))
    t = want(M, "translator")(pkg, renderer)
    assert t("Overall pass rate") == "Overall pass rate (package)"
    assert t("Contents") == "Table of contents"


def test_no_catalogue_for_the_language_means_english():
    assert want(M, "package_catalogue")("fake_i18n_pkg", "de") is None
    t = want(M, "translator")()
    assert t("Overall pass rate") == "Overall pass rate"


def test_a_missing_catalogue_logs_nothing(caplog):
    with caplog.at_level("WARNING", logger=M):
        want(M, "package_catalogue")("fake_i18n_pkg", "de")
    assert caplog.records == []


def test_a_broken_package_catalogue_falls_back_to_english_with_a_warning(tmp_path, monkeypatch, caplog):
    (tmp_path / "broken_i18n_pkg" / "i18n").mkdir(parents=True)
    (tmp_path / "broken_i18n_pkg" / "__init__.py").write_text("")
    (tmp_path / "broken_i18n_pkg" / "i18n" / "en.json").write_text("{ not json", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    with caplog.at_level("WARNING", logger=M):
        assert want(M, "package_catalogue")("broken_i18n_pkg", "en") is None
    [record] = caplog.records
    assert record.levelname == "WARNING"
    assert "broken_i18n_pkg" in record.getMessage() and "not a catalogue" in record.getMessage()


def test_a_failing_translate_for_falls_back_to_the_report_translator_with_a_warning(caplog):
    class Ctx:
        def translate_for(self, package):
            raise RuntimeError("no catalogue store")

        def t(self, msgid, **params):
            return f"report: {msgid}"

    with caplog.at_level("WARNING", logger=M):
        t = want(M, "translator_for")(Ctx(), "some_plugin")
    assert t("Contents") == "report: Contents"
    [record] = caplog.records
    assert "some_plugin" in record.getMessage() and "no catalogue store" in record.getMessage()


# singular forms ("1 objective", not "1 objectives")
# The rule [0, 1] is sample data for the mechanism: a catalogue may name any counts that take the singular.

PLURAL = {"{count} of {total} objectives with evidence": "{count} objectives out of {total} have evidence",
          "{count} of {total} objectives with evidence|one": "{count} objective out of {total} has evidence",
          "Rate: {rate} across {groups} groups": "Rate {rate} over {groups} groups",
          "Rate: {rate} across {groups} groups|one": "Rate {rate} over {groups} group"}


def test_plural_the_singular_variant_is_used_for_the_counts_the_rule_names(tmp_path):
    c = want(M, "load_catalogue")(write(tmp_path, messages=PLURAL, meta={"plural_one": [0, 1]}))
    t = want(M, "translator")(c)
    msgid = "{count} of {total} objectives with evidence"
    assert t(msgid, count=1, total=4) == "1 objective out of 4 has evidence"
    assert t(msgid, count=0, total=4) == "0 objective out of 4 has evidence"
    assert t(msgid, count=2, total=4) == "2 objectives out of 4 have evidence"


def test_plural_the_first_whole_number_parameter_decides(tmp_path):
    """A text parameter (a formatted rate) is skipped; the count of groups decides."""
    c = want(M, "load_catalogue")(write(tmp_path, messages=PLURAL, meta={"plural_one": [0, 1]}))
    t = want(M, "translator")(c)
    assert t("Rate: {rate} across {groups} groups", rate="68.8%", groups=1) == "Rate 68.8% over 1 group"
    assert t("Rate: {rate} across {groups} groups", rate="68.8%", groups=3) == "Rate 68.8% over 3 groups"


def test_plural_default_rule_is_one_only(tmp_path):
    c = want(M, "load_catalogue")(write(tmp_path, code="en", messages={"{count} evaluations|one": "{count} evaluation"}))
    assert c.plural_one == (1,)
    t = want(M, "translator")(c)
    assert t("{count} evaluations", count=1) == "1 evaluation"
    assert t("{count} evaluations", count=0) == "0 evaluations"
    assert t("{count} evaluations", count=True) == "True evaluations"     # a flag is not a count


def test_plural_without_a_variant_the_text_is_unchanged(tmp_path):
    c = want(M, "load_catalogue")(write(tmp_path, messages={"{count} more": "{count} others"},
                                        meta={"plural_one": [0, 1]}))
    assert want(M, "translator")(c)("{count} more", count=1) == "1 others"
    assert want(M, "translator")()("{count} more", count=1) == "1 more"


def test_plural_the_variant_of_a_later_catalogue_serves_when_the_first_has_the_text_only(tmp_path):
    """The package catalogue comes first; a variant is taken from the catalogue that gave the text."""
    pkg = want(M, "load_catalogue")(write(tmp_path, name="p.json", messages={"{count} groups": "{count} sets"},
                                          meta={"plural_one": [0, 1]}))
    ren = want(M, "load_catalogue")(write(tmp_path, name="r.json", messages={"{count} groups": "{count} clusters",
                                                                            "{count} groups|one": "{count} cluster"},
                                          meta={"plural_one": [0, 1]}))
    assert want(M, "translator")(pkg, ren)("{count} groups", count=1) == "1 sets"


@pytest.mark.parametrize("bad", [["one"], "1", [-1], [True], {"a": 1}])
def test_plural_a_bad_rule_is_refused(tmp_path, bad):
    with pytest.raises(ValueError):
        want(M, "load_catalogue")(write(tmp_path, meta={"plural_one": bad}))


# numbers and percentages as a tool renderer prints them

class NumberCtx:
    def __init__(self, decimal_separator=".", percent_format="{value}%"):
        self.decimal_separator = decimal_separator
        self.percent_format = percent_format


@pytest.mark.parametrize("value, decimals, expected", [
    (0.5, None, "0,5"),
    (3, None, "3"),
    (2.0, 2, "2,00"),
    (1.236, 2, "1,24"),
    (None, None, "n/a"),
    ("abc", None, "abc"),
])
def test_format_number_uses_the_report_decimal_separator(value, decimals, expected):
    assert want(M, "format_number")(NumberCtx(decimal_separator=","), value, decimals) == expected


def test_format_number_without_a_separator_on_the_context_uses_a_point():
    assert want(M, "format_number")(object(), 0.25) == "0.25"


@pytest.mark.parametrize("share, decimals, expected", [
    (0.85, 1, "85 %"),
    (0.1234, 1, "12,3 %"),
    (0.125, 2, "12,5 %"),
    (1, 1, "100 %"),
    (-0.0001, 1, "0 %"),
    (None, 1, "n/a"),
])
def test_format_percent_uses_the_report_percent_format(share, decimals, expected):
    ctx = NumberCtx(decimal_separator=",", percent_format="{value} %")
    assert want(M, "format_percent")(ctx, share, decimals) == expected


def test_format_percent_without_formats_on_the_context_prints_value_and_percent_sign():
    assert want(M, "format_percent")(object(), 0.5) == "50%"


def test_translator_for_prefers_the_renderer_translate_for():
    class Ctx:
        def translate_for(self, package):
            return lambda msgid, **params: f"{package}: {msgid}"

        def t(self, msgid, **params):
            return f"report: {msgid}"

    assert want(M, "translator_for")(Ctx(), "some_plugin")("Contents") == "some_plugin: Contents"


def test_translator_for_without_translate_for_uses_the_report_translator():
    class Ctx:
        def t(self, msgid, **params):
            return f"report: {msgid}"

    assert want(M, "translator_for")(Ctx(), "some_plugin")("Contents") == "report: Contents"


def test_translator_for_without_any_translator_is_english():
    t = want(M, "translator_for")(object(), "some_plugin")
    assert t("{count} groups", count=2) == "2 groups"
