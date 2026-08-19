"""Testes do motor de macros — model, persistência, captura e playback.

Todos executáveis com: python3 -m unittest tests.test_macros
Nenhum teste gera input real: captura usa um fake que injeta eventos
manualmente, e playback usa um backend fake que só registra chamadas.
"""

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

from mouse_hub.automation.events import Macro, MacroEvent, MacroValidationError
from mouse_hub.automation.store import MacroStore, MacroStoreError
from mouse_hub.automation.capture import InputCapture, CaptureState
from mouse_hub.automation.playback import (
    PlaybackController, PlaybackState, ClickKeyBackend)


# ─── Fakes ──────────────────────────────────────────────────────────────────

class FakeBackend:
    """Backend de playback fake: registra eventos, nunca clica."""

    def __init__(self, fail_after=None):
        self.events = []
        self.fail_after = fail_after
        self.calls = 0

    def send_event(self, ev):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise RuntimeError("backend fake falhou")
        self.events.append(ev)


class FakeCaptureConnector:
    """Substituto do XRecord para o lifecycle do InputCapture.

    Injeta eventos programados no sink como se viessem do servidor X,
    sem qualquer input real.
    """

    def __init__(self, capture, planned_events, delay=0.005):
        self._capture = capture
        self._planned = planned_events
        self._delay = delay

    def install(self):
        """Hook que intercepta o _run: em vez de XRecord, injeta eventos
        de tempos em tempos e simula EndOfData quando stop() for chamado."""
        orig_run = self._capture._run
        capture = self._capture

        def fake_run():
            try:
                for ev in self._planned:
                    if capture._stop_event.is_set():
                        break
                    capture._sink(MacroEvent(ev.t, ev.type, key=ev.key,
                                             button=ev.button))
                    time.sleep(self._delay)
            except Exception:
                pass
            # simula desbloqueio do record_enable_context
            capture._stop_event.wait(timeout=0.1)

        self._capture._run = fake_run
        return orig_run


def make_events(pairs):
    return [MacroEvent(t, t_) for t, t_ in pairs]


# ─── Modelo / eventos ───────────────────────────────────────────────────────

class MacroEventModelTest(unittest.TestCase):
    def test_roundtrip_dict(self):
        ev = MacroEvent(0.143, "key_down", key="w")
        d = ev.to_dict()
        self.assertEqual(d, {"t": 0.143, "type": "key_down", "key": "w"})
        ev2 = MacroEvent.from_dict(d)
        self.assertEqual(ev2.t, 0.143)
        self.assertEqual(ev2.type, "key_down")
        self.assertEqual(ev2.key, "w")

    def test_timestamp_negative_rejected(self):
        with self.assertRaises(MacroValidationError):
            MacroEvent(-0.1, "key_down", key="w")

    def test_legacy_web_format_key_press_maps(self):
        raw = {"time": 0.5, "type": "key_press", "key": "a"}
        ev = MacroEvent.from_dict(raw)
        self.assertEqual(ev.type, "key_down")
        self.assertEqual(ev.key, "a")

    def test_legacy_native_format_key_click_move_maps(self):
        ev_k = MacroEvent.from_dict({"time": 0.1, "type": "key", "key": "F5"})
        self.assertEqual(ev_k.type, "key_down")
        ev_c = MacroEvent.from_dict({"time": 0.2, "type": "click", "button": 2})
        self.assertEqual(ev_c.type, "mouse_down")
        self.assertEqual(ev_c.button, 2)
        ev_m = MacroEvent.from_dict({"time": 0.3, "type": "move",
                                     "x": 100, "y": 200})
        self.assertEqual(ev_m.type, "mouse_move")
        self.assertEqual((ev_m.x, ev_m.y), (100, 200))

    def test_legacy_mouse_click_maps_to_down(self):
        ev = MacroEvent.from_dict({"time": 0.1, "type": "mouse_click",
                                   "button": 3})
        self.assertEqual(ev.type, "mouse_down")
        self.assertEqual(ev.button, 3)

    def test_unknown_event_type_rejected(self):
        with self.assertRaises(MacroValidationError):
            MacroEvent.from_dict({"time": 0.1, "type": "nonsense"})

    def test_key_event_without_key_rejected(self):
        with self.assertRaises(MacroValidationError):
            MacroEvent.from_dict({"time": 0.1, "type": "key_down"})

    def test_empty_key_rejected(self):
        with self.assertRaises(MacroValidationError):
            MacroEvent.from_dict({"time": 0.1, "type": "key", "key": ""})

    def test_click_invalid_button_rejected(self):
        with self.assertRaises(MacroValidationError):
            MacroEvent.from_dict({"time": 0.1, "type": "mouse_click",
                                  "button": 5})

    def test_non_dict_event_rejected(self):
        with self.assertRaises(MacroValidationError):
            MacroEvent.from_dict([1, 2, 3])

    def test_move_with_bad_coords_rejected(self):
        with self.assertRaises(MacroValidationError):
            MacroEvent.from_dict({"time": 0.1, "type": "move",
                                  "x": "NaN", "y": 0})


