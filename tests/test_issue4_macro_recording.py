"""Issue #4 — gravação de macros funcional e responsiva.

Cobre (sem hardware, fakes determinísticos):

1. cancelar/parar DURANTE o handshake XRecord aborta o start (antes
   o pedido era ignorado e o worker vazava);
2. truncamento pelo teto MAX_EVENTS é sinalizado (nada de macro
   truncada com cara de sucesso);
3. cancelamento durante o handshake no nível do serviço;
4. a UI (MacrosPage) não bloqueia a thread de eventos: start/stop/
   cancel rodam em worker e o resultado é aplicado pelo polling.
"""

from __future__ import annotations

import threading
import time
import types
from typing import List, Optional

import pytest

from mouse_hub.core.automation.service import AutomationService
from mouse_hub.platform.linux import capture as capture_module
from mouse_hub.platform.linux.capture import InputCapture

pytest.importorskip("PyQt5")
from PyQt5.QtWidgets import QApplication  # noqa: E402

from tests.fakes import (  # noqa: E402
    StrictFakeXRecordBackend,
    wire_key_press,
    wire_key_release,
)


# ── backend com handshake bloqueável (sem StartOfData até soltar) ──

class BlockedHandshakeBackend(StrictFakeXRecordBackend):
    """enable_context bloqueia SEM entregar StartOfData até que
    `release()` seja chamado — simula servidor X lento/travado."""

    def __init__(self) -> None:
        super().__init__(events_to_inject=[wire_key_press(38)])
        self._release = threading.Event()
        self.disable_during_start = False

    def release(self):
        self._release.set()

    def enable_context(self, ctx, data_display, ctl_display, callback):
        if ctx not in self._ctx_map:
            raise ValueError(f"ctx {ctx} desconhecido")
        stored_data, stored_ctl, _ = self._ctx_map[ctx]
        if data_display is not stored_data or ctl_display is not stored_ctl:
            raise ValueError("identidade divergente")
        self.enable_count += 1
        self._enabled_ctx = ctx
        self._callback = callback
        # bloqueia SEM handshake — o caso patológico real
        self._release.wait()
        callback(self._make_reply_start())
        for blob in self.events_to_inject:
            callback(self._make_reply(blob))
        while self._enabled_ctx == ctx:
            time.sleep(0.005)
        callback(self._make_reply_end())


# ── 1) cancel/stop durante o starting ────────────────────────────

def _start_in_thread(cap: InputCapture):
    out = {}
    def run():
        out["ok"] = cap.start()
    t = threading.Thread(target=run, daemon=True)
    t.start()
    time.sleep(0.2)  # handshake bloqueado, estado starting
    return t, out


def test_cancel_during_starting_aborts_start():
    backend = BlockedHandshakeBackend()
    cap = InputCapture(lambda e: None, backend=backend)
    t, out = _start_in_thread(cap)
    assert cap.state == "starting"

    cap.cancel()
    t.join(timeout=2.0)
    assert t.is_alive() is False, "start() não retornou após cancel"
    assert out["ok"] is False
    assert "cancelado" in (cap.failure or "")
    assert cap.state == "stopped"
    # contexto liberado exatamente uma vez — sem vazamento
    assert backend.free_count == 1


def test_stop_during_starting_aborts_start():
    backend = BlockedHandshakeBackend()
    cap = InputCapture(lambda e: None, backend=backend)
    t, out = _start_in_thread(cap)
    assert cap.state == "starting"

    count = cap.stop()
    t.join(timeout=2.0)
    assert t.is_alive() is False
    assert out["ok"] is False
    assert count == 0
    assert "parado" in (cap.failure or "")
    assert backend.free_count == 1


def test_normal_lifecycle_unaffected():
    """O aborto durante starting não quebra o lifecycle normal."""
    backend = BlockedHandshakeBackend()
    received = []
    cap = InputCapture(lambda e: received.append(e), backend=backend)
    t, out = _start_in_thread(cap)
    backend.release()  # handshake chega → recording
    t.join(timeout=2.0)
    assert out["ok"] is True and cap.recording
    cap.stop()
    assert any(e.kind.name == "KEY_PRESS" for e in received)


# ── 2) truncamento sinalizado ────────────────────────────────────

def test_max_events_truncation_is_signalled(monkeypatch):
    received = []
    monkeypatch.setattr(capture_module, "MAX_EVENTS", 2)
    backend = StrictFakeXRecordBackend(
        events_to_inject=[
            wire_key_press(38, time_ms=10),
            wire_key_release(38, time_ms=60),
            wire_key_press(39, time_ms=90),  # excede o teto
        ]
    )
    cap = InputCapture(lambda e: received.append(e), backend=backend)
    assert cap.start() is True
    cap.stop()

    assert len(received) == 2  # o terceiro evento é descartado
    assert cap.truncated is True


