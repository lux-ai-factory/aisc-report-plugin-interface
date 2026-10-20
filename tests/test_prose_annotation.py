"""The schema annotation `x-aisc-prose`.

`x-aisc-prose: true` marks a string option as prose written for one project, `false` as a name, id or other
identifier. It does not change validation. The common option `commentary` carries `x-aisc-prose: true`.
"""
from v2_helpers import want

M = "aisc_report_plugin_interface"
B = "aisc_report_plugin_interface.blocks"


def block_class(options_schema, default_options):
    Base = want(M, "BaseBlockRenderer")
    BlockResult = want(M, "BlockResult")
    return type("ProseBlock", (Base,), dict(
        type_id="prose_block", title="Prose", contract_version=2, options_schema=options_schema,
        default_options=default_options, reads=("platform",),
        load=lambda self, ctx, options: None,
        render=lambda self, data, options, ctx: BlockResult(html="<p>x</p>", status="ok")))


def test_commentary_is_marked_as_prose():
    props = want(B, "COMMON_PROPERTIES")
    assert props["commentary"].get("x-aisc-prose") is True, "missing feature: x-aisc-prose on commentary"


def test_other_common_options_are_not_marked_as_prose():
    props = want(B, "COMMON_PROPERTIES")
    for name in ("title", "page_break_before", "commentary_position"):
        assert props[name].get("x-aisc-prose") is not True


def test_the_annotation_does_not_change_validation():
    schema = {"type": "object", "additionalProperties": False, "properties": {
        "note": {"type": "string", "x-aisc-prose": True},
        "code": {"type": ["string", "null"], "x-aisc-prose": False},
    }}
    cls = block_class(schema, {"note": "", "code": None})
    cls.validate_declaration()
    base = cls.full_default_options()
    assert cls.options_problems({**base, "note": "x" * 50000, "code": "ab-12"}) == []
    assert cls.options_problems({**base, "note": 3}) == [{"pointer": "/note", "message": "must be of type string"}]
