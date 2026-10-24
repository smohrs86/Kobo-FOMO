"""Tests for the font catalogue, using tiny made-up font files."""

import itertools
from pathlib import Path

import pytest

from kraken import fonts as fonts_module
from kraken.fonts import (
    PENDING,
    ManifestEntry,
    apply_font_plan,
    fonts_on_kobo,
    plan_font_sync,
    read_catalogue,
    read_manifest,
    write_manifest,
)
from kraken.kobo import PART_SUFFIX, KoboError, file_hash
from helpers import TRUETYPE_SIGNATURE, make_family

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


# --- Carrying out the plan (step 6), with the fake Kobo from conftest.py ---


def sync(fake_kobo, picks: set[str], catalogue):
    """One whole font sync, the way kraken push will do it: plan, then apply."""
    manifest = read_manifest(fake_kobo)
    plan = plan_font_sync(picks, catalogue, manifest, fonts_on_kobo(fake_kobo))
    return apply_font_plan(fake_kobo, plan, manifest)


def test_kobo_without_a_manifest_has_none(fake_kobo):
    assert read_manifest(fake_kobo) == {}


def test_manifest_is_saved_and_read_back(fake_kobo):
    manifest = {"Literata-Bold.ttf": ManifestEntry("Literata", "abc123")}
    write_manifest(fake_kobo, manifest)
    assert read_manifest(fake_kobo) == manifest
    assert (fake_kobo.mount / ".kraken" / "manifest.json").exists()


@pytest.mark.parametrize("damage", ["not json at all", '{"format": 1}', '{"format": 99, "fonts": {}}', "[]"])
def test_damaged_manifest_stops_the_font_sync(fake_kobo, damage):
    manifest = fake_kobo.mount / ".kraken" / "manifest.json"
    manifest.parent.mkdir()
    manifest.write_text(damage)
    with pytest.raises(KoboError, match="damaged"):
        read_manifest(fake_kobo)


def test_fonts_on_kobo_leaves_out_unfinished_copies(fake_kobo):
    fonts = fake_kobo.mount / "fonts"
    fonts.mkdir()
    (fonts / "Literata-Bold.ttf").write_bytes(b"font")
    (fonts / ("Literata-Regular.ttf" + PART_SUFFIX)).write_bytes(b"half")
    assert fonts_on_kobo(fake_kobo) == {"Literata-Bold.ttf"}


def test_sync_installs_ticked_fonts_and_records_them(fake_kobo, two_families):
    result = sync(fake_kobo, {"Literata"}, two_families)

    assert result.installed == LITERATA and result.problems == []
    assert fonts_on_kobo(fake_kobo) == set(LITERATA)
    assert read_manifest(fake_kobo) == installed(two_families, "Literata")


def test_second_sync_changes_nothing(fake_kobo, two_families):
    sync(fake_kobo, {"Literata"}, two_families)
    manifest = read_manifest(fake_kobo)
    plan = plan_font_sync({"Literata"}, two_families, manifest, fonts_on_kobo(fake_kobo))
    assert not plan.has_changes()


def test_unticking_removes_only_krakens_fonts(fake_kobo, two_families):
    sync(fake_kobo, {"Literata", "Atkinson Hyperlegible"}, two_families)
    (fake_kobo.mount / "fonts" / "MyOwnFont-Regular.ttf").write_bytes(b"added by hand")

    result = sync(fake_kobo, {"Atkinson Hyperlegible"}, two_families)

    assert result.removed == sorted(LITERATA)
    assert fonts_on_kobo(fake_kobo) == {*ATKINSON, "MyOwnFont-Regular.ttf"}
    assert set(read_manifest(fake_kobo)) == set(ATKINSON)


def test_sync_clears_leftovers_from_an_interrupted_run(fake_kobo, two_families):
    leftover = fake_kobo.mount / "fonts" / ("Literata-Bold.ttf" + PART_SUFFIX)
    leftover.parent.mkdir()
    leftover.write_bytes(b"half")
    sync(fake_kobo, set(), two_families)
    assert not leftover.exists()


def test_one_failed_copy_does_not_stop_the_others(fake_kobo, two_families, monkeypatch):
    real_copy = fonts_module.copy_to_kobo

    def bold_fails(kobo, source, destination):
        if destination.name == "Literata-Bold.ttf":
            raise KoboError("Copying Literata-Bold.ttf to the Kobo failed: Input/output error.")
        real_copy(kobo, source, destination)

    monkeypatch.setattr(fonts_module, "copy_to_kobo", bold_fails)
    result = sync(fake_kobo, {"Literata"}, two_families)

    assert result.installed == ["Literata-Regular.ttf"]
    assert result.problems == ["Copying Literata-Bold.ttf to the Kobo failed: Input/output error."]
    assert read_manifest(fake_kobo)["Literata-Bold.ttf"].sha256 == PENDING  # so the next push retries


def test_cable_pulled_mid_sync_is_finished_next_time(fake_kobo, two_families, monkeypatch):
    """The manifest is saved before copying, so an interrupted sync can't lose track of kraken's files."""
    real_copy = fonts_module.copy_to_kobo
    copies = []

    def cable_pulled_on_second_font(kobo, source, destination):
        if destination.parent.name == "fonts":
            copies.append(destination.name)
            if len(copies) == 2:
                raise RuntimeError("cable pulled")  # not a KoboError: kraken just stops here
        real_copy(kobo, source, destination)

    monkeypatch.setattr(fonts_module, "copy_to_kobo", cable_pulled_on_second_font)
    with pytest.raises(RuntimeError):
        sync(fake_kobo, {"Literata"}, two_families)

    manifest = read_manifest(fake_kobo)
    assert set(manifest) == set(LITERATA)  # both names are still claimed as kraken's
    assert all(entry.sha256 == PENDING for entry in manifest.values())

    # Plugged in again: kraken finishes the job, instead of treating its own file as hand-added.
    monkeypatch.setattr(fonts_module, "copy_to_kobo", real_copy)
    result = sync(fake_kobo, {"Literata"}, two_families)
    assert result.installed == LITERATA and result.problems == []
    assert read_manifest(fake_kobo) == installed(two_families, "Literata")


def test_interrupted_font_that_is_then_unticked_is_removed(fake_kobo, two_families):
    """A pending entry still means "kraken's file", so unticking cleans it up."""
    fonts = fake_kobo.mount / "fonts"
    fonts.mkdir()
    (fonts / "Literata-Regular.ttf").write_bytes(b"copied before the cable was pulled")
    write_manifest(fake_kobo, {"Literata-Regular.ttf": ManifestEntry("Literata", PENDING)})

    result = sync(fake_kobo, set(), two_families)
    assert result.removed == ["Literata-Regular.ttf"]
    assert read_manifest(fake_kobo) == {}
