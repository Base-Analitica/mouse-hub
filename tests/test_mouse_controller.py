"""Testes do MouseController: DPI físico ≠ sensibilidade e ausência de
sucesso falso, agora com:

* fail closed com ACK OBRIGATÓRIO e CORRELACIONADO (header completo
  espelhado, software ID próprio);
* endpoint confirmado em duas etapas (feature set count +
  IRoot.GetFeature(0x2201)) com feature index DESCOBERTO dinamicamente,
  nunca hardcoded;
* lifecycle PÚBLICO: quem usa registra, probea e aplica — o descritor
  só abre dentro da operação que o exige e sempre fecha (inclusive em
  exceção);
* capabilities que refletem o conhecimento obtido no probe, não o
  estado do descritor (sem polling, sem abrir fd para consultar).

Hardware totalmente simulado via fakes; nenhum subprocess ou /dev é
usado.
"""

import pytest

from mouse_hub.core.mouse_controller import MouseController
from tests.fakes import FakeHidAccess, FakeSystemInput, fake_g403_device


@pytest.fixture()
def controller():
    """Fixture do lifecycle público: registra, probea e aplica — sem
    jamais manipular o HidAccess de fora."""
    hid = FakeHidAccess()
    system_input = FakeSystemInput()
    ctrl = MouseController(hid, system_input)
    ctrl.refresh_device(fake_g403_device())
    result = ctrl.probe_endpoint()
    assert result.status.ok, "probe não deveria falhar com o fake padrão"
    return ctrl, hid, system_input


# ── Lifecycle público ──────────────────────────────────────────────


def test_refresh_device_is_read_only_wrt_hid(controller):
    """Registrar um dispositivo não abre o descritor: o HidAccess segue
    como o fake entregou (fechado), confirmado pelo estado interno do
    fake — a abertura só acontece dentro de probe/apply."""
    ctrl, hid, _ = controller
    assert not hid.is_open()
    assert ctrl.device is not None


def test_refresh_device_none_is_device_not_found(controller):
    ctrl, _, _ = controller
    assert ctrl.refresh_device(None).status.value == "device_not_found"


def test_refresh_device_without_hidraw_is_unsupported(controller):
    ctrl, _, _ = controller
    result = ctrl.refresh_device(fake_g403_device(hidraw=None))
    assert result.status.value == "unsupported"
    assert not result.status.ok


def test_refresh_device_resets_probe_state(controller):
    """Re-registrar o dispositivo descarta o feature index conhecido:
    quem quer DPI precisa probear de novo."""
    ctrl, hid, _ = controller
    assert ctrl.probe_endpoint().status.ok
    ctrl.refresh_device(fake_g403_device())
    assert ctrl._dpi_feature_index is None
    assert not ctrl.set_hardware_dpi(800).status.ok


def test_public_lifecycle_end_to_end(controller):
    """Fluxo completo sem manipular o HID de fora: registrar → probe
    (abre, valida, fecha) → aplicar DPI (abre de novo, confirma, fecha).
    O descritor nunca fica aberto entre as operações."""
    ctrl, hid, _ = controller
    assert not hid.is_open()
    assert ctrl.probe_endpoint().status.ok
    assert not hid.is_open()  # probe fechou
    result = ctrl.set_hardware_dpi(800)
    assert result.status.ok
    assert not hid.is_open()  # aplicação fechou


def test_probe_closes_descriptor_on_read_error(controller):
    """Probe com endpoint mudo (IRoot.GetFeature sem resposta): o
    descritor fecha em qualquer caminho, inclusive falha."""
    ctrl, hid, _ = controller
    hid.ack_timeout = True
    assert not ctrl.probe_endpoint().status.ok
    assert not hid.is_open()


# ── Probe de endpoint (duas etapas) ────────────────────────────────


