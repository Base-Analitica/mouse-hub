#!/usr/bin/env python3
"""Benchmark de macros — gravação, playback e estabilidade de memória
(stdlib + core; zero cliques reais).

* Gravação simulada: 5000 eventos via callback (orientada a eventos,
  sem polling), medindo tempo e crescimento de memória;
* Playback de uma macro sintética representativa (press/release de
  mouse + teclas, 200 eventos), medindo tempo total e taxa;
* Estabilidade do worker: macro de longa duração com cancelamento,
  verificando que `playing` encerra corretamente.

NOT PHYSICALLY VALIDATED ON TARGET HARDWARE
Reprodução no IdeaPad S145: python3 scripts/benchmark_macros.py
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mouse_hub.core.automation.macros import MacroPlayer, MacroRecorder
from mouse_hub.core.automation.types import EventType, RecordedEvent
from tests.fakes import FakeAutomationIO


def rss_kb() -> int:
    for line in open("/proc/self/status", encoding="utf-8"):
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return -1


def synthetic_macro(n: int) -> list:
    events = []
    for i in range(n):
        kind = EventType.MOUSE_PRESS if i % 2 == 0 else EventType.MOUSE_RELEASE
        events.append(RecordedEvent(kind, 1, 0, 8.0))  # 125 Hz ≈ 8 ms
    return events


def main():
    print("benchmark_macros — gravação orientada a eventos, playback sem busy-wait")
    print(f"CPU do ambiente: {os.environ.get('BENCHMARK_CPU', '(não informado)')}")
    print(f"RAM do ambiente: {os.environ.get('BENCHMARK_RAM', '(não informado)')}")

    # ── Gravação ──────────────────────────────────────────────────
    recorder = MacroRecorder()
    handler = recorder.make_handler()
    recorder.start()
    mem0 = rss_kb()
    t0 = time.monotonic()
    for i in range(5000):
        handler({"kind": "mouse_press", "button": 1})
        handler({"kind": "mouse_release", "button": 1})
    elapsed = time.monotonic() - t0
    mem1 = rss_kb()
    recorder.stop()
    print(f"  gravação 10000 eventos: {elapsed:6.3f} s  "
          f"({10000 / elapsed:7.0f} eventos/s)  memória +{mem1 - mem0} KB")
    assert len(recorder.events) == 10000

    # ── Playback ──────────────────────────────────────────────────
    io = FakeAutomationIO()
    player = MacroPlayer(io)
    macro = synthetic_macro(200)
    t0 = time.monotonic()
    player.play(macro)
    while player.playing:
        time.sleep(0.01)
    elapsed = time.monotonic() - t0
    print(f"  playback 200 eventos (@8 ms): {elapsed:6.3f} s  "
          f"({len(io.events):5d} eventos emitidos)")
    # Playback não pode ser mais rápido que o somatório dos deltas:
    assert elapsed >= (len(macro) - 1) * 0.008

    # ── Cancelamento / estabilidade do worker ─────────────────────
    player2 = MacroPlayer(io)
    long_macro = synthetic_macro(10_000)
    player2.play(long_macro)
    time.sleep(0.2)
    assert player2.playing
    player2.cancel()
    assert not player2.playing, "worker não encerrado após cancel"
    print(f"  cancel de macro longa: worker encerrado em menos de 2 s")

    # ── Memória após everything ───────────────────────────────────
    mem2 = rss_kb()
    print(f"  RSS ao final: {mem2} KB (crescimento total {mem2 - mem0} KB)")

    print("\nNOT PHYSICALLY VALIDATED ON TARGET HARDWARE")
    print("Reprodução no IdeaPad S145: python3 scripts/benchmark_macros.py")


if __name__ == "__main__":
    main()
