"""Auto-sync: push by itself when the Kobo is plugged in (DESIGN.md section 6, R14, D37–D42).

A systemd user service runs `kraken autosync watch`, which checks every few seconds whether the
Kobo is mounted. `kraken autosync on` and `off` write that service's unit file and switch it on or off.
"""

import logging
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from kraken.fonts import PicksError
from kraken.kobo import KoboError, find_kobo
from kraken.lock import BusyError
from kraken.notify import notify
from kraken.push import run_push
from kraken.settings import SettingsError, config_dir

log = logging.getLogger("kraken")

CHECK_EVERY = 3  # seconds between checks
SETTLED_AFTER = 2  # checks in a row that must see the Kobo before pushing (D37)
UNIT_NAME = "kraken-autosync.service"


class AutosyncError(Exception):
    """Switching auto-sync on or off didn't work. The message says why."""


# --- The watcher ---


class PlugInTracker:
    """Decides when to push: once per plug-in, after the Kobo has settled (D37, D38, D41).

    It starts as if the Kobo were absent, so a Kobo that's already connected gets pushed (D41).
    """

    def __init__(self) -> None:
        self.seen_in_a_row = 0
        self.pushed = False

    def should_push(self, kobo_is_there: bool) -> bool:
        """Called after each check. True means "push now"."""
        if not kobo_is_there:
            self.seen_in_a_row = 0
            self.pushed = False  # it's gone, so the next time it appears is a new plug-in
            return False
        self.seen_in_a_row += 1
        if self.seen_in_a_row >= SETTLED_AFTER and not self.pushed:
            self.pushed = True  # set even if the push fails: no retries until the next plug-in (D39)
            return True
        return False


def kobo_is_there() -> bool:
    """Is a Kobo mounted? One that fails the safety checks counts, so that push can explain the problem."""
    try:
        return find_kobo() is not None
    except KoboError:
        return True


def push_once(push: Callable[[], int] = run_push) -> None:
    """Run one push for the watcher. Nothing it raises stops the watcher."""
    try:
        push()
    except BusyError:
        log.info("Kobo plugged in while another kraken was running: auto-sync stepped aside (D40).")
    except (PicksError, SettingsError) as error:
        log.error("%s", error)
        notify("kraken stopped", str(error))
    except Exception:  # a bug: write it in the log, tell the person, and keep watching
        log.exception("Auto-sync push failed unexpectedly")
        notify("kraken stopped", "Something unexpected went wrong. The details are in kraken's log.")


def watch(is_there: Callable[[], bool] = kobo_is_there, push: Callable[[], None] = push_once,
          sleep: Callable[[float], None] = time.sleep) -> None:
    """Check for the Kobo every few seconds, forever, and push once per plug-in.

    The three helpers can be swapped for pretend ones in tests, so no real time passes.
    """
    log.info("Auto-sync is watching for the Kobo.")
    tracker = PlugInTracker()
    while True:
        if tracker.should_push(is_there()):
            push()
        sleep(CHECK_EVERY)


# --- Switching it on and off ---


def unit_path() -> Path:
    """~/.config/systemd/user/kraken-autosync.service, where systemd looks for a user's own services."""
    return config_dir().parent / "systemd" / "user" / UNIT_NAME


def kraken_command() -> Path:
    """The `kraken` command in the same folder as the Python running now (the project's .venv/bin)."""
    return Path(sys.executable).parent / "kraken"


def unit_text(command: Path) -> str:
    """The unit file: a small settings file that tells systemd how to run the watcher."""
    return f"""[Unit]
Description=kraken auto-sync: push to the Kobo when it is plugged in

[Service]
ExecStart="{command}" autosync watch
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
"""


Runner = Callable[[list[str]], subprocess.CompletedProcess]


def _run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, timeout=30)


def _systemctl(*words: str, run: Runner = _run) -> subprocess.CompletedProcess:
    """Run `systemctl --user ...` and raise AutosyncError if it fails."""
    command = ["systemctl", "--user", *words]
    try:
        completed = run(command)
    except (OSError, subprocess.SubprocessError) as error:
        raise AutosyncError(f"Couldn't run systemctl: {error}") from error
    if completed.returncode != 0:
        raise AutosyncError(f"`{' '.join(command)}` failed: {completed.stderr.strip()}")
    return completed


def turn_on(command: Path | None = None, run: Runner = _run) -> None:
    """Write the unit file, then switch the service on now and at every log-in.

    Running it again rewrites the file and restarts the service, which also fixes a moved .venv.
    """
    command = command or kraken_command()
    if not command.exists():
        raise AutosyncError(f"Can't find the kraken command at {command}.")
    path = unit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(unit_text(command))
    _systemctl("daemon-reload", run=run)  # tell systemd to read the new file
    _systemctl("enable", UNIT_NAME, run=run)  # start it at every log-in
    _systemctl("restart", UNIT_NAME, run=run)  # and start it now (or restart it with the new file)


def turn_off(run: Runner = _run) -> bool:
    """Switch the service off and delete its unit file. Returns False if it was already off."""
    path = unit_path()
    if not path.exists():
        return False
    _systemctl("disable", "--now", UNIT_NAME, run=run)
    path.unlink()
    _systemctl("daemon-reload", run=run)
    return True


def status(run: Runner = _run) -> str:
    """'on', 'off', or 'not running' (switched on, but the service isn't running) (D42)."""
    if not unit_path().exists():
        return "off"
    # is-active answers on its standard output, and fails when the answer is "no", so no _systemctl here.
    try:
        answer = run(["systemctl", "--user", "is-active", UNIT_NAME]).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        answer = "unknown"
    return "on" if answer == "active" else "not running"