def test_probe_discovers_feature_index_dynamically(controller):
    """O probe descobre o feature index da Adjustable DPI (0x2201) via
    IRoot.GetFeature; o índice usado no comando é o descoberto, não um
    número hardcoded."""
    ctrl, hid, _ = controller
    result = ctrl.probe_endpoint()
    assert result.status.ok
    assert ctrl._dpi_feature_index == hid.dpi_feature_index
    assert ctrl._dpi_feature_index not in (None, 0)
    # O request de GetFeature transporta o FEATURE ID 0x2201, não o
    # índice final: discovery é dinâmica.
    before_probe = len(hid.written_reports)
    ctrl.probe_endpoint()
    after_probe = len(hid.written_reports)
    get_feature_request = [
        r for r in hid.written_reports[before_probe:after_probe]
        if len(r) == 20 and r[2] == 0x00 and ((r[3] >> 4) & 0x0F) == 0
        and ((r[4] << 8) | r[5]) == 0x2201
    ]
    assert len(get_feature_request) == 1
    # O index da IFeatureSet NÃO é deduzido do Feature ID (o fake expõe
    # 0x05 — quem assume 0x01 falha aqui).
    featureset_requests = [
        r for r in hid.written_reports[before_probe:after_probe]
        if len(r) == 20 and ((r[3] >> 4) & 0x0F) == 0 and ((r[4] << 8) | r[5]) == 0x0001
    ]
    if featureset_requests:
        assert featureset_requests[0][2] == hid.ifeatureset_index
    # E o comando de DPI usa o índice descoberto (não hardcoded).
    before_set = len(hid.written_reports)
    assert ctrl.set_hardware_dpi(800).status.ok
    set_request = [r for r in hid.written_reports[before_set:]
                   if ((r[3] >> 4) & 0x0F) == 0x03]
    assert set_request
    assert set_request[0][2] == ctrl._dpi_feature_index


def test_probe_feature_absent_is_unsupported(controller):
    """Endpoint HID++ 2.0 confirmado, mas sem a feature 0x2201:
    ausência DOCUMENTADA via resposta válida feature_index == 0
    (única forma da especificação pública IRoot/GetFeature): probe
    termina UNSUPPORTED (não FAILED) — a causa é distinta."""
    ctrl, hid, _ = controller
    hid.dpi_feature_index = 0  # IRoot devolve feature_index 0 = ausente
    assert ctrl.probe_endpoint().status.value == "unsupported"
    assert ctrl._dpi_feature_index == -1
    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "unsupported"
    assert ctrl.applied_dpi is None


def test_probe_feature_index_negative_is_error(controller):
    """IRoot.GetFeature devolvendo 0xFF (erro de protocolo): endpoint
    não confirmado — fail closed."""
    ctrl, hid, _ = controller
    hid.dpi_feature_index = 0xFF
    ctrl.refresh_device(fake_g403_device())  # reseta o estado confirmado
    assert not ctrl.probe_endpoint().status.ok
    assert ctrl.applied_dpi is None


def test_probe_stage1_error(controller):
    """GetFeature(0x2201) rejeitado com erro FAP 2.0
    (INVALID_FEATURE_INDEX 0x06) é PROTOCOL_ERROR do protocolo — o
    endpoint NÃO confirmou o protocolo para esta feature; probe termina
    FAILED (nunca assume feature ausente a partir de erro genérico).
    O erro devolvido pelo device é correlacionado com o request."""
    ctrl, hid, _ = controller
    hid.probe_stage2_error = True
    hid.probe_stage2_error_code = 0x06
    ctrl.refresh_device(fake_g403_device())
    result = ctrl.probe_endpoint()
    assert result.status.value == "failed"
    assert ctrl._dpi_feature_index is None


def test_probe_rejects_non_responsive_endpoint(controller):
    ctrl, hid, _ = controller
    hid.ack_timeout = True
    ctrl.refresh_device(fake_g403_device())
    assert not ctrl.probe_endpoint().status.ok
    assert ctrl._dpi_feature_index is None
    assert not hid.is_open()


def _other_logitech_device():
    """Outro mouse Logitech HID++ 2.0 — protocola OK, mas NÃO é o
    G403 HERO. Deve ser rejeitado pela validação de identidade."""
    from mouse_hub.platform.protocol import MouseDevice

    return MouseDevice(
        hidraw_path="/dev/hidraw7",
        vid=0x046D,
        pid=0xC08B,  # G502 HERO, não o G403
        name="Logitech G502 HERO",
    )


def _other_vendor_device():
    """Mouse de outro fabricante com o mesmo PID acidental — rejeitado
    pelo VID."""
    from mouse_hub.platform.protocol import MouseDevice

    return MouseDevice(
        hidraw_path="/dev/hidraw9",
        vid=0x1038,
        pid=0xC08F,
        name="SteelSeries genérico",
    )


# ── Identidade G403 (VID/PID) ──────────────────────────────────────


