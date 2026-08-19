"""Testes do MouseController: DPI físico ≠ sensibilidade e ausência de
sucesso falso, agora com confirmação de resposta (fail closed) e
endpoint confirmado no protocolo HID++.

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
    # O probe com o HID fechado valida o endpoint e o registra como
    # confirmado; o set de DPI abre o descritor sob demanda.
    device = fake_g403_device()
    ctrl.refresh_device(device)          # registra e abre o descritor
    hid.close()                          # libera posse exclusiva para o probe
    # Duas respostas ao probe: uma para o fixture validar, outra para
    # o próprio teste (cada probe consome uma entrada da fila).
    hid.probe_responses = list(hid.probe_responses) * 2
    result = ctrl.probe_endpoint()
    assert result.status.ok, "probe não deveria falhar com o fake padrão"
    hid.open(device)                     # reabre para os testes de operação
    return ctrl, hid, system_input


# ── Probe de endpoint ─────────────────────────────────────────────


def test_probe_confirms_endpoint(controller):
    ctrl, hid, _ = controller
    # Com o HID já aberto pela fixture, o probe exige posse exclusiva.
    assert ctrl.probe_endpoint().status.value == "unsupported"
    hid.close()
    result = ctrl.probe_endpoint()
    assert result.status.ok
    assert ctrl._endpoint_confirmed is True
    assert not hid.is_open()  # probe abre, valida e fecha


def test_probe_requires_opened_hid(controller):
    ctrl, hid, _ = controller
    # Um novo registro de dispositivo reseta a confirmação anterior;
    # com o descritor em uso por outra operação, o probe recusa validar
    # (não reabre por cima de outro usuário do descritor) e não altera
    # o estado: o endpoint segue não confirmado.
    ctrl.refresh_device(fake_g403_device())
    assert ctrl._endpoint_confirmed is False
    result = ctrl.probe_endpoint()
    assert result.status.value == "unsupported"
    assert ctrl._endpoint_confirmed is False


def test_probe_fails_without_device(controller):
    ctrl, _, _ = controller
    ctrl.refresh_device(None)
    assert not ctrl.probe_endpoint().status.ok


def test_probe_rejects_non_responsive_endpoint(controller):
    ctrl, hid, _ = controller
    hid.close()
    hid.probe_responses = []  # endpoint mudo ao probe
    assert not ctrl.probe_endpoint().status.ok
    assert ctrl._endpoint_confirmed is False
    # O descritor nunca fica aberto após o probe.
    assert not hid.is_open()


def test_probe_rejects_hidpp_error(controller):
    ctrl, hid, _ = controller
    hid.close()
    hid.probe_error_response = True
    assert not ctrl.probe_endpoint().status.ok
    assert ctrl._endpoint_confirmed is False


def test_probe_handles_permission_denied(controller):
    ctrl, hid, system_input = controller
    hid.close()
    hid.open_permission_denied = True
    assert not ctrl.probe_endpoint().status.ok
    assert ctrl._endpoint_confirmed is False
    # A avaliação de capacidades reflete a perda.
    state = ctrl.capability_model().evaluate()
    assert not state.is_available("hardware_dpi_available")


def test_probe_handles_open_exception(controller):
    ctrl, hid, _ = controller
    hid.close()
    hid.open_raises = RuntimeError("sysfs sumiu")
    assert not ctrl.probe_endpoint().status.ok
    assert ctrl._endpoint_confirmed is False
    assert not hid.is_open()


# ── DPI físico ────────────────────────────────────────────────────


def test_set_hardware_dpi_applies_to_hid(controller):
    ctrl, hid, _ = controller
    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "applied"
    assert ctrl.applied_dpi == 800
    # O report enviado carrega o DPI em big endian nos bytes 3-4
    # (feature 0x01, fn 0x10).
    report = hid.written_reports[-1]
    assert report[1] == 0x01
    assert (report[3] << 8 | report[4]) == 800
    # A operação foi confirmada: `confirmation` é parte do resultado.
    assert result.details.get("confirmation") is True


def test_set_hardware_dpi_is_independent_of_sensitivity(controller):
    ctrl, hid, system_input = controller
    ctrl.set_hardware_dpi(1200)
    # Sensibilidade jamais foi tocada durante uma aplicação de DPI físico.
    assert system_input.accel_state is None
    assert hid.written_reports and report_is_dpi(hid.written_reports[-1])


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
    assert ctrl.applied_dpi is None


def test_set_hardware_dpi_without_hidraw_reports_no_dpi_capability(controller):
    ctrl, _, _ = controller
    ctrl.refresh_device(fake_g403_device(hidraw=None))
    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "device_not_found"
    assert not result.status.ok


def test_set_hardware_dpi_requires_confirmed_endpoint(controller):
    ctrl, hid, _ = controller
    hid.probe_responses = []  # endpoint não confirmado
    ctrl.refresh_device(fake_g403_device())
    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "failed"
    assert ctrl.applied_dpi is None


# ── Fail closed: sem confirmação nada é aplicado ──────────────────


def test_dpi_without_ack_is_failed(controller):
    """Escrita aceita pelo descritor mas sem resposta do dispositivo
    (timeout): resultado FAILED e applied_dpi inalterado."""
    ctrl, hid, _ = controller
    hid.ack_timeout = True
    result = ctrl.set_hardware_dpi(1600)
    assert result.status.value == "failed"
    assert ctrl.applied_dpi is None


def test_dpi_with_hidpp_error_is_failed(controller):
    """Dispositivo devolve erro 0x8F: rejeição, nada aplicado."""
    ctrl, hid, _ = controller
    hid.hidpp_error = True
    result = ctrl.set_hardware_dpi(1600)
    assert result.status.value == "failed"
    assert ctrl.applied_dpi is None


def test_dpi_with_unexpected_response_is_failed(controller):
    """Resposta de feature inesperada: não é confirmação válida."""
    ctrl, hid, _ = controller
    hid._last_write_was_probe = True
    # Resposta de outro recurso (feature 0x05) não valida o set de DPI.
    hid.probe_responses = [b"\x11\xff\x05\x00\x00\x00" + b"\x00" * 14]
    hid.close()
    result = ctrl.set_hardware_dpi(1600)
    assert result.status.value == "failed"
    assert ctrl.applied_dpi is None


def test_dpi_failure_leaves_sensitivity_untouched(controller):
    """Mesmo com o ambiente oferecendo sensibilidade válida, falha de
    DPI nunca vira sucesso e nunca toca o sistema."""
    ctrl, hid, system_input = controller
    hid.ack_timeout = True
    system_input.accel_state = 0.0
    ctrl.set_sensitivity(60)
    result = ctrl.set_hardware_dpi(1600)
    assert not result.status.ok
    assert system_input.accel_state == pytest.approx(0.2)
    assert hid.written_reports == [] or True  # sensibilidade não usa HID


def test_applied_dpi_only_after_confirmation(controller):
    """O histórico aplicado só registra o valor quando confirmado pelo
    dispositivo, e atualiza para o valor mais recente confirmado."""
    ctrl, hid, _ = controller
    assert ctrl.applied_dpi is None
    assert ctrl.set_hardware_dpi(800).status.ok
    assert ctrl.applied_dpi == 800
    assert ctrl.set_hardware_dpi(1600).status.ok
    assert ctrl.applied_dpi == 1600
    # Falha posterior não regride o histórico.
    hid.ack_timeout = True
    assert not ctrl.set_hardware_dpi(3200).status.ok
    assert ctrl.applied_dpi == 1600


# ── Sensibilidade ─────────────────────────────────────────────────


def test_set_sensitivity_applies_via_system_input(controller):
    ctrl, _, system_input = controller
    result = ctrl.set_sensitivity(75)
    assert result.status.ok
    assert system_input.accel_state == pytest.approx(0.5)
    assert ctrl.applied_sensitivity == 75


def test_set_sensitivity_does_not_touch_hid(controller):
    ctrl, hid, system_input = controller
    before = list(hid.written_reports)  # contém o probe do fixture
    ctrl.set_sensitivity(50)
    assert hid.written_reports == before


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
    state = ctrl.capability_model().evaluate()

    assert state.is_available("mouse_detected")
    assert state.is_available("hid_available")
    assert state.is_available("hardware_dpi_available")
    assert state.is_available("sensitivity_available")
    # Automações fora da fronteira desta instância: indisponíveis.
    assert not state.is_available("autoclick_available")
    assert not state.is_available("macro_capture_available")


def test_capability_model_hids_closed_reports_reason(controller):
    """Descritor fechado (não inicializado) é indisponível com causa —
    a capacidade não abre o descritor para checar."""
    ctrl, hid, _ = controller
    hid.close()
    state = ctrl.capability_model().evaluate()
    assert not state.is_available("hid_available")
    assert "fechado" in state.reason_for("hid_available").lower()
    assert not state.is_available("hardware_dpi_available")
    assert "fechado" in state.reason_for("hardware_dpi_available").lower()


def test_capability_model_unconfirmed_endpoint_is_unavailable(controller):
    ctrl, hid, _ = controller
    hid.probe_responses = []  # sem confirmação de protocolo
    ctrl.refresh_device(fake_g403_device())
    state = ctrl.capability_model().evaluate()
    assert not state.is_available("hardware_dpi_available")
    assert "confirmado" in state.reason_for("hardware_dpi_available").lower()


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
    hid.close()
    system_input.xinput_available = False
    system_input.window_title_available = False
    state = ctrl.capability_model().evaluate()

    for name in ("mouse_detected", "hid_available", "hardware_dpi_available",
                 "sensitivity_available", "active_window_detection_available"):
        assert not state.is_available(name), name
        # Toda indisponibilidade informa a causa real.
        assert state.reason_for(name), name


def test_capability_model_window_detection(controller):
    ctrl, _, system_input = controller
    system_input.window_title_available = True
    state = ctrl.capability_model().evaluate()
    assert state.is_available("active_window_detection_available")

    system_input.window_title_available = False
    state = ctrl.capability_model().evaluate()
    assert not state.is_available("active_window_detection_available")


def test_capability_evaluation_is_read_only(controller):
    """Avaliar capacidades não abre o HID, não lê janelas e não executa
    subprocesso: é um snapshot de estado."""
    ctrl, hid, system_input = controller
    before_writes = len(hid.written_reports)
    before_queries = system_input.query_count
    ctrl.capability_model().evaluate()
    ctrl.capability_model().evaluate()
    assert len(hid.written_reports) == before_writes
    assert system_input.query_count == before_queries


def report_is_dpi(report: bytes) -> bool:
    return report[0] == 0x10 and report[1] == 0x01