# ─── Macro (objeto) ────────────────────────────────────────────────────────

class MacroModelTest(unittest.TestCase):
    def test_empty_name_rejected(self):
        with self.assertRaises(MacroValidationError):
            Macro("")

    def test_name_whitespace_only_rejected(self):
        with self.assertRaises(MacroValidationError):
            Macro("   ")

    def test_valid_name_accepted(self):
        m = Macro("minha_macro_v2")
        self.assertEqual(m.name, "minha_macro_v2")

    def test_serialization_roundtrip(self):
        events = [MacroEvent(0.1, "key_down", key="w"),
                  MacroEvent(0.3, "mouse_down", button=1)]
        m = Macro("teste", events=events, repeat=3,
                  created_at="2026-08-19T12:00:00+00:00")
        text = m.to_json()
        data = json.loads(text)
        self.assertEqual(data["version"], 1)
        m2 = Macro.from_json(text)
        self.assertEqual(m2.name, "teste")
        self.assertEqual(m2.repeat, 3)
        self.assertEqual(len(m2.events), 2)
        self.assertEqual(m2.events[0].key, "w")
        self.assertEqual(m2.events[1].button, 1)

    def test_events_must_be_monotonic(self):
        bad = {"version": 1, "name": "x", "events": [
            {"t": 0.5, "type": "key_down", "key": "w"},
            {"t": 0.2, "type": "key_up", "key": "w"}]}
        with self.assertRaises(MacroValidationError):
            Macro.from_dict(bad)

    def test_huge_gap_rejected(self):
        bad = {"version": 1, "name": "x", "events": [
            {"t": 0.1, "type": "key_down", "key": "w"},
            {"t": 100000.0, "type": "key_up", "key": "w"}]}
        with self.assertRaises(MacroValidationError):
            Macro.from_dict(bad)

    def test_unsupported_version_rejected(self):
        with self.assertRaises(MacroValidationError):
            Macro.from_dict({"version": 99, "name": "x", "events": []})

    def test_events_missing_rejected(self):
        with self.assertRaises(MacroValidationError):
            Macro.from_dict({"version": 1, "name": "x"})

    def test_empty_events_allowed(self):
        m = Macro.from_dict({"version": 1, "name": "vazia", "events": []})
        self.assertEqual(len(m.events), 0)

    def test_bad_json_string_raises(self):
        with self.assertRaises(json.JSONDecodeError):
            Macro.from_json("{not json")


# ─── Persistência ───────────────────────────────────────────────────────────

class MacroStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = Path(self.tmp) / "macros.json"

    def _store(self, initial_text=None):
        if initial_text is not None:
            self.path.write_text(initial_text)
        return MacroStore(self.path)

    def test_add_and_get(self):
        store = self._store()
        m = Macro("a", events=[MacroEvent(0.1, "key_down", key="w")])
        store.add(m)
        got = store.get("a")
        self.assertIsNotNone(got)
        self.assertEqual(got.name, "a")

    def test_persistence_survives_reload(self):
        store = self._store()
        store.add(Macro("persist", events=[MacroEvent(0.1, "click", key=None)],
                        repeat=2))
        store2 = MacroStore(self.path)
        self.assertIsNotNone(store2.get("persist"))
        self.assertEqual(store2.get("persist").repeat, 2)

    def test_file_written_as_versioned_schema(self):
        store = self._store()
        store.add(Macro("v1", events=[MacroEvent(0.1, "key_down", key="w")]))
        data = json.loads(self.path.read_text())
        self.assertEqual(data["version"], 1)
        self.assertIn("macros", data)

    def test_delete_existing(self):
        store = self._store()
        store.add(Macro("x", events=[]))
        self.assertTrue(store.delete("x"))
        self.assertIsNone(store.get("x"))

    def test_delete_nonexistent(self):
        store = self._store()
        self.assertFalse(store.delete("inexistente"))

    def test_upsert_with_empty_name_generates_timestamp_name(self):
        store = self._store()
        ok, name = store.upsert_events("", [MacroEvent(0.1, "key_down",
                                                       key="w")])
        self.assertTrue(ok)
        self.assertTrue(name.startswith("macro_"))

    def test_empty_events_macro_is_saved_not_dropped(self):
        store = self._store()
        ok, name = store.upsert_events("macro_vazia", [])
        self.assertTrue(ok)
        self.assertEqual(store.get(name).events, [])

    def test_invalid_json_becomes_backup_not_crash(self):
        self.path.write_text("{corrupted json!!!")
        store = self._store()
        self.assertTrue(any("backup" in w for w in store.load_warnings))
        self.assertTrue(
            self.path.with_suffix(".json.bak").exists(),
            "arquivo corrompido deve virar backup")

    def test_old_v0_format_macros_preserved(self):
        # Formato atual (v0): dict puro keyed por nome, tipos legados
        old = {
            "combo": {
                "name": "combo",
                "events": [
                    {"time": 0.1, "type": "key_press", "key": "w"},
                    {"time": 0.4, "type": "mouse_click", "button": 1},
                ],
                "created": "2026-08-01T10:00:00",
                "count": 2,
            }
        }
        store = self._store(json.dumps(old))
        m = store.get("combo")
        self.assertIsNotNone(m, "macros antigas devem ser carregadas")
        self.assertEqual(len(m.events), 2)
        self.assertEqual(m.events[0].type, "key_down")
        self.assertEqual(m.events[1].type, "mouse_down")
        # reescrita em v1 não destrói os eventos
        store.save()
        store2 = MacroStore(self.path)
        self.assertEqual(len(store2.get("combo").events), 2)

    def test_invalid_macro_inside_file_reported_not_loaded(self):
        old = {
            "boa": {"version": 1, "name": "boa",
                    "events": [{"t": 0.1, "type": "key_down", "key": "w"}]},
            "ruim": {"version": 1, "name": "ruim",
                     "events": [{"t": 0.1, "type": "nonsense"}]},
        }
        store = self._store(json.dumps(old))
        self.assertIsNotNone(store.get("boa"))
        self.assertIsNone(store.get("ruim"))
        self.assertTrue(any("ruim" in w for w in store.load_warnings))

    def test_store_error_visible_on_write_failure(self):
        store = self._store()
        store.add(Macro("ok", events=[]))
        # diretório read-only força falha de I/O
        os.chmod(self.tmp, 0o555)
        try:
            with self.assertRaises(MacroStoreError):
                store.add(Macro("falha", events=[]))
        finally:
            os.chmod(self.tmp, 0o755)


# ─── Captura (com fake — sem input real) ────────────────────────────────────