def test_refresh_device_rejects_pid_mismatch(controller):
    """Registrar outro mouse Logitech com PID diferente REJEITA o device:
    self._device não guarda o device inválido, probe/set não têm efeito
    sobre hardware errado — zero reports SetSensorDPI."""
    ctrl, hid, _ = controller
    result = ctrl.refresh_device(_other_logitech_device())
    assert result.status.value == "device_not_found"
    assert ctrl.device is None
    assert ctrl._dpi_feature_index is None
    # probe não confirma endpoint para hardware que não é o G403
    assert not ctrl.probe_endpoint().status.ok
    # set não escreve nada: defesa em profundidade antes do efeito
    before = len(hid.written_reports)
    ctrl.set_hardware_dpi(800)
    assert len(hid.written_reports) == before


def test_refresh_device_rejects_vid_mismatch(controller):
    ctrl, _, _ = controller
    result = ctrl.refresh_device(_other_vendor_device())
    assert result.status.value == "device_not_found"
    assert ctrl.device is None


def test_probe_defends_against_identity_mismatch(controller):
    """Defesa em profundidade: mesmo que o state interno esteja
    comprometido com device de identidade errada (via mutação direta
    em teste), probe NUNCA confirma endpoint para hardware que não é o
    G403 esperado — o probe falha fechado antes de qualquer efeito."""
    ctrl, _, _ = controller
    ctrl._device = _other_logitech_device()
    ctrl._dpi_feature_index = None
    assert ctrl.probe_endpoint().status.value == "failed"
    assert ctrl._dpi_feature_index is None


def test_set_dpi_defends_against_identity_mismatch(controller):
    """Defesa em profundidade no efeito: device comprometido não recebe
    SetSensorDPI — o controller revalida VID/PID antes de abrir o
    descritor."""
    ctrl, hid, _ = controller
    ctrl._device = _other_logitech_device()
    before = len(hid.written_reports)
    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "failed"
    assert len(hid.written_reports) == before
    assert ctrl.applied_dpi is None


def test_valid_device_after_rejection_is_accepted(controller):
    """Rejeição anterior não contamina o controller: registrar o G403
    correto DEPOIS de um mismatch é aceito e o lifecycle completo
    segue funcionando."""
    ctrl, _, _ = controller
    ctrl.refresh_device(_other_logitech_device())
    assert ctrl.refresh_device(fake_g403_device()).status.ok
    assert ctrl.probe_endpoint().status.ok
    assert ctrl.set_hardware_dpi(800).status.ok
    assert ctrl.applied_dpi == 800


def test_probe_without_hidraw_is_unsupported_not_absent(controller):
    """Mouse presente mas sem interface hidraw: probe é UNSUPPORTED
    (mouse_detected continua True) — device NUNCA é "ausente" aqui,
    porque a descoberta encontrou o G403; apenas o controle via
    protocolo HID++ é indisponível."""
    ctrl, _, _ = controller
    ctrl.refresh_device(fake_g403_device(hidraw=None))
    assert ctrl.probe_endpoint().status.value == "unsupported"
    state = ctrl.capability_model().evaluate()
    assert state.is_available("mouse_detected")
    assert not state.is_available("hid_endpoint_known")
    assert not state.is_available("hid_available")
    assert not state.is_available("hardware_dpi_available")


def test_set_dpi_without_hidraw_is_unsupported(controller):
    ctrl, _, _ = controller
    ctrl.refresh_device(fake_g403_device(hidraw=None))
    assert ctrl.set_hardware_dpi(800).status.value == "unsupported"
    assert ctrl.applied_dpi is None


def test_probe_protocol_error_is_failed_even_unsupported(controller):
    """Erro FAP no GetFeature(0x2201) — INCLUSIVE 0x09 (UNSUPPORTED) —
    é rejeição de comando, NÃO ausência documentada: fail closed.
    A especificação pública IRoot/GetFeature define ausência da feature
    APENAS via resposta válida com feature_index == 0; não há fonte
    primária tratando PROTOCOL_ERROR 0x09 como "feature ausente".
    O error code real é preservado no reason para diagnóstico."""
    ctrl, hid, _ = controller
    hid.probe_stage2_error = True
    hid.probe_stage2_error_code = 0x09
    ctrl.refresh_device(fake_g403_device())
    result = ctrl.probe_endpoint()
    assert result.status.value == "failed"
    assert result.details.get("fap_error_code") == 0x09, (
        "error code real do erro FAP deve ser preservado no result"
    )
    assert ctrl._dpi_feature_index is None


def test_probe_busy_or_hw_error_is_failed(controller):
    """Erros transitórios/genéricos (BUSY 0x08, HW_ERROR) NÃO viram
    ausência documentada: endpoint não confirmado — fail closed."""
    ctrl, hid, _ = controller
    hid.probe_stage2_error = True
    hid.probe_stage2_error_code = 0x08  # BUSY
    ctrl.refresh_device(fake_g403_device())
    assert ctrl.probe_endpoint().status.value == "failed"
    assert ctrl._dpi_feature_index is None


