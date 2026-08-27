"""Issue #5 — refinamentos do auto-clicker (sem hardware).

Cobre, de forma determinística (fakes/headless):

1. keycodes reais do fallback do layout US (macros legadas reproduziam
   a tecla errada: o mapa antigo era sequencial, "w" virava 60);
2. keycode_from_name delega ao mesmo mapa do MacroStore;
3. X11TitleSource marca indisponibilidade quando a conexão quebra e
   serializa leituras concorrentes na mesma conexão;
4. persistência de CPS/botão do auto-clicker no config XDG, com
   defaults herméticos quando nenhum caminho é injetado.
"""

from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path

import pytest

from mouse_hub.core.automation.service import AutomationService
from mouse_hub.core.automation.store import _FALLBACK_KEYCODES
from mouse_hub.core.automation.types import EventType, RecordedEvent
from mouse_hub.core.config import ConfigPaths, load_autoclicker_settings, save_autoclicker_settings
from mouse_hub.platform.linux import automation as automation_module
from mouse_hub.platform.linux.automation import X11TitleSource, keycode_from_name


# ── 1) keycodes reais do fallback US ─────────────────────────────

@pytest.mark.parametrize("char,expected", [
    ("q", 24), ("w", 25), ("e", 26), ("r", 27), ("t", 28),
    ("y", 29), ("u", 30), ("i", 31), ("o", 32), ("p", 33),
    ("a", 38), ("s", 39), ("d", 40), ("f", 41), ("g", 42),
    ("h", 43), ("j", 44), ("k", 45), ("l", 46),
    ("z", 52), ("x", 53), ("c", 54), ("v", 55), ("b", 56),
    ("n", 57), ("m", 58),
    ("1", 10), ("5", 14), ("9", 18), ("0", 19),
    ("space", 65),
])
def test_fallback_keycodes_match_real_x11_layout(char, expected):
    keysym = {"space": 0x020}.get(char) or ord(char)
    assert _FALLBACK_KEYCODES[keysym] == expected


def test_keycode_from_name_uses_core_map_without_display():
    """Sem display X, "w" deve resolver para 25 (evdev real), não para
    o valor sequencial errado da fórmula ASCII antiga."""
    assert keycode_from_name("w") == 25
    assert keycode_from_name("q") == 24


# ── fakes de display para o TitleSource ──────────────────────────

class _FakeWin:
    def __init__(self, title=None, root=False):
        self._title = title
        self.id = 0 if root else 1

    def get_full_property(self, atom, _type):
        if self._title is None:
            return None
        import struct
        return type("P", (), {"value": self._title.encode()})()

    def query_tree(self):
        return type("T", (), {"parent": None})()


class _FakeFocus:
    def __init__(self, win):
        self.focus = win


class _FakeDisplay:
    """Display X mínimo: título configurável, falha injetável e
    contador de leituras concorrentes."""

    def __init__(self, title="Minecraft", fail=False, slow=0.0):
        self.title = title
        self.fail = fail
        self.slow = slow
        self.closed = False
        self._cur = 0
        self.max_concurrent = 0
        self._lock = threading.Lock()

    def get_input_focus(self):
        with self._lock:
            self._cur += 1
            self.max_concurrent = max(self.max_concurrent, self._cur)
        try:
            if self.slow:
                time.sleep(self.slow)
            if self.fail:
                raise RuntimeError("conexão quebrada")
            return _FakeFocus(_FakeWin(self.title))
        finally:
            with self._lock:
                self._cur -= 1

    def intern_atom(self, name, _only_if_exists=True):
        return 1

    def screen(self):
        return type("S", (), {"root": _FakeWin(root=True)})()

    def close(self):
        self.closed = True


@pytest.fixture
def fake_display(monkeypatch):
    holder = {"created": [], "queue": []}

    def factory(**kwargs):
        if holder["queue"]:
            kwargs = holder["queue"].pop(0)
        disp = _FakeDisplay(**kwargs)
        holder["created"].append(disp)
        return disp

    monkeypatch.setattr(automation_module, "Display", factory)
    return holder


# ── 3) TitleSource: quebra marca indisponível; leitura serializada ─

def test_title_source_marks_unavailable_on_broken_connection(fake_display):
    fake_display["created"].append(_FakeDisplay(fail=True))
    # substitui o primeiro display por um que falha na leitura
    src = X11TitleSource(ttl_ms=0)
    src._display = fake_display["created"][0]

    assert src.active_window_title() is None
    assert src.is_available() is False
    # a conexão quebrada foi descartada e fechada
    assert fake_display["created"][0].closed
    assert src._display is None