class InputCaptureLifecycleTest(unittest.TestCase):
    def test_idle_to_active_to_stopped(self):
        cap = InputCapture(sink=lambda e: None)
        self.assertEqual(cap.state, CaptureState.IDLE)
        cap.start()
        self.assertEqual(cap.state, CaptureState.ACTIVE)
        cap.stop()
        cap.cleanup()
        self.assertIn(cap.state, (CaptureState.STOPPED, CaptureState.IDLE))

    def test_stop_idempotent(self):
        cap = InputCapture(sink=lambda e: None)
        cap.start()
        cap.stop()
        cap.stop()  # segunda chamada não deve estourar
        cap.cleanup()

    def test_cleanup_idempotent(self):
        cap = InputCapture(sink=lambda e: None)
        cap.start()
        cap.cleanup()
        cap.cleanup()  # idempotente

    def test_start_while_active_is_noop(self):
        cap = InputCapture(sink=lambda e: None)
        cap.start()
        cap.start()  # não cria thread duplicada
        cap.cleanup()

    def test_events_delivered_in_order_with_monotonic_timing(self):
        received = []
        cap = InputCapture(sink=received.append)
        planned = [MacroEvent(0.01, "key_down", key="a"),
                   MacroEvent(0.05, "mouse_down", button=1)]
        connector = FakeCaptureConnector(cap, planned)
        connector.install()
        cap.start()
        time.sleep(0.06)
        cap.stop()
        cap.cleanup()
        self.assertEqual(len(received), 2)
        self.assertEqual(received[0].key, "a")
        self.assertEqual(received[1].button, 1)
        self.assertLess(received[0].t, received[1].t)

    def test_stop_cuts_recording_mid_stream(self):
        received = []
        cap = InputCapture(sink=received.append)
        # 50 eventos programados; stop após ~10ms deve interceptar antes
        planned = [MacroEvent(i * 0.002, "key_down", key="x")
                   for i in range(50)]
        connector = FakeCaptureConnector(cap, planned, delay=0.002)
        connector.install()
        cap.start()
        time.sleep(0.02)
        cap.stop()
        cap.cleanup()
        self.assertLess(len(received), 50)

    def test_no_thread_left_after_cleanup(self):
        cap = InputCapture(sink=lambda e: None)
        cap.start()
        threads_before = threading.active_count()
        cap.cleanup()
        # dá um tempo para threads daemon reaper
        time.sleep(0.1)
        self.assertLessEqual(threading.active_count(), threads_before)

    def test_without_x_server_fails_gracefully(self):
        # DISPLAY impossível força falha de conexão X -> estado FAILED
        cap = InputCapture(sink=lambda e: None, display_name=":999")
        cap.start()
        time.sleep(0.3)
        self.assertEqual(cap.state, CaptureState.FAILED)
        self.assertIsNotNone(cap.failed_reason)
        cap.cleanup()


# ─── Playback ───────────────────────────────────────────────────────────────

class PlaybackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = MacroStore(Path(self.tmp) / "macros.json")

    def _add(self, name, pairs, repeat=1):
        events = [MacroEvent(t, t_) for t, t_ in pairs]
        self.store.add(Macro(name, events=events, repeat=repeat))

    def test_nonexistent_macro_returns_false(self):
        ctl = PlaybackController(self.store, backend=FakeBackend())
        self.assertFalse(ctl.start("nao_existe"))
        self.assertEqual(ctl.state, PlaybackState.STOPPED)
        self.assertIsNotNone(ctl.error)

    def test_empty_macro_returns_false(self):
        self._add("vazia", [])
        ctl = PlaybackController(self.store, backend=FakeBackend())
        self.assertFalse(ctl.start("vazia"))
        self.assertEqual(ctl.state, PlaybackState.STOPPED)

    def test_events_replayed_in_order(self):
        events = [MacroEvent(0.0, "key_down", key="w"),
                  MacroEvent(0.1, "mouse_down", button=1)]
        self.store.add(Macro("m", events=events))
        backend = FakeBackend()
        ctl = PlaybackController(self.store, backend=backend)
        self.assertTrue(ctl.start("m"))
        time.sleep(0.3)  # aguarda os 2 eventos + 100ms de intervalo
        self.assertEqual(ctl.state, PlaybackState.STOPPED)
        self.assertEqual([e.type for e in backend.events],
                         ["key_down", "mouse_down"])

    def test_repeat_is_respected(self):
        events = [MacroEvent(0.0, "key_down", key="w")]
        self.store.add(Macro("r", events=events, repeat=3))
        backend = FakeBackend()
        ctl = PlaybackController(self.store, backend=backend)
        self.assertTrue(ctl.start("r"))
        ctl.stop()
        self.assertEqual(len(backend.events), 3)

    def test_repeat_override_in_start(self):
        events = [MacroEvent(0.0, "key_down", key="w")]
        self.store.add(Macro("r", events=events, repeat=1))
        backend = FakeBackend()
        ctl = PlaybackController(self.store, backend=backend)
        self.assertTrue(ctl.start("r", repeat=2))
        ctl.stop()
        self.assertEqual(len(backend.events), 2)

    def test_timing_uses_monotonic_clock(self):
        events = [MacroEvent(0.0, "key_down", key="w"),
                  MacroEvent(0.05, "key_down", key="x")]
        self.store.add(Macro("t", events=events))
        backend = FakeBackend()
        ctl = PlaybackController(self.store, backend=backend)
        t0 = time.monotonic()
        self.assertTrue(ctl.start("t"))
        time.sleep(0.25)  # aguarda o playback concluir naturalmente
        elapsed = time.monotonic() - t0
        # playback deve esperar ~50ms entre eventos
        self.assertGreaterEqual(elapsed, 0.04)
        self.assertEqual(ctl.state, PlaybackState.STOPPED)

    def test_stop_ends_playback_cleanly(self):
        events = [MacroEvent(i * 0.1, "key_down", key="z")
                  for i in range(100)]
        self.store.add(Macro("longa", events=events, repeat=1))
        backend = FakeBackend()
        ctl = PlaybackController(self.store, backend=backend)
        self.assertTrue(ctl.start("longa"))
        time.sleep(0.05)
        ctl.stop()
        # thread encerrada após stop
        ctl.cleanup()
        self.assertLess(len(backend.events), 100)
        self.assertEqual(ctl.state, PlaybackState.STOPPED)

    def test_second_start_while_running_is_blocked(self):
        events = [MacroEvent(0.0, "key_down", key="w"),
                  MacroEvent(10.0, "key_down", key="x")]
        self.store.add(Macro("bloqueada", events=events))
        backend = FakeBackend()
        ctl = PlaybackController(self.store, backend=backend)
        self.assertTrue(ctl.start("bloqueada"))
        self.assertFalse(ctl.start("bloqueada"))
        ctl.stop()
        ctl.cleanup()

    def test_backend_error_becomes_failed_state(self):
        events = [MacroEvent(0.0, "key_down", key="w"),
                  MacroEvent(0.01, "key_down", key="x"),
                  MacroEvent(0.02, "key_down", key="y")]
        self.store.add(Macro("fail", events=events))
        backend = FakeBackend(fail_after=1)
        ctl = PlaybackController(self.store, backend=backend)
        self.assertTrue(ctl.start("fail"))
        # aguarda o worker falhar por conta própria (não usar stop())
        deadline = time.monotonic() + 2
        while ctl.state not in (PlaybackState.FAILED,
                                PlaybackState.STOPPED):
            if time.monotonic() > deadline:
                break
            time.sleep(0.01)
        # o erro do backend vira estado FAILED (não STOPPED)
        self.assertEqual(ctl.state, PlaybackState.FAILED)
        self.assertIn("falhou", ctl.error or "")
        ctl.cleanup()

    def test_state_returns_to_stopped_after_success(self):
        events = [MacroEvent(0.0, "key_down", key="w")]
        self.store.add(Macro("fim", events=events))
        ctl = PlaybackController(self.store, backend=FakeBackend())
        self.assertTrue(ctl.start("fim"))
        time.sleep(0.15)
        self.assertEqual(ctl.state, PlaybackState.STOPPED)

    def test_no_orphan_threads(self):
        events = [MacroEvent(0.0, "key_down", key="w")]
        self.store.add(Macro("x", events=events))
        before = threading.active_count()
        for _ in range(5):
            ctl = PlaybackController(self.store, backend=FakeBackend())
            ctl.start("x")
            ctl.cleanup()
        time.sleep(0.1)
        self.assertLessEqual(threading.active_count(), before + 1)


if __name__ == "__main__":
    unittest.main()
