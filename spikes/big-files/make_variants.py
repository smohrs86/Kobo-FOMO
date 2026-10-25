"""Spike E: why are bolded books slow on the Kobo? Builds five versions of one book to find out.

This is a throwaway experiment (a "spike"). At Checkpoint C, bolded books took 20-30 s to jump to a
chapter, and one jump crashed the reader. Bolding makes each chapter file about 5x bigger, because every
word gains a <b class="kraken-bs">...</b> marker. Two things grow together: the file's size in bytes, and
the number of elements (tags) the reader must lay out. These versions pull the two apart:

    E1  not bolded                      the control: how fast is "normal"?
    E2  bolded as now                   the slow case
    E3  bolded with a bare <b> marker   fewer bytes, same number of elements: is it the bytes?
    E4  split into small files, bolded  fewer bytes *and* elements per file: is it how much is in one file?
    E5  E2 named .kepub.epub            opened by the Kobo's own reader instead of the Adobe one

Run it with a book (the spike used Yarrow's "Mortuary Customs", public domain, from Project Gutenberg):
    .venv/bin/python spikes/big-files/make_variants.py BOOK.epub
    .venv/bin/python spikes/big-files/make_variants.py BOOK.epub --send   # also copy them to the Kobo

The books go to out/ (git-ignored), and with --send to kraken-tests/ on the Kobo, using kraken's safe copy.
E4 is split by Calibre (ebook-convert), which also tidies other markup: if E4 wins, our own splitter
confirms it in Milestone 2 step 7.
"""

import argparse
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

from boldstart.epub import bold_epub, page_names
from kraken.checks import check_bolded, check_book
from kraken.kobo import copy_to_kobo, find_kobo

STRENGTH = 0.45  # the default (D55)
OUT_DIR = Path(__file__).parent / "out"
KOBO_FOLDER = Path("kraken-tests")

# Calibre splits any page bigger than this (in KB). Yarrow's pages are about 75 KB before bolding and
# 5x bigger after, so 20 KB parts become about 100 KB once bolded: well under the ~260 KB limit.
SPLIT_SIZE_KB = 20

OUR_MARKER = b'<b class="kraken-bs">'
BARE_MARKER = b"<b>"
DC = "http://purl.org/dc/elements/1.1/"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Spike E's five test versions of a book.")
    parser.add_argument("book", type=Path, help="the EPUB to test with")
    parser.add_argument("--send", action="store_true", help="also copy them to kraken-tests/ on the Kobo")
    args = parser.parse_args()

    check_book(args.book)
    OUT_DIR.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        books = build_all(args.book, temp)
    for book in books:
        check_bolded(book)  # the same safety check kraken runs before sending (toc.ncx, not damaged)
    report(books)

    if args.send:
        return send(books)
    return 0


def build_all(source: Path, temp: Path) -> list[Path]:
    """Build E1 to E5 in out/. `temp` holds the in-between files."""
    bolded = temp / "bolded.epub"
    bold_epub(source, bolded, STRENGTH)

    e1 = retitle(source, OUT_DIR / "E1 plain.epub", "E1 plain")
    e2 = retitle(bolded, OUT_DIR / "E2 bolded.epub", "E2 bolded")
    e3 = retitle(bolded, OUT_DIR / "E3 bare b.epub", "E3 bare b", change_page=bare_markers)

    split = temp / "split.epub"
    calibre_split(source, split)
    split_bolded = temp / "split-bolded.epub"
    bold_epub(split, split_bolded, STRENGTH)
    e4 = retitle(split_bolded, OUT_DIR / "E4 split.epub", "E4 split")

    e5 = retitle(bolded, OUT_DIR / "E5 kepub.kepub.epub", "E5 kepub")
    return [e1, e2, e3, e4, e5]


def bare_markers(page: bytes) -> bytes:
    """Swap our marker for a bare <b>. Only for this test: a bare <b> can't be told apart from the book's own bold (D7)."""
    return page.replace(OUR_MARKER, BARE_MARKER)


def calibre_split(source: Path, destination: Path) -> None:
    """Have Calibre cut every page bigger than SPLIT_SIZE_KB into smaller files, fixing links and the TOC to match."""
    subprocess.run(
        ["ebook-convert", str(source), str(destination), f"--flow-size={SPLIT_SIZE_KB}"],
        check=True, capture_output=True,
    )


def retitle(source: Path, destination: Path, title: str, change_page=None) -> Path:
    """Copy the book with a new title, so each version shows up separately in the Kobo's library.

    `change_page`, if given, changes each page on the way (used for E3). The mimetype file goes first,
    uncompressed (an EPUB rule).
    """
    with zipfile.ZipFile(source) as book:
        pages = set(page_names(book))
        opf_name = _opf_name(book)
        entries = sorted(book.infolist(), key=lambda info: info.filename != "mimetype")
        with zipfile.ZipFile(destination, "w") as copy:
            for info in entries:
                data = book.read(info)
                if info.filename == opf_name:
                    data = _set_title(data, title)
                elif change_page and info.filename in pages:
                    data = change_page(data)
                stored = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
                copy.writestr(info.filename, data, compress_type=stored)
    return destination


def _opf_name(book: zipfile.ZipFile) -> str:
    container = book.read("META-INF/container.xml").decode()
    return re.search(r'full-path="([^"]+)"', container).group(1)


def _set_title(opf: bytes, title: str) -> bytes:
    root = etree.fromstring(opf)
    root.find(f".//{{{DC}}}title").text = title
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def report(books: list[Path]) -> None:
    """Print each version's largest page: its size, and how many elements it holds."""
    print(f"{'Version':<22}{'pages':>6}{'largest page':>14}{'elements in it':>16}")
    for path in books:
        with zipfile.ZipFile(path) as book:
            pages = [book.read(name) for name in page_names(book)]
        largest = max(pages, key=len)
        elements = sum(1 for _ in etree.fromstring(largest).iter())
        print(f"{path.name:<22}{len(pages):>6}{len(largest) // 1024:>11} KB{elements:>16,}")


def send(books: list[Path]) -> int:
    kobo = find_kobo()
    if kobo is None:
        print("No Kobo found. Plug it in and run again with --send.")
        return 1
    for book in books:
        copy_to_kobo(kobo, book, KOBO_FOLDER / book.name)
        print(f"Sent {book.name} to {KOBO_FOLDER}/ on the Kobo.")
    print("Done. Eject with: udisksctl unmount, then udisksctl power-off.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
