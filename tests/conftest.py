"""Fixtures shared by all the tests. pytest finds this file by its name and loads it first."""

from pathlib import Path

import pytest

from kraken.kobo import Kobo


@pytest.fixture(autouse=True)
def pretend_home(tmp_path, monkeypatch):
    """Every test runs in a temporary home folder, so the real ~/.config and ~/.local are never touched."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for variable in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
        monkeypatch.delenv(variable, raising=False)
    return home


@pytest.fixture
def fake_kobo(tmp_path):
    """A stand-in Kobo: a temporary folder with a .kobo/ inside (a "test double", DESIGN.md section 11)."""
    mount = tmp_path / "KOBOeReader"
    (mount / ".kobo").mkdir(parents=True)
    return Kobo(mount=mount, device=Path("/dev/fake"))
