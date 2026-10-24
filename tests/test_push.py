"""Tests for kraken push, the lock and notifications. Uses the fake Kobo and pretend home from conftest.py."""

import os
import re
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

import pytest

from kraken import notify as notify_module
from kraken import push as push_module
from kraken.cli import main
from kraken.fonts import catalogue_dir, fonts_on_kobo, read_manifest, write_picks
from kraken.kobo import KoboError
from kraken.lock import BusyError, kraken_lock
from kraken.settings import settings_path, state_dir
from helpers import make_epub, make_family

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
    assert desk.notifications == [("kraken", "Books: none waiting. Fonts: 2 installed, 0 removed. Safe to unplug.")]
    assert "Fonts: 2 installed, 0 removed." in capsys.readouterr().out


def test_second_push_has_nothing_to_do(desk):
    main(["push"])
    assert main(["push"]) == 0
    assert desk.notifications[-1] == ("kraken", "Books: none waiting. Fonts: already up to date. Safe to unplug.")


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


# --- Books (Milestone 2) ---


def inbox() -> Path:
    return Path.home() / "KRAKEN"


def drop_book(name: str, **options) -> Path:
    """A tiny test EPUB in the inbox, made a minute ago so it isn't "still arriving" (D50)."""
    inbox().mkdir(exist_ok=True)
    book = make_epub(inbox() / name, **options)
    a_minute_ago = time.time() - 60
    os.utime(book, (a_minute_ago, a_minute_ago))
    return book


def chapter_on_kobo(kobo, name: str) -> str:
    with zipfile.ZipFile(kobo.mount / "kraken" / name) as book:
        return book.read("OEBPS/chapter1.xhtml").decode()


def test_a_book_is_bolded_sent_and_filed(desk, capsys):
    drop_book("Alice.epub")
    assert main(["push"]) == 0

    assert '<b class="kraken-bs">' in chapter_on_kobo(desk.kobo, "Alice.epub")
    assert (inbox() / "sent" / "Alice.epub").exists() and not (inbox() / "Alice.epub").exists()
    assert "Sent Alice.epub  ->  kraken/Alice.epub" in capsys.readouterr().out
    assert desk.notifications[-1][1].startswith("Books: 1 sent. Fonts: 2 installed")


def test_books_go_before_fonts(desk, monkeypatch):
    order = []
    real_copy = push_module.copy_to_kobo
    monkeypatch.setattr(push_module, "copy_to_kobo",
                        lambda kobo, source, destination: (order.append("book"), real_copy(kobo, source, destination)))
    real_fonts = push_module.apply_font_plan
    monkeypatch.setattr(push_module, "apply_font_plan",
                        lambda *args: (order.append("fonts"), real_fonts(*args))[1])
    drop_book("Alice.epub")
    main(["push"])
    assert order == ["book", "fonts"]


def test_a_locked_book_is_skipped_and_the_others_still_go(desk):
    drop_book("Bob.epub")
    drop_book("Locked.epub", extra={"META-INF/encryption.xml": b"<encryption/>"})
    assert main(["push"]) == 0  # handled: it's in skipped/ with a note, so nothing needs fixing in kraken

    assert (desk.kobo.mount / "kraken" / "Bob.epub").exists()
    assert not (desk.kobo.mount / "kraken" / "Locked.epub").exists()
    assert "because it's locked" in (inbox() / "skipped" / "Locked.epub.why.txt").read_text()
    assert desk.notifications[-1][1].startswith("Books: 1 sent, 1 skipped (see skipped/).")


def test_a_book_without_a_table_of_contents_is_skipped(desk):
    # bold_epub would happily bold this one: only check_book knows it can freeze the Kobo (D47).
    drop_book("No TOC.epub", ncx=False)
    main(["push"])
    assert not (desk.kobo.mount / "kraken" / "No TOC.epub").exists()
    assert "no table of contents" in (inbox() / "skipped" / "No TOC.epub.why.txt").read_text()


def test_a_book_with_a_broken_page_is_skipped_not_retried_forever(desk):
    drop_book("Broken.epub", pages={"chapter1.xhtml": "<p>an unclosed paragraph"})
    assert main(["push"]) == 0
    assert not (inbox() / "Broken.epub").exists()
    assert "its page OEBPS/chapter1.xhtml is" in (inbox() / "skipped" / "Broken.epub.why.txt").read_text()


def test_a_bad_bolded_copy_never_reaches_the_kobo(desk, monkeypatch):
    def broken_bolding(source, destination, strength):
        destination.write_text("not a zip")

    monkeypatch.setattr(push_module, "bold_epub", broken_bolding)
    drop_book("Alice.epub")
    main(["push"])
    assert not (desk.kobo.mount / "kraken" / "Alice.epub").exists()
    note = (inbox() / "skipped" / "Alice.epub.why.txt").read_text()
    assert "kraken's bold-start copy failed its check" in note


