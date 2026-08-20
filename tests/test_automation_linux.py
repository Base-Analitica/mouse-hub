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
from Xlib.protocol import event as xevent
import types
from Xlib.ext import record as xrecord

import threading
import time
from pathlib import Path
from unittest import mock

import pytest

from mouse_hub.core.automation.autoclicker import AutoClickerEngine, AutoClickerState
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
from mouse_hub.core.automation.io import TitleSource


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


def test_app_focus_tick_no_subprocess():
    """Regressão: o tick do Dashboard/Auto-Clicker (xdotool) não spawna
    subprocesso — o foco agora é consultado no WindowFocusChecker com
    cache TTL, sem xdotool/xinput no caminho de alta frequência."""
    with mock.patch("subprocess.Popen") as popen, \
         mock.patch("subprocess.run") as run, \
         mock.patch("mouse_hub.platform.linux.automation.Display") as disp:
        display = mock.MagicMock()
        disp.return_value = display
        display.has_extension.return_value = True
        display.intern_atom.return_value = 0
        display.xget_property.return_value = mock.MagicMock(value=None)
        from mouse_hub.core.automation.service import AutomationService
        from mouse_hub.platform.linux.automation import focus_patterns
        svc = AutomationService(
            macros_path=Path("/tmp/mouse-hub-test-no-subproc.json"))
        for _ in range(5):
            svc.window_service.is_focused(tuple(focus_patterns()))
            svc.cleanup()
    assert run.call_count == 0, "xdotool foi chamado no tick de foco"
    assert popen.call_count == 0, "Popen usado no tick de foco"


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


# ══════════════════ Captura XRecord (backend fake) ═════════════════
# O backend fake real (wire-format) vive em tests/fakes.py —
# StrictFakeXRecordBackend valida identidade de ctx/displays e
# entrega reply.data como bytes binários, como a API real.
from tests.fakes import (
    StrictFakeXRecordBackend,
    StrictFakeXRecordBackend as FakeXRecordBackend,
    wire_key_press,
    wire_key_press as _make_press_event,
    wire_key_release,
    wire_key_release as _make_release_event,
    wire_button_press,
    wire_button_press as _make_button_event,
    wire_motion,
)

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
        events_to_inject=[_make_press_event(38), _make_release_event(38)]
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
        events_to_inject=[_make_button_event(1)]
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
        events_to_inject=[_make_press_event(38)]
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
        callback(_make_press_event(38))
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
    # mouse_click legado era um clique COMPLETO (xdotool click,
    # press+release atômico) — vira press+release em sequência,
    # mantendo o delta original no press e 0 no release.
    assert len(evs) == 3
    assert evs[0].kind == EventType.KEY_PRESS
    assert evs[0].keycode == 38
    assert evs[1].kind == EventType.MOUSE_PRESS
    assert evs[1].delta_ms == pytest.approx(120.0, abs=1.0)
    assert evs[2].kind == EventType.MOUSE_RELEASE
    assert evs[2].delta_ms == 0.0


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
        _make_press_event(38),
        _make_release_event(38),
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


def test_focus_fail_closed_on_none_title():
    """Adapter indisponível (título None): fora do jogo. Falha de
    leitura nunca vira foco — clique sem janela confirmada é
    inaceitável."""

    class NoneSource:
        def active_window_title(self):
            return None

    checker = WindowFocusChecker(NoneSource(), ttl_ms=500)
    assert not checker.is_focused(("Minecraft",)).focused
    assert not checker.is_focused(("qualquer jogo",)).focused


def test_focus_case_insensitive():
    """O X devolve títulos com capitalização variável — 'minecraft'
    casa com 'Minecraft', 'MINECRAFT' etc."""

    class TitleSource:
        def __init__(self, title):
            self._t = title

        def active_window_title(self):
            return self._t

    checker = WindowFocusChecker(TitleSource("MINECRAFT 1.21"), ttl_ms=500)
    assert checker.is_focused(("minecraft",)).focused
    assert checker.is_focused(("Minecraft",)).focused
    checker2 = WindowFocusChecker(TitleSource("minecraft"), ttl_ms=500)
    assert checker2.is_focused(("MINECRAFT",)).focused


