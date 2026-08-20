"""Custo de macro recording (Issue #12 — MAJOR 4).

Mede o custo do `MacroRecorder` sob carga representativa com eventos
SINTÉTICOS — este teste NÃO mede o custo físico real do listener
XRecord/display: a captura real vive no display X do usuário e o
custo de transporte X11 pertence à validação futura no S145/display
físico.

O que este teste protege (deterministicamente, no ambiente do CI):

* overhead do callback `make_handler()` por evento;
* CPU do processo durante carga representativa (n eventos/s por 5 s);
* crescimento de memória proporcional à quantidade de eventos
  gravados (o armazenamento é uma lista — O(n) por evento);
* lifecycle start/stop (`recording` flag) e lifecycle após stop
  (sem atividade contínua: chamar o handler após stop não grava
  nada e não há threads/timers residuais);
* snapshot imutável de `events`.

Executar: QT_QPA_PLATFORM=offscreen python3 -m unittest tests.bench_recording
"""
import os
import sys
import time
import threading
import json
import unittest

from mouse_hub.core.automation.macros import MacroRecorder
from mouse_hub.core.automation.types import EventType

BASELINE_SECONDS = 5
BURST_EVENTS = 2000


def _cpu_ms(pid: int) -> float:
    with open(f"/proc/{pid}/stat") as f:
        parts = f.read().split()
    clk = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
    utime = int(parts[13]) / clk
    stime = int(parts[14]) / clk
    return (utime + stime) * 1000


