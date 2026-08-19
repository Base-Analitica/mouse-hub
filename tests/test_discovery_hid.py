"""Testes de descoberta por VID/PID e acesso HID, com sysfs simulado.

O sysfs real é substituído por diretórios temporários populados com
uevents sintéticos, exercitando o mesmo código de produção
(device_discovery) sem depender de um G403 conectado.

O FakeHidAccess é uma máquina de protocolo HID++ 2.0: o probe é
executado de verdade (feature set count + IRoot.GetFeature(0x2201)),
com respostas computadas a partir dos requests — nunca fila fixa.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mouse_hub.core.constants import G403_PID, G403_VID
from mouse_hub.core.operation import OperationStatus
from mouse_hub.platform.read_outcome import ReadOutcomeKind
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


def test_endpoint_selection_validates_single_candidate(tmp_path):
    """Candidato com identidade e protocolo corretos é selecionado.

    O fake executa o probe real: feature set count + IRoot.GetFeature
    devolve o índice dinâmico da Adjustable DPI (0x2201)."""
    root = make_sysfs_root(tmp_path, {"hidraw2": G403_UEVENT})
    hid = FakeHidAccess()
    selection = HydppEndpointSelection(hid)
    selected = selection.select(find_g403_hidraw_devices(G403_VID, G403_PID, root))
    assert selected is not None
    assert selected.hidraw_path == "/dev/hidraw2"


def test_endpoint_selection_probe_queries_0x2201_dynamically(tmp_path):
    """O probe consulta o FEATURE ID 0x2201 via IRoot.GetFeature e usa
    o índice devolvido — não há feature index hardcoded na seleção."""
    root = make_sysfs_root(tmp_path, {"hidraw2": G403_UEVENT})
    hid = FakeHidAccess()
    selection = HydppEndpointSelection(hid)
    selection.select(find_g403_hidraw_devices(G403_VID, G403_PID, root))
    get_feature_request = [
        r for r in hid.written_reports
        if len(r) == 20 and r[2] == 0x00 and ((r[3] >> 4) & 0x0F) == 0
        and ((r[4] << 8) | r[5]) == 0x2201
    ]
    assert len(get_feature_request) == 1
    # Todos os reports de probe são FAP long (0x11), device index 0xFF
    # — nunca short report.
    assert all(r[0] == 0x11 and r[1] == 0xFF for r in hid.written_reports)


def test_endpoint_selection_rejects_non_responsive(tmp_path):
    """Candidato com identidade correta mas que não responde ao
    protocolo HID++ não é selecionado — fail closed."""
    root = make_sysfs_root(tmp_path, {"hidraw2": G403_UEVENT})
    hid = FakeHidAccess()
    hid.ack_timeout = True  # endpoint mudo: read devolve None
    selection = HydppEndpointSelection(hid)
    assert selection.select(find_g403_hidraw_devices(G403_VID, G403_PID, root)) is None


def test_endpoint_selection_rejects_stage1_error(tmp_path):
    """Endpoint que responde IRoot mas rejeita GetFeature(0x2201) com
    erro FAP 2.0 não valida para DPI — o erro é correlacionado com o
    request (eco do header), não um sub-report genérico."""
    root = make_sysfs_root(tmp_path, {"hidraw2": G403_UEVENT})
    hid = FakeHidAccess()
    hid.probe_stage2_error = True
    selection = HydppEndpointSelection(hid)
    assert selection.select(find_g403_hidraw_devices(G403_VID, G403_PID, root)) is None


def test_endpoint_selection_rejects_stage2_error(tmp_path):
    """GetFeature(0x2201) devolvendo feature ausente (index 0): HID++
    válido, mas sem a feature ajustável — não seleciona."""
    root = make_sysfs_root(tmp_path, {"hidraw2": G403_UEVENT})
    hid = FakeHidAccess()
    hid.dpi_feature_index = 0
    selection = HydppEndpointSelection(hid)
    assert selection.select(find_g403_hidraw_devices(G403_VID, G403_PID, root)) is None


def test_endpoint_selection_feature_absent_is_rejected(tmp_path):
    """HID++ confirmado mas sem a feature 0x2201 (índice 0): o endpoint
    não serve para controle de DPI — fail closed."""
    root = make_sysfs_root(tmp_path, {"hidraw2": G403_UEVENT})
    hid = FakeHidAccess()
    hid.dpi_feature_index = 0  # feature ausente
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
    # O fake computa respostas por request: ambos os candidatos
    # validam o probe de forma independente — a seleção termina em
    # ambiguidade e nada é selecionado (fail closed).
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
    outcomes = selection.probe(find_g403_hidraw_devices(G403_VID, G403_PID, root))
    assert outcomes and outcomes[0].access_status == OperationStatus.PERMISSION_DENIED
    assert selection.select(find_g403_hidraw_devices(G403_VID, G403_PID, root)) is None


def test_endpoint_selection_write_failure_preserves_cause(tmp_path):
    """Open OK mas write falha durante o probe (hot-unplug entre open e
    a primeira escrita): a causa REAL do write (DEVICE_NOT_FOUND /
    PERMISSION_DENIED / FAILED) é preservada no ProbeOutcome — nunca
    colapsada em FAILED genérico. O mesmo vale para o write da etapa 2."""
    root = make_sysfs_root(tmp_path, {"hidraw2": G403_UEVENT})
    hid = FakeHidAccess()
    selection = HydppEndpointSelection(hid)
    candidates = find_g403_hidraw_devices(G403_VID, G403_PID, root)

    # Etapa 1 (GetProtocolVersion) falha no write.
    for cause, status in (
        ("device_not_found", OperationStatus.DEVICE_NOT_FOUND),
        ("permission_denied", OperationStatus.PERMISSION_DENIED),
        ("failed", OperationStatus.FAILED),
    ):
        hid.write_failure_status = cause
        outcome = selection.probe(candidates)[0]
        assert outcome.access_status == status, (
            f"write failure '{cause}' deve virar {status.value}"
        )
        assert outcome.valid is False
        hid.write_failure_status = None


def test_endpoint_selection_causes_are_never_collapsed(tmp_path):
    """ProbeOutcome preserva a causa REAL do acesso — permission denied,
    device ausente e falha genérica NUNCA colapsam em um único
    accessible=False (nem se tornam True)."""
    from mouse_hub.core.operation import OperationStatus

    root = make_sysfs_root(tmp_path, {"hidraw2": G403_UEVENT})
    hid = FakeHidAccess()
    selection = HydppEndpointSelection(hid)
    candidates = find_g403_hidraw_devices(G403_VID, G403_PID, root)

    hid.open_permission_denied = True
    outcome = selection.probe(candidates)[0]
    assert outcome.access_status == OperationStatus.PERMISSION_DENIED
    assert outcome.accessible is False

    hid.open_permission_denied = False
    hid.open_raises = RuntimeError("fd sumiu")
    outcome = selection.probe(candidates)[0]
    assert outcome.access_status == OperationStatus.FAILED
    assert outcome.accessible is False

    hid.open_raises = None
    hid.ack_timeout = True  # open OK, protocolo mudo
    outcome = selection.probe(candidates)[0]
    assert outcome.access_status == OperationStatus.APPLIED
    assert outcome.accessible is True
    assert outcome.valid is False


def test_endpoint_selection_protocol_error_carries_error_code(tmp_path):
    """O error code real do erro FAP é preservado no outcome para o
    reason do caller — nunca descartado."""
    root = make_sysfs_root(tmp_path, {"hidraw2": G403_UEVENT})
    hid = FakeHidAccess()
    hid.probe_stage2_error = True
    hid.probe_stage2_error_code = 0x08
    selection = HydppEndpointSelection(hid)
    outcome = selection.probe(
        find_g403_hidraw_devices(G403_VID, G403_PID, root)
    )[0]
    assert outcome.error_code == 0x08
    assert outcome.valid is False


@pytest.mark.parametrize("cause", [
    "device_not_found",
    "permission_denied",
    "failed",
], ids=["hot_unplug", "permission_lost", "generic"])
def test_probe_stage2_write_failure_carries_cause(
    tmp_path: Path, cause: str
):
    """Falha de transporte no SEGUNDO write do probe
    (IRoot.GetFeature(0x2201)) preserva a causa real no ProbeOutcome e
    o endpoint NÃO é validado — sem exceções (nem erro FAP 0x09):

    1. open funciona (device existe);
    2. PRIMEIRO write (GetProtocolVersion) → OK;
    3. read do GetProtocolVersion → ACK válido;
    4. SEGUNDO write (GetFeature) → falha de transporte tipada;
    5. ProbeOutcome.access_status == causa real (A/B/C);
    6. valid=False — nada é aceito.

    write_failure_at garante que a falha ocorre no write #2
    (o primeiro passa e o ACK da etapa 1 é recebido antes)."""
    hid = FakeHidAccess()
    # write_failure_at é ordinal absoluto da máquina de protocolo:
    # reset do contador por cenário — o probe em si tem writes #1 e #2.
    hid._write_counter = 0
    hid.write_failure_status = cause
    hid.write_failure_at = 2

    selection = HydppEndpointSelection(hid)
    root = make_sysfs_root(tmp_path, {"hidraw2": G403_UEVENT})
    devices = find_g403_hidraw_devices(G403_VID, G403_PID, root)
    assert devices, "device G403 deve ser encontrado pela identidade"
    outcome = selection.probe(devices)[0]

    assert outcome.valid is False, (
        "endpoint NÃO deve ser validado após write falho na etapa 2"
    )
    assert outcome.access_status == OperationStatus(cause), (
        f"causa real do write #2 deve ser preservada: {cause}"
    )
    # Evidência de que o write #2 é o que falhou: a primeira etapa
    # completou (protocol_version_request aceito + ACK consumido).
    assert hid.query_count >= 1
    # Sem causa colapsada em FAILED genérico.
    assert outcome.access_status != OperationStatus.FAILED or cause == "failed"


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
    result = hid.write(b"\x10\x00\x01\x34\x00\x06\x40")
    assert not result.status.ok


def test_hid_write_succeeds_on_confirmed_device():
    hid = FakeHidAccess()
    device = fake_g403_device()
    open_result = hid.open(device)
    assert open_result.status.ok
    # FAP long 0x11, device index 0xFF: SetSensorDPI (fn 0x03) com
    # sensor 0 e DPI 1600 big endian.
    report = b"\x11\xff\x01\x34\x00\x06\x40" + b"\x00" * 13
    write_result = hid.write(report)
    assert write_result.status.ok
    assert hid.written_reports == [report]
    # Short report (0x10) não é aceito para FAP: o fake não responde
    # ao request (eco pendente limpo no close).


def test_hid_write_failure_is_reported():
    """Falha de transporte na escrita (fd sumiu, I/O no OS) é relatada
    como OSError — quem escreveu não pode presumir sucesso."""
    hid = FakeHidAccess()
    hid.write_succeeds = False
    hid.open(fake_g403_device())
    report = b"\x11\xff\x01\x34\x00\x06\x40" + b"\x00" * 13
    with pytest.raises(OSError):
        hid.write(report)
    assert hid.written_reports == []  # nada foi escrito de fato


def test_hid_never_writes_before_opening():
    hid = FakeHidAccess()
    report = b"\x11\xff\x01\x34\x00\x06\x40" + b"\x00" * 13
    hid.write(report)
    assert hid.written_reports == []


def test_hid_read_timeout_returns_none_when_closed():
    hid = FakeHidAccess()
    # Contrato tipado (ReadOutcome): handle fechado é TIMEOUT — nunca
    # falha de transporte inventada (fd fechado ≠ device ausente).
    outcome = hid.read(20, timeout=0.01)
    assert outcome.kind == ReadOutcomeKind.TIMEOUT
    assert outcome.data is None


def test_hid_echoes_header_in_response(tmp_path):
    """A resposta espelha o header do request (report id, device index,
    feature index, function+software ID) — o eco que o core exige para
    correlacionar ACKs."""
    root = make_sysfs_root(tmp_path, {"hidraw2": G403_UEVENT})
    hid = FakeHidAccess()
    selection = HydppEndpointSelection(hid)
    selection.select(find_g403_hidraw_devices(G403_VID, G403_PID, root))
    # Os writes de probe devem ter respostas com o mesmo header.
    # Snapshot da lista antes do loop: reescrever os requests de probe
    # os re-adicionaria à mesma lista durante a iteração (crescimento
    # infinito).
    snapshot = list(hid.written_reports)
    for report in snapshot:
        hid.open(fake_g403_device())
        hid.write(report)
        response = hid.read(20)
        assert response.data is not None
        assert response.data[0] == report[0]
        assert response.data[1] == report[1]
        assert response.data[3] == report[3]
        hid.close()


def test_hid_readback_acks_set_dpi():
    """Readback do SetSensorDPI devolve o DPI aplicado no payload,
    ecoando o header — a confirmação que o core exige."""
    hid = FakeHidAccess()
    hid.open(fake_g403_device())
    # SetSensorDPI em FAP long: device index 0xFF, feature index 1
    # (descoberto), fn 0x03 + sw 0x04, sensor 0, 1600 big endian.
    hid.write(b"\x11\xff\x01\x34\x00\x06\x40" + b"\x00" * 13)
    response = hid.read(20)
    assert response.data is not None
    # Eco do header em long report.
    assert response.data[0] == 0x11
    assert response.data[1] == 0xFF
    assert response.data[2] == 0x01
    assert (response.data[3] >> 4) & 0x0F == 0x03
    # Payload: DPI aplicado confirmado pelo dispositivo.
    assert hid.applied_dpi == 1600
