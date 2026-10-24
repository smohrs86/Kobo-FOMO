"""Finding the Kobo, and copying to it safely (DESIGN.md sections 1 and 8).

Safety rule 1: before writing anything, check this really is the Kobo. Its drive must be
labelled KOBOeReader *and* have Kobo's own .kobo/ folder.
Safety rule 2: never write inside .kobo/.
Safety rule 4: check there's enough free space before copying.
"""

import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

KOBO_LABEL = "KOBOeReader"
BY_LABEL_DIR = Path("/dev/disk/by-label")  # Linux keeps a shortcut here for every labelled drive
MOUNTS_FILE = Path("/proc/self/mounts")  # Linux's live list of mounted drives

# A copy in progress is written under this ending, then renamed when it's verified. The ending is
# kraken's own, so a leftover from an interrupted copy can be recognised and safely removed.
PART_SUFFIX = ".kraken.part"

# Room left free for the Kobo itself: its database grows as you read.
SPACE_TO_LEAVE_FREE = 50 * 1024 * 1024  # 50 MB


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


def copy_to_kobo(kobo: Kobo, source: Path, destination: Path) -> None:
    """Copy `source` to `destination` (a path inside the Kobo, such as fonts/Literata-Regular.ttf).

    The copy is written as a .kraken.part file, flushed to the device, read back from the device
    and compared with the original, and only then renamed to its real name. So the real name never
    points at a half-written or damaged file. An existing file with that name is replaced.
    Raises KoboError if anything goes wrong; the Kobo is then left as it was.
    """
    target = _safe_target(kobo, destination)
    _check_free_space(kobo, source)

    part = target.with_name(target.name + PART_SUFFIX)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        _write_to_device(source, part)
        if file_hash(part) != file_hash(source):
            raise KoboError(
                f"The copy of {source.name} on the Kobo doesn't match the original. "
                "Nothing was changed. Check the cable and try again."
            )
        os.replace(part, target)  # a rename: instant, so the real name is never half-written
        _flush_folder(target.parent)
    except OSError as error:
        raise KoboError(f"Copying {source.name} to the Kobo failed: {error.strerror}.") from error
    finally:
        part.unlink(missing_ok=True)


def remove_leftover_parts(kobo: Kobo, folder: Path) -> list[Path]:
    """Delete unfinished copies left in `folder` on the Kobo by an interrupted run. Returns what was deleted.

    Only files with kraken's own .kraken.part ending are touched (safety rule 3).
    """
    target = _safe_target(kobo, folder)
    leftovers = sorted(target.glob("*" + PART_SUFFIX)) if target.is_dir() else []
    for leftover in leftovers:
        leftover.unlink()
    return leftovers


def _safe_target(kobo: Kobo, destination: Path) -> Path:
    """The full path for `destination` on the Kobo, or raise KoboError if it's somewhere kraken mustn't write."""
    if destination.is_absolute() or ".." in destination.parts or not destination.parts:
        raise KoboError(f"Refusing to write to {destination}: it must be a plain path inside the Kobo.")
    # The Kobo's drive ignores upper and lower case (.KOBO is the same folder as .kobo), so compare in lower case.
    if destination.parts[0].lower() == ".kobo":
        raise KoboError(f"Refusing to write to {destination}: kraken never writes inside .kobo/.")
    return kobo.mount / destination


def _check_free_space(kobo: Kobo, source: Path) -> None:
    needed = source.stat().st_size + SPACE_TO_LEAVE_FREE
    free = shutil.disk_usage(kobo.mount).free
    if free < needed:
        raise KoboError(
            f"Not enough room on the Kobo for {source.name}: it needs {_megabytes(needed)} "
            f"(including {_megabytes(SPACE_TO_LEAVE_FREE)} kept free for the Kobo), "
            f"and {_megabytes(free)} is free. Delete some books on the Kobo and try again."
        )


def _write_to_device(source: Path, part: Path) -> None:
    """Copy source to part, make sure it has really reached the device, then forget the in-memory copy.

    Linux keeps recently written data in memory (the "page cache"). Without the last step, reading the
    file back would read that memory instead of the Kobo, and the check would always pass.
    """
    with source.open("rb") as reader, part.open("wb") as writer:
        shutil.copyfileobj(reader, writer)
        writer.flush()  # from Python's buffer to Linux
        os.fsync(writer.fileno())  # from Linux to the device; waits until the device has it
        os.posix_fadvise(writer.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)  # drop the memory copy


def _flush_folder(folder: Path) -> None:
    """Make sure the rename itself has reached the device, not just the file's contents."""
    descriptor = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def file_hash(path: Path) -> str:
    """A SHA-256 fingerprint of the file: any change to the file, however small, changes it."""
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def _megabytes(size: int) -> str:
    return f"{size / (1024 * 1024):.0f} MB"


# Safety rule 3, never delete a book: the only folder kraken may delete files from.
DELETABLE_FOLDERS = ("fonts",)


def delete_from_kobo(kobo: Kobo, destination: Path) -> None:
    """Delete one file on the Kobo, such as fonts/Literata-Bold.ttf. Only files in fonts/ can be deleted.

    The caller must only ask to delete files kraken installed (the ones in the manifest, D18).
    """
    target = _safe_target(kobo, destination)
    if len(destination.parts) < 2 or destination.parts[0].casefold() not in DELETABLE_FOLDERS:
        raise KoboError(f"Refusing to delete {destination}: kraken only ever deletes fonts it installed.")
    try:
        target.unlink(missing_ok=True)
        _flush_folder(target.parent)
    except OSError as error:
        raise KoboError(f"Deleting {destination} from the Kobo failed: {error.strerror}.") from error


def eject(kobo: Kobo) -> None:
    """Eject the Kobo safely: unmount it, then power it off. The same two steps as doing it by hand.

    Unmounting also makes Linux finish writing anything still waiting in memory. If it fails (for
    example because a file manager has the Kobo open), the Kobo isn't powered off.
    """
    for action in ("unmount", "power-off"):
        # --no-user-interaction: fail straight away rather than wait for a password prompt nobody sees.
        command = ["udisksctl", action, "--block-device", str(kobo.device), "--no-user-interaction"]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as error:
            raise KoboError(f"Couldn't eject the Kobo: {error}") from error
        if completed.returncode != 0:
            reason = completed.stderr.strip() or f"udisksctl {action} failed"
            raise KoboError(f"Couldn't eject the Kobo ({reason}). Eject it from the file manager before unplugging.")
