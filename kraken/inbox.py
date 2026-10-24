"""The inbox, ~/KRAKEN/: which files are waiting, and filing them afterwards (DESIGN.md section 1; D49–D51).

Only files sitting directly in the inbox are looked at. sent/ and skipped/ are sub-folders, so a book
filed there is never sent again, which is how a book deleted on the Kobo stays deleted (D22).
"""

import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

WAIT_SECONDS = 10                       # D50: a file changed more recently than this may still be arriving
UNFINISHED = (".part", ".crdownload")   # D50: downloads still in progress (Firefox, Chrome)
FAT_FORBIDDEN = '\\:*?"<>|'             # D51: characters the Kobo's FAT drive can't store
KOBO_FOLDER = Path("kraken")            # where books go on the Kobo
NOTE_SUFFIX = ".why.txt"                # D53: the note beside a file in skipped/


@dataclass
class Waiting:
    """What's in the inbox, sorted into groups. Each group is sorted by name."""

    books: list[Path] = field(default_factory=list)      # EPUBs ready to send
    later: list[Path] = field(default_factory=list)      # other files, for a later version of kraken (D49)
    too_new: list[Path] = field(default_factory=list)    # changed in the last few seconds (D50)
    clashes: list[tuple[Path, Path]] = field(default_factory=list)  # (waits, the book it clashes with)


def scan_inbox(inbox: Path, now: float | None = None) -> Waiting:
    """Sort the files in the inbox into groups. Changes nothing. `now` is for the tests."""
    now = time.time() if now is None else now
    waiting = Waiting()
    if not inbox.is_dir():
        return waiting

    names_taken = {}  # the book's name on the Kobo, in lowercase -> the book that has it
    for path in sorted(inbox.iterdir()):
        if not path.is_file() or path.name.startswith(".") or path.suffix.lower() in UNFINISHED:
            continue
        if abs(now - path.stat().st_mtime) < WAIT_SECONDS:  # abs(): a date in the future doesn't wait forever
            waiting.too_new.append(path)
        elif path.suffix.lower() != ".epub":
            waiting.later.append(path)
        else:
            # FAT ignores upper and lower case, so "Alice.epub" and "alice.epub" would be the same file there.
            key = str(kobo_name(path)).casefold()
            if key in names_taken:
                waiting.clashes.append((path, names_taken[key]))
            else:
                names_taken[key] = path
                waiting.books.append(path)
    return waiting


def kobo_name(path: Path) -> Path:
    """The book's place on the Kobo: research report.epub -> kraken/research report.epub (D51).

    A Kobo-format book (Alice.kepub.epub) loses its ".kepub", because kraken sends plain EPUBs (D54).
    """
    stem = path.stem
    if stem.lower().endswith(".kepub"):
        stem = stem[: -len(".kepub")]
    stem = "".join("_" if letter in FAT_FORBIDDEN else letter for letter in stem)
    return KOBO_FOLDER / f"{stem}.epub"


def file_sent(inbox: Path, path: Path) -> Path:
    """Move a file to sent/ once its book is verified on the Kobo. Returns where it went.

    An older original with the same name on the Kobo is replaced, so sent/ keeps one original per book.
    """
    sent = inbox / "sent"
    sent.mkdir(exist_ok=True)
    key = str(kobo_name(path)).casefold()
    for older in sent.iterdir():
        if older.is_file() and str(kobo_name(older)).casefold() == key:
            older.unlink()
    destination = sent / path.name
    os.replace(path, destination)  # a rename: instant, and replaces a file of the same name
    return destination


def file_skipped(inbox: Path, path: Path, reason: str) -> Path:
    """Move a file kraken can't use to skipped/, with a note saying why. Returns where it went.

    `reason` reads on from "because", for example a CheckError: "it has no table of contents (...)".
    """
    skipped = inbox / "skipped"
    skipped.mkdir(exist_ok=True)
    destination = skipped / path.name
    os.replace(path, destination)
    when = datetime.now().strftime("%Y-%m-%d %H:%M")
    note = skipped / (path.name + NOTE_SUFFIX)
    note.write_text(
        f"kraken didn't send {path.name} ({when}) because {reason}.\n\n"
        f"To try again, fix the file and drop it in {inbox} again.\n"
    )
    return destination
