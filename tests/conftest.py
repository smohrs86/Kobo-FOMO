"""Fixtures shared by all the tests. pytest finds this file by its name and loads it first."""

from pathlib import Path

import pytest

from kraken.kobo import Kobo


@pytest.fixture
def fake_kobo(tmp_path):
    """A stand-in Kobo: a temporary folder with a .kobo/ inside (a "test double", DESIGN.md section 11)."""
    mount = tmp_path / "KOBOeReader"
    (mount / ".kobo").mkdir(parents=True)
    return Kobo(mount=mount, device=Path("/dev/fake"))
