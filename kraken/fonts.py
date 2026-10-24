"""The font catalogue, and (from step 5) syncing fonts to the Kobo (DESIGN.md section 7, R11).

The catalogue is a folder with one sub-folder per font family, named as it should appear
in the `kraken fonts` checklist. Each family needs a Regular, a real Bold and a licence file.
Each file's style comes from the end of its name: Literata-Bold.ttf is the Bold.
"""

from dataclasses import dataclass, field
from pathlib import Path

from kraken.settings import data_dir

STYLES = ("Regular", "Bold", "Italic", "BoldItalic")
REQUIRED_STYLES = ("Regular", "Bold")  # bold-start depends on a real Bold
FONT_EXTENSIONS = (".ttf", ".otf")  # the two kinds of font file the Kobo can use
LICENCE_NAMES = ("ofl", "license", "licence")  # a licence file's name starts with one of these

# The first four bytes of every real font file. A web page saved with a .ttf name fails this check.
FONT_SIGNATURES = (b"\x00\x01\x00\x00", b"true", b"OTTO")


@dataclass(frozen=True)
class FontFamily:
    """One usable family in the catalogue."""

    name: str  # as shown in the checklist, such as "Atkinson Hyperlegible"
    styles: dict[str, Path]  # style -> font file, such as "Bold" -> .../Literata-Bold.ttf
    licence: Path

    def kobo_files(self) -> dict[str, Path]:
        """The name each file gets on the Kobo, mapped to the file in the catalogue.

        The Kobo's pattern is Family-Style.ttf, for example AtkinsonHyperlegible-BoldItalic.ttf.
        """
        family = self.name.replace(" ", "")
        return {f"{family}-{style}{path.suffix.lower()}": path for style, path in self.styles.items()}


@dataclass(frozen=True)
class Catalogue:
    """Everything in the catalogue folder: the usable families, and what's wrong with the rest."""

    families: list[FontFamily] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def catalogue_dir() -> Path:
    """~/.local/share/kraken/fonts"""
    return data_dir() / "fonts"


def read_catalogue(folder: Path | None = None) -> Catalogue:
    """Read the catalogue. A family that isn't usable is left out, with the reason in `problems`."""
    folder = folder or catalogue_dir()
    if not folder.is_dir():
        return Catalogue()

    families, problems = [], []
    for entry in sorted(folder.iterdir(), key=lambda path: path.name.casefold()):
        if entry.name.startswith("."):
            continue  # hidden files, such as ones a file manager leaves behind
        if not entry.is_dir():
            problems.append(f"{entry.name}: put each font family in its own folder")
            continue
        family, problem = _read_family(entry)
        if family:
            families.append(family)
        else:
            problems.append(f"{entry.name}: {problem}")
    return Catalogue(families=families, problems=problems)


def _read_family(folder: Path) -> tuple[FontFamily | None, str]:
    """Return (the family, "") if the folder is usable, or (None, what's wrong)."""
    styles: dict[str, Path] = {}
    licence = None

    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        if path.name.lower().startswith(LICENCE_NAMES):
            licence = path
            continue
        style = path.stem.rsplit("-", 1)[-1]
        if path.suffix.lower() not in FONT_EXTENSIONS or style not in STYLES:
            continue  # other files and weights, such as -SemiBold, aren't used
        if style in styles:
            return None, f"two {style} files ({styles[style].name} and {path.name}); keep one"
        if not _looks_like_a_font(path):
            return None, f"{path.name} isn't a font file (perhaps a web page saved by mistake)"
        styles[style] = path

    missing = [style for style in REQUIRED_STYLES if style not in styles]
    if missing:
        return None, f"no {' or '.join(missing)} font (needs files ending -Regular and -Bold)"
    if licence is None:
        return None, "no licence file (such as OFL.txt); only open-licensed fonts are used"

    # Keep the styles in the usual order: Regular, Bold, Italic, BoldItalic.
    ordered = {style: styles[style] for style in STYLES if style in styles}
    return FontFamily(name=folder.name, styles=ordered, licence=licence), ""


def _looks_like_a_font(path: Path) -> bool:
    with path.open("rb") as file:
        return file.read(4) in FONT_SIGNATURES
