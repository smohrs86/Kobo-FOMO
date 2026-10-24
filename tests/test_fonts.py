"""Tests for the font catalogue, using tiny made-up font files."""

import itertools
from pathlib import Path

import pytest

from kraken.fonts import ManifestEntry, plan_font_sync, read_catalogue
from kraken.kobo import file_hash

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


@pytest.fixture
def catalogue(tmp_path):
    return tmp_path / "fonts"


def test_missing_catalogue_folder_is_empty(catalogue):
    result = read_catalogue(catalogue)
    assert result.families == [] and result.problems == []


def test_reads_a_family_with_regular_and_bold(catalogue):
    make_family(catalogue, "Atkinson Hyperlegible",
                ["AtkinsonHyperlegible-Regular.ttf", "AtkinsonHyperlegible-Bold.ttf"])

    [family] = read_catalogue(catalogue).families
    assert family.name == "Atkinson Hyperlegible"
    assert list(family.styles) == ["Regular", "Bold"]
    assert family.licence.name == "OFL.txt"


def test_kobo_names_follow_the_family_style_pattern(catalogue):
    make_family(catalogue, "Atkinson Hyperlegible",
                ["AtkinsonHyperlegible-Regular.ttf", "AtkinsonHyperlegible-Bold.TTF",
                 "AtkinsonHyperlegible-BoldItalic.ttf"])

    [family] = read_catalogue(catalogue).families
    assert list(family.kobo_files()) == [
        "AtkinsonHyperlegible-Regular.ttf",
        "AtkinsonHyperlegible-Bold.ttf",
        "AtkinsonHyperlegible-BoldItalic.ttf",
    ]


def test_all_four_styles_are_kept_in_the_usual_order(catalogue):
    make_family(catalogue, "Literata", ["Literata-BoldItalic.ttf", "Literata-Italic.ttf",
                                        "Literata-Bold.ttf", "Literata-Regular.ttf"])
    [family] = read_catalogue(catalogue).families
    assert list(family.styles) == ["Regular", "Bold", "Italic", "BoldItalic"]


def test_other_weights_and_files_are_ignored(catalogue):
    make_family(catalogue, "Literata", ["Literata-Regular.ttf", "Literata-Bold.ttf",
                                        "Literata-SemiBold.ttf", "README.md"])
    [family] = read_catalogue(catalogue).families
    assert list(family.styles) == ["Regular", "Bold"]


def test_families_are_sorted_by_name_ignoring_case(catalogue):
    for name in ["literata", "Andika", "Lexend"]:
        make_family(catalogue, name, [f"{name}-Regular.ttf", f"{name}-Bold.ttf"])
    assert [family.name for family in read_catalogue(catalogue).families] == ["Andika", "Lexend", "literata"]


@pytest.mark.parametrize(
    "files, licence, problem",
    [
        (["Lexend-Regular.ttf"], "OFL.txt", "no Bold font"),
        (["Lexend-Bold.ttf"], "OFL.txt", "no Regular font"),
        (["Lexend[wght].ttf"], "OFL.txt", "no Regular or Bold font"),  # a variable font
        (["Lexend-Regular.ttf", "Lexend-Bold.ttf"], None, "no licence file"),
        (["Lexend-Regular.ttf", "Lexend-Bold.ttf", "Lexend-Bold.otf"], "OFL.txt", "two Bold files"),
    ],
)
def test_unusable_family_is_left_out_with_the_reason(catalogue, files, licence, problem):
    make_family(catalogue, "Lexend", files, licence)

    result = read_catalogue(catalogue)
    assert result.families == []
    [message] = result.problems
    assert message.startswith("Lexend: ") and problem in message


def test_web_page_saved_as_a_font_is_caught(catalogue):
    folder = make_family(catalogue, "Andika", ["Andika-Regular.ttf"])
    (folder / "Andika-Bold.ttf").write_text("<!DOCTYPE html><html>GitHub page</html>")

    [message] = read_catalogue(catalogue).problems
    assert "Andika-Bold.ttf isn't a font file" in message


def test_licence_file_names_are_recognised(catalogue):
    for name, licence in [("A", "LICENSE"), ("B", "OFL-atkinson.txt"), ("C", "licence.md")]:
        make_family(catalogue, name, [f"{name}-Regular.ttf", f"{name}-Bold.ttf"], licence)
    assert len(read_catalogue(catalogue).families) == 3


def test_loose_files_and_hidden_files_in_the_catalogue(catalogue):
    make_family(catalogue, "Literata", ["Literata-Regular.ttf", "Literata-Bold.ttf"])
    (catalogue / "Stray-Regular.ttf").write_bytes(TRUETYPE_SIGNATURE)
    (catalogue / ".directory").write_text("file manager settings")

    result = read_catalogue(catalogue)
    assert [family.name for family in result.families] == ["Literata"]
    assert result.problems == ["Stray-Regular.ttf: put each font family in its own folder"]


# --- The sync plan (step 5) ---

ATKINSON = ["AtkinsonHyperlegible-Regular.ttf", "AtkinsonHyperlegible-Bold.ttf"]
LITERATA = ["Literata-Regular.ttf", "Literata-Bold.ttf"]


@pytest.fixture
def two_families(catalogue):
    make_family(catalogue, "Atkinson Hyperlegible", ATKINSON)
    make_family(catalogue, "Literata", LITERATA)
    return read_catalogue(catalogue)