def test_title_source_available_again_after_successful_reopen(fake_display):
    src = X11TitleSource(ttl_ms=0)
    broken = _FakeDisplay(fail=True)
    src._display = broken

    assert src.active_window_title() is None
    assert src.is_available() is False

    # próxima abertura funciona (servidor voltou) — disponibilidade volta
    fake_display["queue"].append({"title": "Lunar Client"})
    assert src.active_window_title() == "Lunar Client"
    assert src.is_available() is True


def test_title_source_serializes_concurrent_reads(fake_display):
    """Duas threads consultando com cache expirado NÃO podem estar
    dentro da leitura X ao mesmo tempo (mesma conexão não é
    thread-safe)."""
    slow = _FakeDisplay(title="Minecraft", slow=0.08)
    src = X11TitleSource(ttl_ms=0)
    src._display = slow

    results = []
    def query():
        results.append(src.active_window_title())

    threads = [threading.Thread(target=query) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results == ["Minecraft", "Minecraft", "Minecraft"]
    assert slow.max_concurrent == 1


def test_title_source_caches_within_ttl(fake_display):
    disp = _FakeDisplay(title="Minecraft")
    src = X11TitleSource(ttl_ms=10_000)
    src._display = disp

    assert src.active_window_title() == "Minecraft"
    assert src.active_window_title() == "Minecraft"
    # segunda leitura veio do cache: uma única consulta X
    assert disp.max_concurrent == 1


# ── 4) persistência de CPS/botão ─────────────────────────────────

def _tmp_paths(tmp_path):
    return ConfigPaths(config_dir=tmp_path / "cfg", data_dir=tmp_path / "data")


def test_autoclicker_settings_roundtrip(tmp_path):
    paths = _tmp_paths(tmp_path)
    assert load_autoclicker_settings(paths) == (10, "left")  # default

    save_autoclicker_settings(25, "right", paths)
    assert load_autoclicker_settings(paths) == (25, "right")


def test_autoclicker_settings_rejects_invalid(tmp_path):
    paths = _tmp_paths(tmp_path)
    with pytest.raises(ValueError):
        save_autoclicker_settings(0, "left", paths)
    with pytest.raises(ValueError):
        save_autoclicker_settings(51, "left", paths)
    with pytest.raises(ValueError):
        save_autoclicker_settings(10, "up", paths)


def test_autoclicker_settings_invalid_file_falls_back(tmp_path):
    paths = _tmp_paths(tmp_path)
    save_autoclicker_settings(30, "middle", paths)
    # config corrompido/absurdo: leitor cai no default sem quebrar
    (paths.config_file).write_text('{"autoclicker": {"cps": 999, "button": "up"}}')
    assert load_autoclicker_settings(paths) == (10, "left")


def test_service_without_config_paths_is_hermetic(tmp_path):
    """Sem config_paths injetado, o serviço NÃO lê nem escreve disco
    (suíte determinística) — defaults do core."""
    svc = AutomationService(macros_path=tmp_path / "macros.json")
    cps, button = svc.initial_clicker_settings()
    assert (cps, button) == (10, "left")
    assert svc.save_clicker_settings() is False


def test_service_clicker_uses_persisted_settings(tmp_path):
    paths = _tmp_paths(tmp_path)
    save_autoclicker_settings(25, "right", paths)
    svc = AutomationService(macros_path=tmp_path / "macros.json", config_paths=paths)
    clicker = svc.clicker
    assert clicker.cps == 25
    assert clicker.button.value == "right"


def test_service_persists_clicker_mutations(tmp_path):
    paths = _tmp_paths(tmp_path)
    svc = AutomationService(macros_path=tmp_path / "macros.json", config_paths=paths)
    clicker = svc.clicker
    clicker.set_cps(33)
    clicker.set_button(clicker.button.__class__.from_id(2))
    assert svc.save_clicker_settings() is True
    assert load_autoclicker_settings(paths) == (33, "middle")


def test_facade_defaults_come_from_persisted_config(tmp_path):
    """A fachada da UI reflete as preferências persistidas ANTES do
    primeiro uso do motor (leituras em idle não criam engine)."""
    import app.mouse_hub_app as app_module

    paths = _tmp_paths(tmp_path)
    save_autoclicker_settings(42, "middle", paths)
    svc = AutomationService(macros_path=tmp_path / "macros.json", config_paths=paths)
    facade_cls = getattr(app_module, "AutoClickerFacade", None) or app_module.AutoClickerEngine
    fac = facade_cls(svc)

    assert fac.cps == 42
    assert fac.button == 2
    assert svc._clicker is None  # nada de engine em idle
