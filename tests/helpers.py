"""Small helpers shared by several test files."""

import zipfile
from pathlib import Path
from urllib.parse import unquote

TRUETYPE_SIGNATURE = b"\x00\x01\x00\x00"


def make_family(catalogue: Path, name: str, files: list[str], licence: str | None = "OFL.txt") -> Path:
    """Make a family folder. Font files get a real font signature followed by pretend data."""
    folder = catalogue / name
    folder.mkdir(parents=True)
    for file_name in files:
        (folder / file_name).write_bytes(TRUETYPE_SIGNATURE + b"pretend font data")
    if licence:
        (folder / licence).write_text("SIL Open Font License")
    return folder


def xhtml_page(body: str, title: str = "A page") -> str:
    """A small, valid XHTML page around `body`."""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n'
        f'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>{title}</title></head><body>{body}</body></html>'
    )


def make_epub(path: Path, pages: dict[str, str] | None = None, *, title: str = "A Test Book",
              ncx: bool = True, extra: dict[str, bytes] | None = None, opf_folder: str = "OEBPS") -> Path:
    """Write a tiny EPUB 2 we made ourselves (DESIGN.md section 11): never a real book.

    pages:  page address in the OPF (spaces written %20) -> its <body> content
    extra:  more files to put in the zip, such as META-INF/encryption.xml
    """
    pages = pages if pages is not None else {"chapter1.xhtml": "<h1>Chapter One</h1><p>Hello world</p>"}
    prefix = f"{opf_folder}/" if opf_folder else ""
    items = "".join(f'<item id="p{i}" href="{name}" media-type="application/xhtml+xml"/>'
                    for i, name in enumerate(pages))
    items += '<item id="css" href="style.css" media-type="text/css"/>'
    if ncx:
        items += '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
    spine = "".join(f'<itemref idref="p{i}"/>' for i in range(len(pages)))
    spine_toc = ' toc="ncx"' if ncx else ""
    opf = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:title>{title}</dc:title><dc:identifier id="id">test-book</dc:identifier><dc:language>en</dc:language>'
        f'</metadata><manifest>{items}</manifest><spine{spine_toc}>{spine}</spine></package>'
    )
    container = (
        '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        f'<rootfiles><rootfile full-path="{prefix}content.opf" media-type="application/oebps-package+xml"/>'
        '</rootfiles></container>'
    )
    with zipfile.ZipFile(path, "w") as book:
        book.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")  # first, and not compressed
        book.writestr("META-INF/container.xml", container)
        book.writestr(f"{prefix}content.opf", opf)
        for name, body in pages.items():
            book.writestr(f"{prefix}{unquote(name)}", xhtml_page(body), zipfile.ZIP_DEFLATED)  # %20 -> space
        book.writestr(f"{prefix}style.css", "p { margin: 0 }", zipfile.ZIP_DEFLATED)
        if ncx:
            book.writestr(f"{prefix}toc.ncx", '<?xml version="1.0"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/"'
                          ' version="2005-1"><navMap/></ncx>', zipfile.ZIP_DEFLATED)
        for name, data in (extra or {}).items():
            book.writestr(name, data)
    return path
