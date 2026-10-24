"""The lock: only one kraken works on the Kobo at a time (DESIGN.md section 3, D34).

It uses flock, the operating system's own file locking. The OS releases the lock when
kraken finishes, even if it crashes, so a stale "busy" lock can never get stuck.
"""

import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from kraken.settings import state_dir


class BusyError(Exception):
    """Another kraken is already running."""


def lock_path() -> Path:
    """~/.local/state/kraken/kraken.lock"""
    return state_dir() / "kraken.lock"


@contextmanager
def kraken_lock(path: Path | None = None) -> Iterator[None]:
    """Hold the lock for the length of a `with` block, or raise BusyError straight away if it's taken."""
    path = path or lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as lock_file:
        try:
            # LOCK_EX: only one holder at a time. LOCK_NB: don't wait, say so if it's taken.
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BusyError("Another kraken is already running. Wait for it to finish, then try again.") from None
        yield
    # Closing the file releases the lock.
