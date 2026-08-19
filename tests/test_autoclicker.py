"""Testes do motor de auto-clicker.

Todos executáveis com: python3 -m unittest tests.test_autoclicker
Sem input real: foco e backend de clique são fakes injetáveis.
"""

import threading
import time
import unittest

from mouse_hub.automation.autoclicker import (
    AutoClickerEngine, AutoClickerState,
    CPS_MIN, CPS_MAX, VALID_BUTTONS)
from mouse_hub.automation.focus import FocusDetector


# ─── Fakes ──────────────────────────────────────────────────────────────────

class FakeFocusDetector(FocusDetector):
    def __init__(self):
        self._name = "Minecraft 1.21.4"
        self._allowed = True

    def set_active(self, name, allowed):
        self._name = name
        self._allowed = allowed

    def active_window_name(self):
        return self._name

    def is_allowed(self, allowed_patterns=None):
        if self._name is None:
            return False
        return self._allowed and super().is_allowed(allowed_patterns)


class FakeClickBackend:
    def __init__(self, fail_after=None):
        self.calls = []
        self.fail_after = fail_after
        self._n = 0

    def click(self, button):
        self._n += 1
        self.calls.append(button)
        if self.fail_after is not None and self._n > self.fail_after:
            raise RuntimeError("backend fake falhou")


# ─── Limites e configuração ────────────────────────────────────────────────

class AutoClickerLimitsTest(unittest.TestCase):
    def setUp(self):
        self.engine = AutoClickerEngine(
            focus_detector=FakeFocusDetector(),
            click_backend=FakeClickBackend())

    def test_cps_clamped_to_1_min(self):
        self.assertEqual(self.engine.set_cps(0), CPS_MIN)
        self.assertEqual(self.engine.set_cps(-10), CPS_MIN)

    def test_cps_clamped_to_50_max(self):
        self.assertEqual(self.engine.set_cps(51), CPS_MAX)
        self.assertEqual(self.engine.set_cps(9999), CPS_MAX)

    def test_cps_inside_range_accepted(self):
        self.assertEqual(self.engine.set_cps(20), 20)
        self.assertEqual(self.engine.cps, 20)

    def test_invalid_button_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.set_button(4)
        with self.assertRaises(ValueError):
            self.engine.set_button(0)

    def test_valid_buttons_accepted(self):
        for b in VALID_BUTTONS:
            self.assertEqual(self.engine.set_button(b), b)
        self.engine.cleanup()

    def test_initial_state_is_stopped(self):
        self.assertEqual(self.engine.state, AutoClickerState.STOPPED)


# ─── Lifecycle ──────────────────────────────────────────────────────────────

class AutoClickerLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.focus = FakeFocusDetector()
        self.backend = FakeClickBackend()
        self.engine = AutoClickerEngine(
            focus_detector=self.focus, click_backend=self.backend)

    def tearDown(self):
        self.engine.cleanup()

    def test_start_stops_and_cleanup(self):
        self.assertTrue(self.engine.start())
        self.assertEqual(self.engine.state, AutoClickerState.RUNNING)
        self.engine.stop()
        self.assertEqual(self.engine.state, AutoClickerState.STOPPED)

    def test_double_start_is_idempotent(self):
        self.assertTrue(self.engine.start())
        self.assertFalse(self.engine.start())
        self.engine.stop()

    def test_stop_idempotent(self):
        self.engine.start()
        self.engine.stop()
        self.engine.stop()  # não estoura

    def test_cleanup_idempotent(self):
        self.engine.start()
        self.engine.cleanup()
        self.engine.cleanup()

    def test_running_reflects_real_state(self):
        self.engine.start()
        # estado real do motor: running ou bloqueado por foco contam
        self.assertIn(self.engine.state, (AutoClickerState.RUNNING,
                                          AutoClickerState.BLOCKED_BY_FOCUS))
        self.engine.stop()
        self.assertEqual(self.engine.state, AutoClickerState.STOPPED)


# ─── Foco ───────────────────────────────────────────────────────────────────

