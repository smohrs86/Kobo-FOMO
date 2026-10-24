"""Tests for finding the Kobo, using a pretend drive list instead of real hardware."""

from pathlib import Path

import pytest

from kraken.kobo import Kobo, KoboError, find_kobo


class PretendComputer:
    """Stands in for the parts of Linux that find_kobo reads: drive labels and the mount list."""

    def __init__(self, root: Path):
        self.by_label = root / "dev" / "disk" / "by-label"
        self.by_label.mkdir(parents=True)
        self.mounts_file = root / "mounts"
        self.mounts_file.write_text("")
        self.root = root

    def plug_in(self, label: str = "KOBOeReader") -> Path:
        """A drive appears: a device file, and a label shortcut pointing at it."""
        device = self.root / "dev" / "sdd"
        device.touch()
        (self.by_label / label).symlink_to(device)
        return device

    def mount(self, device: Path, mount_point: Path, options: str = "rw,nosuid,nodev") -> None:
        """The desktop mounts the drive. Spaces in the mount list are written as \\040, as Linux does."""
        escaped = str(mount_point).replace(" ", "\\040")
        with self.mounts_file.open("a") as mounts:
            mounts.write(f"{device} {escaped} vfat {options} 0 0\n")

    def find(self) -> Kobo | None:
        return find_kobo(by_label_dir=self.by_label, mounts_file=self.mounts_file)


def make_kobo_files(mount_point: Path) -> Path:
    (mount_point / ".kobo").mkdir(parents=True)
    return mount_point


@pytest.fixture
def computer(tmp_path):
    return PretendComputer(tmp_path)


def test_nothing_plugged_in(computer):
    assert computer.find() is None


def test_plugged_in_but_not_mounted_yet(computer):
    computer.plug_in()
    assert computer.find() is None


def test_finds_a_mounted_kobo(computer, tmp_path):
    device = computer.plug_in()
    mount_point = make_kobo_files(tmp_path / "media" / "KOBOeReader")
    computer.mount(device, mount_point)

    assert computer.find() == Kobo(mount=mount_point, device=device)


def test_mount_point_with_a_space_is_read_correctly(computer, tmp_path):
    device = computer.plug_in()
    mount_point = make_kobo_files(tmp_path / "my media" / "KOBOeReader")
    computer.mount(device, mount_point)

    assert computer.find().mount == mount_point


def test_other_drives_are_ignored(computer, tmp_path):
    other_drive = tmp_path / "dev" / "sdc1"
    other_drive.touch()
    computer.mount(other_drive, make_kobo_files(tmp_path / "media" / "Backup"))
    assert computer.find() is None


def test_drive_with_a_different_label_is_not_the_kobo(computer, tmp_path):
    device = computer.plug_in(label="USB_STICK")
    computer.mount(device, make_kobo_files(tmp_path / "media" / "USB_STICK"))
    assert computer.find() is None


def test_kobo_label_without_kobo_folder_stops(computer, tmp_path):
    device = computer.plug_in()
    mount_point = tmp_path / "media" / "KOBOeReader"
    mount_point.mkdir(parents=True)  # no .kobo/ inside
    computer.mount(device, mount_point)

    with pytest.raises(KoboError, match="no .kobo folder"):
        computer.find()


def test_read_only_kobo_stops(computer, tmp_path):
    device = computer.plug_in()
    computer.mount(device, make_kobo_files(tmp_path / "media" / "KOBOeReader"), options="ro,nosuid")

    with pytest.raises(KoboError, match="read-only"):
        computer.find()
