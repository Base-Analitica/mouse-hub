"""Benchmark mínimo de performance (Issue #12).

Medições de baixo custo, sem dependências extras:
  1. startup aproximado (import + instanciação da janela)
  2. RSS estabilizado
  3. threads em idle
  4. processos filhos em idle
  5. CPU durante 60s de idle (poll em /proc)
  6. CPU durante autoclicker ativo a 20 CPS

Executar: QT_QPA_PLATFORM=offscreen python3 -m unittest tests.bench_perf
Nota: valores medidos no ambiente de execução do teste, NÃO no
hardware-alvo (Lenovo IdeaPad S145).
"""
import os
import sys
import time
import unittest

# app/ não é pacote; importar como módulo independente
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))


def _read_status(pid, key):
    with open(f"/proc/{pid}/status") as f:
        for line in f:
            if line.startswith(key):
                return line.split()[1]
    return None


def _cpu_seconds(pid):
    """Segundos de CPU totais (utime+stime) em ms via /proc/*/stat."""
    with open(f"/proc/{pid}/stat") as f:
        parts = f.read().split()
    clk = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
    utime = int(parts[13]) / clk
    stime = int(parts[14]) / clk
    return (utime + stime) * 1000


class PerfBenchmarkTest(unittest.TestCase):
    def setUp(self):
        from PyQt5.QtWidgets import QApplication
        self.qt_app = QApplication.instance() or QApplication(sys.argv)

    def test_startup_and_idle_metrics(self):
        import mouse_hub_app

        pid = os.getpid()

        # 1) startup aproximado
        t0 = time.perf_counter()
        window = mouse_hub_app.MouseHubApp()
        startup_ms = (time.perf_counter() - t0) * 1000

        # 2) RSS (KB)
        time.sleep(0.5)
        rss_kb = int(_read_status(pid, "VmRSS:") or 0)

        # 3) threads
        threads = len(os.listdir(f"/proc/{pid}/task"))

        # 4) processos filhos
        children = [p for p in os.listdir("/proc") if p.isdigit()
                    and _read_status(int(p), "PPid:") == str(pid)]

        # 5) CPU idle por 60s
        cpu0 = _cpu_seconds(pid)
        wall0 = time.monotonic()
        deadline = wall0 + 60
        while time.monotonic() < deadline:
            time.sleep(1)
            self.qt_app.processEvents()
        cpu1 = _cpu_seconds(pid)
        elapsed = time.monotonic() - wall0
        idle_cpu_pct = (cpu1 - cpu0) / (elapsed * 1000) * 100

        # 6) autoclicker ativo a 20 CPS por 20s
        window.ac.cps = 20
        window.ac.start()
        cpu2 = _cpu_seconds(pid)
        wall1 = time.monotonic()
        deadline2 = wall1 + 20
        while time.monotonic() < deadline2:
            time.sleep(1)
            self.qt_app.processEvents()
        cpu3 = _cpu_seconds(pid)
        elapsed2 = time.monotonic() - wall1
        active_cpu_pct = (cpu3 - cpu2) / (elapsed2 * 1000) * 100
        window.ac.stop()

        # grava os resultados num arquivo para o corpo da PR
        results = {
            "startup_ms": round(startup_ms, 1),
            "rss_mb": round(rss_kb / 1024, 1),
            "threads": threads,
            "children": len(children),
            "idle_cpu_pct": round(idle_cpu_pct, 2),
            "active_20cps_cpu_pct": round(active_cpu_pct, 2),
        }
        with open("/tmp/bench_results.json", "w") as f:
            import json
            json.dump(results, f, indent=2)
        print("BENCHMARK:", results)

        # asserções (fundação leve):
        self.assertLess(idle_cpu_pct, 10,
                        f"CPU idle {idle_cpu_pct}% acima do esperado")
        self.assertEqual(len(children), 0,
                         f"{len(children)} subprocessos filhos em idle")
        window.close()


if __name__ == "__main__":
    unittest.main()
