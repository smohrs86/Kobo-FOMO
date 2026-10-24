"""Tests for auto-sync: the watcher's decisions, and switching the service on and off.

No real time passes and no real systemd is touched: pretend versions stand in for both.
"""

import subprocess

import pytest

from kraken import autosync
from kraken.autosync import (
    UNIT_NAME,
    AutosyncError,
    PlugInTracker,
    push_once,
    status,
    turn_off,
    turn_on,
    unit_path,
    unit_text,
    watch,
)
from kraken.cli import main
from kraken.fonts import PicksError
from kraken.kobo import KoboError
from kraken.lock import BusyError

# --- When to push (D37, D38, D39, D41) ---


def pushes_for(*checks):
    """Feed a run of "is the Kobo there?" answers to a tracker; return which checks said "push now"."""
    tracker = PlugInTracker()
    return [number for number, there in enumerate(checks, start=1) if tracker.should_push(there)]


def test_pushes_once_the_kobo_has_been_seen_twice_in_a_row():
    assert pushes_for(False, True, True) == [3]


def test_a_single_sighting_is_not_enough():
    assert pushes_for(True, False, True, False) == []


def test_pushes_only_once_while_it_stays_connected():
    assert pushes_for(True, True, True, True, True) == [2]


def test_unplugging_and_plugging_in_again_pushes_again():
    assert pushes_for(True, True, False, True, True) == [2, 5]


def test_a_kobo_already_there_when_watching_starts_is_pushed():
    assert pushes_for(True, True) == [2]


# --- Is the Kobo there? ---


def test_a_kobo_that_fails_the_safety_checks_counts_as_there(monkeypatch):
    def unsafe():
        raise KoboError("read-only")

    monkeypatch.setattr(autosync, "find_kobo", unsafe)
    assert autosync.kobo_is_there() is True


def test_no_kobo_is_not_there(monkeypatch):
    monkeypatch.setattr(autosync, "find_kobo", lambda: None)
    assert autosync.kobo_is_there() is False


# --- The loop ---


class StopWatching(Exception):
    """Raised by the pretend clock to end the endless loop."""


def test_watch_checks_pushes_and_waits_between_checks():
    answers = iter([False, True, True, True])
    pushes, waits = [], []

    def pretend_sleep(seconds):
        waits.append(seconds)
        if len(waits) == 4:
            raise StopWatching

    with pytest.raises(StopWatching):
        watch(is_there=lambda: next(answers), push=lambda: pushes.append("push"), sleep=pretend_sleep)
    assert pushes == ["push"]
    assert waits == [autosync.CHECK_EVERY] * 4


# --- One push, and what can go wrong (D39, D40) ---


@pytest.fixture
def notifications(monkeypatch):
    shown = []
    monkeypatch.setattr(autosync, "notify", lambda title, message: shown.append((title, message)))
    return shown


def failing(error):
    def push():
        raise error
    return push


def test_busy_steps_aside_quietly(notifications):
    push_once(failing(BusyError("busy")))
    assert notifications == []


def test_a_settings_or_picks_problem_is_shown(notifications):
    push_once(failing(PicksError("The picks file is damaged.")))
    assert notifications == [("kraken stopped", "The picks file is damaged.")]


def test_an_unexpected_error_is_shown_and_does_not_stop_the_watcher(notifications):
    push_once(failing(ZeroDivisionError()))  # returns normally, so the loop carries on
    assert notifications[0][0] == "kraken stopped"


# --- Switching it on and off (D42) ---


class PretendSystemctl:
    """Stands in for running systemctl: records each command, and answers is-active with `active`."""

    def __init__(self, active="active", fail_on=None):
        self.commands = []
        self.active = active
        self.fail_on = fail_on

    def __call__(self, command):
        self.commands.append(command[2:])  # leave out "systemctl --user"
        failed = self.fail_on is not None and self.fail_on in command
        stdout = self.active if "is-active" in command else ""
        return subprocess.CompletedProcess(command, 1 if failed else 0, stdout=stdout, stderr="it broke")


@pytest.fixture
def kraken_script(tmp_path):
    script = tmp_path / "venv" / "bin" / "kraken"
    script.parent.mkdir(parents=True)
    script.write_text("#!/bin/sh\n")
    return script


def test_the_unit_file_runs_the_watcher_and_restarts_it():
    text = unit_text("/somewhere/.venv/bin/kraken")
    assert 'ExecStart="/somewhere/.venv/bin/kraken" autosync watch' in text
    assert "Restart=on-failure" in text
    assert "WantedBy=default.target" in text


def test_on_writes_the_unit_file_and_starts_the_service(kraken_script, pretend_home):
    systemctl = PretendSystemctl()
    turn_on(kraken_script, run=systemctl)

    assert unit_path() == pretend_home / ".config" / "systemd" / "user" / UNIT_NAME
    assert f'ExecStart="{kraken_script}"' in unit_path().read_text()
    assert systemctl.commands == [["daemon-reload"], ["enable", UNIT_NAME], ["restart", UNIT_NAME]]


def test_on_refuses_a_missing_kraken_command(tmp_path):
    with pytest.raises(AutosyncError, match="Can't find the kraken command"):
        turn_on(tmp_path / "nowhere" / "kraken", run=PretendSystemctl())
    assert not unit_path().exists()


def test_a_systemctl_failure_is_explained(kraken_script):
    with pytest.raises(AutosyncError, match="enable.*it broke"):
        turn_on(kraken_script, run=PretendSystemctl(fail_on="enable"))


def test_off_stops_the_service_and_deletes_the_unit_file(kraken_script):
    turn_on(kraken_script, run=PretendSystemctl())
    systemctl = PretendSystemctl()

    assert turn_off(run=systemctl) is True
    assert not unit_path().exists()
    assert systemctl.commands == [["disable", "--now", UNIT_NAME], ["daemon-reload"]]


def test_off_when_already_off_does_nothing():
    systemctl = PretendSystemctl()
    assert turn_off(run=systemctl) is False
    assert systemctl.commands == []


@pytest.mark.parametrize("active, expected", [("active", "on"), ("failed", "not running"), ("inactive", "not running")])
def test_status_when_switched_on(kraken_script, active, expected):
    turn_on(kraken_script, run=PretendSystemctl())
    assert status(run=PretendSystemctl(active=active)) == expected


def test_status_when_off():
    assert status(run=PretendSystemctl()) == "off"


def test_kraken_autosync_on_its_own_says_whether_it_is_on(capsys):
    assert main(["autosync"]) == 0
    assert "Auto-sync is off" in capsys.readouterr().out
