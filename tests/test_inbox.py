"""Tests for kraken/inbox.py: waiting files, names on the Kobo, sent/ and skipped/ (D49–D51, D53)."""

import os
from pathlib import Path

from kraken.inbox import WAIT_SECONDS, file_sent, file_skipped, kobo_name, scan_inbox

NOW = 1_800_000_000.0  # a fixed "now", so the tests don't depend on the clock


def drop(inbox: Path, name: str, age: float = 60, text: str = "pretend file") -> Path:
    """Put a file in the inbox, last changed `age` seconds before NOW."""
    inbox.mkdir(exist_ok=True)
    path = inbox / name
    path.write_text(text)
    os.utime(path, (NOW - age, NOW - age))
    return path


def test_an_epub_is_ready_to_send(tmp_path):
    book = drop(tmp_path, "Alice.epub")
    assert scan_inbox(tmp_path, NOW).books == [book]


def test_the_extension_can_be_in_capitals(tmp_path):
    book = drop(tmp_path, "Alice.EPUB")
    assert scan_inbox(tmp_path, NOW).books == [book]


def test_books_come_in_name_order(tmp_path):
    names = ["b.epub", "c.epub", "a.epub"]
    for name in names:
        drop(tmp_path, name)
    assert [book.name for book in scan_inbox(tmp_path, NOW).books] == sorted(names)


def test_other_files_wait_for_a_later_version(tmp_path):
    report = drop(tmp_path, "report.docx")
    waiting = scan_inbox(tmp_path, NOW)
    assert waiting.later == [report] and waiting.books == []


def test_a_file_changed_in_the_last_few_seconds_waits(tmp_path):
    book = drop(tmp_path, "Alice.epub", age=WAIT_SECONDS - 1)
    waiting = scan_inbox(tmp_path, NOW)
    assert waiting.too_new == [book] and waiting.books == []


def test_a_file_with_a_date_in_the_future_doesnt_wait_forever(tmp_path):
    book = drop(tmp_path, "Alice.epub", age=-3600)  # the clock was wrong when it was made
    assert scan_inbox(tmp_path, NOW).books == [book]


def test_hidden_files_and_unfinished_downloads_are_ignored(tmp_path):
    for name in [".Alice.epub", "Alice.epub.part", "Alice.epub.crdownload", "Alice.epub.PART"]:
        drop(tmp_path, name)
    waiting = scan_inbox(tmp_path, NOW)
    assert waiting.books == waiting.later == waiting.too_new == []


def test_sub_folders_are_never_looked_in(tmp_path):
    drop(tmp_path / "sent", "Alice.epub")
    drop(tmp_path / "skipped", "Bob.epub")
    assert scan_inbox(tmp_path, NOW).books == []


def test_a_missing_inbox_has_nothing_waiting(tmp_path):
    assert scan_inbox(tmp_path / "KRAKEN", NOW).books == []


def test_the_scan_changes_nothing(tmp_path):
    drop(tmp_path, "Alice.epub")
    before = sorted(tmp_path.rglob("*"))
    scan_inbox(tmp_path, NOW)
    assert sorted(tmp_path.rglob("*")) == before


def test_the_name_on_the_kobo_is_in_the_kraken_folder():
    assert kobo_name(Path("research report.epub")) == Path("kraken/research report.epub")


def test_characters_the_kobo_cant_store_become_underscores():
    assert kobo_name(Path('a\\b:c*d?e"f<g>h|i.epub')) == Path("kraken/a_b_c_d_e_f_g_h_i.epub")


def test_the_name_on_the_kobo_always_ends_in_lowercase_epub():
    assert kobo_name(Path("Alice.EPUB")) == Path("kraken/Alice.epub")


def test_a_kobo_format_book_loses_its_kepub_ending():
    # The Kobo reads a .kepub.epub with its own Kobo-format reader; kraken's bolded copy is a plain EPUB (D54).
    assert kobo_name(Path("Alice.KEPUB.epub")) == Path("kraken/Alice.epub")


