"""Tests for kraken/checks.py: is this EPUB safe for the Kobo? (D12, D46, D47)"""

import zipfile

import pytest

from boldstart.epub import bold_epub
from kraken.checks import CheckError, check_bolded, check_book
from helpers import make_epub

CHAPTER = "OEBPS/chapter1.xhtml"


def damage(path, name):
    """Change one byte of a stored file's data, so it no longer matches its fingerprint (CRC)."""
    with zipfile.ZipFile(path) as book:
        info = book.getinfo(name)
    data = bytearray(path.read_bytes())
    start = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)  # skip the file's header
    data[start] ^= 0xFF
    path.write_bytes(bytes(data))


def test_a_good_book_passes(tmp_path):
    check_book(make_epub(tmp_path / "book.epub"))


def test_a_file_that_isnt_a_zip_is_refused(tmp_path):
    path = tmp_path / "book.epub"
    path.write_text("not a book")
    with pytest.raises(CheckError, match="isn't a readable EPUB"):
        check_book(path)


def test_a_missing_file_is_refused(tmp_path):
    with pytest.raises(CheckError, match="isn't a readable EPUB"):
        check_book(tmp_path / "gone.epub")


def test_a_locked_book_is_refused(tmp_path):
    book = make_epub(tmp_path / "book.epub", extra={"META-INF/encryption.xml": b"<encryption/>"})
    with pytest.raises(CheckError, match="locked"):
        check_book(book)


def test_a_locked_book_is_refused_before_anything_else_is_read(tmp_path):
    # Locked and damaged: the lock is the reason given, because D46 says a locked book is never opened.
    book = make_epub(tmp_path / "book.epub", extra={"META-INF/encryption.xml": b"<encryption/>"})
    damage(book, CHAPTER)
    with pytest.raises(CheckError, match="locked"):
        check_book(book)


def test_a_damaged_file_inside_is_refused(tmp_path):
    book = make_epub(tmp_path / "book.epub")
    damage(book, "mimetype")  # stored uncompressed, so the damage is only caught by the fingerprint
    with pytest.raises(CheckError, match="damaged: mimetype"):
        check_book(book)


def test_damage_that_stops_the_reading_is_refused(tmp_path):
    book = make_epub(tmp_path / "book.epub")
    damage(book, CHAPTER)  # compressed, so the damage breaks the unpacking itself
    with pytest.raises(CheckError, match="damaged"):
        check_book(book)


def test_a_book_without_container_xml_is_refused(tmp_path):
    book = make_epub(tmp_path / "book.epub")
    with zipfile.ZipFile(book) as original, zipfile.ZipFile(tmp_path / "no-container.epub", "w") as copy:
        for info in original.infolist():
            if info.filename != "META-INF/container.xml":
                copy.writestr(info, original.read(info))
    with pytest.raises(CheckError, match="no META-INF/container.xml"):
        check_book(tmp_path / "no-container.epub")


def test_a_book_with_an_unreadable_opf_is_refused(tmp_path):
    book = make_epub(tmp_path / "book.epub")
    with zipfile.ZipFile(book) as original, zipfile.ZipFile(tmp_path / "bad-opf.epub", "w") as copy:
        for info in original.infolist():
            data = b"<package><unclosed>" if info.filename == "OEBPS/content.opf" else original.read(info)
            copy.writestr(info, data)
    with pytest.raises(CheckError, match="content.opf can't be read"):
        check_book(tmp_path / "bad-opf.epub")


def test_a_book_without_toc_ncx_is_refused(tmp_path):
    with pytest.raises(CheckError, match="no table of contents"):
        check_book(make_epub(tmp_path / "book.epub", ncx=False))


def test_a_toc_ncx_listed_but_missing_from_the_zip_is_refused(tmp_path):
    book = make_epub(tmp_path / "book.epub")
    with zipfile.ZipFile(book) as original, zipfile.ZipFile(tmp_path / "lost-ncx.epub", "w") as copy:
        for info in original.infolist():
            if info.filename != "OEBPS/toc.ncx":
                copy.writestr(info, original.read(info))
    with pytest.raises(CheckError, match="no table of contents"):
        check_book(tmp_path / "lost-ncx.epub")


def test_the_toc_is_found_by_its_type_not_its_name(tmp_path):
    book = make_epub(tmp_path / "book.epub")
    with zipfile.ZipFile(book) as original, zipfile.ZipFile(tmp_path / "renamed.epub", "w") as copy:
        for info in original.infolist():
            data = original.read(info)
            if info.filename == "OEBPS/content.opf":
                data = data.replace(b'href="toc.ncx"', b'href="contents.ncx"')
            name = "OEBPS/contents.ncx" if info.filename == "OEBPS/toc.ncx" else info.filename
            copy.writestr(zipfile.ZipInfo(name, info.date_time), data)
    check_book(tmp_path / "renamed.epub")


def test_kraken_s_own_bolded_copy_passes_the_light_check(tmp_path):
    out = tmp_path / "bolded.epub"
    bold_epub(make_epub(tmp_path / "book.epub"), out, 0.30)
    check_bolded(out)


def test_the_light_check_refuses_a_damaged_copy(tmp_path):
    book = make_epub(tmp_path / "book.epub")
    damage(book, "mimetype")
    with pytest.raises(CheckError, match="damaged"):
        check_bolded(book)


def test_the_light_check_wants_mimetype_first(tmp_path):
    # Every file stored uncompressed, so the order is the only thing wrong.
    book = make_epub(tmp_path / "book.epub")
    with zipfile.ZipFile(book) as original, zipfile.ZipFile(tmp_path / "jumbled.epub", "w") as jumbled:
        for info in reversed(original.infolist()):
            jumbled.writestr(info.filename, original.read(info), zipfile.ZIP_STORED)
    with pytest.raises(CheckError, match="mimetype"):
        check_bolded(tmp_path / "jumbled.epub")


def test_the_light_check_wants_mimetype_uncompressed(tmp_path):
    book = make_epub(tmp_path / "book.epub")
    with zipfile.ZipFile(book) as original, zipfile.ZipFile(tmp_path / "squashed.epub", "w") as squashed:
        for info in original.infolist():
            squashed.writestr(info.filename, original.read(info), zipfile.ZIP_DEFLATED)
    with pytest.raises(CheckError, match="mimetype"):
        check_bolded(tmp_path / "squashed.epub")


def test_the_light_check_refuses_an_empty_zip(tmp_path):
    with zipfile.ZipFile(tmp_path / "empty.epub", "w"):
        pass
    with pytest.raises(CheckError, match="mimetype"):
        check_bolded(tmp_path / "empty.epub")
