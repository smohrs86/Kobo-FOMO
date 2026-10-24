"""Tests for the kraken command line. Each runs in the pretend home folder from conftest.py."""

import pytest

from kraken import __version__
from kraken.cli import font_checklist, main
from kraken.fonts import catalogue_dir, picks_path, read_picks, write_picks
from helpers import make_family


def test_version_prints_name_and_version(capsys):
    # argparse prints the version, then exits; SystemExit with code 0 means "success".
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"kraken {__version__}"


def test_no_command_shows_the_help(capsys):
    assert main([]) == 0
    assert "fonts" in capsys.readouterr().out


# --- The checklist on its own ---


def pretend_typing(*answers):
    """Stands in for input(): gives back each answer in turn, as if typed."""
    typed = iter(answers)
    return lambda prompt: next(typed)


def run_checklist(*answers, families=("Atkinson Hyperlegible", "Literata"), missing=(), problems=(), picks=(),
                  no_italic=()):
    screen = []
    result = font_checklist(list(families), list(missing), list(problems), set(picks), set(no_italic),
                            ask=pretend_typing(*answers), show=screen.append)
    return result, "\n".join(screen)


def test_enter_straight_away_keeps_the_picks():
    result, screen = run_checklist("", picks={"Literata"})
    assert result == {"Literata"}
    assert "  1. [ ] Atkinson Hyperlegible" in screen
    assert "  2. [x] Literata" in screen


def test_typing_a_number_ticks_and_unticks():
    result, _ = run_checklist("1", "2", "1", "", picks={"Literata"})
    assert result == set()


def test_several_numbers_at_once():
    result, _ = run_checklist("1, 2", "")
    assert result == {"Atkinson Hyperlegible", "Literata"}


@pytest.mark.parametrize("typo", ["3", "0", "one", "1.5", "-1"])
def test_typos_are_explained_and_change_nothing(typo):
    result, screen = run_checklist(typo, "")
    assert result == set()
    assert "Please type numbers from 1 to 2" in screen


def test_family_gone_from_the_catalogue_can_be_unticked():
    result, screen = run_checklist("2", "", families=["Literata"], missing=["Lexend"], picks={"Lexend"})
    assert "  2. [x] Lexend   (no longer in the catalogue)" in screen
    assert result == set()


def test_unusable_families_are_listed_with_the_reason():
    _, screen = run_checklist("", problems=["Noto Emoji: no Regular or Bold font"])
    assert "Can't be used:\n  Noto Emoji: no Regular or Bold font" in screen


def test_family_without_italic_is_warned_about_but_can_be_ticked():
    result, screen = run_checklist("1", "", no_italic={"Atkinson Hyperlegible"})
    assert "  1. [ ] Atkinson Hyperlegible   (no Italic: the Kobo will show italic text as bold)" in screen
    assert "  2. [ ] Literata\n" in screen  # no warning for a family that has one
    assert result == {"Atkinson Hyperlegible"}


# --- kraken fonts, the whole command ---


@pytest.fixture
def catalogue_with_two_families():
    make_family(catalogue_dir(), "Atkinson Hyperlegible",
                ["AtkinsonHyperlegible-Regular.ttf", "AtkinsonHyperlegible-Bold.ttf"])
    make_family(catalogue_dir(), "Literata", ["Literata-Regular.ttf", "Literata-Bold.ttf"])


def test_kraken_fonts_saves_the_picks(catalogue_with_two_families, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", pretend_typing("2", ""))
    assert main(["fonts"]) == 0
    assert read_picks() == {"Literata"}
    assert "Saved" in capsys.readouterr().out


def test_kraken_fonts_warns_only_about_families_without_italic(catalogue_with_two_families, monkeypatch, capsys):
    make_family(catalogue_dir(), "Lexend", ["Lexend-Regular.ttf", "Lexend-Bold.ttf", "Lexend-Italic.ttf"])
    monkeypatch.setattr("builtins.input", pretend_typing(""))
    main(["fonts"])
    screen = capsys.readouterr().out
    assert "Literata   (no Italic" in screen
    assert "] Lexend\n" in screen  # listed, with no warning


def test_ctrl_c_saves_nothing(catalogue_with_two_families, monkeypatch, capsys):
    write_picks({"Literata"})

    def ctrl_c(prompt):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", ctrl_c)
    assert main(["fonts"]) == 1
    assert read_picks() == {"Literata"}
    assert "Nothing saved" in capsys.readouterr().out


def test_empty_catalogue_says_where_fonts_go(capsys):
    assert main(["fonts"]) == 1
    assert str(catalogue_dir()) in capsys.readouterr().out


def test_damaged_picks_file_is_explained(catalogue_with_two_families, capsys):
    picks_path().parent.mkdir(parents=True, exist_ok=True)
    picks_path().write_text("{ not json")
    assert main(["fonts"]) == 1
    assert "is damaged" in capsys.readouterr().out
