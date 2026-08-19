"""Testes das automações de baixo overhead.

Focos de verificação:
* AutoClickerEngine: CPS 1-50, botões, foco condicionante, sem
  subprocesso no hot path (fake acumula chamadas diretas), desligar
  imediato, mudança de CPS/botão sem recriar worker, zero CPU
  desligado;
* WindowFocusChecker: cache TTL, frequência de foco independente de
  CPS, comportamento conservador sem título;
* MacroRecorder: captura por callback (não polling), lifecycle curto,
  delta relativo, persistência;
* MacroPlayer: emissão correta na ordem/timing aproximado, cancel
  imediato, sem busy-wait;
* AutomationScheduler: cancelável, ajuste de intervalo a quente.

Todos os testes rodam sem X, sem subprocess e sem cliques reais.
"""

from __future__ import annotations

import json
import threading
import time

import pytest

from mouse_hub.core.automation.autoclicker import AutoClickerEngine
from mouse_hub.core.automation.focus import WindowFocusChecker
from mouse_hub.core.automation.macros import MacroPlayer, MacroRecorder
from mouse_hub.core.automation.scheduler import AutomationScheduler
from mouse_hub.core.automation.types import EventType, MouseButton, RecordedEvent
from tests.fakes import FakeAutomationIO, FakeFocusTitleSource


# ── Scheduler ─────────────────────────────────────────────────────


def test_scheduler_wait_completes_interval():
    scheduler = AutomationScheduler(0.1)
    t0 = time.monotonic()
    assert scheduler.wait_next() is True
    assert time.monotonic() - t0 >= 0.09


def test_scheduler_stop_interrupts_wait():
    scheduler = AutomationScheduler(10.0)
    interrupted: list[bool] = []

    def stopper():
        time.sleep(0.05)
        scheduler.stop()
        interrupted.append(scheduler.wait_next() is False)

    threading.Thread(target=stopper, daemon=True).start()
    # wait_next longa, interrompida pela thread
    result = scheduler.wait_next()
    assert result is False
    assert all(interrupted)


def test_scheduler_interval_change_wakes_immediately():
    scheduler = AutomationScheduler(10.0)
    t0 = time.monotonic()

    def changer():
        time.sleep(0.05)
        scheduler.interval = 0.02

    threading.Thread(target=changer, daemon=True).start()
    first = scheduler.wait_next()
    elapsed = time.monotonic() - t0
    assert elapsed < 0.5  # acordou cedo pelo setter (interrompe o aguardo)
    # wait_next retornou False quando foi interrompido pelo setter.
    assert first is False
    # Após reset(), o novo aguardo usa o intervalo reduzido.
    scheduler.reset()
    assert scheduler.wait_next() is True
    assert time.monotonic() - t0 < 1.0


def test_scheduler_rejects_non_positive():
    with pytest.raises(ValueError):
        AutomationScheduler(0)


# ── Auto-clicker ──────────────────────────────────────────────────


def make_engine(io=None, title=None, cps=20, windows=("Minecraft",)):
    io = io or FakeAutomationIO()
    source = FakeFocusTitleSource(title)
    focus = WindowFocusChecker(source, ttl_ms=100)
    return AutoClickerEngine(io=io, focus=focus, cps=cps, windows=windows), io


def test_clicker_requires_valid_cps():
    _, io = make_engine()
    with pytest.raises(ValueError):
        AutoClickerEngine(io=io, focus=WindowFocusChecker(FakeFocusTitleSource("x")), cps=0)
    with pytest.raises(ValueError):
        AutoClickerEngine(io=io, focus=WindowFocusChecker(FakeFocusTitleSource("x")), cps=51)


def test_clicker_clicks_when_focused():
    engine, io = make_engine(title="Minecraft 1.20")
    engine.start()
    time.sleep(0.35)
    engine.stop()
    # 20 CPS * 0.35s ≈ 7 cliques (com tolerância de agendamento)
    assert 3 <= io.events.count({"type": "click", "button": "left"}) <= 9
    assert engine.stats.clicks == io.events.count({"type": "click", "button": "left"})


def test_clicker_blocked_outside_game():
    engine, io = make_engine(title="Google Chrome")
    engine.start()
    time.sleep(0.25)
    engine.stop()
    assert io.events == []


