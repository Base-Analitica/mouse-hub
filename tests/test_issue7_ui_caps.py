"""Issue #7 — a UI reflete o CapabilityModel real, página por página.

Cobre (Qt offscreen, sem hardware):

1. composição de capacidades (hardware do core + evidências da
   instância de automação) sem colapsar verdades distintas;
2. copy da sidebar identifica o estado local sem linguagem de serviço web;
3. subtítulo do Dashboard declara DPI físico só com evidência;
4. Sensibilidade/Auto-Clicker/Macros desabilitam controles COM a
   causa quando a capacidade correspondente está indisponível.
"""

from __future__ import annotations

import os

import pytest

from mouse_hub.core.capabilities import (
    CAPABILITY_NAMES,
    CapabilityModel,
    CapabilityState,
    with_overrides,
)

pytest.importorskip("PyQt5")
from PyQt5.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    yield app


def all_available_model(**overrides) -> CapabilityModel:
    kwargs = {name: (lambda: True) for name in CAPABILITY_NAMES}
    for name, value in overrides.items():
        if isinstance(value, tuple):
            kwargs[name] = lambda value=value: value
        else:
            kwargs[name] = (lambda v=value: v) if value else (lambda v=value: (False, "ausente"))
    return CapabilityModel(**kwargs)


UNAVAILABLE = CapabilityModel.unavailable().evaluate()


class FakeState:
    """Estado mínimo consumido pelas páginas (mesma superfície de
    MouseCoreState usada pela UI)."""

    def __init__(self, caps: CapabilityState):
        self._caps = caps
        self.applied_dpi = None
        self.applied_sensitivity = None

    def capability_state(self) -> CapabilityState:
        return self._caps

    def refresh(self) -> None:
        pass


class FakeMC:
    current_dpi = 800
    current_sensitivity = 50


class FakeFocused:
    focused = False


class FakeWindowService:
    def is_focused(self, patterns):
        return FakeFocused()


class FakeSvc:
    window_service = FakeWindowService()


class FakeMe:
    """Superfície mínima usada por MacrosPage._build."""

    playback_state = "idle"
    playback_error = None

    def list_all(self):
        return {}

    def cleanup(self):
        pass


class FakeAcState:
    value = "stopped"


class FakeAc:
    cps = 10
    button = 1
    state = FakeAcState()
    running = False
    error = None

    def start(self):
        pass

    def stop(self):
        pass

    def cleanup(self):
        pass


# ── 1) composição de capacidades ─────────────────────────────────

def test_with_overrides_preserves_hardware_evidence():
    caps = all_available_model().evaluate()
    merged = with_overrides(caps, {"autoclick_available": (False, "sem X11")})
    assert merged.is_available("mouse_detected") is True
    assert merged.is_available("hardware_dpi_available") is True
    assert merged.is_available("autoclick_available") is False
    assert merged.reason_for("autoclick_available") == "sem X11"


def test_with_overrides_rejects_unknown_capability():
    caps = UNAVAILABLE
    with pytest.raises(ValueError):
        with_overrides(caps, {"capacidade_inventada": (True, "")})


def test_automation_overrides_follow_display(qapp, monkeypatch):
    import app.mouse_hub_app as app_module

    window = app_module.MouseHubApp()
    try:
        monkeypatch.setenv("DISPLAY", ":99")
        caps = window.full_capability_state()
        assert caps.is_available("autoclick_available") is True

        monkeypatch.delenv("DISPLAY", raising=False)
        caps = window.full_capability_state()
        assert caps.is_available("autoclick_available") is False
        assert "X11" in caps.reason_for("autoclick_available")
        assert caps.is_available("macro_capture_available") is False
    finally:
        window.close()
        window.me.cleanup()
        window.ac.cleanup()
        window.svc.cleanup()


# ── 2) sidebar identifica o estado local sem copy de serviço web ───