def test_a_kepub_and_an_epub_of_the_same_book_clash(tmp_path):
    epub = drop(tmp_path, "Alice.epub")
    kepub = drop(tmp_path, "Alice.kepub.epub")
    waiting = scan_inbox(tmp_path, NOW)
    assert waiting.books == [epub] and waiting.clashes == [(kepub, epub)]


def test_accents_and_other_letters_are_kept():
    assert kobo_name(Path("Les Misérables – tome 1.epub")) == Path("kraken/Les Misérables – tome 1.epub")


def test_two_books_with_the_same_name_on_the_kobo_clash(tmp_path):
    first = drop(tmp_path, "a:b.epub")
    second = drop(tmp_path, "a_b.epub")
    waiting = scan_inbox(tmp_path, NOW)
    assert waiting.books == [first]  # ":" sorts before "_", so "a:b" is first and keeps the name
    assert waiting.clashes == [(second, first)]


def test_names_that_differ_only_in_capitals_clash(tmp_path):
    # The Kobo's FAT drive treats "Alice" and "alice" as the same name.
    upper = drop(tmp_path, "Alice.epub")
    lower = drop(tmp_path, "alice.epub")
    waiting = scan_inbox(tmp_path, NOW)
    assert waiting.books == [upper] and waiting.clashes == [(lower, upper)]


def test_a_sent_book_moves_to_sent(tmp_path):
    book = drop(tmp_path, "Alice.epub", text="the original")
    moved = file_sent(tmp_path, book)
    assert moved == tmp_path / "sent" / "Alice.epub"
    assert moved.read_text() == "the original" and not book.exists()


def test_a_book_sent_again_replaces_its_old_original(tmp_path):
    file_sent(tmp_path, drop(tmp_path, "Alice.epub", text="version 1"))
    file_sent(tmp_path, drop(tmp_path, "Alice.epub", text="version 2"))
    assert [path.name for path in (tmp_path / "sent").iterdir()] == ["Alice.epub"]
    assert (tmp_path / "sent" / "Alice.epub").read_text() == "version 2"


def test_sent_keeps_one_original_per_book_on_the_kobo(tmp_path):
    # Both become kraken/Alice.epub on the Kobo, so the newer one replaces the older in sent/ as well.
    file_sent(tmp_path, drop(tmp_path, "alice.epub", text="version 1"))
    file_sent(tmp_path, drop(tmp_path, "Alice.epub", text="version 2"))
    assert [path.name for path in (tmp_path / "sent").iterdir()] == ["Alice.epub"]


def test_other_books_in_sent_are_left_alone(tmp_path):
    file_sent(tmp_path, drop(tmp_path, "Alice.epub"))
    file_sent(tmp_path, drop(tmp_path, "Bob.epub"))
    assert sorted(path.name for path in (tmp_path / "sent").iterdir()) == ["Alice.epub", "Bob.epub"]


def test_a_skipped_file_moves_to_skipped_with_a_note(tmp_path):
    book = drop(tmp_path, "Locked.epub")
    moved = file_skipped(tmp_path, book, "it's locked")
    assert moved == tmp_path / "skipped" / "Locked.epub" and not book.exists()
    note = (tmp_path / "skipped" / "Locked.epub.why.txt").read_text()
    assert "didn't send Locked.epub" in note and "because it's locked." in note
    assert f"drop it in {tmp_path} again" in note


def test_a_file_skipped_again_gets_a_fresh_note(tmp_path):
    file_skipped(tmp_path, drop(tmp_path, "Bad.epub"), "it's damaged")
    file_skipped(tmp_path, drop(tmp_path, "Bad.epub"), "it has no table of contents")
    note = (tmp_path / "skipped" / "Bad.epub.why.txt").read_text()
    assert "no table of contents" in note and "damaged" not in note
