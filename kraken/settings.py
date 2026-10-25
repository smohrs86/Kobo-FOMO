"""kraken's folders and settings (DESIGN.md sections 1 and 4).

Folders follow the XDG Base Directory rules: settings in ~/.config, data in ~/.local/share,
logs and the lock in ~/.local/state. Each can be moved with its XDG_..._HOME variable.
"""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

# Written to settings.toml the first time kraken runs. Kept as text, not built from a
# dictionary, so the notes (lines starting with #) are kept for the person editing it.
DEFAULT_SETTINGS_TEXT = """\
# kraken settings. Lines starting with # are notes and are ignored.

[boldstart]
# Fraction of each word's letters in bold. 0.45 = Medium, picked at Checkpoint C (D55).
strength = 0.45

[folders]
inbox = "~/KRAKEN"

[autosync]
eject_after_push = true    # eject the Kobo safely when push is done
notify = true              # show a desktop notification with the results
"""

# Every setting kraken understands: (section, key) -> the type its value must have.
# Anything not listed here is a typo, and is reported rather than silently ignored.
KNOWN_SETTINGS = {
    ("boldstart", "strength"): float,
    ("folders", "inbox"): str,
    ("autosync", "eject_after_push"): bool,
    ("autosync", "notify"): bool,
}


class SettingsError(Exception):
    """settings.toml can't be used. The message says what's wrong, in plain words."""


@dataclass(frozen=True)
class Settings:
    """kraken's settings, checked and ready to use. `frozen` means they can't be changed by accident."""

    strength: float
    inbox: Path
    eject_after_push: bool
    notify: bool


def _xdg_dir(variable: str, fallback: str) -> Path:
    """The folder named by an XDG variable, or the fallback inside the home folder.

    The XDG rules say a relative path in the variable must be ignored.
    """
    value = os.environ.get(variable, "")
    if value and Path(value).is_absolute():
        return Path(value)
    return Path.home() / fallback


def config_dir() -> Path:
    """Where settings.toml lives: ~/.config/kraken."""
    return _xdg_dir("XDG_CONFIG_HOME", ".config") / "kraken"


def data_dir() -> Path:
    """Where kraken keeps its data, such as the font catalogue: ~/.local/share/kraken."""
    return _xdg_dir("XDG_DATA_HOME", ".local/share") / "kraken"


def state_dir() -> Path:
    """Where the log and the lock live: ~/.local/state/kraken."""
    return _xdg_dir("XDG_STATE_HOME", ".local/state") / "kraken"


def settings_path() -> Path:
    return config_dir() / "settings.toml"


def load_settings(path: Path | None = None) -> Settings:
    """Read settings.toml, creating it with the defaults if it doesn't exist yet."""
    path = path or settings_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_SETTINGS_TEXT)

    defaults = tomllib.loads(DEFAULT_SETTINGS_TEXT)
    try:
        yours = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as error:
        raise SettingsError(f"{path} isn't valid TOML: {error}") from None

    values = {}
    for (section, key), wanted_type in KNOWN_SETTINGS.items():
        value = yours.get(section, {}).get(key, defaults[section][key])
        values[key] = _check_type(path, section, key, value, wanted_type)

    _reject_unknown(path, yours)

    if not 0 < values["strength"] <= 1:
        raise SettingsError(
            f"{path}: [boldstart] strength must be more than 0 and at most 1 "
            f"(0.30 means 30% of each word in bold), not {values['strength']}"
        )

    return Settings(
        strength=values["strength"],
        inbox=Path(values["inbox"]).expanduser(),
        eject_after_push=values["eject_after_push"],
        notify=values["notify"],
    )


def _check_type(path: Path, section: str, key: str, value, wanted_type: type):
    """Return the value if it has the right type, or raise a SettingsError saying what was expected."""
    if isinstance(value, bool):
        # Checked first because Python also counts True and False as the numbers 1 and 0.
        if wanted_type is bool:
            return value
    elif wanted_type is float and isinstance(value, (int, float)):
        return float(value)  # allows "strength = 1" as well as "strength = 1.0"
    elif isinstance(value, wanted_type):
        return value
    expected = {float: "a number", str: "text in quotes", bool: "true or false"}[wanted_type]
    raise SettingsError(f"{path}: [{section}] {key} should be {expected}, not {value!r}")


def _reject_unknown(path: Path, yours: dict) -> None:
    """Raise a SettingsError naming the first section or setting kraken doesn't know."""
    known_sections = {section for section, _ in KNOWN_SETTINGS}
    for section, keys in yours.items():
        if section not in known_sections or not isinstance(keys, dict):
            raise SettingsError(f"{path}: unknown section [{section}]")
        for key in keys:
            if (section, key) not in KNOWN_SETTINGS:
                raise SettingsError(f"{path}: unknown setting '{key}' in [{section}]")
