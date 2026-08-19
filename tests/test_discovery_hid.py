"""Testes de descoberta por VID/PID e acesso HID, com sysfs simulado.

O sysfs real é substituído por diretórios temporários populados com
uevents sintéticos, exercitando o mesmo código de produção
(device_discovery) sem depender de um G403 conectado.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from mouse_hub.core.constants import G403_PID, G403_VID
from mouse_hub.core.discovery import discover
from mouse_hub.platform.linux.device_discovery import (
    find_g403_hidraw_devices,
    read_uevent_identity,
)
from tests.fakes import FakeHidAccess, fake_g403_device


# ── Helpers de sysfs falso ────────────────────────────────────────


def make_sysfs_root(tmp_path: Path, entries: dict[str, str]) -> Path:
    """Cria um sysfs fake. `entries` mapeia nome do hidraw -> conteúdo
    do device/uevent (None = sem arquivo uevent)."""
    root = tmp_path / "sys" / "class" / "hidraw"
    for name, content in entries.items():
        uevent = root / name / "device" / "uevent"
        if content is not None:
            uevent.parent.mkdir(parents=True)
            uevent.write_text(content)
        else:
            (root / name).mkdir(parents=True)
    return root


G403_UEVENT = (
    "HID_ID=0003:0000046D:0000C08F\n"
    "HID_NAME=Logitech G403 HERO Gaming Mouse\n"
    "HID_PHYS=usb-0000:00:14.0-1/input0\n"
)

OTHER_MOUSE_UEVENT = (
    "HID_ID=0003:0000046D:0000C091\n"
    "HID_NAME=Logitech G Pro Wireless\n"
)

KEYBOARD_UEVENT = (
    "HID_ID=0003:0000046D:0000C31C\n"
    "HID_NAME=Logitech K120 Keyboard\n"
)


# ── Descoberta ────────────────────────────────────────────────────


def test_find_g403_by_vid_pid_in_fake_sysfs(tmp_path):
    root = make_sysfs_root(tmp_path, {
        "hidraw0": KEYBOARD_UEVENT,
        "hidraw1": OTHER_MOUSE_UEVENT,
        "hidraw2": G403_UEVENT,
    })
    devices = find_g403_hidraw_devices(G403_VID, G403_PID, root)
    assert len(devices) == 1
    assert devices[0].hidraw_path == "/dev/hidraw2"
    assert devices[0].vid == G403_VID
    assert devices[0].pid == G403_PID


def test_find_g403_never_matches_other_devices(tmp_path):
    root = make_sysfs_root(tmp_path, {
        "hidraw0": KEYBOARD_UEVENT,
        "hidraw1": OTHER_MOUSE_UEVENT,
        "hidraw2": KEYBOARD_UEVENT,
    })
    assert find_g403_hidraw_devices(G403_VID, G403_PID, root) == []


def test_find_g403_returns_all_matches_when_multiple(tmp_path):
    root = make_sysfs_root(tmp_path, {
        "hidraw1": G403_UEVENT,
        "hidraw3": G403_UEVENT,
    })
    devices = find_g403_hidraw_devices(G403_VID, G403_PID, root)
    assert len(devices) == 2


def test_discover_returns_first_match(tmp_path):
    root = make_sysfs_root(tmp_path, {
        "hidraw1": G403_UEVENT,
        "hidraw3": G403_UEVENT,
    })
    device = discover(G403_VID, G403_PID, root)
    assert device is not None
    assert device.hidraw_path == "/dev/hidraw1"


def test_discover_returns_none_when_g403_absent(tmp_path):
    root = make_sysfs_root(tmp_path, {
        "hidraw0": KEYBOARD_UEVENT,
        "hidraw1": OTHER_MOUSE_UEVENT,
    })
    assert discover(G403_VID, G403_PID, root) is None


def test_discover_returns_none_with_empty_sysfs(tmp_path):
    root = make_sysfs_root(tmp_path, {})
    assert discover(G403_VID, G403_PID, root) is None


def test_discover_returns_none_with_missing_sysfs(tmp_path):
    assert discover(G403_VID, G403_PID, tmp_path / "nonexistent") is None


def test_discover_ignores_hidraw_without_uevent(tmp_path):
    root = make_sysfs_root(tmp_path, {"hidraw0": None})
    assert discover(G403_VID, G403_PID, root) is None


def test_read_uevent_identity_missing_file(tmp_path):
    assert read_uevent_identity(tmp_path / "nope") is None


def test_read_uevent_identity_garbage_uevent(tmp_path):
    uevent = tmp_path / "uevent"
    uevent.write_text("garbage without hid id\n")
    assert read_uevent_identity(uevent) is None


# ── Acesso HID: device ausente / permissão / falha ────────────────


def test_hid_open_device_not_found_without_hidraw():
    hid = FakeHidAccess()
    device = fake_g403_device(hidraw=None)
    result = hid.open(device)
    assert result.status.value == "device_not_found"
    assert not hid.is_open()


def test_hid_open_permission_denied():
    hid = FakeHidAccess()
    device = fake_g403_device(hidraw="/dev/permission_denied")
    result = hid.open(device)
    assert result.status.value == "permission_denied"


def test_hid_write_without_open_fails():
    hid = FakeHidAccess()
    device = fake_g403_device()
    hid.open(device)
    hid.close()
    result = hid.write(b"\x10\x10\x00\x03\x20\x00\x00")
    assert not result.status.ok


def test_hid_write_succeeds_on_confirmed_device(tmp_path):
    hid = FakeHidAccess()
    device = fake_g403_device()
    open_result = hid.open(device)
    assert open_result.status.ok
    write_result = hid.write(b"\x10\x10\x00\x03\x20\x00\x00")
    assert write_result.status.ok
    assert hid.written_reports == [b"\x10\x10\x00\x03\x20\x00\x00"]


def test_hid_write_failure_is_reported(tmp_path):
    hid = FakeHidAccess()
    hid.write_succeeds = False
    hid.open(fake_g403_device())
    result = hid.write(b"\x10\x10\x00\x03\x20\x00\x00")
    assert result.status.value == "failed"


def test_hid_never_writes_before_opening(tmp_path):
    hid = FakeHidAccess()
    hid.write(b"\x10\x10\x00\x03\x20\x00\x00")
    assert hid.written_reports == []
