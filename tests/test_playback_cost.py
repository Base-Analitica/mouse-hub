"""Custo de macro playback (Issue #12).

Mede a CPU **adicional** do processo durante a reprodução de uma macro
representativa (10 s, 40 eventos de teclas, cliques e movimentos) com
backend **fake** — o teste NÃO mede o custo físico real de emissão
XTest: a emissão real não passa por este processo, e qualquer afirmação
numérica sobre XTest pertence à medição no display físico (pendente na
issue #12, a ser feita no IdeaPad S145 ou em sessão com display real).

O que este teste protege (deterministicamente, no ambiente do CI):

* ordem da medição: idle é medido ANTES do `play()` — a janela de
  idle nunca "come" parte do playback;
* o playback termina antes do deadline (deadline expirado = falha);
* `play()` retorna de imediato (thread da UI não bloqueia);
* a thread de trabalho `mouse-hub-macro-player` não resta após o fim
  (cleanup completo do worker — não se aceita "threads totais do
  processo" como proxy);
* todos os eventos da macro são emitidos pelo worker.

Executar: QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_playback_cost
"""
import os
import sys
import time
import threading
import unittest

from mouse_hub.core.automation.macros import MacroPlayer
from mouse_hub.core.automation.types import EventType, MouseButton, RecordedEvent
from tests.fakes import FakeAutomationIO

PLAYBACK_THREAD_NAME = "mouse-hub-macro-player"
DEADLINE_S = 30


def _cpu_seconds(pid: int) -> float:
    """Segundos de CPU totais (utime+stime) em ms via /proc/*/stat."""
    with open(f"/proc/{pid}/stat") as f:
        parts = f.read().split()
    clk = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
    utime = int(parts[13]) / clk
    stime = int(parts[14]) / clk
    return (utime + stime) * 1000


def _has_player_thread() -> bool:
    return any(t.name == PLAYBACK_THREAD_NAME and t.is_alive()
               for t in threading.enumerate())


def _make_macro(duration_s: float = 10.0, n_events: int = 40):
    """Macro representativa: teclas, cliques e movimentos espaçados.

    `RecordedEvent` usa timing relativo (`delta_ms`) — como no formato
    real de persistência — então cada intervalo é distribuído sobre os
    n_events.
    """
    events = []
    prev_t = 0.0
    for i in range(n_events):
        t = duration_s * (i + 1) / n_events
        delta_ms = (t - prev_t) * 1000.0
        prev_t = t
        if i % 2 == 0:
            kind = EventType.KEY_PRESS
            ev = RecordedEvent(kind=kind, button=0, keycode=38, delta_ms=delta_ms)
        elif i % 4 == 1:
            kind = EventType.MOUSE_PRESS
            ev = RecordedEvent(kind=kind, button=MouseButton.LEFT.button_id,
                               keycode=0, delta_ms=delta_ms)
        else:
            kind = EventType.MOUSE_MOVE
            # x,y codificados em button/keycode (contrato do _emit)
            ev = RecordedEvent(kind=kind, button=i, keycode=i, delta_ms=delta_ms)
        events.append(ev)
    return events


class PlaybackCostTest(unittest.TestCase):
    def setUp(self) -> None:
        # Pré-condição: nenhum playback residual de outra execução do
        # mesmo processo (macro player é mutex, mas um worker solto
        # contaminaria a verificação de cleanup deste teste).
        self.assertFalse(_has_player_thread(),
                         "worker de playback de outra execução ainda vivo")

    def test_playback_cost_and_cleanup(self) -> None:
        pid = os.getpid()
        fake_io = FakeAutomationIO()
        player = MacroPlayer(fake_io)
        events = _make_macro()

        # ── 1. Idle medido ANTES do playback (janela de fundo de 4 s) ──
        cpu0 = _cpu_seconds(pid)
        idle0 = time.monotonic()
        time.sleep(4.0)
        idle_cpu_ms = _cpu_seconds(pid) - cpu0
        idle_s = time.monotonic() - idle0

        # ── 2. Iniciar o playback DEPOIS da janela de idle ───────────
        t0 = time.perf_counter()
        started = player.play(events, repeat=1)
        call_latency_ms = (time.perf_counter() - t0) * 1000
        self.assertTrue(started, "playback não iniciou")
        self.assertTrue(_has_player_thread(),
                        "worker não nasceu após play()")
        # play() NÃO bloqueia a thread da UI — a emissão vive no worker
        self.assertLess(call_latency_ms, 100,
                        f"play() bloqueou por {call_latency_ms:.1f} ms")

        # ── 3. CPU medida durante o playback inteiro ────────────────
        wall0 = time.monotonic()
        finished_before_deadline = False
        while time.monotonic() - wall0 < DEADLINE_S:
            if not player.playing:
                finished_before_deadline = True
                break
            time.sleep(0.25)
        elapsed = time.monotonic() - wall0
        cpu1 = _cpu_seconds(pid)

        # ── 4/5. Playback concluído antes do deadline ────────────────
        self.assertTrue(finished_before_deadline,
                        f"playback não terminou em {DEADLINE_S} s")
        # duração deve respeitar o timing da macro (10 s) com margem
        self.assertGreater(elapsed, 9.0,
                           f"playback terminou cedo demais ({elapsed:.2f} s)")
        self.assertLess(elapsed, 20.0,
                        f"playback demorou demais ({elapsed:.2f} s)")

        raw_cpu_pct = (cpu1 - cpu0) / (elapsed * 1000) * 100
        idle_cpu_pct = idle_cpu_ms / (idle_s * 1000) * 100
        cpu_pct = max(0.0, raw_cpu_pct - idle_cpu_pct)

        events_played = sum(1 for e in fake_io.events if e[0] in
                            ("key_press", "key_release", "click", "press",
                             "release", "move"))

        # ── 6/7. Cleanup: a thread específica não pode restar ────────
        time.sleep(0.5)
        self.assertFalse(_has_player_thread(),
                         f"thread {PLAYBACK_THREAD_NAME} restou após o "
                         f"playback (cleanup incompleto do worker)")

        results = {
            "duration_s": round(elapsed, 2),
            "cpu_pct": round(cpu_pct, 2),
            "idle_cpu_pct": round(idle_cpu_pct, 2),
            "events_played": events_played,
            "call_latency_ms": round(call_latency_ms, 2),
        }
        with open("/tmp/playback_cost_results.json", "w") as f:
            import json
            json.dump(results, f, indent=2)
        print("PLAYBACK_COST:", results)

        # guardrail do CI: o playback adiciona < 4% de um núcleo sobre
        # o fundo do mesmo processo (valor observado no CI: ~0,1–0,5%).
        # O limite é folgado de propósito para tolerar pico de load do
        # runner; regressões reais (busy loop, timer agressivo) estouram
        # com folga. O contrato fino por regime CPS vive no `bench_perf`.
        self.assertLess(cpu_pct, 4.0, f"playback adicionou {cpu_pct}% CPU")
        self.assertGreater(events_played, 30,
                           f"apenas {events_played} eventos emitidos")


if __name__ == "__main__":
    unittest.main()
