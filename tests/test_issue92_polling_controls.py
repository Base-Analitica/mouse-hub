# -*- coding: utf-8 -*-
"""Regressões da issue #92: não exibir controles mortos de polling rate."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QLabel

from app.mouse_hub_app import MouseController, MouseCoreState, SensitivityPage
from mouse_hub.core.dpi_persistence import NeverDpiPersister
from mouse_hub.core.mouse_controller import MouseController as CoreMouseController
from tests.fakes import FakeHidAccess, FakeSystemInput


_VIEWPORTS = [(1050, 680), (760, 560)]


class _CapabilitySnapshot:
    def __init__(self, polling_available, reason=""):
        self._available = {
            "polling_rate_available": polling_available,
            "sensitivity_available": True,
        }
        self._reasons = {
            "polling_rate_available": reason,
            "sensitivity_available": "",
        }

    def is_available(self, name):
        return self._available.get(name, False)

    def reason_for(self, name):
        return self._reasons.get(name, "")


def _state_with_polling_capability(available, reason=""):
    hid = FakeHidAccess()
    system_input = FakeSystemInput()
    core = CoreMouseController(
        hid=hid,
        system_input=system_input,
        dpi_persister=NeverDpiPersister(),
    )
    state = MouseCoreState(core)
    snapshot = {"value": _CapabilitySnapshot(available, reason)}
    state.capability_state = lambda: snapshot["value"]
    state.refresh = lambda: None
    return state, hid, snapshot


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _polling_controls(page):
    controls = getattr(page, "polling_controls", None)
    assert controls is not None, "SensitivityPage must expose polling_controls"
    return controls


def _show(page, qapp, size):
    page.resize(*size)
    page.show()
    qapp.processEvents()


def _polling_title(page):
    return next(
        label for label in page.findChildren(QLabel)
        if label.text() == "Polling Rate"
    )


@pytest.mark.parametrize("size", _VIEWPORTS)
def test_unavailable_polling_controls_are_hidden_but_reason_stays_visible(
    qapp, size
):
    state, _, _ = _state_with_polling_capability(
        False,
        "a feature Report Rate do G403 não está implementada",
    )
    page = SensitivityPage(MouseController(), state=state)
    _show(page, qapp, size)

    controls = _polling_controls(page)
    assert _polling_title(page).isVisible()
    assert "Report Rate" in page.polling_hint.text()
    assert controls.isHidden()
    assert not controls.isEnabled()
    assert all(not button.isVisible() for button in page.polling_buttons)
    assert all(not button.isEnabled() for button in page.polling_buttons)
    assert all(not button.isChecked() for button in page.polling_buttons)

    page.close()


@pytest.mark.parametrize("size", _VIEWPORTS)
def test_confirmed_polling_capability_shows_existing_controls_without_selection(
    qapp, size
):
    state, hid, _ = _state_with_polling_capability(True)
    page = SensitivityPage(MouseController(), state=state)
    _show(page, qapp, size)

    controls = _polling_controls(page)
    assert controls.isVisible()
    assert controls.isEnabled()
    assert [button.text() for button in page.polling_buttons] == [
        "125 Hz",
        "250 Hz",
        "500 Hz",
        "1000 Hz",
    ]
    assert all(button.isVisible() for button in page.polling_buttons)
    assert all(button.isEnabled() for button in page.polling_buttons)
    assert all(not button.isChecked() for button in page.polling_buttons)
    assert page.polling_controls.layout().contentsMargins().left() == 0
    assert page.polling_controls.layout().contentsMargins().right() == 0
    assert page.polling_controls.layout().spacing() == 12

    for button in page.polling_buttons:
        button.click()
    assert hid.raw_written_reports == []

    page.close()


def test_polling_controls_follow_an_explicit_capability_transition(qapp):
    state, _, snapshot = _state_with_polling_capability(
        False, "capacidade ausente"
    )
    page = SensitivityPage(MouseController(), state=state)
    _show(page, qapp, _VIEWPORTS[0])

    controls = _polling_controls(page)
    assert controls.isHidden()
    assert all(not button.isEnabled() for button in page.polling_buttons)

    snapshot["value"] = _CapabilitySnapshot(True)
    page._sync_polling()
    qapp.processEvents()
    assert controls.isVisible()
    assert all(button.isEnabled() for button in page.polling_buttons)
    assert all(not button.isChecked() for button in page.polling_buttons)

    snapshot["value"] = _CapabilitySnapshot(False, "capacidade revogada")
    page._sync_polling()
    qapp.processEvents()
    assert controls.isHidden()
    assert all(not button.isEnabled() for button in page.polling_buttons)

    page.close()


def test_missing_core_state_hides_unconfirmed_polling_controls(qapp):
    page = SensitivityPage(MouseController(), state=None)
    _show(page, qapp, _VIEWPORTS[0])

    controls = _polling_controls(page)
    assert controls.isHidden()
    assert "indisponível" in page.polling_hint.text().lower()
    assert all(not button.isEnabled() for button in page.polling_buttons)
    assert all(not button.isChecked() for button in page.polling_buttons)

    page.close()


def test_unavailable_polling_controls_keep_the_fallback_reason(qapp):
    state, _, _ = _state_with_polling_capability(False)
    page = SensitivityPage(MouseController(), state=state)
    _show(page, qapp, _VIEWPORTS[0])

    controls = _polling_controls(page)
    assert controls.isHidden()
    assert "capacidade não disponível no ambiente atual" in (
        page.polling_hint.text()
    )

    page.close()


def test_polling_sync_keeps_capability_decision_in_state(monkeypatch, qapp):
    state, _, _ = _state_with_polling_capability(False, "razão controlada")
    calls = []
    original = state.capability_state

    def capability_state():
        calls.append(True)
        return original()

    monkeypatch.setattr(state, "capability_state", capability_state)
    page = SensitivityPage(MouseController(), state=state)
    _show(page, qapp, _VIEWPORTS[0])

    assert calls
    controls = _polling_controls(page)
    assert controls.isHidden()
    assert "razão controlada" in page.polling_hint.text()

    page.close()


def test_show_event_refresh_reprojects_polling_capability(qapp):
    state, _, snapshot = _state_with_polling_capability(
        False, "capacidade ainda indisponível"
    )
    page = SensitivityPage(MouseController(), state=state)
    _show(page, qapp, _VIEWPORTS[0])

    controls = _polling_controls(page)
    assert controls.isHidden()

    def refresh():
        snapshot["value"] = _CapabilitySnapshot(True)

    state.refresh = refresh
    page.hide()
    page.show()
    qapp.processEvents()

    assert controls.isVisible()
    assert controls.isEnabled()
    assert all(button.isEnabled() for button in page.polling_buttons)
    assert all(not button.isChecked() for button in page.polling_buttons)

    page.close()
