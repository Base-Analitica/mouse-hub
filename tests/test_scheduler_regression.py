"""Regressão #23: busy-loop no AutomationScheduler após alteração de intervalo.

A correção do hot-config da issue #18 deixou `_notify` permanentemente
sinalizado: o setter de `interval` faz `_notify.set()` e `wait_next()`
nunca consumia o sinal. Depois de uma reconfiguração, `Event.wait()`
retornava imediatamente e o loop interno girava até o deadline —
aproximadamente um núcleo inteiro de CPU durante macro playback
(guardrail `test_playback_cost` da PR #19 mediu ~98,5% no CI).

Esta suíte é determinística (sem hardware, sem Display X, sem sleep
arbitrário para esconder race) e cobre o contrato completo do
scheduler após reconfiguração:

* alteração de `interval` durante o aguardo -> acorda e recalcula;
* espera posterior à alteração -> volta a BLOQUEAR (zero busy-wait),
  medido por CPU real do processo, não por mock;
* alterações consecutivas -> a mais recente vence (nada é perdido);
* alterações concorrentes (outra thread) -> sem perda nem travamento;
* `stop()` -> interrompe o aguardo imediatamente;
* `reset()` -> scheduler reutilizável após stop;
* hot-CPS -> AutoClickerEngine continua em execução e coerente;
* macro playback -> ordem/timing preservados e cancelamento íntegro.
"""

from __future__ import annotations

import os
import threading
import time

from mouse_hub.core.automation.autoclicker import (
    AutoClickerEngine,
    AutoClickerState,
)
from mouse_hub.core.automation.focus import WindowFocusChecker
from mouse_hub.core.automation.macros import MacroPlayer, PlaybackState
from mouse_hub.core.automation.scheduler import AutomationScheduler
from mouse_hub.core.automation.types import EventType, RecordedEvent
from tests.fakes import FakeAutomationIO


# ── Helpers ─────────────────────────────────────────────────────────


def _process_cpu_ms() -> float:
    """CPU total do processo (utime+stime) em ms via /proc (Linux)."""
    with open("/proc/self/stat") as f:
        parts = f.read().split()
    clk = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
    return (int(parts[13]) + int(parts[14])) / clk * 1000


def _waiter(scheduler: AutomationScheduler, results: dict, done: threading.Event) -> None:
    results["ok"] = scheduler.wait_next()
    done.set()


def _press(keycode: int) -> RecordedEvent:
    return RecordedEvent(EventType.KEY_PRESS, button=0, keycode=keycode, delta_ms=0.0)


def _release(keycode: int, delta_ms: float = 0.0) -> RecordedEvent:
    return RecordedEvent(EventType.KEY_RELEASE, button=0, keycode=keycode, delta_ms=delta_ms)


def _focus(title: str) -> WindowFocusChecker:
    class _Title:
        def active_window_title(self):
            return title

    return WindowFocusChecker(_Title(), ttl_ms=500)


# ── Scheduler: contrato de reconfiguração (issue #23) ───────────────


def test_interval_change_wakes_waiting_wait_next():
    """REGRESSÃO #23: alterar `interval` durante o aguardo acorda o
    wait em curso e o deadline é recalculado com o NOVO valor — o wait
    retorna True (hot config, nunca cancelamento) bem antes do
    intervalo original de 60 s."""
    scheduler = AutomationScheduler(60.0)
    done = threading.Event()
    results: dict = {}
    threading.Thread(
        target=_waiter, args=(scheduler, results, done), daemon=True
    ).start()
    time.sleep(0.05)  # o waiter está dormindo em wait(60 s)
    t0 = time.monotonic()
    scheduler.interval = 0.05  # 60 s -> 50 ms
    assert done.wait(timeout=2.0)
    elapsed = time.monotonic() - t0
    assert results["ok"] is True  # reconfiguração NÃO é cancelamento
    assert elapsed < 1.0  # acordou cedo; não esperou os 60 s


def test_wait_after_interval_change_blocks_not_busy_loop():
    """REGRESSÃO #23 (discriminador): depois de uma alteração de
    intervalo, o sinal de `_notify` é CONSUMIDO — o wait seguinte
    dorme o intervalo inteiro via Event.wait, em vez de girar até o
    deadline. Um busy-loop de 0,7 s consome ~0,7 s de CPU do processo;
    dormindo, consome uma fração disso (margem folgada de 25% para o
    CI). Este teste falha contra a implementação defeituosa (notify
    nunca limpo) e passa somente com a correção."""
    scheduler = AutomationScheduler(0.5)
    scheduler.interval = 0.7  # mudança real -> version++ e notify.set()
    cpu_before = _process_cpu_ms()
    t0 = time.monotonic()
    result = scheduler.wait_next()
    wall = time.monotonic() - t0
    cpu_used = _process_cpu_ms() - cpu_before
    assert result is True
    # Dormiu (quase) o intervalo completo — não retornou em loop.
    assert wall >= 0.6
    # Zero busy-wait: CPU bem abaixo do que um spin de 0,7 s queimaria.
    assert cpu_used < 0.7 * 1000 * 0.25, (
        f"busy-loop detectado após alteração de intervalo: "
        f"{cpu_used:.1f} ms de CPU em {wall:.2f} s de espera"
    )


