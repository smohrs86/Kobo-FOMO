"""Words, and how much of each to make bold (DESIGN.md section 5).

This part works on plain text only. It knows nothing about web pages or Kobos: it splits a piece
of text into pieces, each marked "bold" or "plain". boldstart/page.py turns those into markup.

The rules:
- Letters only. Numbers, and words mixing letters with digits ("1st", "mp3"), are left alone (D43).
- A hyphen splits words ("daisy-chain" is two words); an apostrophe joins them ("didn't" is one) (D44).
- Every word gets at least one bold letter, rounding up (D45).
- Web addresses and email addresses are left alone.
- Letters from every alphabet count, including accented ones, whether the accent is part of the
  letter (é) or a separate "combining" mark after it (e + ́).
"""

import math
import re

# A combining mark is an accent stored as its own character, drawn on top of the letter before it.
COMBINING_MARKS = "̀-ͯ᪰-᫿᷀-᷿⃐-⃿︠-︯"

# A run of letters and digits (and accent marks), which may have apostrophes inside it ("didn't",
# "rock’n’roll"). [^\W_] means "a letter or a digit, from any alphabet": \W is "not a word
# character", and _ is a word character we don't want.
_PART = rf"[^\W_](?:[^\W_]|[{COMBINING_MARKS}])*"
TOKEN_PATTERN = re.compile(rf"{_PART}(?:['’]{_PART})*")

# Web and email addresses, which are left alone. Generous on purpose: leaving a little too much
# plain is harmless, but a half-bold address is hard to read.
ADDRESS_PATTERN = re.compile(r"(?:https?://|www\.)\S+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.IGNORECASE)

Piece = tuple[str, bool]  # (some text, is it bold?)


def bold_count(letters: int, strength: float) -> int:
    """How many of a word's letters to make bold. Rounds up, so every word gets at least one (D45)."""
    if strength <= 0:
        return 0
    return min(letters, math.ceil(letters * strength))


def split_for_bold(text: str, strength: float) -> list[Piece]:
    """Split text into pieces marked bold or plain. Joined back together, they are exactly `text`.

    >>> split_for_bold("Hello world", 0.3)
    [('He', True), ('llo ', False), ('wo', True), ('rld', False)]
    """
    protected = [match.span() for match in ADDRESS_PATTERN.finditer(text)]
    pieces: list[Piece] = []
    position = 0  # everything before this has been placed in a piece

    for match in TOKEN_PATTERN.finditer(text):
        word = match.group()
        if _inside(match.start(), protected) or any(character.isdigit() for character in word):
            continue  # left as plain text: it becomes part of the next plain piece
        head = _head_length(word, strength)
        if head == 0:
            continue
        _add(pieces, text[position:match.start()], False)
        _add(pieces, word[:head], True)
        position = match.start() + head

    _add(pieces, text[position:], False)
    return pieces


def _head_length(word: str, strength: float) -> int:
    """How many characters of `word` go in bold, counting letters but not apostrophes or accents.

    An accent written as a separate mark always stays with its letter, so it's never cut off.
    """
    wanted = bold_count(sum(1 for character in word if _is_letter(character)), strength)
    counted = 0
    for index, character in enumerate(word):
        if _is_letter(character):
            if counted == wanted:
                return index
            counted += 1
        elif counted == wanted and not _is_mark(character):
            return index
    return len(word)


def _is_letter(character: str) -> bool:
    return character.isalpha()  # False for digits, apostrophes and accent marks


def _is_mark(character: str) -> bool:
    return re.fullmatch(f"[{COMBINING_MARKS}]", character) is not None


def _inside(index: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= index < end for start, end in spans)


def _add(pieces: list[Piece], text: str, bold: bool) -> None:
    """Add a piece, unless it's empty. Plain and bold pieces always take turns, so plain text that
    was skipped (numbers, addresses) simply becomes part of the next plain piece."""
    if text:
        pieces.append((text, bold))
