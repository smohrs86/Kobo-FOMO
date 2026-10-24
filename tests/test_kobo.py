"""Tests for finding the Kobo and copying to it, using pretend drives instead of real hardware."""

import shutil
from collections import namedtuple
from pathlib import Path

import pytest

from kraken import kobo as kobo_module
from kraken.kobo import (
    PART_SUFFIX,
    Kobo,
    KoboError,
    copy_to_kobo,
    delete_from_kobo,
    find_kobo,
    remove_leftover_parts,
)


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


# --- Copying safely (step 3), with the fake Kobo from conftest.py ---


@pytest.fixture
def font_file(tmp_path):
    source = tmp_path / "Literata-Regular.ttf"
    source.write_bytes(b"pretend font data")
    return source


def part_files(folder: Path) -> list[Path]:
    return list(folder.rglob("*" + PART_SUFFIX))


def test_copy_puts_an_identical_file_on_the_kobo(fake_kobo, font_file):
    copy_to_kobo(fake_kobo, font_file, Path("fonts/Literata-Regular.ttf"))

    copied = fake_kobo.mount / "fonts" / "Literata-Regular.ttf"
    assert copied.read_bytes() == font_file.read_bytes()
    assert part_files(fake_kobo.mount) == []


def test_copy_replaces_an_older_version(fake_kobo, font_file):
    old = fake_kobo.mount / "fonts" / "Literata-Regular.ttf"
    old.parent.mkdir()
    old.write_bytes(b"old version")

    copy_to_kobo(fake_kobo, font_file, Path("fonts/Literata-Regular.ttf"))
    assert old.read_bytes() == b"pretend font data"


@pytest.mark.parametrize(
    "destination, message",
    [
        (".kobo/KoboReader.sqlite", "never writes inside .kobo"),
        (".KOBO/screensaver/x.png", "never writes inside .kobo"),  # same folder on the Kobo's drive
        ("../outside.ttf", "plain path inside the Kobo"),
        ("/tmp/outside.ttf", "plain path inside the Kobo"),
    ],
)
def test_copy_refuses_forbidden_places(fake_kobo, font_file, destination, message):
    with pytest.raises(KoboError, match=message):
        copy_to_kobo(fake_kobo, font_file, Path(destination))
    assert sorted(p.name for p in fake_kobo.mount.iterdir()) == [".kobo"]  # nothing was written


def test_copy_stops_when_the_kobo_is_nearly_full(fake_kobo, font_file, monkeypatch):
    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda path: Usage(2_000, 1_990, 10))

    with pytest.raises(KoboError, match="Not enough room"):
        copy_to_kobo(fake_kobo, font_file, Path("fonts/Literata-Regular.ttf"))
    assert not (fake_kobo.mount / "fonts").exists()


def test_damaged_copy_is_removed_and_the_old_file_kept(fake_kobo, font_file, monkeypatch):
    old = fake_kobo.mount / "fonts" / "Literata-Regular.ttf"
    old.parent.mkdir()
    old.write_bytes(b"old version")
    # Pretend the copy came back different: the fingerprint of the copy and the original don't match.
    fingerprints = iter(["fingerprint-of-copy", "fingerprint-of-original"])
    monkeypatch.setattr(kobo_module, "file_hash", lambda path: next(fingerprints))

    with pytest.raises(KoboError, match="doesn't match the original"):
        copy_to_kobo(fake_kobo, font_file, Path("fonts/Literata-Regular.ttf"))
    assert old.read_bytes() == b"old version"
    assert part_files(fake_kobo.mount) == []


def test_failed_write_is_reported_and_cleaned_up(fake_kobo, font_file, monkeypatch):
    def unplugged_mid_copy(source, part):
        part.write_bytes(b"half a fo")
        raise OSError(5, "Input/output error")

    monkeypatch.setattr(kobo_module, "_write_to_device", unplugged_mid_copy)

    with pytest.raises(KoboError, match="Input/output error"):
        copy_to_kobo(fake_kobo, font_file, Path("fonts/Literata-Regular.ttf"))
    assert part_files(fake_kobo.mount) == []


def test_leftover_part_files_are_removed_and_nothing_else(fake_kobo):
    fonts = fake_kobo.mount / "fonts"
    fonts.mkdir()
    (fonts / ("Literata-Bold.ttf" + PART_SUFFIX)).write_bytes(b"interrupted")
    (fonts / "MyOwnFont-Regular.ttf").write_bytes(b"added by hand")
    (fonts / "notes.part").write_bytes(b"not kraken's")

    removed = remove_leftover_parts(fake_kobo, Path("fonts"))

    assert [path.name for path in removed] == ["Literata-Bold.ttf" + PART_SUFFIX]
    assert sorted(path.name for path in fonts.iterdir()) == ["MyOwnFont-Regular.ttf", "notes.part"]


def test_leftover_clean_up_never_looks_inside_kobo_folder(fake_kobo):
    with pytest.raises(KoboError, match="never writes inside .kobo"):
        remove_leftover_parts(fake_kobo, Path(".kobo"))


def test_leftover_clean_up_of_a_missing_folder_does_nothing(fake_kobo):
    assert remove_leftover_parts(fake_kobo, Path("fonts")) == []


def test_delete_removes_a_font(fake_kobo):
    font = fake_kobo.mount / "fonts" / "Literata-Bold.ttf"
    font.parent.mkdir()
    font.write_bytes(b"font")
    delete_from_kobo(fake_kobo, Path("fonts/Literata-Bold.ttf"))
    assert not font.exists()


@pytest.mark.parametrize("destination", ["kraken/alice.epub", "alice.epub", "fonts", ".kobo/KoboReader.sqlite"])
def test_delete_refuses_anything_outside_fonts(fake_kobo, destination):
    book = fake_kobo.mount / destination
    book.parent.mkdir(parents=True, exist_ok=True)
    if not book.exists():
        book.write_bytes(b"a book")

    with pytest.raises(KoboError, match="Refusing to"):
        delete_from_kobo(fake_kobo, Path(destination))
    assert book.exists()