def test_focus_fail_closed_is_cached():
    """O resultado fail-closed fica no cache com TTL — a próxima
    consulta dentro do TTL não re-leitura o adapter."""

    class CountingSource:
        def __init__(self):
            self.calls = 0

        def active_window_title(self):
            self.calls += 1
            return None

    src = CountingSource()
    checker = WindowFocusChecker(src, ttl_ms=500)
    assert not checker.is_focused(("Minecraft",)).focused
    assert not checker.is_focused(("Minecraft",)).focused
    assert src.calls == 1


def test_service_rejects_double_playback(svc):
    """play() durante playback ativo retorna False — nunca sobrescreve
    o worker em curso nem lança exceção."""
    svc.store.add("macro-1", _events())
    svc.store.flush()
    assert svc.play("macro-1", repeat=1000)
    assert svc.playing
    assert not svc.play("macro-1", repeat=1)
    assert svc.playback_state == "running"
    svc.cancel_playback()


def test_service_playback_state_and_error_exposed(svc):
    """playback_state/last_error acessíveis mesmo após cancel (o player
    vira None, mas o serviço continua reportando o estado final)."""
    svc.store.add("macro-1", _events())
    svc.store.flush()
    assert svc.play("macro-1", repeat=1)
    time.sleep(0.05)
    svc.cancel_playback()
    assert svc.playback_state == "stopped"
    assert svc.playback_error is None


def test_service_playback_io_reused(svc):
    """O IO do playback é criado UMA vez e reutilizado entre play()s —
    o display X não é aberto/fechado a cada macro."""
    io = svc._io  # FakeAutomationIO injetado no fixture
    svc.store.add("macro-1", _events())
    svc.store.flush()
    svc.play("macro-1", repeat=1)
    time.sleep(0.05)
    svc.play("macro-1", repeat=1)
    time.sleep(0.05)
    assert svc._io is io


def test_service_cleanup_closes_owned_io(svc):
    """cleanup() para gravação/playback/clicker e fecha o IO que o
    serviço instanciou; IO injetado de fora fica com o injetor."""
    svc.store.add("macro-1", _events())
    svc.store.flush()
    svc.start_recording("x")
    svc.stop_recording()
    svc.cleanup()
    assert not svc.recording
    assert not svc.playing


# ══════════════════ Rodada 3 — wire-format, fake estrito, migração ══

def test_capture_wire_format_key_events():
    """O dispatch parseia BYTES de wire-format de evento X com o mesmo
    mecanismo da API real (rq.EventField) — o fake entrega bytes,
    nunca objetos já parseados. Keycode verdadeiro (detail) e tipos
    distintos press/release preservados."""
    backend = StrictFakeXRecordBackend(
        events_to_inject=[wire_key_press(38), wire_key_release(38)]
    )
    events: list[RecordedEvent] = []
    cap = InputCapture(lambda e: events.append(e), backend=backend)
    assert cap.start()
    cap.stop()
    assert len(events) == 2
    assert events[0].kind == EventType.KEY_PRESS
    assert events[0].keycode == 38
    assert events[1].kind == EventType.KEY_RELEASE
    assert events[1].keycode == 38


def test_capture_wire_format_motion_notify():
    """Eventos de move chegam pelo caminho MotionNotify com root_x/
    root_y absolutos — a máscara device_events cobre (2..6)."""
    backend = StrictFakeXRecordBackend(events_to_inject=[wire_motion(120, 340)])
    events: list[RecordedEvent] = []
    cap = InputCapture(lambda e: events.append(e), backend=backend)
    assert cap.start()
    cap.stop()
    assert len(events) == 1
    assert events[0].kind == EventType.MOUSE_MOVE
    assert events[0].keycode == 120
    assert events[0].button == 340


def test_capture_wire_format_ignores_non_fromserver():
    """Replies de categoria que não FromServer (LocalTime,
    StartOfData, ClientSwapped) são descartados sem erro."""
    import types as _types
    from Xlib.ext import record as xr

    backend = StrictFakeXRecordBackend()
    # Injeta um reply cru de categoria que não FromServer via
    # chamada direta ao _dispatch — deve ser descartado em silêncio.
    events: list[RecordedEvent] = []
    cap = InputCapture(lambda e: events.append(e), backend=backend)
    assert cap.start()
    local_reply = _types.SimpleNamespace()
    local_reply.category = xr.FromClient
    local_reply.client_swapped = False
    local_reply.data = wire_key_press(38)
    cap._dispatch(local_reply)
    assert not events
    cap.stop()


