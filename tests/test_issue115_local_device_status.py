"""Issue #115: a sidebar deve descrever o estado local do mouse."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

from mouse_hub.core.capabilities import CAPABILITY_NAMES, CapabilityModel, CapabilityState


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def capability_state(*, mouse_detected, hid_available, hardware_dpi_available=True):
    values = {name: False for name in CAPABILITY_NAMES}
    values.update(
        mouse_detected=mouse_detected,
        hid_available=hid_available,
        hardware_dpi_available=hardware_dpi_available,
    )
    return CapabilityModel(
        **{name: (lambda value=value: value) for name, value in values.items()}
    ).evaluate()


class FakeState:
    def __init__(self, caps: CapabilityState):
        self._caps = caps
        self.applied_dpi = None
        self.applied_sensitivity = None

    def capability_state(self) -> CapabilityState:
        return self._caps

    def refresh(self):
        pass


@pytest.fixture
def window(qapp, monkeypatch):
    import app.mouse_hub_app as app_module

    class DummyMonitor:
        def __init__(self, out):
            pass

        def start(self):
            return True

        def stop(self):
            pass

    monkeypatch.setattr(app_module, "UdevHidrawMonitor", DummyMonitor)
    monkeypatch.setattr(
        app_module, "build_mouse_state", lambda: FakeState(capability_state(
            mouse_detected=False, hid_available=False
        ))
    )
    app = app_module.MouseHubApp()
    try:
        yield app
    finally:
        app.close()


@pytest.mark.parametrize(
    ("caps", "expected_text", "expected_color"),
    (
        (
            capability_state(mouse_detected=True, hid_available=True),
            "G403 conectado",
            "success",
        ),
        (
            capability_state(mouse_detected=True, hid_available=False),
            "Mouse detectado",
            "warning",
        ),
        (
            capability_state(mouse_detected=False, hid_available=False),
            "Mouse não detectado",
            "text_muted",
        ),
    ),
)
def test_sidebar_uses_local_device_copy(window, caps, expected_text, expected_color):
    import app.mouse_hub_app as app_module

    window.mouse_state = FakeState(caps)
    window._update_sidebar_status()

    assert window._status_text.text() == expected_text
    assert "Online" not in window._status_text.text()
    assert f"background: {app_module.COLORS[expected_color]}" in (
        window._status_dot.styleSheet()
    )


def test_sidebar_connection_copy_does_not_depend_on_dpi(window):
    caps = capability_state(
        mouse_detected=True,
        hid_available=True,
        hardware_dpi_available=False,
    )
    window.mouse_state = FakeState(caps)
    window._update_sidebar_status()

    assert window._status_text.text() == "G403 conectado"


def test_sidebar_copy_fits_small_window(window, qapp):
    window.resize(760, 560)
    window.show()
    qapp.processEvents()
    window.mouse_state = FakeState(
        capability_state(mouse_detected=True, hid_available=True)
    )
    window._update_sidebar_status()
    qapp.processEvents()

    assert window._status_text.isVisible()
    assert window._status_text.sizeHint().width() <= window.status_indicator.width()
    assert window._status_text.text() == "G403 conectado"
