"""The `kraken` command line (DESIGN.md section 3).

Each subcommand is added in the milestone that builds it (D30).
"""

import argparse
from collections.abc import Callable

from kraken import __version__
from kraken.fonts import PicksError, catalogue_dir, read_catalogue, read_picks, write_picks

# --- kraken fonts (D25, D31) ---


def font_checklist(families: list[str], missing: list[str], problems: list[str], picks: set[str],
                   ask: Callable[[str], str] | None = None, show: Callable[[str], None] | None = None) -> set[str]:
    """Show the numbered checklist until Enter is pressed, and return the ticked families.

    families: usable families in the catalogue
    missing:  ticked families that are no longer in the catalogue (shown so they can be unticked)
    problems: catalogue folders that can't be used, with the reason
    `ask` and `show` default to input and print; tests pass pretend ones instead.
    """
    # Looked up now, not in the line above: a default there is fixed once, when Python first reads the file.
    ask = ask or input
    show = show or print
    ticked = set(picks)
    choices = families + missing

    while True:
        show("")
        show("Fonts (ticked = on the Kobo after the next push)")
        for number, name in enumerate(choices, start=1):
            mark = "x" if name in ticked else " "
            note = "   (no longer in the catalogue)" if name in missing else ""
            show(f"  {number}. [{mark}] {name}{note}")
        if problems:
            show("")
            show("Can't be used:")
            for problem in problems:
                show(f"  {problem}")

        answer = ask("\nType a number to tick or untick it, or press Enter to save (Ctrl+C quits without saving): ")
        if not answer.strip():
            return ticked

        words = answer.replace(",", " ").split()
        if not all(word.isdigit() and 1 <= int(word) <= len(choices) for word in words):
            show(f"Please type numbers from 1 to {len(choices)}, or just press Enter to save.")
            continue
        for word in words:
            ticked ^= {choices[int(word) - 1]}  # ^ is "toggle": add it if absent, remove it if present


def run_fonts(args: argparse.Namespace) -> int:
    catalogue = read_catalogue()
    picks = read_picks()
    families = [family.name for family in catalogue.families]
    missing = sorted(picks - set(families))

    if not families and not missing:
        print(f"No usable fonts in the catalogue yet. Put each font family in its own folder in {catalogue_dir()}")
        for problem in catalogue.problems:
            print(f"  {problem}")
        return 1

    try:
        new_picks = font_checklist(families, missing, catalogue.problems, picks)
    except (KeyboardInterrupt, EOFError):  # Ctrl+C, or Ctrl+D
        print("\nNothing saved.")
        return 1

    write_picks(new_picks)
    print("Saved. The Kobo gets these fonts on the next push.")
    return 0


# --- The command line itself ---


def build_parser() -> argparse.ArgumentParser:
    """Describe the command line: its name, help text, options and subcommands."""
    parser = argparse.ArgumentParser(
        prog="kraken",
        description="Put bold-start books and documents on a Kobo Glo over USB.",
    )
    parser.add_argument("--version", action="version", version=f"kraken {__version__}")
    commands = parser.add_subparsers(title="commands")

    fonts = commands.add_parser("fonts", help="choose which fonts go on the Kobo")
    fonts.set_defaults(run=run_fonts)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run kraken. `argv` is the list of command-line words; None means "use the real ones"."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "run"):  # no subcommand given
        parser.print_help()
        return 0
    try:
        return args.run(args)
    except PicksError as error:
        print(f"kraken: {error}")
        return 1
