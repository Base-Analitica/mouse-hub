"""Estabilidade de memória em sessão prolongada (Issue #12).

Mantém a janela do app viva e mede RSS a cada 10 s via /proc.

Contrato (separar sempre):
* META de produto (docs/performance/metodologia.md): crescimento
  < 10% sobre o baseline em sessão prolongada — só é comprovada
  após medição física no IdeaPad S145.
* Guardrail deste teste de CI: < 10% também — o CI roda o mesmo
  critério da meta porque o esperado em offscreen é 0–2%; NÃO
  enfraquecer o threshold para acomodar ruído.
* RESULTADO MEDIDO (commit aa58b88, CI ubuntu-latest): 0,0% de
  crescimento em 120 s — dentro da meta.

Detalhes do método:
* warm-up de 5 s antes do baseline para não contar lazy allocations
  normais do Qt (temas, fontes, ícones) como leak;
* processEvents a cada 10 s durante TODA a sessão (o event loop não
  pode ficar parado — timers e callbacks continuam rodando);
* baseline e amostras via VmRSS de /proc/<pid>/status;
* sem automações ativas (idle de UI).

Executar: QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_memory_stability
"""
import os
import sys
import time
import json
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))


def rss_kb(pid: int) -> int:
    with open(f"/proc/{pid}/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    return 0


class MemoryStabilityTest(unittest.TestCase):
    def test_memory_stability(self) -> None:
        from PyQt5.QtWidgets import QApplication
        import mouse_hub_app

        qt = QApplication.instance() or QApplication(sys.argv)
        pid = os.getpid()
        window = mouse_hub_app.MouseHubApp()

        # Warm-up: lazy allocations do Qt (temas, fontes, ícones)
        # acontecem nas primeiras interações do event loop. Sem o
        # warm-up, esse crescimento normal seria contado como leak.
        for _ in range(5):
            time.sleep(1)
            qt.processEvents()

        baseline = rss_kb(pid)
        samples = []
        t0 = time.monotonic()
        deadline = t0 + 120
        while time.monotonic() < deadline:
            time.sleep(10)
            # O event loop continua sendo processado durante toda a
            # sessão (imersão a cada 10 s) — timers e callbacks
            # registrados seguem rodando.
            qt.processEvents()
            samples.append({
                "t_s": round(time.monotonic() - t0, 1),
                "rss_kb": rss_kb(pid),
            })
        window.close()
        rss_final = rss_kb(pid)
        growth_kb = rss_final - baseline
        growth_pct = growth_kb / baseline * 100 if baseline else 0

        results = {
            "baseline_rss_kb": baseline,
            "final_rss_kb": rss_final,
            "growth_kb": growth_kb,
            "growth_pct": round(growth_pct, 2),
            "samples": samples,
        }
        with open("/tmp/memory_stability_results.json", "w") as f:
            json.dump(results, f, indent=2)
        print("MEMORY:", json.dumps({k: v for k, v in results.items()
                                     if k != "samples"}, indent=1)[:600])

        # META de produto: crescimento < 10%. O CI usa o MESMO critério
        # da meta (o esperado é 0–2%); NÃO aumentar o threshold para
        # deixar CI verde — se o RSS crescer de verdade, o teste deve
        # reprovar.
        self.assertLess(growth_pct, 10,
                        f"crescimento de {growth_pct:.1f}% em 120 s "
                        f"(meta de projeto: < 10%)")


if __name__ == "__main__":
    unittest.main()
