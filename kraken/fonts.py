"""The font catalogue, and syncing fonts to the Kobo (DESIGN.md section 7, R11).

The catalogue is a folder with one sub-folder per font family, named as it should appear
in the `kraken fonts` checklist. Each family needs a Regular, a real Bold and a licence file.
Each file's style comes from the end of its name: Literata-Bold.ttf is the Bold.
"""

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from kraken.kobo import (
    PART_SUFFIX,
    Kobo,
    KoboError,
    copy_to_kobo,
    delete_from_kobo,
    file_hash,
    remove_leftover_parts,
)
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


def picks_path() -> Path:
    """Where the families ticked in `kraken fonts` are saved: ~/.local/share/kraken/font-picks.json"""
    return data_dir() / "font-picks.json"


class PicksError(Exception):
    """The saved font picks can't be read. The message says what to do."""


def read_picks(path: Path | None = None) -> set[str]:
    """The families ticked in `kraken fonts`. None are ticked until you first save the checklist."""
    path = path or picks_path()
    if not path.exists():
        return set()
    try:
        picks = json.loads(path.read_text())["picks"]
        if not all(isinstance(name, str) for name in picks):
            raise ValueError("every pick must be a family name")
        return set(picks)
    except (ValueError, KeyError, TypeError) as error:
        raise PicksError(f"{path} is damaged ({error}). Delete it and pick your fonts again.") from None


def write_picks(picks: set[str], path: Path | None = None) -> None:
    """Save the ticked families. Written to a draft first, then renamed, so it's never half-saved."""
    path = path or picks_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    draft = path.with_name(path.name + ".draft")
    draft.write_text(json.dumps({"picks": sorted(picks)}, indent=2) + "\n")
    os.replace(draft, path)


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


# --- The sync plan (step 5) ---
#
# Safety rule 3 and D18: kraken only removes or replaces font files it installed itself,
# which are the ones listed in the manifest on the Kobo. Any other font is never touched.


@dataclass(frozen=True)
class ManifestEntry:
    """What the manifest remembers about one font file kraken installed on the Kobo."""

    family: str
    sha256: str  # the file's fingerprint when it was installed


# The manifest: the file's name in fonts/ on the Kobo -> what kraken remembers about it.
Manifest = dict[str, ManifestEntry]


@dataclass(frozen=True)
class Install:
    """Copy one catalogue file to fonts/ on the Kobo."""

    kobo_name: str
    source: Path
    family: str
    sha256: str


@dataclass(frozen=True)
class FontPlan:
    """What a font sync will do. Working it out changes nothing; step 6 carries it out."""

    install: list[Install] = field(default_factory=list)
    remove: list[str] = field(default_factory=list)  # file names in fonts/, every one in the manifest
    forget: list[str] = field(default_factory=list)  # manifest entries whose file is already gone
    warnings: list[str] = field(default_factory=list)

    def has_changes(self) -> bool:
        return bool(self.install or self.remove or self.forget)


def plan_font_sync(picks: set[str], catalogue: Catalogue, manifest: Manifest, on_kobo: set[str]) -> FontPlan:
    """Work out what to install and remove so the Kobo has exactly the picked families.

    picks:     the families ticked in `kraken fonts`
    catalogue: what's in the catalogue folder on the computer
    manifest:  the font files kraken installed on the Kobo earlier
    on_kobo:   the names of the files in fonts/ on the Kobo right now
    """
    # The Kobo's drive ignores upper and lower case, so names are compared in lower case.
    present = {name.casefold() for name in on_kobo}
    ours = {name.casefold() for name in manifest}
    in_catalogue = {family.name: family for family in catalogue.families}

    install, warnings = [], []
    wanted = set()  # files that should stay on the Kobo

    for family_name in sorted(picks):
        family = in_catalogue.get(family_name)
        if family is None:
            # Leave its files alone: removing fonts you still have ticked would be a surprise.
            warnings.append(f"{family_name} is ticked but no longer in the catalogue, so it was left as it is")
            wanted.update(name for name, entry in manifest.items() if entry.family == family_name)
            continue

        files = family.kobo_files()
        not_ours = [name for name in files if name.casefold() in present and name.casefold() not in ours]
        if not_ours:
            warnings.append(
                f"{family_name} was not installed: {not_ours[0]} is already on the Kobo and kraken "
                "didn't put it there, so it won't overwrite it"
            )
            continue

        for kobo_name, source in files.items():
            wanted.add(kobo_name)
            sha256 = file_hash(source)
            entry = manifest.get(kobo_name)
            already_there = kobo_name.casefold() in present and entry is not None and entry.sha256 == sha256
            if not already_there:
                install.append(Install(kobo_name, source, family_name, sha256))

    remove, forget = [], []
    for kobo_name in sorted(manifest):
        if kobo_name in wanted:
            continue
        if kobo_name.casefold() in present:
            remove.append(kobo_name)
        else:
            forget.append(kobo_name)  # you already deleted it on the Kobo

    return FontPlan(install=install, remove=remove, forget=forget, warnings=warnings)