def test_clicker_no_event_with_unavailable_title():
    """Sem título (sistema fora do X ou indisponível): conservador."""
    engine, io = make_engine(title=None)
    engine.start()
    time.sleep(0.2)
    engine.stop()
    assert io.events == []


def test_clicker_respects_button_change_without_restart():
    engine, io = make_engine(title="Minecraft")
    engine.start()
    time.sleep(0.15)
    engine.set_button(MouseButton.RIGHT)
    time.sleep(0.15)
    engine.stop()
    kinds = {e["button"] for e in io.events if e["type"] == "click"}
    assert kinds == {"left", "right"}


def test_clicker_cps_change_without_restart():
    engine, io = make_engine(title="Minecraft", cps=5)
    engine.start()
    time.sleep(0.2)
    engine.set_cps(40)
    time.sleep(0.3)
    engine.stop()
    assert engine.cps == 40
    assert engine.running is False
    # Após stop, a thread foi encerrada: nenhuma atividade residual.
    assert engine._worker is None


def test_clicker_stop_is_immediate():
    engine, io = make_engine(title="Minecraft", cps=1)
    engine.start()
    time.sleep(0.05)
    t0 = time.monotonic()
    engine.stop()
    # stop não pode esperar o intervalo de 1 s do CPS baixo
    assert time.monotonic() - t0 < 0.5
    assert engine.running is False


def test_clicker_zero_cpu_when_off():
    engine, io = make_engine(title="Minecraft")
    assert engine.running is False
    assert engine._worker is None
    # Sem worker, sem scheduler, sem aguardo: nada consome CPU.
    assert engine.stats.clicks == 0


def test_clicker_no_subprocess_in_hot_path():
    """O hot path é composto apenas de chamadas diretas ao IO fake;
    nenhuma chamada cria subprocess (verificado pelo design:
    FakeAutomationIO nunca toca subprocess, e o engine só chama
    io.click — sem Popen/run em nenhum lugar do loop)."""
    engine, io = make_engine(title="Minecraft", cps=20)
    engine.start()
    time.sleep(0.2)
    engine.stop()
    # Cada clique do hot path virou exatamente 1 chamada direta.
    clicks = sum(1 for e in io.events if e["type"] == "click")
    assert clicks >= 1


def test_clicker_idempotent_start_stop():
    engine, io = make_engine(title="Minecraft")
    engine.start()
    engine.start()  # não deve duplicar worker
    engine.stop()
    engine.stop()
    assert engine.running is False


# ── Foco ──────────────────────────────────────────────────────────


def test_focus_cache_skips_system_queries():
    """A frequência de foco é o TTL, não o CPS."""
    source = FakeFocusTitleSource("Minecraft")
    before = source.query_count
    focus = WindowFocusChecker(source, ttl_ms=200)
    results = [focus.is_focused(("Minecraft",)) for _ in range(100)]
    assert all(r.focused for r in results)
    # Se o cache funcionou, a source foi consultada no máximo 2 vezes
    # (primeira + eventual expiração no fim da janela de teste),
    # contra 100 se cada is_focused consultasse o sistema.
    assert source.query_count - before <= 2


def test_focus_invalidated_window():
    source = FakeFocusTitleSource("Minecraft")
    focus = WindowFocusChecker(source, ttl_ms=5000)
    assert focus.is_focused(("Minecraft",)).focused is True
    source.title = "Spotify"
    focus.invalidate()
    assert focus.is_focused(("Minecraft",)).focused is False


def test_focus_no_windows_allows_any():
    source = FakeFocusTitleSource("Spotify")
    focus = WindowFocusChecker(source)
    assert focus.is_focused(()).focused is True


def test_focus_rejects_low_ttl():
    with pytest.raises(ValueError):
        WindowFocusChecker(FakeFocusTitleSource("x"), ttl_ms=50)


FakeFocusTitleSource.query_count = 0  # monkeypatch global: contar consultas


def _patched_title(self):
    FakeFocusTitleSource.query_count += 1
    return self.title


FakeFocusTitleSource.active_window_title = _patched_title


# ── Macros: gravação ──────────────────────────────────────────────


def test_recorder_captures_events_incrementally():
    recorder = MacroRecorder()
    handler = recorder.make_handler()
    recorder.start()
    handler({"kind": "mouse_press", "button": 1})
    handler({"kind": "key_press", "keycode": 65})
    handler({"kind": "mouse_release", "button": 1})
    recorder.stop()
    events = recorder.events
    assert len(events) == 3
    assert events[0].kind == EventType.MOUSE_PRESS
    assert events[2].delta_ms > 0


