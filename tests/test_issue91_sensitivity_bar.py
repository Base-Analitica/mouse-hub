"""Regressão da issue #91: a SensitivityPage não exibe barra decorativa."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt5")
from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication, QFrame, QLabel  # noqa: E402

from mouse_hub.core.capabilities import CapabilityModel

import app.mouse_hub_app as app_module


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class FakeState:
    """Superfície mínima de MouseCoreState usada pela SensitivityPage."""

    applied_sensitivity = 50

    def __init__(self):
        self._caps = CapabilityModel.unavailable().evaluate()

    def capability_state(self):
        return self._caps

    def refresh(self):
        pass


class FakeMC:
    def __init__(self):
        self.current_sensitivity = 50
        self.set_calls = []

    def set_sensitivity(self, value):
        self.set_calls.append(value)
        self.current_sensitivity = value


@pytest.mark.parametrize("size", [(1050, 680), (760, 560)])
def test_sensitivity_page_removes_static_speed_bar_and_preserves_controls(
    qapp, size
):
    page = app_module.SensitivityPage(FakeMC(), state=FakeState())
    page.resize(*size)
    page.show()
    qapp.processEvents()
    try:
        assert page.findChildren(QFrame, "speedBar") == []
        assert page.slider.orientation() == Qt.Horizontal
        assert (page.slider.minimum(), page.slider.maximum()) == (0, 100)
        assert page.slider.value() == 50
        assert page.slider.isEnabled() is False

        labels = {label.text() for label in page.findChildren(QLabel)}
        assert {"Lento", "Rápido"}.issubset(labels)
        assert page.sens_value.text() == "50%"
        assert page.sens_state.text() == "VELOCIDADE DO SISTEMA (libinput)"
        assert "Sensibilidade indisponível" in page.caps_hint.text()
        assert len(page.polling_buttons) == 4
        assert "Polling rate indisponível" in page.polling_hint.text()
    finally:
        page.close()
        page.deleteLater()
        qapp.processEvents()


def test_sensitivity_slider_keeps_preview_and_release_callbacks(qapp):
    mc = FakeMC()
    page = app_module.SensitivityPage(mc)
    page.show()
    qapp.processEvents()
    try:
        page.slider.setValue(60)
        assert page.sens_value.text() == "60%"
        assert mc.set_calls == []

        page.slider.sliderReleased.emit()
        assert mc.set_calls == [60]
    finally:
        page.close()
        page.deleteLater()
        qapp.processEvents()
