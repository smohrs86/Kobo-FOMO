"""Tests for kraken push, the lock and notifications. Uses the fake Kobo and pretend home from conftest.py."""

import subprocess

import pytest

from kraken import notify as notify_module
from kraken import push as push_module
from kraken.cli import main
from kraken.fonts import catalogue_dir, fonts_on_kobo, read_manifest, write_picks
from kraken.kobo import KoboError
from kraken.lock import BusyError, kraken_lock
from kraken.settings import settings_path, state_dir
from helpers import make_family

LITERATA = ["Literata-Regular.ttf", "Literata-Bold.ttf"]


@pytest.fixture
def desk(fake_kobo, monkeypatch):
    """Everything push talks to, with pretend versions that record what happened."""

    class Desk:
        kobo = fake_kobo
        ejected = []
        notifications = []

    desk = Desk()
    monkeypatch.setattr(push_module, "find_kobo", lambda: desk.kobo)
    monkeypatch.setattr(push_module, "eject", lambda kobo: desk.ejected.append(kobo))
    monkeypatch.setattr(push_module, "notify", lambda title, message: desk.notifications.append((title, message)))
    make_family(catalogue_dir(), "Literata", LITERATA)
    write_picks({"Literata"})
    return desk


def test_push_installs_ticked_fonts_ejects_and_notifies(desk, capsys):
    assert main(["push"]) == 0

    assert fonts_on_kobo(desk.kobo) == set(LITERATA)
    assert desk.ejected == [desk.kobo]
    assert desk.notifications == [("kraken", "Fonts: 2 installed, 0 removed. Safe to unplug.")]
    assert "Fonts: 2 installed, 0 removed." in capsys.readouterr().out


def test_second_push_has_nothing_to_do(desk):
    main(["push"])
    assert main(["push"]) == 0
    assert desk.notifications[-1] == ("kraken", "Fonts: already up to date. Safe to unplug.")


def test_push_writes_the_log(desk):
    main(["push"])
    log = (state_dir() / "kraken.log").read_text()
    assert "Kobo found at" in log and "Fonts: 2 installed" in log


def test_dry_run_changes_nothing(desk, capsys):
    assert main(["push", "--dry-run"]) == 0

    out = capsys.readouterr().out
    assert "would install  Literata-Regular.ttf   (Literata)" in out
    assert "Then it would eject the Kobo." in out
    assert fonts_on_kobo(desk.kobo) == set()
    assert read_manifest(desk.kobo) == {}
    assert desk.ejected == [] and desk.notifications == []


def test_no_kobo_says_how_to_connect(desk, monkeypatch, capsys):
    monkeypatch.setattr(push_module, "find_kobo", lambda: None)
    assert main(["push"]) == 1
    assert "No Kobo found" in capsys.readouterr().out
    assert desk.ejected == []


def test_unsafe_drive_stops_and_notifies(desk, monkeypatch):
    def not_a_kobo():
        raise KoboError("The drive is labelled KOBOeReader but has no .kobo folder")

    monkeypatch.setattr(push_module, "find_kobo", not_a_kobo)
    assert main(["push"]) == 1
    assert desk.notifications == [("kraken stopped", "The drive is labelled KOBOeReader but has no .kobo folder")]
    assert desk.ejected == []


def test_damaged_manifest_stops_before_changing_anything(desk):
    manifest = desk.kobo.mount / ".kraken" / "manifest.json"
    manifest.parent.mkdir()
    manifest.write_text("not json")

    assert main(["push"]) == 1
    assert fonts_on_kobo(desk.kobo) == set()
    assert desk.ejected == []  # left connected, so you can look
    assert desk.notifications[0][0] == "kraken stopped"


def test_eject_failure_is_reported(desk, monkeypatch, capsys):
    def busy(kobo):
        raise KoboError("Couldn't eject the Kobo (target is busy). Eject it from the file manager before unplugging.")

    monkeypatch.setattr(push_module, "eject", busy)
    assert main(["push"]) == 1
    [(title, message)] = desk.notifications
    assert "Eject it from the file manager" in message and "1 problem(s)" in message


def test_settings_can_turn_off_eject_and_notify(desk):
    settings_path().parent.mkdir(parents=True)
    settings_path().write_text("[autosync]\neject_after_push = false\nnotify = false\n")

    assert main(["push"]) == 0
    assert fonts_on_kobo(desk.kobo) == set(LITERATA)
    assert desk.ejected == [] and desk.notifications == []


def test_settings_typo_is_explained(desk, capsys):
    settings_path().parent.mkdir(parents=True)
    settings_path().write_text("[autosync]\nnotfy = false\n")
    assert main(["push"]) == 1
    assert "unknown setting 'notfy'" in capsys.readouterr().out


def test_push_waits_its_turn(desk, capsys):
    with kraken_lock():  # another kraken is busy
        assert main(["push"]) == 1
    assert "Another kraken is already running" in capsys.readouterr().out
    assert fonts_on_kobo(desk.kobo) == set()


# --- The lock on its own ---


def test_lock_is_released_afterwards():
    with kraken_lock():
        pass
    with kraken_lock():  # free again
        pass


def test_lock_is_released_even_after_an_error():
    with pytest.raises(ValueError):
        with kraken_lock():
            raise ValueError("kraken crashed")
    with kraken_lock():
        pass


def test_second_lock_is_refused_while_the_first_is_held():
    with kraken_lock():
        with pytest.raises(BusyError):
            with kraken_lock():
                pass


# --- Notifications on their own ---


def test_missing_notify_send_does_not_fail(monkeypatch):
    def not_installed(*args, **kwargs):
        raise FileNotFoundError("notify-send")

    monkeypatch.setattr(subprocess, "run", not_installed)
    notify_module.notify("kraken", "hello")  # no exception


def test_notification_command(monkeypatch):
    commands = []
    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs: commands.append(command))
    notify_module.notify("kraken", "Fonts: 2 installed")
    assert commands == [["notify-send", "--app-name=kraken", "kraken", "Fonts: 2 installed"]]