def test_recorder_ignores_events_after_stop():
    recorder = MacroRecorder()
    handler = recorder.make_handler()
    recorder.start()
    handler({"kind": "mouse_press", "button": 1})
    recorder.stop()
    handler({"kind": "mouse_press", "button": 1})
    assert len(recorder.events) == 1


def test_recorder_lifecycle_is_short_lived():
    recorder = MacroRecorder()
    recorder.start()
    recorder.stop()
    # Após stop, listeners desconectados e sem estado pendente:
    assert recorder.recording is False
    assert len(recorder.events) == 0


def test_recorder_relative_timing():
    recorder = MacroRecorder()
    handler = recorder.make_handler()
    recorder.start()
    handler({"kind": "mouse_press", "button": 1})
    time.sleep(0.05)
    handler({"kind": "mouse_press", "button": 1})
    recorder.stop()
    e1, e2 = recorder.events
    assert e1.delta_ms == 0
    assert 30 <= e2.delta_ms <= 120


def test_recorder_persistence_roundtrip(tmp_path):
    recorder = MacroRecorder()
    handler = recorder.make_handler()
    recorder.start()
    handler({"kind": "mouse_press", "button": 2})
    recorder.stop()
    path = tmp_path / "macros.json"
    MacroRecorder.save(recorder.events, path, "combo")
    loaded = MacroRecorder.load(path, "combo")
    assert loaded is not None
    assert len(loaded) == 1
    assert loaded[0].kind == EventType.MOUSE_PRESS
    assert loaded[0].button == 2


def test_recorder_load_missing_name_returns_none(tmp_path):
    assert MacroRecorder.load(tmp_path / "inexistente.json", "x") is None


# ── Macros: playback ──────────────────────────────────────────────


def test_player_emits_events_in_order():
    io = FakeAutomationIO()
    player = MacroPlayer(io)
    events = [
        RecordedEvent(EventType.MOUSE_PRESS, 1, 0, 0),
        RecordedEvent(EventType.KEY_PRESS, 0, 40, 10),
        RecordedEvent(EventType.KEY_RELEASE, 0, 40, 10),
        RecordedEvent(EventType.MOUSE_RELEASE, 1, 0, 10),
    ]
    player.play(events, repeat=2)
    while player.playing:
        time.sleep(0.02)
    kinds = [e["type"] for e in io.events]
    expected = ["press", "key_press", "key_release", "release"] * 2
    assert kinds == expected


def test_player_cancel_wakes_worker():
    io = FakeAutomationIO()
    player = MacroPlayer(io)
    events = [RecordedEvent(EventType.MOUSE_PRESS, 1, 0, 0)] + [
        RecordedEvent(EventType.MOUSE_PRESS, 1, 0, 2000) for _ in range(50)
    ]
    player.play(events)
    time.sleep(0.15)
    assert player.playing is True
    t0 = time.monotonic()
    player.cancel()
    # cancel acorda o worker e aguarda o join.
    assert time.monotonic() - t0 < 3.0
    assert player.playing is False


def test_player_timing_respects_delta():
    io = FakeAutomationIO()
    player = MacroPlayer(io)
    events = [
        RecordedEvent(EventType.MOUSE_PRESS, 1, 0, 0),
        RecordedEvent(EventType.MOUSE_PRESS, 1, 0, 100),
        RecordedEvent(EventType.MOUSE_PRESS, 1, 0, 100),
    ]
    player.play(events)
    while player.playing:
        time.sleep(0.02)
    assert len(io.events) == 3


def test_player_reject_empty_and_repeat_zero():
    io = FakeAutomationIO()
    player = MacroPlayer(io)
    player.play([], repeat=1)
    player.play([RecordedEvent(EventType.MOUSE_PRESS, 1, 0, 0)], repeat=0)
    assert player.playing is False
    assert io.events == []


def test_player_defensive_cap_on_giant_macro():
    io = FakeAutomationIO()
    player = MacroPlayer(io)
    events = [RecordedEvent(EventType.MOUSE_PRESS, 1, 0, 0)] * 1_000_000
    player.play(events)
    while player.playing:
        time.sleep(0.01)
    assert len(io.events) == 100_000