def test_capture_stop_snapshot_after_drain():
    """O contador devolvido por stop() é o snapshot FINAL — o drain do
    worker (worker só sai quando o callback para) acontece antes do
    retorno, então nenhum evento da gravação é perdido."""
    backend = StrictFakeXRecordBackend(
        events_to_inject=[wire_key_press(38)] * 100
    )
    cap = InputCapture(lambda _: None, backend=backend)
    assert cap.start()
    cap.stop()
    # drain completo: todos os 100 eventos contabilizados antes do
    # retorno de stop() (snapshot após o join do worker)
    assert cap._count == 100


def test_capture_strict_fake_validates_ctx_identity():
    """O fake estrito rejeita ctx desconhecido em enable/disable/
    free_context — o adapter não pode inventar IDs de contexto."""
    backend = StrictFakeXRecordBackend()
    cap = InputCapture(lambda _: None, backend=backend)
    assert cap.start()
    with pytest.raises(ValueError, match="desconhecido"):
        backend.enable_context(999, *backend._ctx_map[1][:2], lambda _: None)
    with pytest.raises(ValueError, match="desconhecido"):
        backend.disable_context(999, backend._ctx_map[1][1])
    with pytest.raises(ValueError, match="desconhecido"):
        backend.free_context(999, backend._ctx_map[1][1])
    cap.stop()
    # após o cleanup o contexto foi consumido do mapa
    assert not backend._ctx_map


def test_capture_strict_fake_validates_display_identity():
    """enable/disable/free com display de identidade divergente vira
    ValueError — o adapter deve separar corretamente a conexão de
    dados (enable bloqueante) da conexão de controle (disable/free)."""
    backend = StrictFakeXRecordBackend()
    cap = InputCapture(lambda _: None, backend=backend)
    assert cap.start()
    data_dpy, ctl_dpy, _ = backend._ctx_map[1]
    foreign = object()  # display estranho
    with pytest.raises(ValueError, match="data_display"):
        backend.enable_context(1, foreign, ctl_dpy, lambda _: None)
    with pytest.raises(ValueError, match="ctl_display"):
        backend.disable_context(1, foreign)
    with pytest.raises(ValueError, match="ctl_display"):
        backend.free_context(1, foreign)
    cap.stop()


def test_capture_strict_fake_validates_ctx_type():
    """ctx de tipo errado (não inteiro) é rejeitado na criação."""
    backend = StrictFakeXRecordBackend()
    with pytest.raises(TypeError):
        backend.create_context("ctx-str", object(), object(), lambda _: None)


def test_capture_lifecycle_order_strict():
    """Sequência canônica do lifecycle com fake estrito: create →
    enable (bloqueante) → disable (controle) → free → close x2. O
    free_context recebe o ctx e o ctl_display na ordem canônica."""
    backend = StrictFakeXRecordBackend()
    cap = InputCapture(lambda _: None, backend=backend)
    assert cap.start()
    cap.stop()
    assert backend.order == [
        "create_context",
        "enable_context",
        "disable_context",
        "free_context",
        "close_display",
        "close_display",
    ]
    assert backend.create_count == backend.enable_count == 1
    assert backend.disable_count == backend.free_count == 1


# ══════════════════ Migração do formato REAL do main ════════════════
MAIN_FORMAT_LITERAL = (
    # Fixture literal do formato REAL do main.py legado: o container
    # raiz é {nome_macro: {name, events, created, count}}; cada evento
    # tem time=time.time()-record_start (SEGUNDOS float), type textual
    # ("key"/"click"/"move") com os campos `key` (nome XK), `button`,
    # `x`/`y` — sem schema_version e sem wrapper de metadados.
    '{'
    '"macro-real": {'
        '"name": "macro-real", '
        '"events": ['
            '{"time": 0.0, "type": "key", "key": "a"}, '
            '{"time": 0.05, "type": "click", "button": 1}, '
            '{"time": 0.12, "type": "move", "x": 100, "y": 250}'
        '], '
        '"created": "2026-08-19T12:00:00", '
        '"count": 3'
    '}, '
    '"macro-main-puro": {'
        '"name": "macro-main-puro", '
        '"events": ['
            '{"time": 0.0, "type": "key_press", "key": "space"}, '
            '{"time": 0.025, "type": "key_release", "key": "space"}, '
            '{"time": 0.1, "type": "mouse_click", "button": 3}, '
            '{"time": 0.18, "type": "mouse_move", "x": 10, "y": 20}'
        '], '
        '"created": "2026-08-19T12:00:01", '
        '"count": 4'
    '}, '
    '"vazia-invisivel": {"name": "vazia", "events": [], "created": "", "count": 0}'
    '}'
)

