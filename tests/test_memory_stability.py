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
        results = {
            "baseline_rss_kb": baseline,
            "final_rss_kb": rss_final,
            "growth_kb": growth_kb,
            "growth_pct": round(growth_pct, 2),
            "samples": samples,
        }
        with open("/tmp/memory_stability_results.json", "w") as f:
            json.dump(results, f, indent=2)
        print("MEMORY:", json.dumps(results, indent=1)[:600])
        # Sem crescimento contínuo: crescimento total deve ser < 10%
        self.assertLess(growth_pct, 10, f"crescimento de {growth_pct}%")

if __name__ == "__main__":
    unittest.main()
