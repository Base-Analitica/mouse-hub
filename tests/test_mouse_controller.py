"""Testes do MouseController: DPI físico ≠ sensibilidade e ausência de
sucesso falso.

Hardware totalmente simulado via fakes; nenhum subprocess ou /dev é
usado.
"""

import pytest

from mouse_hub.core.mouse_controller import MouseController
from tests.fakes import FakeHidAccess, FakeSystemInput, fake_g403_device


@pytest.fixture()
def controller():
    hid = FakeHidAccess()
    system_input = FakeSystemInput()
    ctrl = MouseController(hid, system_input)
    ctrl.refresh_device(fake_g403_device())
    return ctrl, hid, system_input


# ── DPI físico ────────────────────────────────────────────────────


def test_set_hardware_dpi_applies_to_hid(controller):
    ctrl, hid, _ = controller
    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "applied"
    assert ctrl.applied_dpi == 800
    # O report enviado carrega o DPI em big endian nos bytes 3-4.
    report = hid.written_reports[-1]
    assert (report[3] << 8 | report[4]) == 800


def test_set_hardware_dpi_is_independent_of_sensitivity(controller):
    ctrl, hid, system_input = controller
    ctrl.set_hardware_dpi(1200)
    # Sensibilidade jamais foi tocada durante uma aplicação de DPI físico.
    assert system_input.accel_state is None


def test_set_hardware_dpi_normalizes_and_reports_partial(controller):
    ctrl, _, _ = controller
    result = ctrl.set_hardware_dpi(824)
    assert result.status.value == "applied_partial"
    assert ctrl.applied_dpi == 800
    assert result.details.get("requested") == 824
    assert result.details.get("applied") == 800


def test_set_hardware_dpi_clamps_out_of_range(controller):
    ctrl, _, _ = controller
    result = ctrl.set_hardware_dpi(99999)
    assert result.status.value == "applied_partial"
    assert ctrl.applied_dpi == 25600


def test_set_hardware_dpi_device_absent(controller):
    ctrl, _, _ = controller
    ctrl.refresh_device(None)
    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "device_not_found"
    assert not result.status.ok


def test_set_hardware_dpi_permission_denied(controller):
    ctrl, _, _ = controller
    ctrl.refresh_device(fake_g403_device(hidraw="/dev/permission_denied"))
    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "permission_denied"
    assert not result.status.ok


def test_set_hardware_dpi_hid_write_failure_no_success(controller):
    ctrl, hid, _ = controller
    hid.write_succeeds = False
    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "failed"
    assert not result.status.ok


def test_set_hardware_dpi_without_hidraw_reports_no_dpi_capability(controller):
    ctrl, _, _ = controller
    ctrl.refresh_device(fake_g403_device(hidraw=None))
    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "device_not_found"
    assert not result.status.ok


# ── Sensibilidade ─────────────────────────────────────────────────


def test_set_sensitivity_applies_via_system_input(controller):
    ctrl, _, system_input = controller
    result = ctrl.set_sensitivity(75)
    assert result.status.ok
    assert system_input.accel_state == pytest.approx(0.5)
    assert ctrl.applied_sensitivity == 75


def test_set_sensitivity_does_not_touch_hid(controller):
    ctrl, hid, system_input = controller
    ctrl.set_sensitivity(50)
    assert hid.written_reports == []


def test_set_sensitivity_pointer_missing(controller):
    ctrl, _, system_input = controller
    system_input.pointer_name = None
    result = ctrl.set_sensitivity(50)
    assert result.status.value == "device_not_found"
    assert not result.status.ok


def test_set_sensitivity_system_failure(controller):
    ctrl, _, system_input = controller
    system_input.set_succeeds = False
    result = ctrl.set_sensitivity(50)
    assert result.status.value == "failed"
    assert not result.status.ok


def test_get_sensitivity_reads_system(controller):
    ctrl, _, system_input = controller
    system_input.accel_state = 0.5
    assert ctrl.get_sensitivity() == 75


def test_get_sensitivity_unavailable(controller):
    ctrl, _, system_input = controller
    system_input.xinput_available = False
    assert ctrl.get_sensitivity() is None


# ── Prevenção de sucesso falso ────────────────────────────────────


def test_hid_failure_never_reports_dpi_changed(controller):
    """Invariant central do produto: se o hardware rejeita o DPI, o
    resultado nunca indica sucesso, mesmo que a sensibilidade do
    sistema estivesse disponível no ambiente."""
    ctrl, hid, system_input = controller
    hid.write_succeeds = False
    system_input.accel_state = 0.0

    result = ctrl.set_hardware_dpi(1600)
    assert not result.status.ok
    assert ctrl.applied_dpi is None
    # Sensibilidade permaneceu exatamente como estava.
    assert system_input.accel_state == 0.0


def test_no_device_means_no_false_success(controller):
    ctrl, _, _ = controller
    ctrl.refresh_device(None)
    assert not ctrl.set_hardware_dpi(800).status.ok
    assert not ctrl.set_sensitivity(50).status.ok


# ── Modelo de capacidades ─────────────────────────────────────────


def test_capability_model_reflects_environment(controller):
    ctrl, hid, system_input = controller
    model = ctrl.capability_model()
    state = model.evaluate()

    assert state.is_available("mouse_detected")
    assert state.is_available("hid_available")
    assert state.is_available("hardware_dpi_available")
    assert state.is_available("sensitivity_available")


def test_capability_model_hid_missing_mouse_still_detected(controller):
    ctrl, _, _ = controller
    ctrl.refresh_device(fake_g403_device(hidraw=None))
    state = ctrl.capability_model().evaluate()

    assert state.is_available("mouse_detected")
    assert not state.is_available("hid_available")
    assert not state.is_available("hardware_dpi_available")
    assert state.is_available("sensitivity_available")


def test_capability_model_all_absent(controller):
    ctrl, hid, system_input = controller
    ctrl.refresh_device(None)
    system_input.xinput_available = False
    state = ctrl.capability_model().evaluate()

    for name in ("mouse_detected", "hid_available", "hardware_dpi_available",
                 "sensitivity_available", "active_window_detection_available"):
        assert not state.is_available(name), name


def test_capability_model_window_detection(controller):
    ctrl, _, system_input = controller
    system_input.window_title = "Minecraft"
    state = ctrl.capability_model().evaluate()
    assert state.is_available("active_window_detection_available")

    system_input.window_title = None
    state = ctrl.capability_model().evaluate()
    assert not state.is_available("active_window_detection_available")