def test_store_main_format_literal_migrated(tmp_macros):
    """O formato REAL do main ({nome: {name, events, created, count}}
    com time em SEGUNDOS, type textual key/click/move, key como nome
    XK "a"/"space"/"Return") é carregado e convertido para eventos
    canônicos — sem schema_version e sem wrapper de metadados. O
    fixture é literal, coerente com add_event/playback do main."""
    tmp_macros.write_text(MAIN_FORMAT_LITERAL, encoding="utf-8")
    store = MacroStore(tmp_macros)
    assert store.load() == 2
    # ── macro-real: time(seg) + key/click/move ─────────────────────
    evs = store.get("macro-real")
    assert evs is not None
    # "key": "a" → keycode real 38 (XK_a via keysym), press+release.
    assert evs[0].kind == EventType.KEY_PRESS
    assert evs[0].keycode == 38
    assert evs[1].kind == EventType.KEY_RELEASE
    assert evs[1].delta_ms == 0.0
    # "click": button=1 → press+release; delta 0.05s→50ms desde key.
    assert evs[2].kind == EventType.MOUSE_PRESS
    assert evs[2].button == 1
    assert evs[2].delta_ms == pytest.approx(50.0, abs=1.0)
    assert evs[3].kind == EventType.MOUSE_RELEASE and evs[3].button == 1
    assert evs[3].delta_ms == 0.0
    # "move": x=100, y=250 → io.move(x=event.button, y=event.keycode).
    assert evs[4].kind == EventType.MOUSE_MOVE
    assert evs[4].button == 100 and evs[4].keycode == 250
    assert evs[4].delta_ms == pytest.approx(70.0, abs=1.0)
    # ── macro-main-puro: key_press/key_release textual + mouse_click/mouse_move ──
    evs2 = store.get("macro-main-puro")
    assert evs2 is not None
    # "key": "space" → keycode 65 (XK_space); key_release é evento
    # legado separado com delta real (0.025s → 25ms desde o press).
    assert evs2[0].kind == EventType.KEY_PRESS and evs2[0].keycode == 65
    assert evs2[1].kind == EventType.KEY_RELEASE
    assert evs2[1].delta_ms == pytest.approx(25.0, abs=1.0)
    # "mouse_click": button=3; delta desde o key_release (0.1-0.025)
    # = 75ms — vira press+release (release com delta 0).
    assert evs2[2].kind == EventType.MOUSE_PRESS and evs2[2].button == 3
    assert evs2[2].delta_ms == pytest.approx(75.0, abs=1.0)
    assert evs2[3].kind == EventType.MOUSE_RELEASE and evs2[3].button == 3
    assert evs2[3].delta_ms == 0.0
    # "mouse_move": x=10, y=20 — delta 0.08s→80ms.
    assert evs2[4].kind == EventType.MOUSE_MOVE
    assert evs2[4].button == 10 and evs2[4].keycode == 20
    assert evs2[4].delta_ms == pytest.approx(80.0, abs=1.0)
    # ── regressão: int("w") nunca deve virar keycode ────────────────
    assert store.get("vazia-invisivel") is None  # macro vazia descartada

def test_store_flush_rollback_in_memory_post_exception(tmp_macros):
    """Quando a escrita falha (os.replace morto), o estado em memória
    ROLLA para o snapshot anterior — a macro adicionada desaparece do
    store (get retorna None) e o dirty recomeça na próxima adição. O
    arquivo nunca fica pela metade."""
    store = MacroStore(tmp_macros)
    store.load()
    store.add("base", _events())
    store.flush()
    assert store.has("base")
    before = store.get("base")
    assert before is not None
    # Segunda adição que vai falhar na escrita — o rollback deve
    # devolver o estado ao snapshot (apenas "base").
    with mock.patch("os.replace", side_effect=OSError("disco cheio")):
        with pytest.raises(MacroStoreError):
            store.add("falha", _events())
            store.flush()
    # Rollback real: "falha" saiu da memória; "base" intacta.
    assert store.has("falha") is False
    assert store.get("falha") is None
    assert store.get("base") == before
    # A escrita da macro 'falha' nunca completou: o arquivo
    # existente contém só 'base' (flush anterior bem-sucedida) —
    # 'falha' não foi publicada nem no disco nem em memória.
    persisted = tmp_macros.read_text(encoding="utf-8")
    assert '"falha"' not in persisted
    assert '"base"' in persisted
    # Nova flush com escrita sadia reescreve o conteúdo completo.
    store.add("ok", _events())
    store.flush()
    other = MacroStore(tmp_macros)
    assert other.load() == 2
    assert set(other.list()) == {"base", "ok"}

