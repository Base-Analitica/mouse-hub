"""Testes de descoberta por VID/PID e acesso HID, com sysfs simulado.

O sysfs real é substituído por diretórios temporários populados com
uevents sintéticos, exercitando o mesmo código de produção
(device_discovery) sem depender de um G403 conectado.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mouse_hub.core.constants import G403_PID, G403_VID
from mouse_hub.core.operation import OperationStatus
from mouse_hub.platform.linux.device_discovery import (
    HydppEndpointSelection,
    discover,
    discover_g403,
    find_g403_hidraw_devices,
    parse_hid_id,
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


# ── Parser defensivo de HID_ID ────────────────────────────────────


def test_parse_hid_id_valid():
    assert parse_hid_id("HID_ID=0003:0000046D:0000C08F") == (G403_VID, G403_PID)
    # Trailing de campos extras não invalida quando os campos essenciais
    # são numéricos — o parser extrai apenas os dois primeiros.
    assert parse_hid_id("HID_ID=0003:046D:C08F:0000:extra") == (G403_VID, G403_PID)


def test_parse_hid_id_case_insensitive():
    assert parse_hid_id("HID_ID=0003:0000046d:0000c08f") == (G403_VID, G403_PID)


def test_parse_hid_id_ignores_garbage_lines():
    for garbage in [
        "garbage without hid id",
        "HID_ID=",
        "HID_ID=0003",
        "HID_ID=0003:zzzz",
        "HID_ID=0003:0000046D:GHIJ",
        "HID_ID=0003::C08F",
        "HID_ID=0003:ZZZZ:C08F",
        "HID_NAME=not an id",
        "",
        "  ",
    ]:
        assert parse_hid_id(garbage) is None, garbage
    # Tipos errados também não lançam.
    assert parse_hid_id(None) is None  # type: ignore[arg-type]
    assert parse_hid_id(123) is None  # type: ignore[arg-type]


def test_read_uevent_identity_returns_first_valid_hid_id():
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".uevent", delete=False) as fh:
        fh.write("HID_NAME=Noise\n")
        fh.write("HID_ID=garbage:broken:fields\n")
        fh.write("HID_ID=0003:0000046D:0000C08F\n")
        fh.write("HID_PHYS=usb-0\n")
        path = Path(fh.name)
    try:
        assert read_uevent_identity(path) == (G403_VID, G403_PID)
    finally:
        path.unlink()


def test_read_uevent_identity_missing_file():
    assert read_uevent_identity(Path("/nonexistent/path/uevent")) is None


def test_read_uevent_identity_garbage_uevent():
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".uevent", delete=False) as fh:
        fh.write("garbage without hid id\n")
        path = Path(fh.name)
    try:
        assert read_uevent_identity(path) is None
    finally:
        path.unlink()


# ── Descoberta por identidade ─────────────────────────────────────


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
    assert devices[0].name == "Logitech G403 HERO Gaming Mouse"


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


def test_find_g403_ignores_malformed_uevents(tmp_path):
    """UEvents malformados (HID_ID ilegível) são ignorados, não
    quebram a varredura nem contaminam candidatos."""
    root = make_sysfs_root(tmp_path, {
        "hidraw0": "HID_ID=garbage:broken\nHID_NAME=Bad\n",
        "hidraw1": G403_UEVENT,
        "hidraw2": None,
    })
    devices = find_g403_hidraw_devices(G403_VID, G403_PID, root)
    assert len(devices) == 1
    assert devices[0].hidraw_path == "/dev/hidraw1"


def test_find_g403_handles_unreadable_uevent(tmp_path):
    """uevent sem permissão de leitura não lança; o hidraw é ignorado."""
    root = make_sysfs_root(tmp_path, {
        "hidraw0": G403_UEVENT,
        "hidraw1": G403_UEVENT,
    })
    blocked = root / "hidraw1" / "device" / "uevent"
    blocked.chmod(0o000)
    try:
        devices = find_g403_hidraw_devices(G403_VID, G403_PID, root)
        assert len(devices) == 1
        assert devices[0].hidraw_path == "/dev/hidraw0"
    finally:
        blocked.chmod(0o644)


def test_discover_returns_identity_match(tmp_path):
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


def test_discover_and_discover_g403_are_the_same():
    """Compatibilidade de alias: quem usava `discover` continua ok,
    mas a semântica é identidade apenas (precisa validação de
    protocolo depois)."""
    assert discover is discover_g403


# ── Seleção de endpoint em duas etapas (identidade + protocolo) ───


def _selection_device(root: Path, hidraw: str) -> None:
    ...


def test_endpoint_selection_validates_single_candidate(tmp_path):
    root = make_sysfs_root(tmp_path, {"hidraw2": G403_UEVENT})
    hid = FakeHidAccess()
    # Resposta ao probe GET_FEATURE_TABLE_COUNT: 4 features.
    hid.probe_responses = [b"\x11\xff\x00\x04" + b"\x00" * 16]
    selection = HydppEndpointSelection(hid)
    selected = selection.select(find_g403_hidraw_devices(G403_VID, G403_PID, root))
    assert selected is not None
    assert selected.hidraw_path == "/dev/hidraw2"


def test_endpoint_selection_rejects_non_responsive(tmp_path):
    """Candidato com identidade correta mas que não responde ao
    protocolo HID++ não é selecionado — fail closed."""
    root = make_sysfs_root(tmp_path, {"hidraw2": G403_UEVENT})
    hid = FakeHidAccess()
    hid.probe_responses = []  # probe: read devolve None = não validado
    selection = HydppEndpointSelection(hid)
    assert selection.select(find_g403_hidraw_devices(G403_VID, G403_PID, root)) is None


def test_endpoint_selection_rejects_error_response(tmp_path):
    """Candidato que responde com erro HID++ (0x8F) não é válido."""
    root = make_sysfs_root(tmp_path, {"hidraw2": G403_UEVENT})
    hid = FakeHidAccess()
    hid.probe_error_response = True
    selection = HydppEndpointSelection(hid)
    assert selection.select(find_g403_hidraw_devices(G403_VID, G403_PID, root)) is None


def test_endpoint_selection_fails_closed_on_ambiguity(tmp_path):
    """Dois endpoints que respondem ao protocolo: sem critério seguro
    de desempate, nada é selecionado (nada é escrito em endpoint
    incerto)."""
    root = make_sysfs_root(tmp_path, {
        "hidraw1": G403_UEVENT,
        "hidraw3": G403_UEVENT,
    })
    hid = FakeHidAccess()
    # Um candidato por resposta: os dois endpoints validam o probe,
    # então a seleção termina em ambiguidade (fail closed: nada).
    valid_response = hid.probe_responses[0]
    hid.probe_responses = [valid_response, valid_response]
    selection = HydppEndpointSelection(hid)
    assert selection.select(find_g403_hidraw_devices(G403_VID, G403_PID, root)) is None


def test_endpoint_selection_empty_candidates():
    selection = HydppEndpointSelection(FakeHidAccess())
    assert selection.select([]) is None


def test_endpoint_selection_handles_permission_denied(tmp_path):
    """Permissão negada no descritor é desfecho distinto, não falha
    genérica."""
    root = make_sysfs_root(tmp_path, {"hidraw2": G403_UEVENT})
    hid = FakeHidAccess()
    hid.open_permission_denied = True
    selection = HydppEndpointSelection(hid)
    assert selection.select(find_g403_hidraw_devices(G403_VID, G403_PID, root)) is None


def test_endpoint_selection_closes_descriptor_after_probe(tmp_path):
    """O probe nunca deixa o descritor aberto: open/write/read são
    seguidos de close."""
    root = make_sysfs_root(tmp_path, {"hidraw2": G403_UEVENT})
    hid = FakeHidAccess()
    selection = HydppEndpointSelection(hid)
    selection.select(find_g403_hidraw_devices(G403_VID, G403_PID, root))
    assert not hid.is_open()


def test_endpoint_selection_handles_open_exception(tmp_path):
    """Exceção inesperada no acesso não vaza nem vira seleção."""
    root = make_sysfs_root(tmp_path, {"hidraw2": G403_UEVENT})
    hid = FakeHidAccess()
    hid.open_raises = RuntimeError("sysfs sumiu")
    selection = HydppEndpointSelection(hid)
    assert selection.select(find_g403_hidraw_devices(G403_VID, G403_PID, root)) is None
    assert not hid.is_open()


# ── Acesso HID: device ausente / permissão / falha ────────────────


def test_hid_open_device_not_found_without_hidraw():
    hid = FakeHidAccess()
    device = fake_g403_device(hidraw=None)
    result = hid.open(device)
    assert result.status == OperationStatus.DEVICE_NOT_FOUND
    assert not hid.is_open()


def test_hid_open_permission_denied():
    hid = FakeHidAccess()
    device = fake_g403_device(hidraw="/dev/permission_denied")
    result = hid.open(device)
    assert result.status == OperationStatus.PERMISSION_DENIED


def test_hid_write_without_open_fails():
    hid = FakeHidAccess()
    device = fake_g403_device()
    hid.open(device)
    hid.close()
    result = hid.write(b"\x10\x10\x01\x03\x20\x00\x00")
    assert not result.status.ok


def test_hid_write_succeeds_on_confirmed_device():
    hid = FakeHidAccess()
    device = fake_g403_device()
    open_result = hid.open(device)
    assert open_result.status.ok
    write_result = hid.write(b"\x10\x10\x01\x03\x20\x00\x00")
    assert write_result.status.ok
    assert hid.written_reports == [b"\x10\x10\x01\x03\x20\x00\x00"]


def test_hid_write_failure_is_reported():
    hid = FakeHidAccess()
    hid.write_succeeds = False
    hid.open(fake_g403_device())
    result = hid.write(b"\x10\x10\x01\x03\x20\x00\x00")
    assert result.status == OperationStatus.FAILED


def test_hid_never_writes_before_opening():
    hid = FakeHidAccess()
    hid.write(b"\x10\x10\x01\x03\x20\x00\x00")
    assert hid.written_reports == []


def test_hid_read_timeout_returns_none_when_closed():
    hid = FakeHidAccess()
    assert hid.read(20, timeout=0.01) is None


def test_hid_readback_acks_set_dpi():
    hid = FakeHidAccess()
    hid.open(fake_g403_device())
    hid.write(b"\x10\x01\x10\x06\x40\x00\x00")  # set DPI 1600
    response = hid.read(20)
    assert response is not None
    assert response[2] == hid.FEATURE_DPI
    assert (response[3] << 8) | response[4] == 1600
