"""Spike A: build a sample EPUB that shows bold-start text at several strengths.

This is a throwaway experiment (a "spike"). It answers one question:
does bold-start lettering look good, and help, on the Kobo Glo's screen?

Run it with:
    python3 spikes/boldstart-sample/make_sample.py

It writes two copies of the same book to out/:
    boldstart-sample-v2.epub        opened by Kobo's Adobe-based engine
    boldstart-sample-v2.kepub.epub  opened by Kobo's own (newer) engine
Only Python's standard library is used, so there's nothing to install.
"""

import html
import math
import re
import zipfile
from pathlib import Path

# The opening of "Alice's Adventures in Wonderland" (Lewis Carroll, 1865).
# It's in the public domain, so it's free to use and publish.
SAMPLE_TEXT = [
    "Alice was beginning to get very tired of sitting by her sister on the bank, "
    "and of having nothing to do: once or twice she had peeped into the book her "
    "sister was reading, but it had no pictures or conversations in it, ‘and "
    "what is the use of a book,’ thought Alice ‘without pictures or "
    "conversations?’",
    "So she was considering in her own mind (as well as she could, for the hot day "
    "made her feel very sleepy and stupid), whether the pleasure of making a "
    "daisy-chain would be worth the trouble of getting up and picking the daisies, "
    "when suddenly a White Rabbit with pink eyes ran close by her.",
    "There was nothing so very remarkable in that; nor did Alice think it so very "
    "much out of the way to hear the Rabbit say to itself, ‘Oh dear! Oh dear! "
    "I shall be late!’",
]

# Each strength is the fraction of every word's letters to make bold.
# 0.0 is the plain control version, for comparison.
STRENGTHS = [
    ("Plain (no bolding)", 0.0),
    ("Light (about 30%)", 0.3),
    ("Medium (about 45%)", 0.45),
    ("Heavy (about 60%)", 0.6),
]

# A "word" is a run of letters or digits, optionally with an apostrophe inside
# (so "didn't" is one word). Everything else (spaces, punctuation) is left alone.
WORD_PATTERN = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)*")

# Our bolding is tagged with this class, so it can be found and removed exactly
# later (decision D7), and never confused with a book's own bold text.
BOLD_CLASS = "bs"

OUT_DIR = Path(__file__).parent / "out"


def bold_count(word_length, strength):
    """How many letters at the start of a word to make bold."""
    if strength == 0:
        return 0
    # Round up, so even short words get at least one bold letter.
    return min(word_length, math.ceil(word_length * strength))


def bold_start(text, strength):
    """Return `text` as HTML, with the start of each word wrapped in <b>."""
    pieces = []
    position = 0
    for match in WORD_PATTERN.finditer(text):
        pieces.append(html.escape(text[position:match.start()]))  # text between words
        word = match.group()
        n = bold_count(len(word), strength)
        if n:
            head, tail = html.escape(word[:n]), html.escape(word[n:])
            pieces.append(f'<b class="{BOLD_CLASS}">{head}</b>{tail}')
        else:
            pieces.append(html.escape(word))
        position = match.end()
    pieces.append(html.escape(text[position:]))
    return "".join(pieces)


def chapter_xhtml(title, strength):
    """One chapter of the book: the sample text at a single strength."""
    paragraphs = "\n".join(f"<p>{bold_start(p, strength)}</p>" for p in SAMPLE_TEXT)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head><title>{html.escape(title)}</title><link rel="stylesheet" href="style.css"/></head>
<body>
<h2>{html.escape(title)}</h2>
{paragraphs}
</body>
</html>
"""


# --- The fixed parts of an EPUB --------------------------------------------
# An EPUB is a zip file with a few required files that tell readers what's inside.

CONTAINER_XML = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

STYLE_CSS = """body { margin: 0 1em; }
p { line-height: 1.5; text-indent: 1.5em; margin: 0 0 0.6em 0; }
b.bs { font-weight: bold; }
"""


def content_opf(chapter_ids, title, book_id):
    """The book's "package" file: title, list of files, and reading order."""
    manifest = "\n".join(
        f'    <item id="{cid}" href="{cid}.xhtml" media-type="application/xhtml+xml"/>'
        for cid in chapter_ids
    )
    spine = "\n".join(f'    <itemref idref="{cid}"/>' for cid in chapter_ids)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">{book_id}</dc:identifier>
    <dc:title>{html.escape(title)}</dc:title>
    <dc:creator>Kobo-FOMO</dc:creator>
    <dc:language>en</dc:language>
    <meta property="dcterms:modified">2026-10-23T00:00:00Z</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="css" href="style.css" media-type="text/css"/>
{manifest}
  </manifest>
  <spine toc="ncx">
{spine}
  </spine>
</package>
"""


def nav_xhtml(chapters):
    """The table of contents, so each strength can be jumped to directly."""
    links = "\n".join(
        f'      <li><a href="{cid}.xhtml">{html.escape(title)}</a></li>'
        for cid, title, _ in chapters
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>Contents</title></head>
<body>
  <nav epub:type="toc"><ol>
{links}
  </ol></nav>
</body>
</html>
"""


def toc_ncx(chapters, title, book_id):
    """An older-style table of contents (EPUB 2). Kobo's Adobe-based engine expects it."""
    points = "\n".join(
        f'''    <navPoint id="{cid}" playOrder="{i}">
      <navLabel><text>{html.escape(ch_title)}</text></navLabel>
      <content src="{cid}.xhtml"/>
    </navPoint>'''
        for i, (cid, ch_title, _) in enumerate(chapters, start=1)
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="{book_id}"/></head>
  <docTitle><text>{html.escape(title)}</text></docTitle>
  <navMap>
{points}
  </navMap>
</ncx>
"""


def build_epub(path, title, book_id):
    chapters = [(f"strength{i}", title, s) for i, (title, s) in enumerate(STRENGTHS)]
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as epub:
        # The EPUB rules say "mimetype" must come first, uncompressed.
        epub.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        deflate = zipfile.ZIP_DEFLATED
        epub.writestr("META-INF/container.xml", CONTAINER_XML, compress_type=deflate)
        epub.writestr("OEBPS/content.opf", content_opf([c[0] for c in chapters], title, book_id), compress_type=deflate)
        epub.writestr("OEBPS/nav.xhtml", nav_xhtml(chapters), compress_type=deflate)
        epub.writestr("OEBPS/toc.ncx", toc_ncx(chapters, title, book_id), compress_type=deflate)
        epub.writestr("OEBPS/style.css", STYLE_CSS, compress_type=deflate)
        for cid, title, strength in chapters:
            epub.writestr(f"OEBPS/{cid}.xhtml", chapter_xhtml(title, strength), compress_type=deflate)


if __name__ == "__main__":
    # Each copy gets its own title and ID so the Kobo treats them as separate books.
    builds = [
        ("boldstart-sample-v2.epub", "Bold-start Sample v2 (EPUB)", "urn:kobo-fomo:spike-a:v2-epub"),
        ("boldstart-sample-v2.kepub.epub", "Bold-start Sample v2 (KEPUB)", "urn:kobo-fomo:spike-a:v2-kepub"),
    ]
    for filename, title, book_id in builds:
        build_epub(OUT_DIR / filename, title, book_id)
        print(f"Wrote {OUT_DIR / filename}")