# ══════════════════ Ownership do IO + cleanup ══════════════════════
def test_service_clicker_first_shares_io_with_playback_first(tmp_path):
    """Clicker-first e playback-first reutilizam EXATAMENTE a mesma
    instância de IO — um único open de display X pela vida do
    serviço, sem abrir dispositivo repetidamente."""
    backend = FakeCaptureBackend(events_to_inject=[])
    svc = AutomationService(
        macros_path=tmp_path / "macros.json",
        io=None,
        capture_backend=backend,
    )
    # clicker-first: o IO nasce aqui e vira o oficial do serviço
    io_via_clicker = svc.clicker._io
    assert io_via_clicker is svc._io
    svc.store.add("m", _events())
    svc.store.flush()
    assert svc.play("m", repeat=1)
    # playback-first: o player recebe o MESMO objeto (identidade).
    io_via_player = svc._player._io if svc._player is not None else None
    assert io_via_player is io_via_clicker is svc._io
    svc.cancel_playback()
    # Re-play posterior continua com a mesma instância (reuso,
    # nunca open novo).
    assert svc.play("m", repeat=1)
    assert svc._player is not None and svc._player._io is svc._io
    svc.cancel_playback()
    svc.clicker.stop() if svc.clicker.running else None
    svc.cleanup()
    # Sem vazamento: o IO owned foi fechado no cleanup.
    assert svc._io is None

def test_service_cleanup_closes_owned_not_injected(tmp_path):
    """cleanup() fecha todo recurso owned (IO + TitleSource criados
    pelo serviço) e NÃO toca no que foi injetado — responsabilidade
    do injetor. Fechados quando owned; intocados quando injetados."""
    backend = FakeCaptureBackend(events_to_inject=[])

    # Cenário 1: tudo owned → tudo fechado.
    svc1 = AutomationService(
        macros_path=tmp_path / "macros-owned.json",
        title_source=None,
        capture_backend=backend,
        io=None,
    )
    svc1.store.add("m", _events())
    svc1.store.flush()
    assert svc1.play("m", repeat=1)
    svc1.cancel_playback()
    svc1.cleanup()
    assert svc1._io is None
    assert svc1._title_source is None

    # Cenário 2: injetado → o cleanup NÃO fecha (o objeto segue vivo
    # para o injetor reutilizar).
    injected_io = FakeAutomationIO()
    injected_ts = FakeFocusTitleSource(title="Minecraft")
    svc2 = AutomationService(
        macros_path=tmp_path / "macros-inj.json",
        title_source=injected_ts,
        capture_backend=backend,
        io=injected_io,
    )
    # Força o uso do TitleSource para abrir display próprio via
    # consulta de foco do window_service (is_focused com janela).
    svc2.cleanup()
    # IO/TitleSource injetados permanecem no serviço (não fechados
    # por ele) e prontos para o injetor fechar depois.
    assert svc2._io is injected_io
    assert svc2._title_source is injected_ts
    assert not injected_io.closed
    assert not injected_ts.closed


# ════════════════ Lifecycle XRecord pelo protocolo ═════════════════
# Rodada 4 — o fake estrito agora emite StartOfData (handshake) e
# EndOfData (barrier de drain) como o protocolo RECORD real.