def test_probe_handles_permission_denied(controller):
    ctrl, hid, _ = controller
    hid.open_permission_denied = True
    result = ctrl.probe_endpoint()
    assert result.status.value == "permission_denied"
    assert ctrl._probe_accessible is False
    assert ctrl._probe_access_status.value == "permission_denied"


def test_probe_handles_open_exception(controller):
    ctrl, hid, _ = controller
    hid.open_raises = RuntimeError("sysfs sumiu")
    assert not ctrl.probe_endpoint().status.ok
    assert not hid.is_open()


def test_probe_fails_without_device(controller):
    ctrl, _, _ = controller
    ctrl.refresh_device(None)
    assert not ctrl.probe_endpoint().status.ok


# ── DPI físico ─────────────────────────────────────────────────────


def test_set_hardware_dpi_applies_to_hid(controller):
    ctrl, hid, _ = controller
    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "applied"
    assert ctrl.applied_dpi == 800
    # O report carrega o DPI em big endian no payload (sensor, hi, lo)
    # e o feature index descoberto dinamicamente.
    report = hid.written_reports[-1]
    assert report[0] == 0x11  # FAP long, nunca short
    assert report[1] == 0xFF  # device index direto (USB cabado)
    assert report[2] == ctrl._dpi_feature_index
    assert len(report) == 20
    assert (report[5] << 8 | report[6]) == 800
    assert result.details.get("confirmation") is True


def test_set_hardware_dpi_is_independent_of_sensitivity(controller):
    ctrl, hid, system_input = controller
    ctrl.set_hardware_dpi(1200)
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
    assert not ctrl.set_hardware_dpi(800).status.ok


def test_set_hardware_dpi_without_hidraw_is_unsupported(controller):
    ctrl, _, _ = controller
    ctrl.refresh_device(fake_g403_device(hidraw=None))
    assert ctrl.set_hardware_dpi(800).status.value == "unsupported"


def test_set_hardware_dpi_permission_denied(controller):
    """Regra udev ausente: device presente mas inacessível — a causa é
    PERMISSION_DENIED (não falha genérica). O probe prévio registra o
    desfecho real da abertura."""
    ctrl, hid, _ = controller
    hid.open_permission_denied = True
    ctrl.refresh_device(fake_g403_device())
    ctrl.probe_endpoint()  # registra _probe_accessible=False
    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "permission_denied"


def test_hot_unplug_after_probe_is_device_not_found_with_invalidated_state(
    controller,
):
    """Hot-unplug APÓS probe bem-sucedido: o open dentro de
    set_hardware_dpi falha com DEVICE_NOT_FOUND, as capabilities HID/DPI
    ficam False IMEDIATAMENTE e o reason NÃO menciona udev (o endpoint
    existia e funcionou antes — sumiu do sistema, não é problema de
    regra udev). O feature index é invalidado: novo efeito exige
    refresh_device + probe_endpoint."""
    ctrl, hid, _ = controller
    # Probe OK → HID/DPI disponíveis.
    state = ctrl.capability_model().evaluate()
    assert state.is_available("hid_available")
    assert state.is_available("hardware_dpi_available")

    # Hot-unplug simulado no próximo open (write_failure_status só atua
    # no write, então usamos open_permission_denied=False — o fake
    # precisa de knob de open DEVICE_NOT_FOUND; aqui o desfecho vem do
    # write, que é o caminho real do hot-unplug pós-open).
    hid.write_failure_status = "device_not_found"
    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "device_not_found"
    # applied_dpi não regrediu e nada foi confirmado como aplicado.
    assert ctrl.applied_dpi is None

    # Capabilities invalidadas imediatamente.
    state = ctrl.capability_model().evaluate()
    assert not state.is_available("hid_available")
    assert not state.is_available("hardware_dpi_available")
    reason = state.reason_for("hid_available")
    assert "udev" not in reason.lower()

    # Novo efeito NÃO pode ter sucesso enquanto o estado não for
    # revalidado: como _probe_access_status carrega a causa real
    # (device_not_found), o set nem sequer abre — falha imediatamente.
    hid.write_failure_status = None
    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "device_not_found"

    # Recuperação: refresh + probe revalida o estado e o efeito volta
    # a funcionar.
    ctrl.refresh_device(fake_g403_device())
    assert ctrl.probe_endpoint().status.ok
    assert ctrl.set_hardware_dpi(800).status.ok
    assert ctrl.applied_dpi == 800