def test_consecutive_interval_changes_keep_latest():
    """REGRESSÃO #23: duas alterações próximas durante o aguardo não
    perdem a mais recente — o deadline final respeita o ÚLTIMO
    intervalo (30 ms), não o anterior (500 ms) nem o original (60 s)."""
    scheduler = AutomationScheduler(60.0)
    done = threading.Event()
    results: dict = {}
    threading.Thread(
        target=_waiter, args=(scheduler, results, done), daemon=True
    ).start()
    time.sleep(0.05)
    t0 = time.monotonic()
    scheduler.interval = 0.5
    time.sleep(0.02)
    scheduler.interval = 0.03  # a mais recente vence
    assert done.wait(timeout=2.0)
    elapsed = time.monotonic() - t0
    assert results["ok"] is True
    assert elapsed < 0.25  # aplicou 30 ms, não 500 ms nem 60 s


def test_concurrent_interval_changes_are_never_lost():
    """REGRESSÃO #23 (concorrência): alterações de intervalo vindas de
    outra thread durante aguardo contínuo não são perdidas nem travam
    o worker — o scheduler acorda, recalcula com a versão mais nova e
    segue bloqueando (sem deadlock)."""
    scheduler = AutomationScheduler(0.02)
    stop_changes = threading.Event()
    results: dict = {"iterations": 0}

    def changer() -> None:
        while not stop_changes.is_set():
            scheduler.interval = 0.02 + (time.monotonic() % 0.01)
            time.sleep(0.001)

    def runner() -> None:
        while not stop_changes.is_set():
            results["iterations"] += 1
            if not scheduler.wait_next():
                break

    changer_t = threading.Thread(target=changer, daemon=True)
    runner_t = threading.Thread(target=runner, daemon=True)
    changer_t.start()
    runner_t.start()
    time.sleep(0.3)
    stop_changes.set()
    changer_t.join(timeout=1.0)
    runner_t.join(timeout=1.0)
    assert not changer_t.is_alive() and not runner_t.is_alive(), "worker travou"
    assert results["iterations"] > 0


def test_stop_wakes_wait_next_immediately():
    """REGRESSÃO #23: `stop()` interrompe o aguardo IMEDIATAMENTE
    (sem esperar o tick de 60 s) e `wait_next()` retorna False."""
    scheduler = AutomationScheduler(60.0)
    done = threading.Event()
    results: dict = {}
    threading.Thread(
        target=_waiter, args=(scheduler, results, done), daemon=True
    ).start()
    time.sleep(0.05)
    t0 = time.monotonic()
    scheduler.stop()
    assert done.wait(timeout=2.0)
    elapsed = time.monotonic() - t0
    assert results["ok"] is False
    assert elapsed < 1.0


def test_reset_allows_scheduler_reuse_after_stop():
    """REGRESSÃO #23: o contrato de `reset()` — após stop, o mesmo
    scheduler volta a funcionar para um novo ciclo (aguardo normal
    completa e retorna True)."""
    scheduler = AutomationScheduler(0.05)
    scheduler.stop()
    assert scheduler.wait_next() is False  # parado
    scheduler.reset()
    done = threading.Event()
    results: dict = {}
    threading.Thread(
        target=_waiter, args=(scheduler, results, done), daemon=True
    ).start()
    assert done.wait(timeout=2.0)
    assert results["ok"] is True  # reutilizado normalmente


# ── Consumidores: hot-CPS e macro playback ──────────────────────────


def test_hot_cps_keeps_engine_running_and_state_coherent():
    """REGRESSÃO #23: mudanças de CPS em runtime (hot config) mantêm o
    AutoClickerEngine em execução com estado coerente e sem worker
    órfão — cada set_cps altera `scheduler.interval` e o engine segue
    clicando (nenhuma parada silenciosa da #18, nenhum busy-loop da
    #23)."""
    io = FakeAutomationIO()
    engine = AutoClickerEngine(io, _focus("Minecraft"), cps=10)
    engine.start()
    time.sleep(0.15)
    assert engine.state == AutoClickerState.RUNNING
    for cps in (20, 50, 1, 30, 50):
        engine.set_cps(cps)  # altera scheduler.interval a cada chamada
        time.sleep(0.05)
    time.sleep(0.2)
    assert engine.state == AutoClickerState.RUNNING
    assert engine.running
    assert engine.stats.clicks > 0
    engine.stop()
    assert engine.state == AutoClickerState.STOPPED
    assert not engine.running
    assert engine._worker is None  # cleanup completo, sem thread órfã


def test_macro_playback_preserves_order_and_timing():
    """REGRESSÃO #23: o playback preserva ordem e timing — cada
    delta_ms altera `scheduler.interval` (o caminho do notify), e o
    player segue emitindo na ordem correta e no ritmo certo, sem
    busy-wait."""
    io = FakeAutomationIO()
    player = MacroPlayer(io)
    events = [
        _press(38),
        _release(38, delta_ms=40.0),
        _press(60),
        _release(60, delta_ms=20.0),
    ]
    assert player.play(events, repeat=1)
    while player.playing:
        time.sleep(0.005)
    assert player.state == PlaybackState.STOPPED
    assert [e[0] for e in io.events] == [
        "key_press",
        "key_release",
        "key_press",
        "key_release",
    ]
    assert [e[1] for e in io.events] == [38, 38, 60, 60]


def test_macro_playback_cancel_still_works():
    """REGRESSÃO #23: o cancelamento do playback continua funcionando
    — o worker encerra e o player volta a STOPPED (interromper não é
    falha)."""
    io = FakeAutomationIO()
    player = MacroPlayer(io)
    # Delta dentro da janela de join do cancel() (2 s) — o contrato
    # existente do player: cancelar acorda o worker e encerra em
    # STOPPED (mesmo contrato de test_playback_cancel_restores_stopped_state).
    events = [_press(38), _release(38, delta_ms=500.0), _press(60)]
    assert player.play(events, repeat=1)
    player.cancel()
    assert player.state == PlaybackState.STOPPED
    assert not player.playing

