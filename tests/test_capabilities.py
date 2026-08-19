"""Testes do modelo de capacidades granular."""

from mouse_hub.core.capabilities import CapabilityModel, CAPABILITY_NAMES


def test_evaluate_all_capabilities_are_reported():
    model = CapabilityModel(
        mouse_detected=lambda: True,
        hid_available=lambda: False,
        hardware_dpi_available=lambda: False,
        sensitivity_available=lambda: True,
        polling_rate_available=lambda: False,
        macro_capture_available=lambda: True,
        autoclick_available=lambda: False,
        active_window_detection_available=lambda: True,
    )
    state = model.evaluate()
    assert len(state.capabilities) == len(CAPABILITY_NAMES)
    assert state.is_available("mouse_detected")
    assert not state.is_available("hid_available")
    assert not state.is_available("hardware_dpi_available")
    assert state.is_available("sensitivity_available")
    assert state.is_available("macro_capture_available")
    assert state.is_available("active_window_detection_available")


def test_unavailable_model_reports_everything_false():
    state = CapabilityModel.unavailable().evaluate()
    for name in CAPABILITY_NAMES:
        assert not state.is_available(name), name


def test_detector_exception_degrades_gracefully():
    def broken() -> bool:
        raise RuntimeError("xinput sumiu do PATH")

    model = CapabilityModel(sensitivity_available=broken)
    state = model.evaluate()
    assert not state.is_available("sensitivity_available")
    assert "erro no detector" in state.get("sensitivity_available").reason


def test_state_is_immutable_once_evaluated():
    model = CapabilityModel(mouse_detected=lambda: True)
    state = model.evaluate()
    model.mouse_detected = lambda: False
    assert state.is_available("mouse_detected") is True


def test_unknown_capability_returns_unavailable():
    state = CapabilityModel.unavailable().evaluate()
    assert not state.is_available("invented_capability_xyz")


def test_detect_hid_independently_of_sensitivity():
    """mouse_detected, hid_available e sensitivity_available são
    avaliados de forma independente — um booleano único nunca basta."""
    model = CapabilityModel(
        mouse_detected=lambda: True,
        hid_available=lambda: False,   # sem permissão hidraw
        sensitivity_available=lambda: True,  # mas xinput funciona
    )
    state = model.evaluate()
    assert state.is_available("mouse_detected")
    assert not state.is_available("hid_available")
    assert state.is_available("sensitivity_available")