class AutoClickerFocusTest(unittest.TestCase):
    def setUp(self):
        self.focus = FakeFocusDetector()
        self.backend = FakeClickBackend()
        self.engine = AutoClickerEngine(
            focus_detector=self.focus, click_backend=self.backend,
            allowed_patterns=("Minecraft", "Lunar"))

    def tearDown(self):
        self.engine.cleanup()

    def test_clicks_only_when_allowed_window_active(self):
        self.focus.set_active("Minecraft", True)
        self.engine.set_cps(20)
        self.engine.start()
        time.sleep(0.35)
        self.assertGreater(len(self.backend.calls), 2)
        n_during_focus = len(self.backend.calls)

        # troca para janela não permitida (engine segue rodando)
        self.focus.set_active("Google Chrome", True)
        time.sleep(0.4)
        n_after = len(self.backend.calls)
        # nenhum clique extra enquanto fora do jogo (poll 200ms)
        self.assertEqual(n_during_focus, n_after)
        # o motor reporta bloqueio por foco enquanto segue em execução
        self.assertIn(self.engine.state,
                      (AutoClickerState.BLOCKED_BY_FOCUS,
                       AutoClickerState.RUNNING))
        # e para corretamente
        self.engine.stop()
        self.assertEqual(self.engine.state, AutoClickerState.STOPPED)

    def test_resumes_after_window_returns(self):
        self.focus.set_active("Minecraft", True)
        self.engine.set_cps(20)
        self.engine.start()
        time.sleep(0.2)
        self.focus.set_active("Firefox", True)
        time.sleep(0.25)
        self.assertEqual(self.engine.state,
                         AutoClickerState.BLOCKED_BY_FOCUS)
        self.focus.set_active("Minecraft", True)
        time.sleep(0.4)
        after = len(self.backend.calls)
        self.assertEqual(self.engine.state, AutoClickerState.RUNNING)
        self.assertGreater(after, 0)

    def test_no_clicks_when_no_window(self):
        self.focus.set_active(None, False)
        self.engine.set_cps(50)
        self.engine.start()
        time.sleep(0.4)
        self.engine.stop()
        self.assertEqual(len(self.backend.calls), 0)


# ─── Configuração hot ───────────────────────────────────────────────────────

class AutoClickerHotConfigTest(unittest.TestCase):
    def setUp(self):
        self.focus = FakeFocusDetector()
        self.backend = FakeClickBackend()
        self.engine = AutoClickerEngine(
            focus_detector=self.focus, click_backend=self.backend)

    def tearDown(self):
        self.engine.cleanup()

    def test_cps_change_applies_during_execution(self):
        self.engine.set_cps(2)
        self.engine.start()
        time.sleep(0.7)
        mid = len(self.backend.calls)
        self.engine.set_cps(40)
        time.sleep(0.7)
        self.engine.stop()
        after = len(self.backend.calls)
        # 40 CPS > 2 CPS: o delta do segundo intervalo deve ser maior
        self.assertGreater(after - mid, mid)

    def test_button_change_applies_during_execution(self):
        self.engine.set_cps(40)
        self.engine.set_button(1)
        self.engine.start()
        time.sleep(0.15)
        self.engine.set_button(3)
        time.sleep(0.15)
        self.engine.stop()
        self.assertIn(1, self.backend.calls)
        self.assertIn(3, self.backend.calls)


# ─── Erros e worker ─────────────────────────────────────────────────────────

class AutoClickerErrorTest(unittest.TestCase):
    def setUp(self):
        self.focus = FakeFocusDetector()
        self.backend = FakeClickBackend(fail_after=3)
        self.engine = AutoClickerEngine(
            focus_detector=self.focus, click_backend=self.backend)

    def tearDown(self):
        self.engine.cleanup()

    def test_backend_error_becomes_failed_state(self):
        self.engine.set_cps(40)
        self.engine.start()
        time.sleep(0.4)
        self.assertEqual(self.engine.state, AutoClickerState.FAILED)
        self.assertIsNotNone(self.engine.error)

    def test_worker_thread_cleaned_up_after_failure(self):
        self.engine.set_cps(40)
        before = threading.active_count()
        self.engine.start()
        time.sleep(0.5)
        self.engine.cleanup()
        time.sleep(0.1)
        self.assertLessEqual(threading.active_count(), before + 1)


if __name__ == "__main__":
    unittest.main()