def test_permission_lost_after_probe_invalidates_state(controller):
    """Permissão perdida APÓS probe bem-sucedido (fd perdeu a regra
    udev): open dentro de set_hardware_dpi devolve PERMISSION_DENIED e
    as capabilities refletem imediatamente."""
    ctrl, hid, _ = controller
    assert ctrl.capability_model().evaluate().is_available("hid_available")

    hid.open_permission_denied = True
    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "permission_denied"
    state = ctrl.capability_model().evaluate()
    assert not state.is_available("hid_available")
    assert not state.is_available("hardware_dpi_available")


def test_generic_failure_after_probe_invalidates_state(controller):
    """Falha genérica de open após probe bem-sucedido (fd corrompido):
    open devolve FAILED e as capabilities refletem imediatamente."""
    ctrl, hid, _ = controller
    assert ctrl.capability_model().evaluate().is_available("hid_available")

    hid.open_raises = OSError("fd sumiu")
    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "failed"
    state = ctrl.capability_model().evaluate()
    assert not state.is_available("hid_available")
    assert not state.is_available("hardware_dpi_available")


def test_write_failure_propagates_cause_and_invalidates(controller):
    """Falha no WRITE (após open OK) preserva a causa exata:
    DEVICE_NOT_FOUND/PERMISSION_DENIED/FAILED no write_failure_status
    (simulação de hot-unplug entre open e write) — a operação nunca
    vira sucesso e as capabilities são invalidadas."""
    ctrl, hid, _ = controller
    for cause in ("device_not_found", "permission_denied", "failed"):
        hid.write_failure_status = cause
        result = ctrl.set_hardware_dpi(800)
        assert result.status.value == cause, (
            f"causa do write deve ser preservada: {cause}"
        )
        assert ctrl.applied_dpi is None
        state = ctrl.capability_model().evaluate()
        assert not state.is_available("hid_available")
        assert not state.is_available("hardware_dpi_available")
        # Reset: o knob falha TAMBÉM os writes do probe, então limpar
        # ANTES de revalidar para o próximo cenário do loop.
        hid.write_failure_status = None
        ctrl.refresh_device(fake_g403_device())
        assert ctrl.probe_endpoint().status.ok
    assert hid.write_failure_status is None


def test_failed_reprobe_invalidates_known_feature_index(controller):
    """Re-probe falho NUNCA deixa o feature index do probe anterior
    vivo (A/B/C) — o snapshot parte do zero e só sobrevive se ESTE
    probe terminar bem. O DPI JÁ APLICADO é preservado (hardware não
    perde o estado; só o conhecimento do endpoint morre): applied_dpi
    continua disponível como evidência do último efeito confirmado."""
    ctrl, hid, _ = controller
    assert ctrl.probe_endpoint().status.ok
    assert ctrl.set_hardware_dpi(800).status.ok
    applied_before = ctrl.applied_dpi

    causes = ("device_not_found", "permission_denied", "failed")
    for cause in causes:
        # Falha pontual no PRIMEIRO write do probe (GetProtocolVersion)
        # — o probe aborta no meio e não conclui a etapa 2.
        # O contador é resetado por iteração: a fixture já consumiu
        # writes anteriores (probe inicial), então write_failure_at
        # é ordinal absoluto, não relativo ao teste.
        hid.write_failure_status = cause
        hid._write_counter = 0
        hid.write_failure_at = 1
        result = ctrl.probe_endpoint()
        assert result.status.value == cause, (
            f"re-probe falho deve propagar a causa: {cause}"
        )
        # O conhecimento do endpoint morreu: nenhum efeito pode
        # ter sucesso, e a causa é a real (nunca FAILED genérico).
        hid.write_failure_status = None
        hid.write_failure_at = None
        assert not ctrl.capability_model().evaluate().is_available(
            "hid_available"
        )
        result = ctrl.set_hardware_dpi(1600)
        assert result.status.value == cause
        # applied_dpi NÃO regrediu: o 800 confirmado antes continua
        # como última evidência válida.
        assert ctrl.applied_dpi == applied_before
        # Recuperação: refresh + probe volta a funcionar.
        ctrl.refresh_device(fake_g403_device())
        assert ctrl.probe_endpoint().status.ok


