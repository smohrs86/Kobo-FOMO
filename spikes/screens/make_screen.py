"""Spike D: build a custom Kobo Glo sleep screen from a framed picture plus text.

The picture goes in the middle, a bold-start title at the top, and a small
footer at the bottom. The result is a 758 x 1024 greyscale PNG using the
16 grey levels the Glo's e-ink screen can show.

Personal details (the picture, the title text) are passed in when you run it,
so nothing personal is stored in this file. Example:

    python3 spikes/screens/make_screen.py \\
        --image personal/portrait.jpeg \\
        --title "My Custom E-Reader" --title "Line Two" \\
        --emoji "🙂" --footer "**MODEL** · Personal Assistive Reading Device" \\
        --out personal/sleep-screen.png
"""

import argparse
import math
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PROJECT = Path(__file__).resolve().parents[2]
FONT_DIR = PROJECT / "downloads" / "fonts"

# The Kobo Glo screen, in portrait orientation.
WIDTH, HEIGHT = 758, 1024
MARGIN = 40

# Same bold-start rules as Spike A, at the strength chosen there (Light, 30%).
STRENGTH = 0.3
WORD_PATTERN = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)*")


def bold_count(word_length, strength=STRENGTH):
    """How many letters at the start of a word to make bold."""
    return min(word_length, math.ceil(word_length * strength))


def bold_start_segments(text):
    """Split text into (piece, is_bold) pairs, bolding the start of each word."""
    segments = []
    position = 0
    for match in WORD_PATTERN.finditer(text):
        segments.append((text[position:match.start()], False))
        word = match.group()
        n = bold_count(len(word))
        segments.append((word[:n], True))
        segments.append((word[n:], False))
        position = match.end()
    segments.append((text[position:], False))
    return [(piece, bold) for piece, bold in segments if piece]


class LineWriter:
    """Draws one centred line made of bold-start text, plus optional emoji."""

    def __init__(self, size):
        self.regular = ImageFont.truetype(str(FONT_DIR / "AtkinsonHyperlegible-Regular.ttf"), size)
        self.bold = ImageFont.truetype(str(FONT_DIR / "AtkinsonHyperlegible-Bold.ttf"), size)
        self.emoji = ImageFont.truetype(str(FONT_DIR / "NotoEmoji[wght].ttf"), size)
        self.emoji.set_variation_by_name("Bold")  # thicker strokes survive e-ink better
        self.size = size

    def pieces(self, text, emoji=""):
        """Every piece of the line with the font it's drawn in."""
        pieces = [(p, self.bold if b else self.regular) for p, b in bold_start_segments(text)]
        if emoji:
            pieces += [(" ", self.regular), (emoji, self.emoji)]
        return pieces

    def width(self, text, emoji=""):
        return sum(font.getlength(piece) for piece, font in self.pieces(text, emoji))

    def draw(self, draw, y, text, emoji=""):
        x = (WIDTH - self.width(text, emoji)) / 2
        for piece, font in self.pieces(text, emoji):
            draw.text((x, y), piece, font=font, fill=0)
            x += font.getlength(piece)


def fit_writer(lines, emoji, max_size, max_width):
    """The biggest text size (up to max_size) at which every line fits."""
    for size in range(max_size, 10, -1):
        writer = LineWriter(size)
        widths = [writer.width(line, emoji if i == len(lines) - 1 else "") for i, line in enumerate(lines)]
        if max(widths) <= max_width:
            return writer
    raise ValueError("Title is too long to fit on the screen")


def draw_marked_line(draw, y, text, size):
    """Draw a centred line where **marked** pieces are bold (like Markdown)."""
    regular = ImageFont.truetype(str(FONT_DIR / "AtkinsonHyperlegible-Regular.ttf"), size)
    bold = ImageFont.truetype(str(FONT_DIR / "AtkinsonHyperlegible-Bold.ttf"), size)
    # Splitting on "**" makes every second piece a bold one.
    pieces = [(piece, bold if i % 2 else regular) for i, piece in enumerate(text.split("**")) if piece]
    x = (WIDTH - sum(font.getlength(piece) for piece, font in pieces)) / 2
    for piece, font in pieces:
        draw.text((x, y), piece, font=font, fill=0)
        x += font.getlength(piece)


def crop_to_content(image, threshold=240, edge=0.01):
    """Trim the plain white border around the picture.

    The outer `edge` fraction is cut off first, because generated images
    sometimes have stray lines right at their edges.
    """
    dx, dy = round(image.width * edge), round(image.height * edge)
    image = image.crop((dx, dy, image.width - dx, image.height - dy))
    grey = image.convert("L")
    mask = grey.point(lambda p: 255 if p < threshold else 0)
    return image.crop(mask.getbbox())


def to_eink_greys(image):
    """Snap every pixel to the nearest of the Glo's 16 grey levels."""
    return image.convert("L").point(lambda p: round(p / 17) * 17)


def build_screen(image_path, title_lines, emoji, footer):
    canvas = Image.new("L", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(canvas)
    usable = WIDTH - 2 * MARGIN

    # Title at the top; the emoji (if any) goes at the end of the last line.
    writer = fit_writer(title_lines, emoji, max_size=54, max_width=usable)
    line_gap = int(writer.size * 1.25)
    y = MARGIN
    for i, line in enumerate(title_lines):
        writer.draw(draw, y, line, emoji if i == len(title_lines) - 1 else "")
        y += line_gap
    title_bottom = y

    # Footer at the bottom, small. Words wrapped in **double asterisks** are bold.
    footer_size = 22
    footer_y = HEIGHT - MARGIN - footer_size
    if footer:
        draw_marked_line(draw, footer_y, footer, footer_size)

    # The picture fills the space between, keeping its shape.
    picture = crop_to_content(Image.open(image_path))
    box_top, box_bottom = title_bottom + 20, footer_y - 28
    scale = min(usable / picture.width, (box_bottom - box_top) / picture.height)
    picture = picture.resize((round(picture.width * scale), round(picture.height * scale)), Image.LANCZOS)
    left = (WIDTH - picture.width) // 2
    top = box_top + (box_bottom - box_top - picture.height) // 2
    canvas.paste(picture.convert("L"), (left, top))

    return to_eink_greys(canvas)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--image", required=True, type=Path, help="framed picture for the middle")
    parser.add_argument("--title", action="append", required=True, help="a title line (repeat for more lines)")
    parser.add_argument("--emoji", default="", help="emoji to put at the end of the title")
    parser.add_argument("--footer", default="", help="small text at the bottom; **marked** words are bold")
    parser.add_argument("--out", required=True, type=Path, help="where to save the PNG")
    args = parser.parse_args()

    screen = build_screen(args.image, args.title, args.emoji, args.footer)
    screen.save(args.out)
    print(f"Wrote {args.out} ({screen.width} x {screen.height})")


if __name__ == "__main__":
    main()