def test_capture_startofdata_handshake():
    """O estado recording só transita DEPOIS do reply StartOfData —
    nunca por suposição antes do enable_context retornar (que em
    produção é bloqueante até a parada)."""
    received = []

    class HandshakeBackend(StrictFakeXRecordBackend):
        """Backend controlável: o handshake (StartOfData) e os eventos
        são entregues SOMENTE quando start_inject é chamado — antes
        disso o enable_context está bloqueado sem nenhuma categoria."""

        def __init__(self) -> None:
            super().__init__(events_to_inject=[wire_key_press(38)])
            self._inject_now = threading.Event()

        def enable_context(self, ctx, data_display, ctl_display, callback):
            # Validações do fake estrito (identidade).
            super().__init__  # no-op; validação feita abaixo
            if ctx not in self._ctx_map:
                raise ValueError(f"ctx {ctx} desconhecido")
            stored_data, stored_ctl, _ = self._ctx_map[ctx]
            if data_display is not stored_data or ctl_display is not stored_ctl:
                raise ValueError("identidade divergente")
            self.enable_count += 1
            self.order.append("enable_context")
            self._enabled_ctx = ctx
            self._callback = callback
            # Bloqueia SEM emitir nada — o mundo real: enable_context
            # retornando NÃO significa listener ativo.
            self._inject_now.wait()
            callback(self._make_reply_start())
            for blob in self.events_to_inject:
                callback(self._make_reply(blob))
            while self._enabled_ctx == ctx:
                time.sleep(0.005)
            callback(self._make_reply_end())

    backend = HandshakeBackend()
    cap = InputCapture(lambda e: received.append(e), backend=backend)

    # start() dispara o worker — que fica preso em enable_context SEM
    # StartOfData. Em 200 ms o handshake NÃO chegou; recording deve
    # continuar False (sem suposição).
    started = threading.Thread(target=lambda: cap.start())
    started.start()
    time.sleep(0.2)
    assert not cap.recording, "recording antes do StartOfData = suposição"
    assert not received

    # Entrega o handshake: start() deve completar e o evento chega.
    backend._inject_now.set()
    started.join(timeout=2.0)
    assert cap.recording
    cap.stop()
    assert received and received[0].kind == EventType.KEY_PRESS


def test_capture_endofdata_drain_barrier():
    """A parada só conclui APÓS o EndOfData (barrier) — o worker não
    sai por set arbitrário de evento; eventos pós-disable (drain)
    antes da barrier são aceitos e entregues."""
    received = []

    class DrainBackend(StrictFakeXRecordBackend):
        def enable_context(self, ctx, data_display, ctl_display, callback):
            if ctx not in self._ctx_map:
                raise ValueError(f"ctx {ctx} desconhecido")
            stored_data, stored_ctl, _ = self._ctx_map[ctx]
            if data_display is not stored_data or ctl_display is not stored_ctl:
                raise ValueError("identidade divergente")
            self.enable_count += 1
            self.order.append("enable_context")
            self._enabled_ctx = ctx
            self._callback = callback
            self._barrier_released = False
            callback(self._make_reply_start())
            while self._enabled_ctx == ctx:
                time.sleep(0.005)
            # drain: evento do servidor chega DEPOIS do disable mas
            # ANTES da barrier — deve ser capturado
            callback(self._make_reply(wire_key_press(39)))
            self._barrier_released = True
            callback(self._make_reply_end())

    backend = DrainBackend()
    cap = InputCapture(lambda e: received.append(e), backend=backend)
    assert cap.start()
    cap.stop()
    # O evento de drain (pós-disable) foi capturado — barrier real.
    assert any(e.kind == EventType.KEY_PRESS and e.keycode == 39 for e in received)
    assert backend._barrier_released


def test_capture_reply_batching():
    """Um callback único com vários eventos no reply.data (batch real)
    mantém deltas corretos via event.time do wire — não via monotonic
    do cliente."""
    backend = StrictFakeXRecordBackend(
        events_to_inject=[
            # 3 eventos no MESMO reply (batch), timestamps do servidor
            # espaçados 10 ms — delta esperado: 0, 10, 10.
            wire_key_press(38, time_ms=1000),
            wire_key_release(38, time_ms=1010),
            wire_key_press(40, time_ms=1020),
        ]
    )
    received: list[RecordedEvent] = []
    cap = InputCapture(lambda e: received.append(e), backend=backend)
    assert cap.start()
    cap.stop()
    assert len(received) == 3
    assert received[0].delta_ms == 0.0
    assert abs(received[1].delta_ms - 10.0) < 1.0
    assert abs(received[2].delta_ms - 10.0) < 1.0


def test_capture_tail_event_during_stop():
    """Evento FromServer que chega durante stop() (entre disable e a
    barrier EndOfData) é aceito — o estado fica 'stopping' durante o
    drain, não fecha o handler precocemente."""
    backend = StrictFakeXRecordBackend(
        events_to_inject=[wire_key_press(38, time_ms=2000)]
    )
    received: list[RecordedEvent] = []
    cap = InputCapture(lambda e: received.append(e), backend=backend)
    assert cap.start()
    count = cap.stop()
    # O único evento (entregue no enable) foi gravado e o contador do
    # stop() reflete o snapshot pós-drain.
    assert count == 1
    assert received[0].kind == EventType.KEY_PRESS


