"""The `kraken` command line (DESIGN.md section 3).

Each subcommand is added in the milestone that builds it (D30).
"""

import argparse
import logging
from collections.abc import Callable

from kraken import __version__
from kraken.autosync import AutosyncError, status, turn_off, turn_on, unit_path, watch
from kraken.fonts import PicksError, catalogue_dir, read_catalogue, read_picks, write_picks
from kraken.lock import BusyError
from kraken.push import run_push
from kraken.settings import SettingsError, state_dir

# --- kraken fonts (D25, D31) ---


def font_checklist(families: list[str], missing: list[str], problems: list[str], picks: set[str],
                   no_italic: set[str] = frozenset(),
                   ask: Callable[[str], str] | None = None, show: Callable[[str], None] | None = None) -> set[str]:
    """Show the numbered checklist until Enter is pressed, and return the ticked families.

    families: usable families in the catalogue
    missing:  ticked families that are no longer in the catalogue (shown so they can be unticked)
    problems: catalogue folders that can't be used, with the reason
    no_italic: usable families with no Italic file, which get a warning (D36)
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
            if name in no_italic:
                note = "   (no Italic: the Kobo will show italic text as bold)"
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
    no_italic = {family.name for family in catalogue.families if "Italic" not in family.styles}

    if not families and not missing:
        print(f"No usable fonts in the catalogue yet. Put each font family in its own folder in {catalogue_dir()}")
        for problem in catalogue.problems:
            print(f"  {problem}")
        return 1

    try:
        new_picks = font_checklist(families, missing, catalogue.problems, picks, no_italic)
    except (KeyboardInterrupt, EOFError):  # Ctrl+C, or Ctrl+D
        print("\nNothing saved.")
        return 1

    write_picks(new_picks)
    print("Saved. The Kobo gets these fonts on the next push.")
    return 0


# --- kraken autosync (DESIGN.md section 6) ---

STATUS_MESSAGES = {
    "on": "Auto-sync is on: plug in the Kobo and tap Connect, and kraken pushes by itself.",
    "off": "Auto-sync is off. `kraken autosync on` switches it on.",
    "not running": ("Auto-sync is switched on, but it isn't running. "
                    "`journalctl --user -u kraken-autosync` shows why; `kraken autosync on` restarts it."),
}


def run_autosync(args: argparse.Namespace) -> int:
    if args.action == "watch":  # what the background service runs
        watch()
        return 0  # never reached: watch() runs until the service is stopped
    if args.action == "on":
        turn_on()
        print(f"Auto-sync is on. Its unit file is {unit_path()}")
        print("Plug in the Kobo and tap Connect: kraken pushes, ejects it and tells you when to unplug.")
        return 0
    if args.action == "off":
        print("Auto-sync is off." if turn_off() else "Auto-sync was already off.")
        return 0
    state = status()
    print(STATUS_MESSAGES[state])
    return 0 if state != "not running" else 1


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

    push = commands.add_parser("push", help="send waiting books and fonts to the Kobo, then eject it")
    push.add_argument("--dry-run", action="store_true", help="show what push would do, without doing it")
    push.set_defaults(run=lambda args: run_push(dry_run=args.dry_run))

    autosync = commands.add_parser("autosync", help="push by itself whenever the Kobo is plugged in")
    autosync.add_argument("action", nargs="?", choices=["on", "off", "watch"],
                          help="on or off; leave it out to see which it is (watch is what the background service runs)")
    autosync.set_defaults(run=run_autosync)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run kraken. `argv` is the list of command-line words; None means "use the real ones"."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "run"):  # no subcommand given
        parser.print_help()
        return 0
    start_log()
    try:
        return args.run(args)
    except (AutosyncError, BusyError, PicksError, SettingsError) as error:
        print(f"kraken: {error}")
        logging.getLogger("kraken").error("%s", error)
        return 1


def start_log() -> None:
    """Write kraken's diary to ~/.local/state/kraken/kraken.log, for when something goes wrong."""
    log = logging.getLogger("kraken")
    for old in list(log.handlers):  # running main() again (as the tests do) replaces the old log file
        log.removeHandler(old)
        old.close()
    path = state_dir() / "kraken.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
