"""Tests for the kraken command line."""

import pytest

from kraken import __version__
from kraken.cli import main


def test_version_prints_name_and_version(capsys):
    # argparse prints the version, then exits; SystemExit with code 0 means "success".
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"kraken {__version__}"
