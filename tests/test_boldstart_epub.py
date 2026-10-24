"""Tests for boldstart/epub.py: bold-start on a whole book, and taking it off again (D7, D46, D48)."""

import zipfile

import pytest

from boldstart.epub import EpubError, bold_epub, page_names, unbold_epub
from boldstart.page import rewrite_page
from helpers import make_epub

LIGHT = 0.30
BS = b'<b class="kraken-bs">'


@pytest.fixture
def book(tmp_path):
    return make_epub(tmp_path / "book.epub", {
        "chapter1.xhtml": "<h1>Chapter One</h1><p>Hello <i>dear</i> world</p>",
        "chapter%202.xhtml": "<p>Second page</p>",  # a space in the name, written %20 in the OPF
    })


def read_all(path):
    with zipfile.ZipFile(path) as book:
        return {info.filename: book.read(info) for info in book.infolist()}


def test_every_page_gets_bold_start(book, tmp_path):
    out = tmp_path / "bolded.epub"
    assert bold_epub(book, out, LIGHT) == 2
    files = read_all(out)
    assert BS + b"He</b>llo" in files["OEBPS/chapter1.xhtml"]
    assert BS + b"Se</b>cond" in files["OEBPS/chapter 2.xhtml"]


def test_everything_that_isnt_a_page_is_copied_unchanged(book, tmp_path):
    out = tmp_path / "bolded.epub"
    bold_epub(book, out, LIGHT)
    before, after = read_all(book), read_all(out)
    assert set(after) == set(before)
    for name in ("mimetype", "META-INF/container.xml", "OEBPS/content.opf", "OEBPS/style.css", "OEBPS/toc.ncx"):
        assert after[name] == before[name]


def test_mimetype_comes_first_and_uncompressed(tmp_path):
    # A book whose zip has mimetype last: the copy must put it first, as the EPUB rules require.
    source = make_epub(tmp_path / "book.epub")
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(tmp_path / "jumbled.epub", "w") as jumbled:
        for info in reversed(original.infolist()):
            jumbled.writestr(info, original.read(info))
    out = tmp_path / "bolded.epub"
    bold_epub(tmp_path / "jumbled.epub", out, LIGHT)
    first = zipfile.ZipFile(out).infolist()[0]
    assert first.filename == "mimetype"
    assert first.compress_type == zipfile.ZIP_STORED


def test_page_names_follow_the_opf_wherever_it_is(tmp_path):
    root = make_epub(tmp_path / "root.epub", {"a.xhtml": "<p>x</p>"}, opf_folder="")
    deep = make_epub(tmp_path / "deep.epub", {"text/a.xhtml": "<p>x</p>"}, opf_folder="OPS/book")
    assert page_names(zipfile.ZipFile(root)) == ["a.xhtml"]
    assert page_names(zipfile.ZipFile(deep)) == ["OPS/book/text/a.xhtml"]


# --- The promise (D7, D48) ---


def test_bold_then_unbold_gives_back_every_page(book, tmp_path):
    bold_epub(book, tmp_path / "bolded.epub", LIGHT)
    assert unbold_epub(tmp_path / "bolded.epub", tmp_path / "plain.epub") == 2
    before, after = read_all(book), read_all(tmp_path / "plain.epub")
    for name, data in before.items():
        expected = rewrite_page(data) if name.endswith(".xhtml") else data
        assert after[name] == expected, name


def test_bolding_a_bolded_book_again_changes_nothing(book, tmp_path):
    bold_epub(book, tmp_path / "once.epub", LIGHT)
    bold_epub(tmp_path / "once.epub", tmp_path / "twice.epub", LIGHT)
    assert read_all(tmp_path / "twice.epub") == read_all(tmp_path / "once.epub")


# --- Books that can't be bolded ---


def test_a_locked_book_is_refused_and_nothing_is_written(tmp_path):  # D46
    locked = make_epub(tmp_path / "locked.epub", extra={"META-INF/encryption.xml": b"<encryption/>"})
    out = tmp_path / "bolded.epub"
    with pytest.raises(EpubError, match="locked"):
        bold_epub(locked, out, LIGHT)
    assert not out.exists()


def test_a_file_that_isnt_a_zip_is_refused(tmp_path):
    fake = tmp_path / "fake.epub"
    fake.write_text("<html>a web page saved with the wrong name</html>")
    with pytest.raises(EpubError, match="isn't a readable EPUB"):
        bold_epub(fake, tmp_path / "out.epub", LIGHT)


def test_a_book_with_no_container_is_refused(tmp_path):
    bare = tmp_path / "bare.epub"
    with zipfile.ZipFile(bare, "w") as book:
        book.writestr("mimetype", "application/epub+zip")
    with pytest.raises(EpubError, match="no META-INF/container.xml"):
        bold_epub(bare, tmp_path / "out.epub", LIGHT)


def test_a_broken_page_names_the_page(tmp_path):
    book = make_epub(tmp_path / "book.epub", {"good.xhtml": "<p>fine</p>", "bad.xhtml": "<p>not closed"})
    with pytest.raises(EpubError, match="OEBPS/bad.xhtml is not valid XHTML"):
        bold_epub(book, tmp_path / "out.epub", LIGHT)
    assert not (tmp_path / "out.epub").exists()  # the half-written copy was deleted