def test_a_failed_copy_leaves_the_book_in_the_inbox_and_the_others_still_go(desk, monkeypatch):
    real_copy = push_module.copy_to_kobo

    def cable_trouble_for_alice(kobo, source, destination):
        if destination.name == "Alice.epub":
            raise KoboError("The copy of Alice.epub on the Kobo doesn't match the original.")
        real_copy(kobo, source, destination)

    monkeypatch.setattr(push_module, "copy_to_kobo", cable_trouble_for_alice)
    drop_book("Alice.epub")
    drop_book("Bob.epub")
    assert main(["push"]) == 1

    assert (inbox() / "Alice.epub").exists()  # tried again next time
    assert (inbox() / "sent" / "Bob.epub").exists()
    message = desk.notifications[-1][1]
    assert message.startswith("Books: 1 sent, 1 waiting.") and "1 problem(s)" in message


def test_an_unexpected_error_in_one_book_doesnt_stop_the_others(desk, monkeypatch):
    real_bold = push_module.bold_epub

    def buggy_for_alice(source, destination, strength):
        if source.name == "Alice.epub":
            raise ValueError("a bug in kraken")
        return real_bold(source, destination, strength)

    monkeypatch.setattr(push_module, "bold_epub", buggy_for_alice)
    drop_book("Alice.epub")
    drop_book("Bob.epub")
    assert main(["push"]) == 1
    assert (inbox() / "Alice.epub").exists() and (inbox() / "sent" / "Bob.epub").exists()


def test_a_book_deleted_on_the_kobo_doesnt_come_back(desk):
    drop_book("Alice.epub")
    main(["push"])
    (desk.kobo.mount / "kraken" / "Alice.epub").unlink()  # you deleted it on the Kobo
    main(["push"])
    assert not (desk.kobo.mount / "kraken" / "Alice.epub").exists()


def test_a_book_dropped_again_replaces_its_copy(desk):
    drop_book("Alice.epub", pages={"chapter1.xhtml": "<p>first edition</p>"})
    main(["push"])
    drop_book("Alice.epub", pages={"chapter1.xhtml": "<p>second edition</p>"})
    main(["push"])
    text = re.sub("<[^>]+>", "", chapter_on_kobo(desk.kobo, "Alice.epub"))  # the words, without the bold tags
    assert "second edition" in text and "first" not in text
    assert [path.name for path in (inbox() / "sent").iterdir()] == ["Alice.epub"]


def test_the_bolded_copy_is_built_in_a_temporary_folder_and_deleted(desk, tmp_path, monkeypatch):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))  # where TemporaryDirectory makes its folders
    drop_book("Alice.epub")
    drop_book("Locked.epub", extra={"META-INF/encryption.xml": b"<encryption/>"})
    main(["push"])
    assert list(scratch.iterdir()) == []
    assert [path.name for path in (inbox() / "sent").iterdir()] == ["Alice.epub"]  # only the original (D52)


def test_leftover_copies_from_an_interrupted_push_are_removed(desk):
    leftover = desk.kobo.mount / "kraken" / "Alice.epub.kraken.part"
    leftover.parent.mkdir()
    leftover.write_text("half a book")
    main(["push"])
    assert not leftover.exists()


def test_files_that_wait_are_named_and_counted(desk, capsys):
    report = inbox() / "report.docx"
    inbox().mkdir()
    report.write_text("a document")
    os.utime(report, (time.time() - 60,) * 2)
    make_epub(inbox() / "Arriving.epub")  # changed just now
    drop_book("Alice.epub")
    drop_book("alice.epub")  # the same name on the Kobo
    main(["push"])

    out = capsys.readouterr().out
    assert "Waiting: report.docx (kraken can't send this kind of file yet)" in out
    assert "Waiting: Arriving.epub (it changed in the last few seconds" in out
    assert "Waiting: alice.epub (it would have the same name on the Kobo as Alice.epub" in out
    assert desk.notifications[-1][1].startswith("Books: 1 sent, 3 waiting.")
    assert report.exists()  # left in the inbox for a later version (D49)


def test_the_inbox_is_made_on_the_first_push(desk):
    main(["push"])
    assert inbox().is_dir()


def test_dry_run_lists_books_and_changes_nothing(desk, capsys):
    drop_book("Alice.epub")
    drop_book("Locked.epub", extra={"META-INF/encryption.xml": b"<encryption/>"})
    before = sorted(inbox().rglob("*"))

    assert main(["push", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "would send     Alice.epub  ->  kraken/Alice.epub" in out
    assert "would skip     Locked.epub: it's locked" in out
    assert sorted(inbox().rglob("*")) == before
    assert not (desk.kobo.mount / "kraken").exists()


def test_dry_run_with_an_empty_inbox_says_so(desk, capsys):
    main(["push", "--dry-run"])
    assert "Books: none to send." in capsys.readouterr().out
    assert not inbox().exists()  # a dry run doesn't even make the inbox


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
