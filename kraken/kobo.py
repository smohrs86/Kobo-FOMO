"""Finding the Kobo, and (from step 3) copying to it safely (DESIGN.md sections 1 and 8).

Safety rule 1: before writing anything, check this really is the Kobo. Its drive must be
labelled KOBOeReader *and* have Kobo's own .kobo/ folder.
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path

KOBO_LABEL = "KOBOeReader"
BY_LABEL_DIR = Path("/dev/disk/by-label")  # Linux keeps a shortcut here for every labelled drive
MOUNTS_FILE = Path("/proc/self/mounts")  # Linux's live list of mounted drives


class KoboError(Exception):
    """Something is wrong with the Kobo, so kraken stops. The message says what, in plain words."""


@dataclass(frozen=True)
class Kobo:
    """A connected, checked Kobo."""

    mount: Path  # where its files are, such as /run/media/<user>/KOBOeReader
    device: Path  # the drive itself, such as /dev/sdd, needed for ejecting


def find_kobo(by_label_dir: Path = BY_LABEL_DIR, mounts_file: Path = MOUNTS_FILE) -> Kobo | None:
    """Return the connected Kobo, or None if it isn't connected and mounted yet.

    Raises KoboError if a drive labelled KOBOeReader is mounted but fails the safety checks.
    The two paths can be swapped for pretend ones in tests.
    """
    label_link = by_label_dir / KOBO_LABEL
    if not label_link.exists():
        return None  # not plugged in, or *Connect* not tapped yet
    device = label_link.resolve()

    for mount_device, mount_point, options in _read_mounts(mounts_file):
        if Path(mount_device).resolve() == device:
            return _checked(Kobo(mount=mount_point, device=device), options)

    return None  # plugged in, but the desktop hasn't mounted it yet


def _read_mounts(mounts_file: Path) -> list[tuple[str, Path, list[str]]]:
    """(device, mount point, options) for each line of the mount list."""
    mounts = []
    for line in mounts_file.read_text().splitlines():
        # Each line is: device, mount point, filesystem type, options, then two numbers.
        device, mount_point, _fs_type, options, *_ = line.split()
        mounts.append((device, Path(_unescape(mount_point)), options.split(",")))
    return mounts


def _unescape(field: str) -> str:
    r"""Undo the mount list's escapes: a space is written as \040, a tab as \011, and so on."""
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), field)


def _checked(kobo: Kobo, options: list[str]) -> Kobo:
    """Return the Kobo if it passes the safety checks, or raise KoboError."""
    if not (kobo.mount / ".kobo").is_dir():
        raise KoboError(
            f"The drive at {kobo.mount} is labelled {KOBO_LABEL} but has no .kobo folder, "
            "so it may not be a Kobo. Stopping without changing anything."
        )
    if "ro" in options:
        # Linux makes a drive read-only when it finds errors on it, often after a flaky USB connection.
        raise KoboError(
            f"The Kobo at {kobo.mount} is mounted read-only, so nothing can be copied to it. "
            "Eject it, check the cable, and plug it in again."
        )
    if not os.access(kobo.mount, os.W_OK):
        raise KoboError(f"You don't have permission to write to the Kobo at {kobo.mount}.")
    return kobo
