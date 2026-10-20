"""Light formatting.

`aisc_report_plugin_interface.richtext.render(text) -> Markup`: markdown-it-py (CommonMark + tables,
raw HTML off, breaks on, linkify off), then sanitised with nh3 against a fixed allowlist.
"""
import random
import re

import pytest

from v2_helpers import want

M = "aisc_report_plugin_interface.richtext"
ALLOWED_TAGS = {"p", "br", "strong", "em", "ul", "ol", "li", "a", "table", "thead", "tbody", "tr", "th", "td",
                "code", "blockquote"}


def rt(text: str) -> str:
    out = want(M, "render")(text)
    assert hasattr(out, "__html__"), "render must return Markup"
    return str(out)


def tags(html: str) -> set[str]:
    return {t.lower() for t in re.findall(r"<\s*/?\s*([a-zA-Z0-9]+)", html)}


def test_richtext_render_returns_markup():
    assert hasattr(want(M, "render")("plain"), "__html__")


def test_richtext_bold():
    assert "<strong>bold</strong>" in rt("**bold**")


@pytest.mark.parametrize("src", ["*it*", "_it_"])
def test_richtext_italic(src):
    assert "<em>it</em>" in rt(src)


def test_richtext_bullet_list():
    html = rt("- a\n- b")
    assert "<ul>" in html and "<li>a</li>" in html and "<li>b</li>" in html


def test_richtext_numbered_list():
    html = rt("1. a\n2. b")
    assert "<ol>" in html and "<li>a</li>" in html


def test_richtext_pipe_table():
    html = rt("| h1 | h2 |\n|---|---|\n| a | b |")
    assert "<table>" in html and "<th>h1</th>" in html and "<td>b</td>" in html


def test_richtext_link_with_rel():
    html = rt("[x](https://e.org)")
    assert re.search(r'<a [^>]*href="https://e\.org"', html)
    assert 'rel="noopener noreferrer"' in html
    assert ">x</a>" in html


# mailto allowed, other schemes not
def test_mailto_link_is_allowed():
    assert 'href="mailto:a@e.org"' in rt("[mail](mailto:a@e.org)")


def test_ftp_link_is_not_a_link():
    assert "href" not in rt("[f](ftp://e.org/x)")


def test_code_and_blockquote_are_allowed():
    html = rt("> quoted `x`")
    assert "<blockquote>" in html and "<code>x</code>" in html


# raw HTML disabled, then escaped
def test_script_is_literal_text():
    html = rt("<script>alert(1)</script>")
    assert "<script" not in html.lower()
    assert "&lt;script&gt;" in html


def test_bold_tag_is_literal_text():
    html = rt("<b>x</b>")
    assert "<b>" not in html
    assert "&lt;b&gt;x&lt;/b&gt;" in html


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,<script>alert(1)</script>"])
def test_dangerous_link_gives_text_without_link(url):
    html = rt(f"[x]({url})")
    assert "<a" not in html and "href" not in html
    assert "x" in html
    assert "<script" not in html.lower()


def test_heading_becomes_a_paragraph():
    html = rt("# Heading")
    assert not re.search(r"<h[1-6]", html)
    assert re.search(r"<p>\s*Heading\s*</p>", html)


def test_image_gives_its_alt_text_only():
    html = rt("![alt](https://e.org/i.png)")
    assert "<img" not in html
    assert "alt" in html


def test_single_newline_is_a_line_break():
    html = rt("a\nb")
    assert re.search(r"a\s*<br\s*/?>\s*b", html)


def test_blank_line_starts_a_new_paragraph():
    assert rt("a\n\nb").count("<p>") == 2


# linkify off
def test_bare_urls_are_not_linked():
    assert "<a" not in rt("see https://e.org now")


# only allowlisted tags ever come out
def test_output_tags_are_within_the_allowlist():
    src = ("# h\n**b** *i* `c`\n\n> q\n\n- a\n1. b\n\n| a |\n|---|\n| b |\n\n<div onclick=x>y</div>\n"
           "<iframe src=//e.org></iframe>\n![i](https://e.org/i.png) [l](https://e.org)")
    assert tags(rt(src)) <= ALLOWED_TAGS


def test_no_attribute_but_href_and_rel():
    html = rt("[l](https://e.org \"title\")\n\n| a |\n|:-:|\n| b |")
    attrs = set(re.findall(r"\s([a-zA-Z-]+)=", html))
    assert attrs <= {"href", "rel"}, attrs


# never raises on any input
def test_fuzz_never_raises():
    render = want(M, "render")
    rnd = random.Random(20260924)
    pieces = ["**", "*", "_", "`", "[", "](", ")", "<", ">", "|", "---", "\n", "\n\n", "# ", "- ", "1. ", "![",
              "javascript:", "<script>", "&", "\\", "{", "}", "\x00", "�", "é"]
    for i in range(400):
        if i % 2:
            text = bytes(rnd.getrandbits(8) for _ in range(rnd.randint(0, 300))).decode("latin-1")
        else:
            text = "".join(rnd.choice(pieces) + "x" for _ in range(rnd.randint(0, 80)))
        out = str(render(text))
        assert tags(out) <= ALLOWED_TAGS


def test_deep_nesting_never_raises():
    render = want(M, "render")
    render(">" * 5000 + " x")
    render("- " * 2000 + "x")
    render("[" * 5000 + "x" + "]" * 5000)
    render("*" * 20000)
