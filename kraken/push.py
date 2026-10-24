"""`kraken push` (DESIGN.md sections 0, 2, 3 and 6).

Find the Kobo, plan the font sync (reading only), send the waiting books, sync the fonts, eject, notify.
Books go before fonts. Each book is checked, bolded in a temporary folder, checked again, then copied and
verified on the Kobo; only then is its original filed in sent/.
"""

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from boldstart.epub import EpubError, bold_epub
from kraken.checks import CheckError, check_bolded, check_book
from kraken.fonts import (
    FontPlan,
    FontSyncResult,
    apply_font_plan,
    fonts_on_kobo,
    plan_font_sync,
    read_catalogue,
    read_manifest,
    read_picks,
)
from kraken.inbox import KOBO_FOLDER, Waiting, file_sent, file_skipped, kobo_name, scan_inbox
from kraken.kobo import Kobo, KoboError, copy_to_kobo, eject, find_kobo, remove_leftover_parts
from kraken.lock import kraken_lock
from kraken.notify import notify
from kraken.settings import Settings, load_settings

log = logging.getLogger("kraken")


@dataclass
class BookResult:
    """What happened to the waiting books, for the summary and the log."""

    sent: list[Path] = field(default_factory=list)      # the books' names on the Kobo
    skipped: list[str] = field(default_factory=list)    # file names, now in skipped/ with a note
    problems: list[str] = field(default_factory=list)   # books that stay in the inbox, to try again next time


def say(message: str) -> None:
    """Tell the person at the terminal, and write it in the log."""
    print(message)
    log.info(message)


def run_push(dry_run: bool = False) -> int:
    """Run a push. Returns 0 if everything worked, 1 if something needs your attention."""
    settings = load_settings()
    with kraken_lock():
        try:
            kobo = find_kobo()
        except KoboError as error:
            return _stop(settings, str(error))
        if kobo is None:
            say("No Kobo found. Plug it in, tap Connect on the Kobo, then try again.")
            return 1
        say(f"Kobo found at {kobo.mount}")

        try:
            manifest = read_manifest(kobo)
            plan = plan_font_sync(read_picks(), read_catalogue(), manifest, fonts_on_kobo(kobo))
        except KoboError as error:
            return _stop(settings, str(error))
        for warning in plan.warnings:
            say(f"Note: {warning}")

        waiting = scan_inbox(settings.inbox)
        _describe_waiting(waiting)
        if dry_run:
            _describe(plan, waiting, settings)
            return 0

        settings.inbox.mkdir(parents=True, exist_ok=True)  # so the inbox is there to drop books in
        try:
            books = send_books(kobo, waiting.books, settings)
            fonts = apply_font_plan(kobo, plan, manifest)
        except KoboError as error:
            return _stop(settings, str(error))
        problems = books.problems + fonts.problems
        for problem in problems:
            say(f"Problem: {problem}")

        summary = f"{_book_summary(waiting, books)} {_font_summary(fonts)}"
        if settings.eject_after_push:
            try:
                eject(kobo)
                summary += " Safe to unplug."
            except KoboError as error:
                problems.append(str(error))
                summary += f" {error}"

        if problems:
            summary += f" {len(problems)} problem(s): see the terminal or the log."
        say(summary)
        if settings.notify:
            notify("kraken", summary)
        return 1 if problems else 0


def send_books(kobo: Kobo, books: list[Path], settings: Settings) -> BookResult:
    """Send each book to the Kobo. One bad book never stops the others (safety rule 5)."""
    result = BookResult()
    remove_leftover_parts(kobo, KOBO_FOLDER)
    for book in books:
        try:
            _send_book(kobo, book, settings, result)
        except KoboError as error:
            result.problems.append(f"{book.name} stays in the inbox: {error}")
        except Exception as error:  # a bug in kraken: this book waits, and the others still go
            log.exception("Unexpected error sending %s", book.name)
            result.problems.append(f"{book.name} stays in the inbox: kraken hit an unexpected error ({error})")
    return result


def _send_book(kobo: Kobo, book: Path, settings: Settings, result: BookResult) -> None:
    """Check, bold, check again, copy and verify, then file the original. Raises KoboError if the copy fails."""
    destination = kobo_name(book)
    with tempfile.TemporaryDirectory(prefix="kraken-") as folder:  # D52: deleted afterwards, whatever happens
        bolded = Path(folder) / destination.name
        try:
            check_book(book)
            bold_epub(book, bolded, settings.strength)
            _check_our_copy(bolded)
        except (CheckError, EpubError) as error:
            file_skipped(settings.inbox, book, str(error))
            result.skipped.append(book.name)
            say(f"Skipped {book.name}: {error}")
            return
        copy_to_kobo(kobo, bolded, destination)
    file_sent(settings.inbox, book)
    result.sent.append(destination)
    say(f"Sent {book.name}  ->  {destination}")


def _check_our_copy(bolded: Path) -> None:
    """check_bolded, with a reason that makes clear it's kraken's copy that failed, not your book."""
    try:
        check_bolded(bolded)
    except CheckError as error:
        raise CheckError(f"kraken's bold-start copy failed its check ({error})") from error


def _stop(settings: Settings, message: str) -> int:
    """Something went wrong before anything was changed: say so, and leave the Kobo connected."""
    say(f"Stopped: {message}")
    if settings.notify:
        notify("kraken stopped", message)
    return 1


def _describe_waiting(waiting: Waiting) -> None:
    """Name the files that stay in the inbox this time, and why."""
    for path in waiting.later:
        say(f"Waiting: {path.name} (kraken can't send this kind of file yet)")  # D49
    for path in waiting.too_new:
        say(f"Waiting: {path.name} (it changed in the last few seconds, so it may still be arriving)")  # D50
    for path, other in waiting.clashes:
        say(f"Waiting: {path.name} (it would have the same name on the Kobo as {other.name}: rename one)")


def _book_summary(waiting: Waiting, result: BookResult) -> str:
    still_waiting = len(waiting.later) + len(waiting.too_new) + len(waiting.clashes) + len(result.problems)
    parts = []
    if result.sent:
        parts.append(f"{len(result.sent)} sent")
    if result.skipped:
        parts.append(f"{len(result.skipped)} skipped (see skipped/)")
    if still_waiting:
        parts.append(f"{still_waiting} waiting")
    return f"Books: {', '.join(parts)}." if parts else "Books: none waiting."


def _font_summary(result: FontSyncResult) -> str:
    if not (result.installed or result.removed):
        return "Fonts: already up to date."
    return f"Fonts: {len(result.installed)} installed, {len(result.removed)} removed."


def _describe(plan: FontPlan, waiting: Waiting, settings: Settings) -> None:
    """--dry-run: show what push would do, without doing it (D32). Books are checked but not bolded."""
    say("Dry run: nothing has been changed.")
    if not waiting.books:
        say("Books: none to send.")
    for book in waiting.books:
        try:
            check_book(book)
            say(f"  would send     {book.name}  ->  {kobo_name(book)}")
        except CheckError as error:
            say(f"  would skip     {book.name}: {error}")
    if not plan.has_changes():
        say("Fonts: already up to date.")
    for step in plan.install:
        say(f"  would install  {step.kobo_name}   ({step.family})")
    for name in plan.remove:
        say(f"  would remove   {name}")
    for name in plan.forget:
        say(f"  would forget   {name}   (already deleted on the Kobo)")
    if settings.eject_after_push:
        say("Then it would eject the Kobo.")
