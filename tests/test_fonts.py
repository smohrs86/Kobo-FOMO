"""Tests for the font catalogue, using tiny made-up font files."""

from pathlib import Path

import pytest

from kraken.fonts import read_catalogue

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