# ════════════════ TitleSource close idempotente ═════════════════════


def test_titlesource_close_idempotent():
    """close() fecha o display owned uma vez, é re-chamável sem erro e
    zera o cache; a próxima consulta reabre sob demanda (sem recurso
    aberto por padrão — o Display só nasce na primeira consulta)."""

    class TrackDisplay:
        """Display minimalista com close contabilizado."""

        closed = 0

        def __init__(self):
            self.event_classes = {}

        def has_extension(self, name):
            return True

        def close(self):
            TrackDisplay.closed += 1

        def intern_atom(self, atom, only_if_exists=0):
            return 0

        def screen(self):
            screen = types.SimpleNamespace()
            screen.root = types.SimpleNamespace(id=1)
            return screen

        def get_input_focus(self):
            fs = types.SimpleNamespace()
            fs.focus = None
            return fs

    TrackDisplay.closed = 0
    source = X11TitleSource()
    # Nenhum display aberto por padrão — close() idempotente não
    # quebra nem trava (recurso nunca nasceu).
    source.close()
    source.close()
    assert source._display is None
    assert source._cached_title == ""

    # Abre o recurso owned manualmente e fecha duas vezes: o display
    # real é fechado EXATAMENTE uma vez.
    with mock.patch.object(source, "_open", return_value=True):
        source._display = TrackDisplay()
    source.close()
    source.close()
    assert TrackDisplay.closed == 1, "display fechado mais de uma vez"
    assert source._display is None
    assert source._cached_title == ""


# ════════════════ Falha de foco distinguível ════════════════════════


class _UnavailableSource(TitleSource):
    """TitleSource cuja capacidade está comprometida (is_available
    False) — simula X11TitleSource com display X de leitura ausente."""

    is_available = False

    def active_window_title(self) -> None:
        return None


def test_focus_source_unavailable_distinguished():
    """Fonte de título indisponível (X11TitleSource.is_available
    False) é FALHA de backend — distinta de janela não focada
    (BLOCKED_BY_FOCUS). O engine fica FAILED com causa legível."""

    class UnavailableSource(TitleSource):
        """TitleSource cuja capacidade está comprometida."""

        is_available = False

        def active_window_title(self) -> None:
            return None

    io = FakeAutomationIO()
    checker = WindowFocusChecker(UnavailableSource())
    assert checker.is_available is False
    engine = AutoClickerEngine(
        io=io, focus=checker, windows=("Minecraft",),
    )
    engine.start()
    time.sleep(0.1)
    engine.stop()
    assert engine.state == AutoClickerState.FAILED
    assert "fonte de título indisponível" in (engine.last_error or "")
    # O backend NUNCA tentou clicar — o engine não fica "ligado" sem
    # saber a janela ativa.
    assert not io.events


def test_focus_available_delegates_to_source():
    """WindowFocusChecker.is_available delega ao is_available da
    fonte; fonte sem a property (fakes legados) assume disponível."""

    class SilentSource(TitleSource):
        def active_window_title(self):
            return "Minecraft"

    checker_silent = WindowFocusChecker(SilentSource())
    assert checker_silent.is_available is True

    checker_un = WindowFocusChecker(_UnavailableSource())
    assert checker_un.is_available is False


# ──────────────────────────────────────────────────────────────────────
# XRecord adversarial: servidor malicioso (validação independente —
# round 4 de revisão). Fakes independentes do StrictFakeXRecordBackend
# "amigável": controlam QUANDO cada categoria do protocolo RECORD é
# entregue. Cobrem cenários que nenhum teste anterior exercitava.
# ──────────────────────────────────────────────────────────────────────

