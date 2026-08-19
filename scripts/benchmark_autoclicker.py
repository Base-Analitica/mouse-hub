#!/usr/bin/env python3
"""Benchmark do AutoClickerEngine (stdlib + core; zero cliques reais).

Mede CPU e taxa de clique efetiva em três regimes, usando o fake
`FakeAutomationIO` como saída (nenhum evento chega ao X, seguro para
rodar na CI ou em qualquer máquina):

* idle — engine desligado;
* CPS baixo (5);
* próximo do limite (50).

O benchmark não falsifica números: tudo vem de `/proc/self/stat`
e do contador real de cliques acumulados pelo fake. No ambiente de
desenvolvimento do executor, informe o CPU/RAM observado — esta PR
não roda no IdeaPad S145, portanto o resultado é:

    NOT PHYSICALLY VALIDATED ON TARGET HARDWARE
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mouse_hub.core.automation.autoclicker import AutoClickerEngine
from mouse_hub.core.automation.focus import WindowFocusChecker
from mouse_hub.core.automation.types import MouseButton
from tests.fakes import FakeAutomationIO, FakeFocusTitleSource

CLK_TCK = os.sysconf("SC_CLK_TCK")


def cpu_seconds() -> float:
    with open("/proc/self/stat", encoding="utf-8") as fh:
        parts = fh.read().split()
    return (int(parts[13]) + int(parts[14])) / CLK_TCK


def make_engine(cps: int):
    io = FakeAutomationIO()
    source = FakeFocusTitleSource("Minecraft 1.20")
    focus = WindowFocusChecker(source, ttl_ms=200)
    engine = AutoClickerEngine(io=io, focus=focus, cps=cps)
    return engine, io


def run(label: str, cps: int, duration: float):
    engine, io = make_engine(cps)
    engine.start()
    t0 = time.monotonic()
    c0 = cpu_seconds()
    time.sleep(duration)
    elapsed = time.monotonic() - t0
    c1 = cpu_seconds()
    engine.stop()
    clicks = sum(1 for e in io.events if e["type"] == "click")
    cpu_pct = (c1 - c0) / elapsed * 100
    print(f"  {label:38s} clicks={clicks:4d} "
          f"({clicks / elapsed:5.1f} cps)  cpu={cpu_pct:4.1f}%/core")


def main():
    print("benchmark_autoclicker — hot path sem subprocesso (fake IO)")
    print(f"CPU do ambiente: {os.environ.get('BENCHMARK_CPU', '(não informado)')}")
    print(f"RAM do ambiente: {os.environ.get('BENCHMARK_RAM', '(não informado)')}")

    # Idle: engine desligado, CPU de um segundo de repouso.
    engine, io = make_engine(10)
    c0 = cpu_seconds()
    time.sleep(1.0)
    c1 = cpu_seconds()
    print(f"  {'idle (clicker off)':38s} clicks={0:4d}  cpu={(c1 - c0) * 100:4.1f}%/core")

    run("CPS baixo (5)", 5, 3.0)
    run("CPS alto (50)", 50, 3.0)
    run("CPS intermediário (20)", 20, 3.0)

    print("\nNOT PHYSICALLY VALIDATED ON TARGET HARDWARE")
    print("Reprodução no IdeaPad S145: python3 scripts/benchmark_autoclicker.py")


if __name__ == "__main__":
    main()
