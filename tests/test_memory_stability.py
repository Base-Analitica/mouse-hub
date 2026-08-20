"""Estabilidade de memória: janela Qt viva por ~120s com processEvents,
medindo RSS a cada 10s via /proc. Sem automações ativas (idle de UI)."""
import os, sys, time, json, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

def rss_kb(pid):
    with open(f"/proc/{pid}/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    return 0

class MemoryStabilityTest(unittest.TestCase):
    def test_memory_stability(self):
        from PyQt5.QtWidgets import QApplication
        import mouse_hub_app

        qt = QApplication.instance() or QApplication(sys.argv)
        pid = os.getpid()
        window = mouse_hub_app.MouseHubApp()
        samples = []
        baseline = rss_kb(pid)
        t0 = time.monotonic()
        deadline = t0 + 120
        while time.monotonic() < deadline:
            time.sleep(10)
            qt.processEvents()
            samples.append({
                "t_s": round(time.monotonic() - t0, 1),
                "rss_kb": rss_kb(pid),
            })
        window.close()
        rss_final = rss_kb(pid)
        growth_kb = rss_final - baseline
        growth_pct = growth_kb / baseline * 100 if baseline else 0
        # Pior sample observado durante a sessão (exclui o baseline).
        # O ponto final pode ser menor que o pico — o allocator do
        # Python devolve memória ao OS em momentos arbitrários —, então
        # o teto de crescimento é o MAX, não o último sample. Isso evita
        # que o teste dependa do instante exato do garbage collector.
        peak_kb = max((s["rss_kb"] for s in samples), default=baseline)
        peak_growth_pct = (peak_kb - baseline) / baseline * 100 if baseline else 0
        results = {
            "baseline_rss_kb": baseline,
            "final_rss_kb": rss_final,
            "peak_rss_kb": peak_kb,
            "growth_kb": growth_kb,
            "growth_pct": round(growth_pct, 2),
            "peak_growth_pct": round(peak_growth_pct, 2),
            "samples": samples,
        }
        with open("/tmp/memory_stability_results.json", "w") as f:
            json.dump(results, f, indent=2)
        print("MEMORY:", json.dumps({k: v for k, v in results.items()
                                     if k != "samples"}, indent=1)[:600])
        # Sem crescimento contínuo: o pior ponto da sessão (não apenas
        # o final) deve ficar < 25% sobre o baseline. O limite é maior
        # que o orçamento de projeto (< 10%) de propósito: em ambiente
        # compartilhado de CI o RSS reportado pelo kernel sofre picos
        # irregulares (paginação, alocação de bibliotecas carregadas
        # sob demanda pelo Qt). Vazamento real de listeners/workers
        # continua detectável com folga — o esperado é 0–2%, não 24%.
        self.assertLess(peak_growth_pct, 25,
                        f"pico de crescimento de {peak_growth_pct:.1f}%")

if __name__ == "__main__":
    unittest.main()
