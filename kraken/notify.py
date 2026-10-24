"""Desktop notifications, with notify-send (DESIGN.md section 6).

A notification is a courtesy: if it can't be shown, kraken carries on.
"""

import logging
import subprocess

log = logging.getLogger("kraken")


def notify(title: str, message: str) -> None:
    """Show a desktop notification. Never raises: a missing notification must not fail a push."""
    try:
        subprocess.run(["notify-send", "--app-name=kraken", title, message],
                       capture_output=True, timeout=10, check=True)
    except (OSError, subprocess.SubprocessError) as error:
        log.warning("Couldn't show a notification: %s", error)
