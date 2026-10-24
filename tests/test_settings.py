"""Tests for kraken's folders and settings."""

from pathlib import Path

import pytest

from kraken.settings import (
    DEFAULT_SETTINGS_TEXT,
    SettingsError,
    config_dir,
    load_settings,
    state_dir,
)


@pytest.fixture(autouse=True)
def pretend_home(tmp_path, monkeypatch):
    """Run every test in a temporary home folder, so the real ~/.config is never touched."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for variable in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
        monkeypatch.delenv(variable, raising=False)
    return tmp_path


def write_settings(home: Path, text: str) -> None:
    path = home / ".config" / "kraken" / "settings.toml"
    path.parent.mkdir(parents=True)
    path.write_text(text)


# --- Folders ---


def test_folders_default_to_the_xdg_places_in_home(pretend_home):
    assert config_dir() == pretend_home / ".config" / "kraken"
    assert state_dir() == pretend_home / ".local" / "state" / "kraken"


def test_xdg_variable_moves_a_folder(pretend_home, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(pretend_home / "elsewhere"))
    assert config_dir() == pretend_home / "elsewhere" / "kraken"


def test_relative_xdg_variable_is_ignored(pretend_home, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", "not/absolute")
    assert config_dir() == pretend_home / ".config" / "kraken"


# --- First run ---


def test_first_run_creates_settings_file_with_defaults(pretend_home):
    settings = load_settings()

    created = pretend_home / ".config" / "kraken" / "settings.toml"
    assert created.read_text() == DEFAULT_SETTINGS_TEXT
    assert settings.strength == 0.30
    assert settings.inbox == pretend_home / "KRAKEN"
    assert settings.eject_after_push is True
    assert settings.notify is True


def test_existing_settings_file_is_not_overwritten(pretend_home):
    write_settings(pretend_home, "[boldstart]\nstrength = 0.35\n")
    load_settings()
    assert "0.35" in (pretend_home / ".config" / "kraken" / "settings.toml").read_text()


# --- Reading your settings ---


def test_changed_values_are_used(pretend_home):
    write_settings(pretend_home, '[boldstart]\nstrength = 0.4\n[folders]\ninbox = "/tmp/books"\n')
    settings = load_settings()
    assert settings.strength == 0.4
    assert settings.inbox == Path("/tmp/books")


def test_missing_settings_fall_back_to_defaults(pretend_home):
    write_settings(pretend_home, "[autosync]\nnotify = false\n")
    settings = load_settings()
    assert settings.notify is False
    assert settings.strength == 0.30


def test_whole_number_strength_is_allowed(pretend_home):
    write_settings(pretend_home, "[boldstart]\nstrength = 1\n")
    assert load_settings().strength == 1.0


# --- Mistakes give clear messages ---


@pytest.mark.parametrize(
    "text, message",
    [
        ("[boldstart]\nstrenght = 0.3\n", "unknown setting 'strenght' in [boldstart]"),
        ("[bold-start]\nstrength = 0.3\n", "unknown section [bold-start]"),
        ('[boldstart]\nstrength = "0.3"\n', "strength should be a number"),
        ("[boldstart]\nstrength = true\n", "strength should be a number"),
        ("[autosync]\nnotify = 1\n", "notify should be true or false"),
        ("[folders]\ninbox = 5\n", "inbox should be text in quotes"),
        ("[boldstart]\nstrength = 0\n", "strength must be more than 0 and at most 1"),
        ("[boldstart]\nstrength = 30\n", "strength must be more than 0 and at most 1"),
        ("[boldstart\nstrength = 0.3\n", "isn't valid TOML"),
    ],
)
def test_mistakes_are_reported_in_plain_words(pretend_home, text, message):
    write_settings(pretend_home, text)
    with pytest.raises(SettingsError, match=message.replace("[", r"\[")):
        load_settings()