def test_sidebar_status_reflects_capabilities(qapp, monkeypatch):
    import app.mouse_hub_app as app_module

    window = app_module.MouseHubApp()
    try:
        # Sem mouse (ambiente de teste): Mouse não detectado
        window.mouse_state = FakeState(UNAVAILABLE)
        window._update_sidebar_status()
        assert window._status_text.text() == "Mouse não detectado"

        # Detectado mas sem HID: Mouse detectado
        caps = all_available_model(hid_available=False).evaluate()
        window.mouse_state = FakeState(caps)
        window._update_sidebar_status()
        assert window._status_text.text() == "Mouse detectado"

        # Detectado + HID: G403 conectado
        window.mouse_state = FakeState(all_available_model().evaluate())
        window._update_sidebar_status()
        assert window._status_text.text() == "G403 conectado"
    finally:
        window.close()
        window.me.cleanup()
        window.ac.cleanup()
        window.svc.cleanup()


def test_sidebar_status_updates_on_page_switch(qapp):
    import app.mouse_hub_app as app_module

    window = app_module.MouseHubApp()
    try:
        window.mouse_state = FakeState(UNAVAILABLE)
        window._switch_page(2)
        assert window._status_text.text() == "Mouse não detectado"
        window.mouse_state = FakeState(all_available_model().evaluate())
        window._switch_page(0)
        assert window._status_text.text() == "G403 conectado"
    finally:
        window.close()
        window.me.cleanup()
        window.ac.cleanup()
        window.svc.cleanup()


# ── 3) subtítulo do Dashboard honesto quanto ao DPI ─────────────

def _subtitle_for(caps):
    import app.mouse_hub_app as app_module

    page = app_module.DashboardPage(
        FakeMC(), FakeAc(), None, FakeSvc(), state=FakeState(caps)
    )
    page._sync_subtitle()
    return page.subtitle.text()


def test_subtitle_says_hardware_dpi_only_with_evidence(qapp):
    caps = all_available_model(hardware_dpi_available=(False, "feature 0x2201 ausente")).evaluate()
    text = _subtitle_for(caps)
    assert "Hardware DPI disponível" not in text
    assert "Acesso HID" in text
    assert "0x2201" in text  # causa real aparece


def test_subtitle_full_green_with_dpi_evidence(qapp):
    assert "Hardware DPI disponível" in _subtitle_for(all_available_model().evaluate())


def test_subtitle_no_mouse(qapp):
    text = _subtitle_for(UNAVAILABLE)
    assert "Sem G403 detectado" in text


# ── 4) páginas desabilitam controles com a causa ────────────────

def test_sensitivity_page_gates_slider(qapp):
    import app.mouse_hub_app as app_module

    page = app_module.SensitivityPage(FakeMC(), state=FakeState(UNAVAILABLE))
    assert page.slider.isEnabled() is False
    assert "indisponível" in page.caps_hint.text()

    page2 = app_module.SensitivityPage(
        FakeMC(), state=FakeState(all_available_model().evaluate())
    )
    assert page2.slider.isEnabled() is True
    assert "disponível" in page2.caps_hint.text()


def test_autoclicker_page_gates_controls(qapp):
    import app.mouse_hub_app as app_module

    page = app_module.AutoClickerPage(
        FakeMC(), FakeAc(), None,
        caps_provider=lambda: UNAVAILABLE,
    )
    assert page.toggle_btn.isEnabled() is False
    assert page.cps_slider.isEnabled() is False
    assert "indisponível" in page.caps_hint.text()

    page2 = app_module.AutoClickerPage(
        FakeMC(), FakeAc(), None,
        caps_provider=lambda: with_overrides(UNAVAILABLE, {"autoclick_available": (True, "")}),
    )
    assert page2.toggle_btn.isEnabled() is True
    assert page2.cps_slider.isEnabled() is True


def test_macros_page_gates_record_and_list(qapp):
    import app.mouse_hub_app as app_module

    page = app_module.MacrosPage(FakeMe(), None, caps_provider=lambda: UNAVAILABLE)
    assert page.record_btn.isEnabled() is False
    assert page.name_input.isEnabled() is False
    assert "indisponível" in page.caps_hint.text()

    page2 = app_module.MacrosPage(
        FakeMe(), None,
        caps_provider=lambda: with_overrides(UNAVAILABLE, {"macro_capture_available": (True, "")}),
    )
    assert page2.record_btn.isEnabled() is True
    assert page2.name_input.isEnabled() is True
