"""`kraken push` (DESIGN.md sections 0, 3 and 6).

Milestone 1 carries fonts only. Milestone 2 adds books from the inbox, through the same steps:
find the Kobo, plan, carry out the plan, eject, notify.
"""

import logging

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
from kraken.kobo import KoboError, eject, find_kobo
from kraken.lock import kraken_lock
from kraken.notify import notify
from kraken.settings import Settings, load_settings

log = logging.getLogger("kraken")


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

        if dry_run:
            _describe(plan, settings)
            return 0

        try:
            result = apply_font_plan(kobo, plan, manifest)
        except KoboError as error:
            return _stop(settings, str(error))
        problems = list(result.problems)
        for problem in problems:
            say(f"Problem: {problem}")

        summary = _summary(result)
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


def _stop(settings: Settings, message: str) -> int:
    """Something went wrong before anything was changed: say so, and leave the Kobo connected."""
    say(f"Stopped: {message}")
    if settings.notify:
        notify("kraken stopped", message)
    return 1


def _summary(result: FontSyncResult) -> str:
    if not (result.installed or result.removed):
        return "Fonts: already up to date."
    return f"Fonts: {len(result.installed)} installed, {len(result.removed)} removed."


def _describe(plan: FontPlan, settings: Settings) -> None:
    """--dry-run: show what push would do, without doing it (D32)."""
    say("Dry run: nothing has been changed.")
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
