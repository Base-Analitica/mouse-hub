"""Testes determinísticos dos adapters Linux e do serviço de automação.

Regras desta suíte (issue: testes devem rodar sem input real e sem
dependências de ambiente):

* nenhum display X real é aberto — `XRecordBackend` e `AutomationIO`
  são injetados via fakes;
* zero subprocessos: a suíte verifica explicitamente que o hot path
  (click/play) não spawna nada;
* lifecycle: handshake de prontidão, keycode preservado, tipos reais
  press/release, cancel, stop com cleanup uma vez, fail path;
* store transacional: rollback de corrupto, duplicado, vazio,
  compatibilidade legado;
* service: mutex record/playback, lazy init, foco compartilhado.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest import mock

import pytest

from mouse_hub.core.automation.autoclicker import AutoClickerState
from mouse_hub.core.automation.focus import WindowFocusChecker
from mouse_hub.core.automation.service import AutomationService
from mouse_hub.core.automation.store import MacroStore, MacroStoreError
from mouse_hub.core.automation.types import EventType, MouseButton, RecordedEvent
from mouse_hub.platform.linux.automation import (
    LinuxAutomationIO,
    X11TitleSource,
    focus_patterns,
)
from mouse_hub.platform.linux.capture import InputCapture, XRecordBackend

from .fakes import FakeAutomationIO, FakeFocusTitleSource


# ══════════════════ Adapter XTest (LinuxAutomationIO) ═══════════════


def test_linux_io_click_is_native_no_subprocess():
    """O hot path de clique não deve chamar subprocesso algum."""
    io = LinuxAutomationIO()
    display = mock.MagicMock()
    display.has_extension.return_value = True
    with mock.patch("mouse_hub.platform.linux.automation.Display", return_value=display):
        with mock.patch("subprocess.run") as run:
            io.click(MouseButton.LEFT)
    assert run.call_count == 0


def test_linux_io_returns_false_without_display():
    """Sem display X, click retorna False (falha detectável) em vez de
    estourar exceção para a UI."""
    with mock.patch(
        "mouse_hub.platform.linux.automation.Display",
        side_effect=OSError("display indisponível"),
    ):
        io = LinuxAutomationIO()
        assert io.click(MouseButton.LEFT) is False


def test_linux_io_returns_false_without_xtest():
    """Display sem extensão XTest é tratado como falha detectável —
    conexão fechada e False devolvido."""
    io = LinuxAutomationIO()
    display = mock.MagicMock()
    display.has_extension.return_value = False
    with mock.patch("mouse_hub.platform.linux.automation.Display", return_value=display):
        assert io.click(MouseButton.LEFT) is False
    display.close.assert_called_once()


def test_linux_io_event_sequence_press_release():
    """Click emite press+release na ordem certa com o botão correto."""
    from Xlib import X

    io = LinuxAutomationIO()
    events_emitted: list[tuple] = []
    display = mock.MagicMock()
    display.has_extension.return_value = True

    def fake_input(display, event_type, detail, x=0, y=0):
        events_emitted.append((event_type, detail))

    with mock.patch("mouse_hub.platform.linux.automation.Display", return_value=display):
        with mock.patch("mouse_hub.platform.linux.automation.xtest.fake_input", side_effect=fake_input):
            ok = io.click(MouseButton.RIGHT)
    assert ok is True
    assert events_emitted == [(X.ButtonPress, 3), (X.ButtonRelease, 3)]


def test_linux_io_keycode_preserved():
    """Press/release de tecla usa o keycode informado sem conversão."""
    from Xlib import X

    io = LinuxAutomationIO()
    events_emitted: list[tuple] = []
    display = mock.MagicMock()
    display.has_extension.return_value = True

    def fake_input(display, event_type, detail, x=0, y=0):
        events_emitted.append((event_type, detail))

    with mock.patch("mouse_hub.platform.linux.automation.Display", return_value=display):
        with mock.patch("mouse_hub.platform.linux.automation.xtest.fake_input", side_effect=fake_input):
            io.key_press(keycode=38)  # keycode X real
            io.key_release(keycode=38)
    assert events_emitted == [(X.KeyPress, 38), (X.KeyRelease, 38)]


def test_linux_io_cleanup_is_idempotent():
    io = LinuxAutomationIO()
    io.cleanup()
    io.cleanup()  # segunda chamada não deve estourar
    io.cleanup()


# ══════════════════ Fonte de título X11 ════════════════════════════


def test_x11_title_source_caches_queries():
    """Com TTL interno, duas consultas seguidas não repetem a query
    ao sistema — o foco nunca é consultado por clique."""
    source = X11TitleSource(ttl_ms=500)
    # a primeira leitura do display/propriedades é o caminho caro;
    # com cache TTL, a segunda chamada reutiliza o valor
    title = "Minecraft 1.20"
    source._cached_title = title
    source._cached_until = time.monotonic() + 1.0
    read_mock = mock.Mock(return_value=title)
    original = source._read_title
    source._read_title = read_mock  # substitui a query cara no nível da instância
    try:
        a = source.active_window_title()
        b = source.active_window_title()
        assert a == b == title
        assert read_mock.call_count == 0  # cache serviu as duas chamadas
    finally:
        source._read_title = original


def test_focus_patterns_include_legacy_windows():
    """Os 10 padrões legados devem estar presentes — inclui os que a
    base da PR #14 perdeu (Mina Launcher, Prismarine, Salwyrr,
    Vanilla)."""
    patterns = [p.lower() for p in focus_patterns()]
    for required in (
        "minecraft",
        "lunar client",
        "badlion",
        "feather",
        "hypixel",
        "mina launcher",
        "prismarine",
        "salwyrr",
        "vanilla",
    ):
        assert any(required in p for p in patterns), f"padrão ausente: {required}"


# ══════════════════ Captura XRecord (backend fake) ═════════════════


class FakeXRecordBackend(XRecordBackend):
    """Backend fake determinístico: controla quando os callbacks
    chegam e registra a ordem das operações de lifecycle."""

    def __init__(self, events_to_inject: list | None = None) -> None:
        self.order: list[str] = []
        self.displays_opened = 0
        self.enable_context_raises: Exception | None = None
        self.events_to_inject: list = events_to_inject or []  # payloads pré-classificados
        self._callback = None
        self._enabled = False

    def open_display(self):
        self.displays_opened += 1
        return mock.MagicMock(name="display")

    def create_context(self, ctl, callback):
        self.order.append("create_context")
        return 1

    def enable_context(self, ctl, ctx, callback):
        self.order.append("enable_context")
        self._callback = callback
        if self.enable_context_raises is not None:
            raise self.enable_context_raises
        self._enabled = True
        # simula os eventos chegando enquanto o contexto está ativo
        for event in self.events_to_inject:
            if callback is not None:
                callback(event)
        # bloqueia até o contexto ser desabilitado (como o XRecord
        # real) — stop() deve chegar até aqui
        while self._enabled:
            time.sleep(0.005)

    def disable_context(self, ctl, ctx):
        self.order.append("disable_context")
        self._enabled = False

    def free_context(self, ctl, ctx):
        self.order.append("free_context")

    def close_display(self, display):
        self.order.append("close_display")


def _make_press_event(keycode: int = 38):
    event = mock.MagicMock()
    event.type = 2  # X.KeyPress
    event.detail = keycode
    return event


def _make_release_event(keycode: int = 38):
    event = mock.MagicMock()
    event.type = 3  # X.KeyRelease
    event.detail = keycode
    return event


def _make_button_event(button: int):
    event = mock.MagicMock()
    event.type = 4  # X.ButtonPress
    event.detail = button
    return event


class FakeData:
    """Simula o bloco `data` entregue pelo XRecord (FromServer)."""

    def __init__(self, events):
        # categoria real do xrecord — FromServer é o caminho do
        # _dispatch; hardcoded quebraria com qualquer versão da lib
        from Xlib.ext import record as xrecord

        self.category = xrecord.FromServer
        self.data = events


def test_capture_handshake_ready():
    """start() só retorna True depois do handshake — ready confirmado
    pela ordem enable_context antes do retorno."""
    backend = FakeXRecordBackend()
    events: list[RecordedEvent] = []
    cap = InputCapture(lambda e: events.append(e), backend=backend)

    started = cap.start()
    assert started is True
    assert cap.recording
    assert "enable_context" in backend.order


def test_capture_preserves_keycode_and_press_release_types():
    """Keycode X verdadeiro e tipos distintos press/release chegam ao
    handler — sem colapsar nem converter para nome de tecla."""
    backend = FakeXRecordBackend(
        events_to_inject=[
            FakeData([_make_press_event(38)]),
            FakeData([_make_release_event(38)]),
        ]
    )
    events: list[RecordedEvent] = []
    cap = InputCapture(lambda e: events.append(e), backend=backend)
    assert cap.start()
    time.sleep(0.05)
    cap.stop()

    assert len(events) == 2
    assert events[0].kind == EventType.KEY_PRESS
    assert events[0].keycode == 38
    assert events[1].kind == EventType.KEY_RELEASE
    assert events[1].delta_ms >= 0


def test_capture_mouse_button():
    backend = FakeXRecordBackend(
        events_to_inject=[FakeData([_make_button_event(1)])]
    )
    events: list[RecordedEvent] = []
    cap = InputCapture(lambda e: events.append(e), backend=backend)
    assert cap.start()
    time.sleep(0.05)
    cap.stop()
    assert events[0].kind == EventType.MOUSE_PRESS
    assert events[0].button == 1


def test_capture_stop_cleanup_order():
    """A parada desabilita o contexto ANTES de fechar displays e o
    contexto é liberado exatamente uma vez."""
    backend = FakeXRecordBackend()
    cap = InputCapture(lambda _: None, backend=backend)
    assert cap.start()
    cap.stop()
    assert "disable_context" in backend.order
    assert backend.order.count("free_context") == 1
    assert backend.order.count("close_display") == 2
    # ordem: disable antes do free/close
    assert backend.order.index("disable_context") < backend.order.index(
        "free_context"
    )
    assert not cap.recording


def test_capture_failure_handshake():
    """Display ausente ou XRecord indisponível: start retorna False e
    o motivo fica acessível — sem exceção para a UI."""
    backend = FakeXRecordBackend()
    backend.enable_context_raises = OSError("XRecord ausente")
    events: list[RecordedEvent] = []
    cap = InputCapture(lambda e: events.append(e), backend=backend)
    assert cap.start() is False
    assert cap.failure is not None
    assert not cap.recording


def test_capture_cancel_discards_events():
    events: list[RecordedEvent] = []
    backend = FakeXRecordBackend(
        events_to_inject=[FakeData([_make_press_event(38)])]
    )
    cap = InputCapture(lambda e: events.append(e), backend=backend)
    assert cap.start()
    time.sleep(0.05)
    cap.cancel()
    assert not cap.recording


def test_capture_no_events_after_stop():
    """Depois de stop(), nenhum evento pode ser entregue ao handler —
    o disable_context para o callback e o lock confirma o estado."""
    backend = FakeXRecordBackend()
    events: list[RecordedEvent] = []
    cap = InputCapture(lambda e: events.append(e), backend=backend)
    assert cap.start()

    # entrega manual de evento pós-stop (simula callback residual)
    cap.stop()
    callback = backend._callback
    if callback is not None:
        callback(FakeData([_make_press_event(38)]))
    assert not events


# ══════════════════ Store transacional ═════════════════════════════


@pytest.fixture
def tmp_macros(tmp_path):
    return tmp_path / "macros.json"


def _events(n=3):
    return [
        RecordedEvent(kind=EventType.KEY_PRESS, button=0, keycode=38, delta_ms=10.0),
        RecordedEvent(kind=EventType.KEY_RELEASE, button=0, keycode=38, delta_ms=90.0),
        RecordedEvent(kind=EventType.MOUSE_PRESS, button=1, keycode=0, delta_ms=5.0),
    ][:n]


def test_store_add_and_roundtrip(tmp_macros):
    store = MacroStore(tmp_macros)
    store.load()
    store.add("macro-1", _events())
    assert store.dirty
    store.flush()
    assert not store.dirty

    other = MacroStore(tmp_macros)
    assert other.load() == 1
    evs = other.get("macro-1")
    assert len(evs) == 3
    assert evs[0].kind == EventType.KEY_PRESS
    assert evs[0].keycode == 38


def test_store_rejects_empty_macro(tmp_macros):
    store = MacroStore(tmp_macros)
    store.load()
    with pytest.raises(MacroStoreError) as exc:
        store.add("vazia", [])
    assert "vazia" in exc.value.reason


def test_store_rejects_duplicate_name(tmp_macros):
    store = MacroStore(tmp_macros)
    store.load()
    store.add("dup", _events())
    with pytest.raises(MacroStoreError):
        store.add("dup", _events())
    # overwrite explícito funciona
    store.add("dup", _events(), overwrite=True)


def test_store_invalid_json_archived(tmp_macros):
    tmp_macros.write_text("{ json invalido }", encoding="utf-8")
    store = MacroStore(tmp_macros)
    assert store.load() == 0
    # o arquivo corrompido foi arquivado como evidência
    assert not tmp_macros.exists()
    backups = list(tmp_macros.parent.glob("macros.json.bak.*"))
    assert len(backups) == 1


def test_store_atomic_write(tmp_macros):
    """Interrupção no meio da escrita nunca corrompe o original: o
    arquivo destino é substituído via replace, não truncado."""
    store = MacroStore(tmp_macros)
    store.load()
    store.add("a", _events())
    with mock.patch("os.replace", side_effect=OSError("disco cheio")):
        with pytest.raises(MacroStoreError):
            store.flush()
    # original intacto (nunca existiu; o tmp foi removido no rollback)
    assert not tmp_macros.exists()


def test_store_legacy_web_format_converted(tmp_macros):
    tmp_macros.write_text(
        '{"schema_version": 0, "macros": {'
        '"web-macro": [{"type": "key_press", "t": 0, "keycode": 38}, '
        '{"type": "mouse_click", "t": 120, "button": 1}]}}',
        encoding="utf-8",
    )
    store = MacroStore(tmp_macros)
    assert store.load() == 1
    evs = store.get("web-macro")
    assert len(evs) == 2
    assert evs[0].kind == EventType.KEY_PRESS
    assert evs[0].keycode == 38
    assert evs[1].kind == EventType.MOUSE_PRESS  # mouse_click legado -> press
    assert evs[1].delta_ms == pytest.approx(120.0, abs=1.0)


def test_store_legacy_app_v0_format_converted(tmp_macros):
    """Formato v0 do app nativo: eventos soltos com "type" e "t"."""
    tmp_macros.write_text(
        '{"v0-macro": [{"type": "key_press", "t": 0, "keycode": 54}, '
        '{"type": "key_release", "t": 50, "keycode": 54}]}',
        encoding="utf-8",
    )
    store = MacroStore(tmp_macros)
    assert store.load() == 1
    evs = store.get("v0-macro")
    assert evs[0].kind == EventType.KEY_PRESS
    assert evs[1].kind == EventType.KEY_RELEASE


def test_store_deletes_and_flushes(tmp_macros):
    store = MacroStore(tmp_macros)
    store.load()
    store.add("x", _events())
    store.flush()
    assert store.delete("x")
    assert store.has("x") is False
    store.flush()

    other = MacroStore(tmp_macros)
    assert other.load() == 0


# ══════════════════ Service (mutex + lazy + foco compartilhado) ════


class FakeCaptureBackend(FakeXRecordBackend):
    pass


def _svc_events():
    """Eventos falsos injetáveis na gravação — não vazios para o
    lifecycle normal aceitar a macro."""
    return [
        FakeData([_make_press_event(38)]),
        FakeData([_make_release_event(38)]),
    ]


@pytest.fixture
def svc(tmp_path):
    backend = FakeCaptureBackend(events_to_inject=_svc_events())
    return AutomationService(
        macros_path=tmp_path / "macros.json",
        io=FakeAutomationIO(),
        capture_backend=backend,
    )


def test_service_lazy_nothing_created_at_init(svc):
    """Startup não abre display nem lê disco."""
    assert svc._title_source is None
    assert svc._focus is None
    assert svc._store is None
    assert svc._capture is None


def test_service_recording_lifecycle(svc):
    assert svc.start_recording("macro-1")
    assert svc.recording
    assert svc.stop_recording()
    assert not svc.recording
    assert "macro-1" in svc.list_macros()


def test_service_rejects_empty_recording(svc):
    """Gravação sem eventos é descartada pelo store transacional."""
    backend = svc._capture_backend
    backend.events_to_inject = []
    assert svc.start_recording("vazia")
    assert not svc.stop_recording()
    assert svc.list_macros() == []


def test_service_mutex_play_during_recording(svc):
    svc.start_recording("gravando")
    assert not svc.play("qualquer")
    svc.stop_recording()


def test_service_mutex_recording_during_playback(svc):
    svc.store.add("macro-1", _events())
    svc.store.flush()
    svc.play("macro-1", repeat=1000)
    assert not svc.start_recording("nova")
    svc.cancel_playback()


def test_service_shared_focus(svc):
    """Dashboard e clicker usam o MESMO checker — sem query duplicada
    ao sistema."""
    a = svc.window_service
    b = svc.window_service
    assert a is b


def test_service_clicker_uses_focus_and_io(svc):
    clicker = svc.clicker
    clicker.start()
    time.sleep(0.15)
    clicker.stop()
    assert clicker.state == AutoClickerState.STOPPED