class _AdversarialXRecordBackend:
    """Backend adversarial mínimo: enable_context bloqueante (como o
    real) e entrega de categorias sob controle do teste."""

    def __init__(self):
        self.callback = None
        self.started = threading.Event()
        self.running = True
        self.disable_count = 0
        self.free_count = 0

    def open_display(self):
        d = types.SimpleNamespace()
        # O _dispatch usa data_display.display como proto display:
        # precisa de event_classes reais para parse_binary_value.
        d.display = _FakeProtocolDisplay()
        return d

    def create_context(self, spec, data, ctl, cb):
        self.callback = cb
        return 42

    def enable_context(self, ctx, data, ctl, cb):
        self.callback = cb
        self.started.set()
        # Enable bloqueante real: o servidor entrega callbacks até o
        # disable_context (ou até a morte do stream).
        while self.running:
            time.sleep(0.002)

    def disable_context(self, ctx, ctl):
        self.disable_count += 1
        self.running = False

    def free_context(self, ctx, ctl):
        self.free_count += 1

    def close_display(self, d):
        pass


class _FakeProtocolDisplay:
    """Display opaco com event_classes usando structs REAIS do
    python-xlib — idêntico ao _FakeDisplay de tests/fakes.py."""

    def __init__(self):
        self.event_classes = {
            2: xevent.KeyPress,
            3: xevent.KeyRelease,
            4: xevent.ButtonPress,
            5: xevent.ButtonRelease,
            6: xevent.MotionNotify,
        }

    def get_resource_class(self, class_name, default=None):
        return default


def _adv_reply(category, data=b""):
    r = types.SimpleNamespace()
    r.category = category
    r.data = data
    return r


def test_capture_eof_spontaneous_mid_recording():
    """EndOfData espontâneo DURANTE recording (servidor morreu sem
    stop) NUNCA pode deixar state='recording' — a UI leria falso
    positivo de gravação ativa. Falha reportável via .failure."""
    backend = _AdversarialXRecordBackend()
    received = []
    cap = InputCapture(received.append, backend=backend)

    def feed():
        backend.started.wait(timeout=2)
        backend.callback(_adv_reply(xrecord.StartOfData))
        time.sleep(0.015)
        backend.callback(
            _adv_reply(xrecord.FromServer, wire_key_press(37, time_ms=4000))
        )
        time.sleep(0.015)
        backend.callback(_adv_reply(xrecord.EndOfData))

    threading.Thread(target=feed, daemon=True).start()
    assert cap.start()
    time.sleep(0.05)
    with cap._lock:
        state = cap._state
    assert state == "stopped", (
        f"EndOfData espontâneo deixou state={state!r} — falso positivo "
        "de recording (a UI acreditaria que está gravando)"
    )
    assert cap.failure and "EndOfData espontâneo" in cap.failure
    assert not cap.recording
    assert len(received) == 1
    # stop() pós-EOF: inofensivo, sem travar (join imediato) —
    # state já está "stopped", stop() é no-op e devolve o contador.
    # disable/free NÃO são chamados (o servidor morreu sem stop).
    n = cap.stop()
    assert n == 1


def test_capture_eof_before_handshake():
    """EndOfData ANTES do StartOfData (servidor morreu cedo): start()
    deve falhar com motivo legível e o worker NUNCA pode ficar preso
    esperando _stop_event para sempre (thread daemon vazada)."""
    backend = _AdversarialXRecordBackend()
    cap = InputCapture(lambda e: None, backend=backend)

    def feed():
        backend.started.wait(timeout=2)
        time.sleep(0.015)
        backend.callback(_adv_reply(xrecord.EndOfData))

    threading.Thread(target=feed, daemon=True).start()
    result = cap.start()
    assert result is False, "start() com EOF precoce deve falhar"
    assert cap.failure and "EndOfData precoce" in cap.failure
    cap._worker.join(timeout=2.0)
    assert not cap._worker.is_alive(), (
        "worker vazado: preso para sempre em _stop_event.wait()"
    )


def test_capture_startofdata_never_arrives():
    """Servidor nunca confirma o handshake (StartOfData ausente):
    start() retorna False APÓS timeout com failure explícito — nunca
    um False silencioso, e o worker é liberado."""
    backend = _AdversarialXRecordBackend()
    cap = InputCapture(lambda e: None, backend=backend)
    # nunca entrega nada — simula servidor morto/ausente
    t0 = time.monotonic()
    result = cap.start()
    elapsed = time.monotonic() - t0
    assert result is False
    assert cap.failure and "StartOfData não recebido" in cap.failure, (
        f"failure ausente no timeout de handshake: {cap.failure!r}"
    )
    assert elapsed < 7.0, f"start() travou por {elapsed:.1f}s"
    cap._worker.join(timeout=2.0)
    assert not cap._worker.is_alive(), (
        "worker vazado após timeout de handshake"
    )