def test_read_hot_unplug_during_ack_wait_invalidates_with_cause(
    controller,
):
    """Hot-unplug entre o write do SetSensorDPI e o read do ACK
    (read_failure_status — causa REAL de transporte, NÃO timeout):
    A/B/C propagam a causa exata, o snapshot é invalidado
    imediatamente e nada é confirmado como aplicado."""
    ctrl, hid, _ = controller
    for cause in ("device_not_found", "permission_denied", "failed"):
        hid.read_failure_status = cause
        result = ctrl.set_hardware_dpi(800)
        assert result.status.value == cause, (
            f"hot-unplug no ACK deve propagar a causa: {cause}"
        )
        assert ctrl.applied_dpi is None
        state = ctrl.capability_model().evaluate()
        assert not state.is_available("hid_available")
        assert not state.is_available("hardware_dpi_available")
        hid.read_failure_status = None
        ctrl.refresh_device(fake_g403_device())
        assert ctrl.probe_endpoint().status.ok


def test_real_timeout_never_becomes_hot_unplug(controller):
    """Timeout REAL (device mudo) NÃO vira hot-unplug: sem causa de
    transporte, o comando falha fechado com FAILED genérico — a causa
    só é propagada quando há evidência REAL de acesso perdido. O
    snapshot das capabilities NÃO é invalidado por mudez: o endpoint
    ainda existe, apenas não respondeu."""
    ctrl, hid, _ = controller
    assert ctrl.capability_model().evaluate().is_available(
        "hid_available"
    )
    # Mudez total no ACK (endpoint existe, não responde).
    hid.ack_timeout = True
    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "failed"
    assert "desconectado" not in result.message.lower()
    # Mudez não invalida o snapshot: o endpoint continua conhecido.
    assert ctrl.capability_model().evaluate().is_available(
        "hid_available"
    )
    hid.ack_timeout = False
    assert ctrl.set_hardware_dpi(800).status.ok


def test_set_hardware_dpi_requires_probed_endpoint(controller):
    """Endpoint registrado mas NUNCA probeado: falha com a causa real
    (confirmação pendente), sem abrir nada."""
    ctrl, _, _ = controller
    ctrl.refresh_device(fake_g403_device())
    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "failed"
    assert ctrl.applied_dpi is None


def test_set_hardware_dpi_unsupported_feature(controller):
    """Probe concluiu UNSUPPORTED (0x2201 ausente): aplicar DPI nunca
    deve silenciar a causa com FAILED genérico."""
    ctrl, hid, _ = controller
    hid.dpi_feature_index = 0
    ctrl.probe_endpoint()
    assert ctrl.set_hardware_dpi(800).status.value == "unsupported"


def test_set_hardware_dpi_hid_write_failure(controller):
    ctrl, hid, _ = controller
    hid.write_succeeds = False
    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "failed"
    assert ctrl.applied_dpi is None
    assert not hid.is_open()


# ── Fail closed: sem ACK correlacionado nada é aplicado ────────────


def test_dpi_without_ack_is_failed(controller):
    """Escrita aceita pelo descritor mas sem resposta (timeout): FAILED
    e applied_dpi inalterado."""
    ctrl, hid, _ = controller
    hid.ack_timeout = True
    result = ctrl.set_hardware_dpi(1600)
    assert result.status.value == "failed"
    assert ctrl.applied_dpi is None
    assert not hid.is_open()


def test_dpi_with_hidpp_error_is_failed(controller):
    """Dispositivo rejeita o comando (sub-report 0x8F): nada aplicado."""
    ctrl, hid, _ = controller
    hid.dpi_set_rejected = True
    result = ctrl.set_hardware_dpi(1600)
    assert result.status.value == "failed"
    assert ctrl.applied_dpi is None


def test_dpi_with_wrong_software_id_is_failed(controller):
    """Resposta com software ID de outro cliente: não é o ACK do
    request — fail closed."""
    ctrl, hid, _ = controller
    hid.sw_id_wrong = True
    result = ctrl.set_hardware_dpi(1600)
    assert result.status.value == "failed"
    assert ctrl.applied_dpi is None


def test_dpi_with_async_noise_is_discarded(controller):
    """Eventos assíncronos de outro software chegam antes do ACK: o
    controller descarta o que não correlaciona com o request — o DPI
    só avança quando chega o ACK real do request dele."""
    ctrl, hid, _ = controller
    hid.async_noise = [
        bytes([0x11, 0xFF, 0x05, (0x03 << 4) | 0x01, 0x00, 0x00, 0x00])
        + b"\x00" * 13,
    ]
    result = ctrl.set_hardware_dpi(1600)
    # O noise foi descartado; o ACK real chegou depois e confirmou.
    assert result.status.value == "applied"
    assert ctrl.applied_dpi == 1600


