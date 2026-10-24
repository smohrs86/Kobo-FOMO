"""Small helpers shared by several test files."""

from pathlib import Path

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