# ── 3) cancelamento durante o handshake no serviço ──────────────

def test_service_cancel_during_starting(tmp_path):
    backend = BlockedHandshakeBackend()
    svc = AutomationService(macros_path=tmp_path / "macros.json", capture_backend=backend)
    out = {}

    def run():
        out["ok"] = svc.start_recording("m1")

    t = threading.Thread(target=run, daemon=True)
    t.start()
    time.sleep(0.2)
    # a captura está registrada e cancelável durante o handshake
    svc.cancel_recording()
    t.join(timeout=2.0)
    assert t.is_alive() is False
    assert out["ok"] is False
    assert "cancelado" in (svc.capture_failure or "")
    assert svc.recording is False
    # nenhuma macro foi salva
    assert svc.list_macros() == []


# ── 4) UI responsiva: gravação fora da thread de eventos ────────

class FakeMe:
    """Superfície MacroEngine com operações lentas (handshake real
    pode levar segundos) — valida o comportamento não bloqueante."""

    def __init__(self):
        self.recording = False
        self.capture_failed: Optional[str] = None
        self.macros = {}
        self.last_recording_truncated = False
        self.start_delay = 0.0
        self.start_result = True
        self.stop_result: Optional[str] = None
        self.cancel_calls = 0

    def start_recording(self, name):
        token = self.cancel_calls
        time.sleep(self.start_delay)
        if self.cancel_calls > token:
            # cancelado durante o "handshake" — o start falha
            self.capture_failed = "cancelado durante inicialização"
            return False
        if self.start_result:
            self.recording = True
            return True
        self.capture_failed = "display indisponível"
        return False

    def stop_recording(self):
        time.sleep(0.05)
        self.recording = False
        name = self.stop_result
        if name is not None:
            self.macros[name] = {"count": 3, "created": "2026-08-27T00:00:00"}
        return name

    def cancel_recording(self):
        time.sleep(0.05)
        self.cancel_calls += 1
        self.recording = False

    playback_state = "stopped"
    playback_error = None

    def list_all(self):
        return self.macros

    def cleanup(self):
        pass


@pytest.fixture(scope="module")
def qapp():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _drain(page, timeout=3.0):
    """Processa eventos Qt até a operação assíncrona concluir."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        page._poll_op()
        if page._op_kind is None and page._op_result is None:
            return True
        time.sleep(0.02)
    return False


def _make_page(qapp):
    import app.mouse_hub_app as app_module
    return app_module.MacrosPage(FakeMe(), None)


def test_ui_start_does_not_block_event_loop(qapp):
    page = _make_page(qapp)
    page.me.start_delay = 0.4  # handshake "lento"

    page._toggle_record()
    # a UI respondeu IMEDIATAMENTE (não bloqueou 0.4s): botão
    # desabilitado e status de progresso, op pendente
    assert page._op_kind == "start"
    assert page.record_btn.isEnabled() is False
    assert "Iniciando" in page.record_status.text()

    assert _drain(page)
    assert page.record_status.text().startswith("🔴 Gravando")
    assert page.cancel_btn.isVisible() or not page.cancel_btn.isHidden()
    assert page.record_btn.isEnabled() is True


def test_ui_start_failure_shows_reason(qapp):
    page = _make_page(qapp)
    page.me.start_result = False

    page._toggle_record()
    assert _drain(page)
    assert "Não foi possível iniciar" in page.record_status.text()
    assert "display indisponível" in page.record_status.text()


def test_ui_stop_saves_and_refreshes(qapp):
    page = _make_page(qapp)
    page.me.recording = True
    page.me.stop_result = "minha_macro"

    page._toggle_record()
    assert page._op_kind == "stop"
    assert page.record_btn.isEnabled() is False

    assert _drain(page)
    assert "✅ Macro 'minha_macro' salva! (3 eventos)" in page.record_status.text()
    assert page.me.recording is False


def test_ui_stop_truncated_warns(qapp):
    page = _make_page(qapp)
    page.me.recording = True
    page.me.stop_result = "grande"
    page.me.last_recording_truncated = True

    page._toggle_record()
    assert _drain(page)
    assert "TRUNCADA" in page.record_status.text()


def test_ui_cancel_during_starting(qapp):
    """Cancelar durante o handshake: o pedido chega ao me (não é
    ignorado) e a UI mostra o desfecho quando o start falha."""
    page = _make_page(qapp)
    page.me.start_delay = 0.4

    page._toggle_record()
    assert page._op_kind == "start"
    page._cancel_record()
    assert page.me.cancel_calls >= 0  # pedido em caminho (worker)

    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and page.me.cancel_calls == 0:
        QApplication.processEvents()
        time.sleep(0.02)
    assert page.me.cancel_calls == 1

    assert _drain(page)
    assert page._op_kind is None
    # o desfecho do start cancelado aparece com o motivo real
    assert "cancelado" in page.record_status.text()