# --- Carrying out the plan (step 6) ---

KOBO_FONTS = Path("fonts")  # where the Kobo looks for extra fonts
MANIFEST = Path(".kraken/manifest.json")  # hidden folder, so the Kobo doesn't list it with the books
MANIFEST_FORMAT = 1  # bumped if the file's layout ever changes
PENDING = ""  # the fingerprint of a file whose copy hasn't been confirmed yet


@dataclass
class FontSyncResult:
    """What a font sync actually did, for the notification and the log."""

    installed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def fonts_on_kobo(kobo: Kobo) -> set[str]:
    """The names of the font files in fonts/ on the Kobo, leaving out unfinished copies."""
    folder = kobo.mount / KOBO_FONTS
    if not folder.is_dir():
        return set()
    return {path.name for path in folder.iterdir() if path.is_file() and not path.name.endswith(PART_SUFFIX)}


def read_manifest(kobo: Kobo) -> Manifest:
    """The fonts kraken installed on this Kobo. A Kobo kraken hasn't used yet has none."""
    path = kobo.mount / MANIFEST
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        if data["format"] != MANIFEST_FORMAT:
            raise ValueError(f"format {data['format']}")
        return {name: ManifestEntry(entry["family"], entry["sha256"]) for name, entry in data["fonts"].items()}
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        # Guessing could remove fonts kraken didn't install, so stop instead (D18).
        raise KoboError(
            f"kraken's list of the fonts it installed ({MANIFEST} on the Kobo) is damaged ({error}), "
            "so fonts were left as they are."
        ) from None


def write_manifest(kobo: Kobo, manifest: Manifest) -> None:
    """Save the manifest on the Kobo, using the same safe copy as everything else."""
    data = {
        "format": MANIFEST_FORMAT,
        "fonts": {name: {"family": entry.family, "sha256": entry.sha256} for name, entry in sorted(manifest.items())},
    }
    with tempfile.TemporaryDirectory() as scratch:
        draft = Path(scratch) / "manifest.json"
        draft.write_text(json.dumps(data, indent=2) + "\n")
        copy_to_kobo(kobo, draft, MANIFEST)


def apply_font_plan(kobo: Kobo, plan: FontPlan, manifest: Manifest) -> FontSyncResult:
    """Carry out a plan from plan_font_sync. One file failing never stops the others (safety rule 5).

    The manifest is saved *before* anything is copied, with each new file marked pending. If kraken is
    stopped halfway (say, the cable is pulled), the manifest still claims those names as kraken's, so
    the next push finishes the job instead of mistaking kraken's own files for hand-added ones.
    """
    result = FontSyncResult()
    manifest = dict(manifest)  # a copy, so the caller's manifest isn't changed behind its back

    remove_leftover_parts(kobo, KOBO_FONTS)

    for name in plan.remove:
        try:
            delete_from_kobo(kobo, KOBO_FONTS / name)
        except KoboError as error:
            result.problems.append(str(error))
            continue
        del manifest[name]
        result.removed.append(name)

    for name in plan.forget:
        del manifest[name]

    for step in plan.install:
        manifest[step.kobo_name] = ManifestEntry(step.family, PENDING)
    if plan.has_changes():
        write_manifest(kobo, manifest)

    for step in plan.install:
        try:
            copy_to_kobo(kobo, step.source, KOBO_FONTS / step.kobo_name)
        except KoboError as error:
            result.problems.append(str(error))
            continue  # stays pending, so the next push tries again
        manifest[step.kobo_name] = ManifestEntry(step.family, step.sha256)
        result.installed.append(step.kobo_name)

    if plan.install:
        write_manifest(kobo, manifest)
    return result