def installed(catalogue, family_name: str) -> dict[str, ManifestEntry]:
    """Manifest entries for a family installed from the current catalogue files."""
    [family] = [f for f in catalogue.families if f.name == family_name]
    return {name: ManifestEntry(family_name, file_hash(path)) for name, path in family.kobo_files().items()}


def test_ticked_family_is_installed(two_families):
    plan = plan_font_sync({"Literata"}, two_families, manifest={}, on_kobo=set())
    assert [step.kobo_name for step in plan.install] == LITERATA
    assert plan.remove == [] and plan.warnings == []


def test_nothing_to_do_when_already_installed(two_families):
    manifest = installed(two_families, "Literata")
    plan = plan_font_sync({"Literata"}, two_families, manifest, on_kobo=set(LITERATA))
    assert not plan.has_changes()


def test_changed_catalogue_file_is_installed_again(two_families):
    manifest = installed(two_families, "Literata")
    manifest["Literata-Bold.ttf"] = ManifestEntry("Literata", "fingerprint-of-an-older-version")

    plan = plan_font_sync({"Literata"}, two_families, manifest, on_kobo=set(LITERATA))
    assert [step.kobo_name for step in plan.install] == ["Literata-Bold.ttf"]


def test_file_deleted_on_the_kobo_is_installed_again_if_still_ticked(two_families):
    manifest = installed(two_families, "Literata")
    plan = plan_font_sync({"Literata"}, two_families, manifest, on_kobo={"Literata-Regular.ttf"})
    assert [step.kobo_name for step in plan.install] == ["Literata-Bold.ttf"]


def test_unticked_family_is_removed(two_families):
    manifest = installed(two_families, "Literata")
    plan = plan_font_sync(set(), two_families, manifest, on_kobo=set(LITERATA))
    assert plan.remove == sorted(LITERATA)
    assert plan.install == []


def test_unticked_family_already_deleted_on_the_kobo_is_just_forgotten(two_families):
    manifest = installed(two_families, "Literata")
    plan = plan_font_sync(set(), two_families, manifest, on_kobo=set())
    assert plan.remove == [] and plan.forget == sorted(LITERATA)


def test_hand_added_fonts_are_never_removed(two_families):
    plan = plan_font_sync(set(), two_families, manifest={}, on_kobo={"MyOwnFont-Regular.ttf", *LITERATA})
    assert not plan.has_changes()


def test_hand_added_file_with_the_same_name_is_not_overwritten(two_families):
    plan = plan_font_sync({"Literata"}, two_families, manifest={}, on_kobo={"Literata-Bold.ttf"})
    assert plan.install == []
    [warning] = plan.warnings
    assert "Literata was not installed" in warning and "Literata-Bold.ttf" in warning


def test_same_name_in_different_case_counts_as_the_same_file(two_families):
    # On the Kobo's drive, literata-bold.ttf and Literata-Bold.ttf are one file.
    plan = plan_font_sync({"Literata"}, two_families, manifest={}, on_kobo={"literata-bold.ttf"})
    assert plan.install == []
    assert len(plan.warnings) == 1


def test_family_gone_from_the_catalogue_is_left_on_the_kobo(two_families, catalogue):
    manifest = {"Lexend-Regular.ttf": ManifestEntry("Lexend", "abc"), "Lexend-Bold.ttf": ManifestEntry("Lexend", "def")}
    plan = plan_font_sync({"Lexend"}, two_families, manifest, on_kobo=set(manifest))
    assert not plan.has_changes()
    [warning] = plan.warnings
    assert "Lexend is ticked but no longer in the catalogue" in warning


def test_style_dropped_from_the_catalogue_is_removed(catalogue):
    make_family(catalogue, "Literata", LITERATA)
    manifest = installed(read_catalogue(catalogue), "Literata")
    manifest["Literata-Italic.ttf"] = ManifestEntry("Literata", "abc")  # installed earlier, gone now

    plan = plan_font_sync({"Literata"}, read_catalogue(catalogue), manifest, {"Literata-Italic.ttf", *LITERATA})
    assert plan.remove == ["Literata-Italic.ttf"]


def test_safety_rules_hold_in_every_combination(two_families):
    """Try every mix of picks, manifest and hand-added files, and check the safety rules in each one."""
    families = ["Atkinson Hyperlegible", "Literata", "Lexend"]  # Lexend: in the manifest, not the catalogue
    lexend = {"Lexend-Regular.ttf": ManifestEntry("Lexend", "abc")}
    hand_added = ["MyOwnFont-Regular.ttf", "literata-bold.ttf"]  # the second clashes with Literata's Bold

    def subsets(items):
        return itertools.chain.from_iterable(itertools.combinations(items, n) for n in range(len(items) + 1))

    for picks in subsets(families):
        for in_manifest in subsets(families):
            manifest = {}
            for name in in_manifest:
                manifest.update(lexend if name == "Lexend" else installed(two_families, name))
            for added in subsets(hand_added):
                if any(name.casefold() in {m.casefold() for m in manifest} for name in added):
                    continue  # a file can't be both in the manifest and hand-added
                for deleted_on_kobo in (False, True):
                    on_kobo = set(manifest) | set(added)
                    if deleted_on_kobo and manifest:
                        on_kobo.discard(sorted(manifest)[0])

                    plan = plan_font_sync(set(picks), two_families, manifest, on_kobo)

                    not_ours = {name.casefold() for name in on_kobo} - {name.casefold() for name in manifest}
                    assert all(name in manifest for name in plan.remove + plan.forget)
                    assert all(step.kobo_name.casefold() not in not_ours for step in plan.install)
                    assert all(name.casefold() not in not_ours for name in plan.remove)
