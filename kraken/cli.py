"""The `kraken` command line (DESIGN.md section 3).

Subcommands (push, pull, fonts, autosync) are added in the milestone that builds each one.
"""

import argparse

from kraken import __version__


def build_parser() -> argparse.ArgumentParser:
    """Describe the command line: its name, help text and options."""
    parser = argparse.ArgumentParser(
        prog="kraken",
        description="Put bold-start books and documents on a Kobo Glo over USB.",
    )
    parser.add_argument("--version", action="version", version=f"kraken {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run kraken. `argv` is the list of command-line words; None means "use the real ones"."""
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0
