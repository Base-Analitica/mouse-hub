"""Issue #78: a causa da capacidade do Auto-Clicker aparece no layout real.

Os testes usam somente CapabilityState fake e Qt offscreen. O status de foco do
Minecraft continua sendo uma informação independente da capacidade do ambiente.
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


def all_available_state() -> CapabilityState:
    model = CapabilityModel(**{name: (lambda: True) for name in CAPABILITY_NAMES})
    return model.evaluate()


def state_with_autoclicker(available: bool, reason: str) -> CapabilityState:
    return with_overrides(
        all_available_state(),
        {"autoclick_available": (available, reason)},
    )


class FakeMC:
    current_dpi = 800
    current_sensitivity = 50


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


def make_page(state_provider):
    import app.mouse_hub_app as app_module

    return app_module.AutoClickerPage(
        FakeMC(),
        FakeAc(),
        None,
        caps_provider=state_provider,
    )


def dispose_page(page):
    page.timer.stop()
    page.close()
    page.deleteLater()


def test_unavailable_hint_is_in_layout_before_controls(qapp):
    state = state_with_autoclicker(False, "ambiente sem suporte à automação")
    page = make_page(lambda: state)
    try:
        layout = page.layout()
        hint_index = layout.indexOf(page.caps_hint)
        status_index = layout.indexOf(page.mc_status)
        toggle_index = layout.indexOf(page.toggle_btn)

        assert hint_index >= 0
        assert hint_index == status_index + 1
        assert hint_index < toggle_index
        assert "ambiente sem suporte" in page.caps_hint.text()
        assert page.cps_slider.isEnabled() is False
        assert all(button.isEnabled() is False for button, _ in page.btn_buttons)
        assert page.toggle_btn.isEnabled() is False
    finally:
        dispose_page(page)


def test_available_hint_is_visible_without_replacing_focus_status(qapp):
    page = make_page(lambda: state_with_autoclicker(True, ""))
    try:
        page.resize(1050, 680)
        page.show()
        qapp.processEvents()

        layout = page.layout()
        assert layout.indexOf(page.caps_hint) >= 0
        assert "disponível" in page.caps_hint.text()
        assert page.caps_hint is not page.mc_status
        assert layout.indexOf(page.mc_status) >= 0
        assert page.mc_status.text() == "Minecraft não detectado"
        assert page.cps_slider.isEnabled() is True
        assert all(button.isEnabled() is True for button, _ in page.btn_buttons)
        assert page.toggle_btn.isEnabled() is True
    finally:
        dispose_page(page)


@pytest.mark.parametrize("size", [(1050, 680), (760, 560)])
def test_hint_and_cta_fit_official_viewports(qapp, size):
    page = make_page(
        lambda: state_with_autoclicker(
            False,
            "a causa de indisponibilidade pode ocupar mais de uma linha",
        )
    )
    try:
        page.resize(*size)
        page.show()
        qapp.processEvents()

        assert page.layout().indexOf(page.caps_hint) >= 0
        assert page.caps_hint.wordWrap() is True
        assert page.caps_hint.isVisible() is True
        assert page.caps_hint.geometry().width() > 0
        assert page.caps_hint.geometry().height() > 0
        hint_rect = page.caps_hint.geometry()
        cta_rect = page.toggle_btn.geometry()
        assert hint_rect.bottom() <= page.height()
        assert cta_rect.bottom() <= page.height()
        assert hint_rect.left() >= 0
        assert hint_rect.right() <= page.width()
        assert cta_rect.left() >= 0
        assert cta_rect.right() <= page.width()
        assert hint_rect.bottom() < cta_rect.top()
        assert not hint_rect.intersects(cta_rect)
    finally:
        dispose_page(page)


def test_state_change_updates_one_hint_in_place(qapp):
    current = {"state": state_with_autoclicker(False, "capacidade ausente")}
    page = make_page(lambda: current["state"])
    try:
        layout = page.layout()
        initial_index = layout.indexOf(page.caps_hint)
        assert initial_index >= 0

        current["state"] = state_with_autoclicker(True, "")
        page._sync_caps()

        assert layout.indexOf(page.caps_hint) == initial_index
        assert "disponível" in page.caps_hint.text()
        assert page.cps_slider.isEnabled() is True
        assert page.toggle_btn.isEnabled() is True
    finally:
        dispose_page(page)
