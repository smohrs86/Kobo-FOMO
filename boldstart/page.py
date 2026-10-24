"""Bold-start for one book page (DESIGN.md section 5).

A book page is XHTML: a web page written as strict XML. lxml reads it into a tree, where each tag
is an element. Text lives in two places on an element:
    .text  the text just inside it, before its first child
    .tail  the text just after it closes, which belongs to the element around it
So in <p>Hello <i>dear</i> world</p>, "Hello " is p.text, "dear" is i.text, and " world" is i.tail.
The engine visits every .text and .tail it's allowed to change, and wraps the start of each word in
our marker, <b class="kraken-bs"> (D7). Removing those markers gives back the page it started from.
"""

from lxml import etree

from boldstart.text import split_for_bold

XHTML = "http://www.w3.org/1999/xhtml"
BOLD_CLASS = "kraken-bs"

# Elements whose text is left alone, with everything inside them (DESIGN.md section 5).
# Headings and bold are already bold; code must stay exactly as written; ruby text (rt) is the
# tiny pronunciation guide above some Asian scripts; the rest isn't text you read.
SKIPPED = {"h1", "h2", "h3", "h4", "h5", "h6", "b", "strong", "code", "pre", "kbd", "samp", "rt",
           "script", "style", "head", "title"}

# A book is someone else's file, so it's read cautiously: no fetching anything from the internet,
# and no expanding "entities" (shortcuts that a booby-trapped file can use to grow enormous).
PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, remove_blank_text=False)


class PageError(Exception):
    """The page can't be read as XHTML. The message says why."""


def bold_page(xhtml: bytes, strength: float) -> bytes:
    """Return the page with bold-start added. Any bold-start already there is removed first (no double-bolding)."""
    tree = _read(xhtml)
    _remove_markers(tree.getroot())
    body = tree.getroot().find(f"{{{XHTML}}}body")
    if body is None:
        body = tree.getroot().find("body")  # a page that forgot its namespace
    if body is not None:
        _bold_element(body, strength)
    return _write(tree)


def unbold_page(xhtml: bytes) -> bytes:
    """Return the page with every bold-start marker removed, and nothing else changed (D7)."""
    tree = _read(xhtml)
    _remove_markers(tree.getroot())
    return _write(tree)


def rewrite_page(xhtml: bytes) -> bytes:
    """Read the page and write it straight back. Used by the tests: this is what "unchanged" looks like
    once lxml has written a page, since it may tidy small things like quote marks around attributes."""
    return _write(_read(xhtml))


# --- Reading and writing ---


def _read(xhtml: bytes) -> etree._ElementTree:
    try:
        return etree.ElementTree(etree.fromstring(xhtml, PARSER))
    except etree.XMLSyntaxError as error:
        raise PageError(f"not valid XHTML ({error})") from error


def _write(tree: etree._ElementTree) -> bytes:
    """Write the page back as UTF-8, keeping its DOCTYPE line."""
    return etree.tostring(tree, xml_declaration=True, encoding="utf-8", doctype=tree.docinfo.doctype or None)


# --- Adding bold-start ---


def _bold_element(element: etree._Element, strength: float) -> None:
    """Add bold-start to this element's text, then to its children's, skipping SKIPPED elements."""
    if _is_skipped(element):
        return
    # The children as they were before any markers are added. Taken first, so the markers added
    # below are never visited themselves: their tails would be bolded a second time.
    children = list(element)
    if element.text:
        lead, markers = _bolded(element.text, strength, element)
        element.text = lead
        for offset, marker in enumerate(markers):
            element.insert(offset, marker)

    for child in children:
        if isinstance(child.tag, str):  # an element, not a comment or processing instruction
            _bold_element(child, strength)
        if child.tail:
            lead, markers = _bolded(child.tail, strength, element)
            child.tail = lead
            position = element.index(child)
            for offset, marker in enumerate(markers, start=1):
                element.insert(position + offset, marker)


def _is_skipped(element: etree._Element) -> bool:
    """Skip SKIPPED elements, and anything that isn't XHTML (pictures drawn as SVG, maths as MathML)."""
    name = etree.QName(element)
    return name.namespace not in (XHTML, None) or name.localname in SKIPPED


def _bolded(text: str, strength: float, parent: etree._Element) -> tuple[str, list[etree._Element]]:
    """Split text into the plain text before the first word, plus a marker for each word's start.

    Each marker holds the bold letters as its .text, and the plain text after them as its .tail.
    """
    lead = ""
    markers: list[etree._Element] = []
    for piece, bold in split_for_bold(text, strength):
        if bold:
            marker = etree.Element(_same_namespace(parent, "b"), {"class": BOLD_CLASS})
            marker.text = piece
            markers.append(marker)
        elif markers:
            markers[-1].tail = piece
        else:
            lead = piece
    return lead, markers


def _same_namespace(element: etree._Element, localname: str) -> str:
    namespace = etree.QName(element).namespace
    return f"{{{namespace}}}{localname}" if namespace else localname


# --- Removing bold-start ---


def _is_marker(element: etree._Element) -> bool:
    """Our marker exactly: a <b> with only class="kraken-bs" and only text inside. Anything else isn't ours."""
    return (isinstance(element.tag, str) and etree.QName(element).localname == "b"
            and dict(element.attrib) == {"class": BOLD_CLASS} and len(element) == 0)


def _remove_markers(root: etree._Element) -> None:
    """Unwrap every marker: its letters, and the text after it, join the text around it."""
    for marker in [element for element in root.iter() if _is_marker(element)]:
        parent = marker.getparent()
        text = (marker.text or "") + (marker.tail or "")
        previous = marker.getprevious()
        if previous is not None:
            previous.tail = (previous.tail or "") + text
        else:
            parent.text = (parent.text or "") + text
        parent.remove(marker)
