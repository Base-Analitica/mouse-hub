"""Issue #9 — teste ponta-a-ponta da promessa central.

O checklist da issue #9 já está coberto pela suíte (clamp/step e
fronteiras DPI/sensibilidade em test_dpi_sensitivity + test_invariants;
persistência de config e perfis em test_config_profiles; serialização/
reprodução/repeat de macros em test_invariants + test_scheduler_
regression; limites do clicker em test_invariants; capacidades sem
HID/ferramentas em test_capabilities; G403 ausente em test_discovery_hid
e test_mouse_controller; falha sem sucesso falso nos testes de
OperationResult). O elo que faltava era o FLUXO COMPLETO em uma
sequência só: gravar → persistir → NOVA instância do serviço →
reproduzir com ordem e timing fiéis.
"""

from __future__ import annotations

import time

import pytest

from mouse_hub.core.automation.service import AutomationService
from tests.fakes import (
    FakeAutomationIO,
    StrictFakeXRecordBackend,
    wire_key_press,
    wire_key_release,
    wire_button_press,
    wire_button_release,
)


@pytest.fixture
def capture_backend():
    """Gravação sintética: tecla (38) → pausa 120 ms → clique (1).
    Timestamps são do clock do SERVIDOR X (wire format)."""
    return StrictFakeXRecordBackend(
        events_to_inject=[
            wire_key_press(38, time_ms=0),
            wire_key_release(38, time_ms=40),
            wire_button_press(1, time_ms=160),
            wire_button_release(1, time_ms=200),
        ]
    )


def test_full_flow_record_persist_reload_play(tmp_path, capture_backend):
    """Gravar → fechar → reabrir o app → reproduzir: ordem e timing
    preservados entre instâncias do serviço (critério de aceite da
    issue #4/#9)."""
    io_1 = FakeAutomationIO()
    svc1 = AutomationService(
        macros_path=tmp_path / "macros.json",
        io=io_1,
        capture_backend=capture_backend,
    )
    assert svc1.start_recording("fluxo") is True
    # eventos chegam via callback do backend (handshake assíncrono)
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not svc1.recording:
        time.sleep(0.01)
    time.sleep(0.1)  # margem para o batch de eventos do fake
    assert svc1.stop_recording() is True
    assert svc1.list_macros() == ["fluxo"]

    macro_1 = svc1.store.get("fluxo")
    svc1.cleanup()

    # NOVA instância (app fechado e reaberto): lê o MESMO arquivo.
    io_2 = FakeAutomationIO()
    backend_2 = StrictFakeXRecordBackend(events_to_inject=[])
    svc2 = AutomationService(
        macros_path=tmp_path / "macros.json",
        io=io_2,
        capture_backend=backend_2,
    )
    assert svc2.list_macros() == ["fluxo"]
    macro_2 = svc2.store.get("fluxo")
    # serialização/desserialização idempotente entre instâncias
    assert [(e.kind, e.keycode, e.button, e.delta_ms) for e in macro_2] == \
        [(e.kind, e.keycode, e.button, e.delta_ms) for e in macro_1]

    # reprodução pelo motor nativo, repeat preservado
    assert svc2.play("fluxo", repeat=2) is True
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and svc2.playing:
        time.sleep(0.02)
    assert svc2.playback_state == "stopped"

    # 4 eventos × 2 repetições, na ordem gravada
    expected = [
        ("key_press", 38), ("key_release", 38),
        ("press", "left"), ("release", "left"),
    ]
    got = [(k, v) for k, v in io_2.events if k in ("key_press", "key_release", "press", "release")]
    # FakeAutomationIO registra botões como ("press"/"release", MouseButton)
    got = [(k, (v.value if hasattr(v, "value") else v)) for k, v in io_2.events
           if k in ("key_press", "key_release", "press", "release")]
    assert got == expected * 2
    svc2.cleanup()


def test_full_flow_rejects_play_during_recording(tmp_path, capture_backend):
    """Mutex gravação↔playback: nunca um worker sobrescrito."""
    io_1 = FakeAutomationIO()
    svc = AutomationService(
        macros_path=tmp_path / "macros.json",
        io=io_1,
        capture_backend=capture_backend,
    )
    # macro pré-existente no arquivo (de uma sessão anterior)
    from mouse_hub.core.automation.types import EventType, RecordedEvent
    svc.store.add("antiga", [RecordedEvent(kind=EventType.KEY_PRESS, button=0, keycode=38, delta_ms=0.0)])
    svc.store.flush()
    assert svc.start_recording("nova") is True
    try:
        assert svc.play("antiga") is False
    finally:
        svc.cancel_recording()
        svc.cleanup()
