"""Tests for boldstart/text.py: words, and how much of each to make bold (D43–D45)."""

import pytest

from boldstart.text import bold_count, split_for_bold

LIGHT = 0.30  # the owner's pick from Spike A


def marked(text, strength=LIGHT):
    """Show the bold pieces in [brackets], which makes the expected results easy to read."""
    return "".join(f"[{piece}]" if bold else piece for piece, bold in split_for_bold(text, strength))


# --- How many letters ---


@pytest.mark.parametrize("letters, expected", [(1, 1), (2, 1), (3, 1), (4, 2), (5, 2), (10, 3)])
def test_bold_count_rounds_up_at_light(letters, expected):
    assert bold_count(letters, LIGHT) == expected


def test_bold_count_never_exceeds_the_word():
    assert bold_count(3, 1.0) == 3


def test_strength_zero_bolds_nothing():
    assert split_for_bold("Hello world", 0) == [("Hello world", False)]


# --- What counts as a word ---


def test_ordinary_words():
    assert marked("Hello world") == "[He]llo [wo]rld"


def test_short_words_get_one_letter():  # D45
    assert marked("a of I") == "[a] [o]f [I]"


def test_apostrophes_join_and_hyphens_split():  # D44
    assert marked("didn't") == "[di]dn't"
    assert marked("rock’n’roll") == "[roc]k’n’roll"
    assert marked("daisy-chain") == "[da]isy-[ch]ain"


def test_quote_marks_are_not_part_of_the_word():
    assert marked("‘and what’") == "‘[a]nd [wh]at’"


def test_numbers_and_words_with_digits_are_left_alone():  # D43
    assert marked("In 1865 the 1st mp3") == "[I]n 1865 [t]he 1st mp3"
    assert marked("COVID-19") == "[CO]VID-19"


@pytest.mark.parametrize("text, expected", [
    ("café", "[ca]fé"),
    ("naïve", "[na]ïve"),
    ("Привет", "[Пр]ивет"),
    ("Ἀλίκη", "[Ἀλ]ίκη"),
])
def test_letters_from_every_alphabet_count(text, expected):
    assert marked(text) == expected


def test_an_accent_written_as_a_separate_mark_stays_with_its_letter():
    word = "éte"  # "éte", with the accent as its own character after the e
    assert marked(word) == "[é]te"


# --- What's left alone ---


@pytest.mark.parametrize("address", [
    "https://example.com/some-page",
    "http://example.com",
    "www.example.com/a",
    "someone@example.org",
    "first.last+kobo@mail.example.co.uk",
])
def test_addresses_are_left_alone(address):
    assert marked(f"see {address} now") == f"[s]ee {address} [n]ow"


def test_text_with_no_words():
    assert split_for_bold("… 42 — !", LIGHT) == [("… 42 — !", False)]
    assert split_for_bold("", LIGHT) == []


# --- The promise: nothing is lost or changed ---


@pytest.mark.parametrize("text", [
    "Alice was beginning to get very tired of sitting by her sister on the bank,",
    "  spaces\tand\nnew lines  ",
    "didn't — rock’n’roll — daisy-chain — éte — 1865 — me@example.org",
])
def test_pieces_join_back_to_exactly_the_original(text):
    pieces = split_for_bold(text, LIGHT)
    assert "".join(piece for piece, _ in pieces) == text
    # plain runs are kept together, so two plain pieces never sit side by side
    assert all(pieces[i][1] or pieces[i + 1][1] for i in range(len(pieces) - 1))
