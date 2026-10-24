"""Is this EPUB safe for the Kobo? (DESIGN.md section 2, step 5; D12, D46, D47)

Each check raises CheckError with a reason in plain words, which becomes the note beside a book in
skipped/. The checks stop at the first problem.
"""

import zipfile
import zlib
from pathlib import Path

from boldstart.epub import ENCRYPTION, EpubError, manifest_names

NCX_TYPE = "application/x-dtbncx+xml"


class CheckError(Exception):
    """The book isn't safe to send. The message says why, in plain words."""


def check_book(path: Path) -> None:
    """Check a book before bolding it: it opens, isn't locked or damaged, and has a readable OPF and a toc.ncx."""
    with _open(path) as book:
        if ENCRYPTION in book.namelist():
            raise CheckError("it's locked (it has an encryption.xml, usually DRM), so kraken leaves it alone")  # D46
        _check_not_damaged(book)
        try:
            tables = manifest_names(book, NCX_TYPE)
        except EpubError as error:
            raise CheckError(str(error)) from error
        if not any(name in book.namelist() for name in tables):  # D47
            raise CheckError("it has no table of contents (toc.ncx), which can freeze the Kobo")


def check_bolded(path: Path) -> None:
    """A light check on kraken's own bolded copy: it opens, nothing is damaged, and mimetype comes first."""
    with _open(path) as book:
        _check_not_damaged(book)
        entries = book.infolist()
        if not entries or entries[0].filename != "mimetype" or entries[0].compress_type != zipfile.ZIP_STORED:
            raise CheckError("its mimetype file isn't first and uncompressed, as the EPUB rules require")


def _open(path: Path) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as error:
        raise CheckError(f"it isn't a readable EPUB ({error})") from error


def _check_not_damaged(book: zipfile.ZipFile) -> None:
    """Read every file in the zip and compare it with its stored fingerprint (CRC)."""
    try:
        damaged = book.testzip()
    except (zipfile.BadZipFile, OSError, EOFError, zlib.error) as error:  # some damage stops the reading itself
        raise CheckError(f"it's damaged ({error})") from error
    if damaged:
        raise CheckError(f"it's damaged: {damaged} doesn't match its fingerprint")