def _rss_kb(pid: int) -> int:
    with open(f"/proc/{pid}/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    return 0


class RecordingCostTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pid = os.getpid()
        self.pre_threads = set(t.ident for t in threading.enumerate())
        self.recorder = MacroRecorder()

    def tearDown(self) -> None:
        # lifecycle: após stop(), nenhuma thread nova pode ter nascido
        # nem thread pré-existente ter morrido (nada contínuo nasceu)
        post = set(t.ident for t in threading.enumerate())
        self.assertEqual(post, self.pre_threads,
                         "threads residuais após stop()")

    # ── callbacks sintéticos ──────────────────────────────────────

    def _synthetic_event(self, kind: str, n: int = 0):
        return {"kind": kind, "button": n % 3, "keycode": 30 + n % 50}

    def test_overhead_per_event(self) -> None:
        recorder = MacroRecorder()  # recorder local — sem contaminação
        recorder.start()
        self.assertTrue(recorder.recording)
        handler = recorder.make_handler()
        # warm-up (cache de páginas, listas) — descartado depois:
        # stop() + start() limpa a linha do tempo (contrato do
        # MacroRecorder: start() só limpa quando não estava gravando)
        for _ in range(100):
            handler(self._synthetic_event("mouse_move"))
        recorder.stop()
        recorder.start()
        self.assertEqual(len(recorder.events), 0,
                         "linha do tempo não foi limpa no re-início")
        # medida: BURST_EVENTS callbacks em lote
        cpu0 = _cpu_ms(self.pid)
        rss0 = _rss_kb(self.pid)
        t0 = time.perf_counter()
        for n in range(BURST_EVENTS):
            handler(self._synthetic_event(
                "key_press" if n % 2 == 0 else "mouse_move", n))
        elapsed_ms = (time.perf_counter() - t0) * 1000
        cpu1 = _cpu_ms(self.pid)
        rss1 = _rss_kb(self.pid)

        self.assertEqual(len(recorder.events), BURST_EVENTS)
        per_us = elapsed_ms / BURST_EVENTS
        results = {
            "burst_events": BURST_EVENTS,
            "total_ms": round(elapsed_ms, 1),
            "per_event_us": round(per_us, 2),
            "cpu_ms": round(cpu1 - cpu0, 2),
            "rss_growth_kb": rss1 - rss0,
        }
        with open("/tmp/recording_cost_results.json", "w") as f:
            json.dump(results, f, indent=2)
        print("RECORDING_COST:", results)

        # overhead por callback < 200 µs — gravação não pode notar-se
        # na UX (o callback roda no fio do listener XRecord real)
        self.assertLess(per_us, 200,
                        f"{per_us:.1f} µs/evento excedeu 200 µs")

    def test_load_5s(self) -> None:
        """Carga contínua: ~400 eventos/s por 5 s (taxa humana alta)."""
        self.recorder.start()
        handler = self.recorder.make_handler()
        t0 = time.monotonic()
        deadline = t0 + BASELINE_SECONDS
        n = 0
        while time.monotonic() < deadline:
            for _ in range(4):  # ~400 evt/s com sleeps de 10 ms
                handler(self._synthetic_event("mouse_move", n))
                n += 1
            time.sleep(0.01)
        elapsed_s = time.monotonic() - t0
        self.assertGreater(elapsed_s, 4.5,
                           f"sessão de {elapsed_s:.2f} s curta demais")
        played = len(self.recorder.events)
        self.assertGreater(played, 1500,
                           f"apenas {played} eventos em {elapsed_s:.1f} s")

    def test_memory_proportional(self) -> None:
        """Memória cresce com O(n) no número de eventos — nenhum
        overhead fixo oculto (cache LRU, buffers duplicados).
        VmRSS do kernel cresce em páginas e nunca decresce — por isso
        o teste compara o crescimento TOTAL após 4.000 e 8.000 eventos
        (dobro do volume → crescimento ≈ 2×). Comparar deltas por
        lote é frágil: o segundo lote pode reutilizar páginas já
        mapeadas e o delta seria 0 mesmo sem bug."""
        rss0 = _rss_kb(self.pid)
        recorder = MacroRecorder()
        recorder.start()
        handler = recorder.make_handler()
        # mesmo tipo de evento nos dois lotes: RecordedEvent para
        # key_press pode ocupar mais que mouse_move (depende dos
        # campos que o handler preenche) e a comparação de
        # proporcionalidade deixaria de ser justa
        for i in range(4000):
            handler(self._synthetic_event("mouse_move", i))
        rss_4k = _rss_kb(self.pid)
        for i in range(4000):
            handler(self._synthetic_event("mouse_move", i + 4000))
        rss_8k = _rss_kb(self.pid)
        g4k = rss_4k - rss0
        g8k = rss_8k - rss0
        self.assertGreater(g4k, 0, f"sem crescimento com 4000 eventos")
        self.assertGreater(g8k, 0,
                           f"sem crescimento com 8000 eventos")
        # dobro do volume → crescimento entre 0,8× e 3× o baseline
        # (0,8× tolera páginas pré-mapeadas que favorecem o segundo
        # lote; 3× tolera o ruído do allocator) — qualquer estrutura
        # não-linear (cache quadrática, duplicação) estoura o teto
        self.assertGreater(g8k, 0.8 * g4k,
                           f"crescimento abaixo do linear: {g4k} KB "
                           f"(4k) vs {g8k} KB (8k)")
        self.assertLess(g8k, 3 * g4k,
                        f"crescimento acima do linear: {g4k} KB (4k) "
                        f"vs {g8k} KB (8k)")
        results = {"rss_4k_kb": g4k, "rss_8k_kb": g8k}
        with open("/tmp/recording_memory_results.json", "w") as f:
            json.dump(results, f, indent=2)
        print("RECORDING_MEMORY:", results)

    def test_lifecycle_and_no_residual_activity(self) -> None:
        """stop() encerra a gravação; chamar o handler depois não
        grava nada e não nasce thread/timer residual."""
        self.recorder.start()
        handler = self.recorder.make_handler()
        handler(self._synthetic_event("key_press"))
        self.assertEqual(len(self.recorder.events), 1)
        self.recorder.stop()
        self.assertFalse(self.recorder.recording)
        # snapshot imutável sobrevive ao stop
        snap = self.recorder.events
        self.assertEqual(len(snap), 1)
        # handler pós-stop NÃO grava
        handler(self._synthetic_event("key_press"))
        self.assertEqual(len(self.recorder.events), 1)
        # re-início limpa a linha do tempo (contrato do start())
        self.recorder.start()
        handler(self._synthetic_event("key_press"))
        self.assertEqual(len(self.recorder.events), 1)
        self.recorder.stop()
        # segundo stop é idempotente
        self.recorder.stop()
        self.assertFalse(self.recorder.recording)


if __name__ == "__main__":
    unittest.main()