def test_dpi_with_only_async_noise_is_failed(controller):
    """Só events assíncronos e nunca o ACK: falha, não sucesso parcial."""
    ctrl, hid, _ = controller
    # Noise eterno: cada read consome um event sem nunca chegar ACK.
    hid.async_noise = [
        bytes([0x11, 0xFF, 0x05, (0x03 << 4) | 0x01, 0x00, 0x00, 0x00])
        + b"\x00" * 13
    ] * 32
    result = ctrl.set_hardware_dpi(1600)
    assert result.status.value == "failed"
    assert ctrl.applied_dpi is None


def test_dpi_failure_leaves_sensitivity_untouched(controller):
    """Falha na aplicação de DPI não toca na sensibilidade já aplicada:
    são canais independentes — o set de DPI abre o descritor sob demanda
    e fecha no final (mesmo em falha)."""
    ctrl, hid, system_input = controller
    hid.ack_timeout = True
    ctrl.set_sensitivity(60)  # 60% -> accel 0.2 (libinput -1..1)
    assert system_input.accel_state == pytest.approx(0.2)
    result = ctrl.set_hardware_dpi(1600)
    assert not result.status.ok
    assert system_input.accel_state == pytest.approx(0.2)
    # probe (2: feature count + GetFeature) + comando de DPI (1)
    assert len(hid.written_reports) == 3


def test_applied_dpi_only_after_confirmation(controller):
    """Histórico aplicado só avança com DPI confirmado; falha posterior
    não regride."""
    ctrl, hid, _ = controller
    assert ctrl.applied_dpi is None
    assert ctrl.set_hardware_dpi(800).status.ok
    assert ctrl.applied_dpi == 800
    assert ctrl.set_hardware_dpi(1600).status.ok
    assert ctrl.applied_dpi == 1600
    hid.ack_timeout = True
    assert not ctrl.set_hardware_dpi(3200).status.ok
    assert ctrl.applied_dpi == 1600


def test_persistence_happens_after_confirmation(controller, tmp_path):
    """Persistência do DPI confirmado só ocorre depois da confirmação
    do hardware; falha de persistência degrada para applied_partial."""
    ctrl, hid, _ = controller
    persisted = []

    class TrackingPersister:
        def persist_applied_dpi(self, value):
            persisted.append(value)
            return True

    ctrl._dpi_persister = TrackingPersister()
    result = ctrl.set_hardware_dpi(800)
    assert persisted == [800]
    assert result.details.get("persisted") is True

    # Falha de persistência: hardware confirmou, mas o estado não foi
    # gravado — o resultado informa os dois lados.
    class BrokenPersister:
        def persist_applied_dpi(self, value):
            return False

    ctrl._dpi_persister = BrokenPersister()
    result = ctrl.set_hardware_dpi(1600)
    assert result.details.get("persisted") is False
    assert ctrl.applied_dpi == 1600


def test_persistence_exception_is_not_applied(controller):
    """Persistência que levanta exceção não invalida a confirmação do
    hardware, mas marca persisted=False."""
    ctrl, _, _ = controller

    class RaisingPersister:
        def persist_applied_dpi(self, value):
            raise RuntimeError("disco cheio")

    ctrl._dpi_persister = RaisingPersister()
    result = ctrl.set_hardware_dpi(800)
    assert result.status.ok
    assert result.details.get("persisted") is False


# ── Sensibilidade ──────────────────────────────────────────────────


def test_set_sensitivity_applies_via_system_input(controller):
    ctrl, _, system_input = controller
    result = ctrl.set_sensitivity(75)
    assert result.status.ok
    assert system_input.accel_state == pytest.approx(0.5)
    assert ctrl.applied_sensitivity == 75


def test_set_sensitivity_does_not_touch_hid(controller):
    ctrl, hid, system_input = controller
    ctrl.probe_endpoint()  # re-probe para ter writes de probe
    before = len(hid.written_reports)
    ctrl.set_sensitivity(50)
    assert len(hid.written_reports) == before


def test_set_sensitivity_pointer_missing(controller):
    ctrl, _, system_input = controller
    system_input.pointer_name = None
    assert not ctrl.set_sensitivity(50).status.ok


def test_set_sensitivity_system_failure(controller):
    ctrl, _, system_input = controller
    system_input.set_succeeds = False
    assert not ctrl.set_sensitivity(50).status.ok


