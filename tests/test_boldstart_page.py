"""Tests for boldstart/page.py: bold-start on one XHTML page, the skip rules, and taking it off again."""

import pytest

from boldstart.page import PageError, bold_page, rewrite_page, unbold_page

LIGHT = 0.30
BS = '<b class="kraken-bs">'  # our marker, as it appears in a written page


def page(body: str, head: str = "<title>A title</title>") -> bytes:
    """A small, valid XHTML page around `body`."""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n'
        f'<html xmlns="http://www.w3.org/1999/xhtml"><head>{head}</head><body>{body}</body></html>'
    ).encode("utf-8")


def body_of(xhtml: bytes) -> str:
    text = xhtml.decode("utf-8")
    return text[text.index("<body>") + len("<body>"):text.index("</body>")]


def bolded(body: str, strength: float = LIGHT) -> str:
    return body_of(bold_page(page(body), strength))


# --- Adding bold-start ---


def test_paragraph_text_gets_bold_start():
    assert bolded("<p>Hello world</p>") == f"<p>{BS}He</b>llo {BS}wo</b>rld</p>"


def test_text_around_and_inside_other_tags():
    # "Hello " is the p's text, "dear" is inside the i, " world" is the i's tail
    assert bolded("<p>Hello <i>dear</i> world</p>") == (
        f"<p>{BS}He</b>llo <i>{BS}de</b>ar</i> {BS}wo</b>rld</p>")


@pytest.mark.parametrize("tag", ["h1", "h3", "h6", "b", "strong", "code", "pre", "kbd", "samp"])
def test_skipped_elements_are_left_alone(tag):
    assert bolded(f"<div><{tag}>Leave me</{tag}> but bold me</div>") == (
        f"<div><{tag}>Leave me</{tag}> {BS}b</b>ut {BS}bo</b>ld {BS}m</b>e</div>")


def test_everything_inside_a_skipped_element_is_left_alone():
    assert bolded("<pre>Some <i>italic code</i></pre>") == "<pre>Some <i>italic code</i></pre>"


def test_the_head_is_never_touched():
    result = bold_page(page("<p>x</p>", head="<title>The Title</title>"), LIGHT).decode("utf-8")
    assert "<title>The Title</title>" in result


def test_pictures_and_maths_in_other_namespaces_are_left_alone():
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><text>Label here</text></svg>'
    assert bolded(f"<div>{svg}</div>") == f"<div>{svg}</div>"


def test_comments_are_left_alone_but_text_after_them_is_bolded():
    assert bolded("<p><!-- a note -->Hello</p>") == f"<p><!-- a note -->{BS}He</b>llo</p>"


def test_link_text_is_bolded_but_addresses_are_not():
    assert bolded('<p><a href="https://example.com">Chapter</a> see https://example.com</p>') == (
        f'<p><a href="https://example.com">{BS}Cha</b>pter</a> {BS}s</b>ee https://example.com</p>')


def test_non_breaking_spaces_and_accents_survive():
    assert bolded("<p>café naïve</p>") == f"<p>{BS}ca</b>fé {BS}na</b>ïve</p>"


def test_a_page_without_a_namespace_still_works():
    raw = b"<html><body><p>Hello</p></body></html>"
    assert f"<p>{BS}He</b>llo</p>" in bold_page(raw, LIGHT).decode("utf-8")


def test_the_doctype_is_kept():
    assert b"<!DOCTYPE html PUBLIC" in bold_page(page("<p>Hello</p>"), LIGHT)


# --- No double-bolding, and taking it off ---


def test_bolding_twice_is_the_same_as_bolding_once():
    once = bold_page(page("<p>Hello <i>dear</i> world</p>"), LIGHT)
    assert bold_page(once, LIGHT) == once


def test_bolding_again_at_a_new_strength_replaces_the_old_bold_start():
    once = bold_page(page("<p>Wonderland</p>"), LIGHT)
    assert body_of(bold_page(once, 0.6)) == f"<p>{BS}Wonder</b>land</p>"


def test_unbold_removes_only_our_marker():
    theirs = '<p><b>Their bold</b> <b class="other">styled</b> <b class="kraken-bs" id="x">not ours</b></p>'
    original = page(theirs)
    assert unbold_page(original) == rewrite_page(original)


# --- The promise (D7): bold, then unbold, gives back the page ---


@pytest.mark.parametrize("body", [
    "<p>Hello <i>dear</i> world</p>",
    "<p>‘and what is the use of a book,’ thought Alice ‘without pictures?’</p>",
    "<div><h2>Chapter I</h2><p>Down the <b>Rabbit</b>-Hole, 1865.</p><!-- note --><pre>keep  this</pre></div>",
    "<ul><li>one</li><li>two <a href='x.html'>links</a></li></ul><p>me@example.org and éte</p>",
    "<p></p><p>   </p><p>Tail<br/>after a line break</p>",
])
def test_bold_then_unbold_gives_back_the_page(body):
    original = page(body)
    assert unbold_page(bold_page(original, LIGHT)) == rewrite_page(original)


@pytest.mark.parametrize("body", ["<p>Hello <i>dear</i> world</p>", "<p>one two <b>x</b> three</p><p>four</p>"])
def test_each_word_is_bolded_once(body):
    # Two markers side by side would mean the rest of a word was bolded a second time.
    assert "</b>" + BS not in bolded(body)


# --- Pages kraken can't read ---


@pytest.mark.parametrize("broken", [b"<html><body><p>not closed</body></html>", b"", b"plain text"])
def test_a_broken_page_is_reported(broken):
    with pytest.raises(PageError, match="not valid XHTML"):
        bold_page(broken, LIGHT)


def test_a_booby_trapped_page_cannot_reach_files_on_the_computer(tmp_path):
    # An "external entity": an old XML trick for pulling a file from the computer into the page.
    secret = tmp_path / "secret.txt"
    secret.write_text("TOPSECRET")
    trap = (f'<?xml version="1.0"?><!DOCTYPE html [<!ENTITY secret SYSTEM "file://{secret}">]>'
            '<html><body><p>&secret;</p></body></html>').encode()
    try:
        result = bold_page(trap, LIGHT)
    except PageError:
        return  # refusing the page is fine too
    assert b"TOPSECRET" not in result and b"TOP" not in result
