"""Bold-start for a whole EPUB (DESIGN.md section 5).

An EPUB is a zip file. META-INF/container.xml points to the OPF file, the book's description, which
lists every file in the book with its type. Each file listed as a page (application/xhtml+xml) gets
bold-start; everything else is copied unchanged.
"""

import posixpath
import zipfile
from collections.abc import Callable
from pathlib import Path
from urllib.parse import unquote

from lxml import etree

from boldstart.page import PARSER, PageError, bold_page, unbold_page

CONTAINER = "META-INF/container.xml"
ENCRYPTION = "META-INF/encryption.xml"
NAMESPACES = {
    "container": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
}
PAGE_TYPE = "application/xhtml+xml"


class EpubError(Exception):
    """The book can't be bolded. The message says why, in plain words."""


def bold_epub(source: Path, destination: Path, strength: float) -> int:
    """Write a bold-start copy of the book at `source` to `destination`. Returns how many pages were bolded."""
    return _rewrite(source, destination, lambda page: bold_page(page, strength))


def unbold_epub(source: Path, destination: Path) -> int:
    """Write a copy with all bold-start removed (D7). Returns how many pages were changed back."""
    return _rewrite(source, destination, unbold_page)


def page_names(book: zipfile.ZipFile) -> list[str]:
    """The names, inside the zip, of every page the book's OPF file lists."""
    return manifest_names(book, PAGE_TYPE)


def manifest_names(book: zipfile.ZipFile, media_type: str) -> list[str]:
    """The names, inside the zip, of every file of one type that the book's OPF file lists."""
    opf_name = _opf_name(book)
    opf = _parse(book, opf_name)
    folder = posixpath.dirname(opf_name)  # addresses in the OPF are relative to its own folder
    names = []
    for item in opf.iterfind("opf:manifest/opf:item", NAMESPACES):
        if item.get("media-type") == media_type and item.get("href"):
            names.append(posixpath.normpath(posixpath.join(folder, unquote(item.get("href")))))
    return names


def _rewrite(source: Path, destination: Path, change_page: Callable[[bytes], bytes]) -> int:
    """Copy the book, passing each page through `change_page`. The mimetype file goes first, uncompressed."""
    try:
        book = zipfile.ZipFile(source)
    except (zipfile.BadZipFile, OSError) as error:
        raise EpubError(f"it isn't a readable EPUB ({error})") from error

    with book:
        if ENCRYPTION in book.namelist():
            raise EpubError("it's locked (it has an encryption.xml, usually DRM), so kraken leaves it alone")  # D46
        pages = set(page_names(book))
        entries = sorted(book.infolist(), key=lambda info: info.filename != "mimetype")  # mimetype first

        changed = 0
        try:
            with zipfile.ZipFile(destination, "w") as copy:
                for info in entries:
                    data = book.read(info)
                    if info.filename in pages:
                        try:
                            data = change_page(data)
                        except PageError as error:
                            raise EpubError(f"its page {info.filename} is {error}") from error
                        changed += 1
                    copy.writestr(_copy_of(info), data)
        except BaseException:
            destination.unlink(missing_ok=True)  # never leave a half-written book behind
            raise
    return changed


def _copy_of(info: zipfile.ZipInfo) -> zipfile.ZipInfo:
    """The same name, date and permissions. The mimetype file must be stored uncompressed (an EPUB rule)."""
    new = zipfile.ZipInfo(info.filename, date_time=info.date_time)
    new.external_attr = info.external_attr
    new.compress_type = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
    return new


def _opf_name(book: zipfile.ZipFile) -> str:
    container = _parse(book, CONTAINER)
    rootfile = container.find("container:rootfiles/container:rootfile", NAMESPACES)
    if rootfile is None or not rootfile.get("full-path"):
        raise EpubError("its container.xml doesn't say where the book's OPF file is")
    return rootfile.get("full-path")


def _parse(book: zipfile.ZipFile, name: str) -> etree._Element:
    try:
        return etree.fromstring(book.read(name), PARSER)
    except KeyError:
        raise EpubError(f"it has no {name}") from None
    except etree.XMLSyntaxError as error:
        raise EpubError(f"its {name} can't be read ({error})") from error