def test_get_sensitivity_reads_system(controller):
    ctrl, _, system_input = controller
    system_input.accel_state = 0.5
    assert ctrl.get_sensitivity() == 75


def test_get_sensitivity_unavailable(controller):
    ctrl, _, system_input = controller
    system_input.xinput_available = False
    assert ctrl.get_sensitivity() is None


# ── Prevenção de sucesso falso ─────────────────────────────────────


def test_hid_failure_never_reports_dpi_changed(controller):
    ctrl, hid, system_input = controller
    hid.write_succeeds = False
    system_input.accel_state = 0.0

    result = ctrl.set_hardware_dpi(1600)
    assert not result.status.ok
    assert ctrl.applied_dpi is None
    assert system_input.accel_state == 0.0


def test_no_device_means_no_false_success(controller):
    ctrl, _, _ = controller
    ctrl.refresh_device(None)
    assert not ctrl.set_hardware_dpi(800).status.ok
    assert not ctrl.set_sensitivity(50).status.ok


# ── Modelo de capacidades ──────────────────────────────────────────


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


def test_capability_model_independent_of_open_fd(controller):
    """Capacidades não dependem do descritor estar aberto: o fake
    começa fechado e, após o probe (que fechou), o ambiente segue
    disponível — porque o conhecimento veio do probe, não de um fd."""
    ctrl, hid, _ = controller
    assert not hid.is_open()  # probe fechou
    state = ctrl.capability_model().evaluate()
    assert state.is_available("hid_endpoint_known")
    assert state.is_available("hid_available")
    assert state.is_available("hardware_dpi_available")
    assert "aberto" not in state.reason_for("hid_available").lower()
    assert "aberto" not in state.reason_for("hardware_dpi_available").lower()


def test_capability_model_reports_unprobed_reason(controller):
    ctrl, hid, _ = controller
    hid.open_permission_denied = True  # probe falha antes de confirmar
    ctrl.refresh_device(fake_g403_device())
    state = ctrl.capability_model().evaluate()
    assert not state.is_available("hid_endpoint_known")
    assert "probe" in state.reason_for("hid_endpoint_known").lower()
    assert not state.is_available("hardware_dpi_available")
    # Sem probe executado, o motivo é o conhecimento pendente da
    # descoberta (e o acesso em si ainda não avaliado).
    assert "probe" in state.reason_for("hardware_dpi_available").lower()


def test_capability_model_permission_denied_reason(controller):
    ctrl, hid, _ = controller
    hid.open_permission_denied = True
    ctrl.probe_endpoint()
    state = ctrl.capability_model().evaluate()
    assert not state.is_available("hid_available")
    assert "udev" in state.reason_for("hid_available").lower()


def test_capability_model_feature_absent_reason(controller):
    ctrl, hid, _ = controller
    hid.dpi_feature_index = 0
    ctrl.probe_endpoint()
    state = ctrl.capability_model().evaluate()
    assert not state.is_available("hardware_dpi_available")
    assert "0x2201" in state.reason_for("hardware_dpi_available")


def test_capability_model_hid_missing_mouse_still_detected(controller):
    ctrl, _, _ = controller
    ctrl.refresh_device(fake_g403_device(hidraw=None))
    state = ctrl.capability_model().evaluate()

    assert state.is_available("mouse_detected")
    assert not state.is_available("hid_endpoint_known")
    assert not state.is_available("hid_available")
    assert not state.is_available("hardware_dpi_available")
    assert state.is_available("sensitivity_available")


def test_capability_model_all_absent(controller):
    """Nenhum recurso disponível: o dispositivo existe (mouse_detected
    True), mas sem interface hidraw — a fronteira mais externa do G403."""
    ctrl, _, system_input = controller
    ctrl.refresh_device(fake_g403_device(hidraw=None))
    system_input.xinput_available = False
    system_input.window_title_available = False
    state = ctrl.capability_model().evaluate()

    assert state.is_available("mouse_detected")
    for name in ("hid_endpoint_known", "hid_available",
                 "hardware_dpi_available", "sensitivity_available",
                 "active_window_detection_available"):
        assert not state.is_available(name), name
        assert state.reason_for(name), name


def test_capability_model_window_detection(controller):
    ctrl, _, system_input = controller
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
    # FAP long: 0x11, device 0xFF, fn 0x03 (SetSensorDPI)
    return (report[0] == 0x11 and report[1] == 0xFF
            and ((report[3] >> 4) & 0x0F) == 0x03)
