"""Issue #68 — seleção de endpoint entre múltiplos hidraw do G403.

Hardware real observado: o G403 HERO expõe DOIS /dev/hidrawN (interface
de input do mouse e interface vendor HID++). Ambos abrem O_RDWR, mas
apenas a vendor responde ao protocolo — a de input rejeita a escrita
com EPIPE. O bug: descoberta antiga registrava o PRIMEIRO candidato;
DPI físico morria com "falha de acesso ao endpoint" mesmo com
permissões corretas.

Estes testes reproduzem a topologia real de forma determinística:
um fake de transporte onde só UM dos candidatos responde HID++."""

from __future__ import annotations

from typing import Optional

import pytest

from mouse_hub.core.mouse_controller import MouseController
from mouse_hub.core.operation import OperationStatus
from mouse_hub.platform.linux.device_discovery import HydppEndpointSelection
from mouse_hub.platform.protocol import MouseDevice
from tests.fakes import FakeHidAccess, FakeSystemInput, fake_g403_device

VENDOR = "/dev/hidraw-vendor"
INPUT = "/dev/hidraw-input"


class MultiEndpointHid(FakeHidAccess):
    """Dois hidraws com a mesma identidade: só o VENDOR responde.

    A interface de input abre normalmente e rejeita QUALQUER escrita
    com EPIPE (exatamente o observado no hardware real — errno 32)."""

    def __init__(self, vendor_path: str = VENDOR) -> None:
        super().__init__()
        self._vendor_path = vendor_path
        self.epipe_writes: list = []

    def write(self, report: bytes):
        device = getattr(self, "_device", None)
        if device is not None and device.hidraw_path != self._vendor_path:
            self.epipe_writes.append(bytes(report))
            from mouse_hub.core.operation import OperationResult
            return OperationResult.failed(
                "Endpoint rejeitou a escrita (EPIPE): interface não "
                "expõe HID++ (ex.: interface de input do mouse)"
            )
        return super().write(report)


def _candidates(*paths: str):
    return [fake_g403_device(hidraw=p) for p in paths]


# ── HydppEndpointSelection.select ────────────────────────────

def test_select_escolhe_o_vendor_entre_input_e_vendor():
    hid = MultiEndpointHid()
    chosen = HydppEndpointSelection(hid).select(_candidates(INPUT, VENDOR))
    assert chosen is not None and chosen.hidraw_path == VENDOR


def test_select_ordem_inversa_ainda_acha_o_vendor():
    hid = MultiEndpointHid()
    chosen = HydppEndpointSelection(hid).select(_candidates(VENDOR, INPUT))
    assert chosen is not None and chosen.hidraw_path == VENDOR


def test_select_so_com_input_falha_fechado():
    """Cenario de máquina com só a interface de input: nenhum endpoint
    elegível — nada é selecionado, nada é escrito."""
    hid = MultiEndpointHid()
    chosen = HydppEndpointSelection(hid).select(_candidates(INPUT))
    assert chosen is None
    assert hid.epipe_writes, "o probe tentou escrever no input (e falhou)"


def test_select_dois_vendors_ambiguidade_falha_fechado():
    hid1 = MultiEndpointHid(vendor_path="/dev/hidrawA")
    hid2 = MultiEndpointHid(vendor_path="/dev/hidrawB")
    # um único transporte não valida dois vendors; a ambiguidade real
    # surge quando AMBOS validam no MESMO transporte — simulado com o
    # select recebendo dois paths ambos tratados como vendor pelo fake.
    class AmbiguousHid(FakeHidAccess):
        pass  # responde para qualquer device

    chosen = HydppEndpointSelection(AmbiguousHid()).select(
        _candidates("/dev/hidrawA", "/dev/hidrawB")
    )
    assert chosen is None


# ── Controller: select_endpoint + guard de ambiguidade ───────

def _controller(hid) -> MouseController:
    return MouseController(hid=hid, system_input=FakeSystemInput())


def test_controller_select_endpoint_registra_o_valido():
    hid = MultiEndpointHid()
    ctrl = _controller(hid)
    chosen = ctrl.select_endpoint(_candidates(INPUT, VENDOR))
    assert chosen is not None and chosen.hidraw_path == VENDOR
    assert not ctrl._selection_ambiguous
    # registro explícito (mesmo fluxo do MouseState.refresh) e probe:
    ctrl.refresh_device(chosen)
    result = ctrl.probe_endpoint()
    assert result.status == OperationStatus.APPLIED
    assert ctrl.capability_model().evaluate().capabilities["hardware_dpi_available"].available


def test_controller_probe_bloqueado_em_selecao_ambigua():
    hid = FakeHidAccess()
    ctrl = _controller(hid)
    # dois candidatos validam no mesmo transporte → ambíguo
    chosen = ctrl.select_endpoint(_candidates("/dev/hidrawA", "/dev/hidrawB"))
    assert chosen is None
    assert ctrl._selection_ambiguous

    ctrl.refresh_device(fake_g403_device(hidraw="/dev/hidrawA"))
    result = ctrl.probe_endpoint()
    assert result.status == OperationStatus.FAILED
    assert "ambígua" in result.message
    # nada confirmado: feature index continua desconhecido
    assert ctrl._dpi_feature_index is None
    caps = ctrl.capability_model().evaluate().capabilities
    assert not caps["hardware_dpi_available"].available
    assert "ambígua" in caps["hardware_dpi_available"].reason

    # novo select com UM candidato limpa a marca (recuperação)
    chosen = ctrl.select_endpoint(_candidates(VENDOR))
    assert chosen is not None
    assert not ctrl._selection_ambiguous
    ctrl.refresh_device(chosen)
    assert ctrl.probe_endpoint().status == OperationStatus.APPLIED


def test_select_endpoint_sem_candidatos_limpa_ambiguidade():
    hid = FakeHidAccess()
    ctrl = _controller(hid)
    ctrl.select_endpoint(_candidates("/dev/hidrawA", "/dev/hidrawB"))
    assert ctrl._selection_ambiguous
    assert ctrl.select_endpoint([]) is None
    assert not ctrl._selection_ambiguous


# ── Mensagem honesta de EPIPE na escrita ─────────────────────

def test_razao_da_capability_menciona_epipe_quando_input_registrado():
    """Se o primeiro candidato (input) for registrado por fallback de
    diagnóstico, a capability explica a causa REAL (EPIPE), não uma
    falha genérica."""
    hid = MultiEndpointHid()
    ctrl = _controller(hid)
    ctrl.refresh_device(fake_g403_device(hidraw=INPUT))
    result = ctrl.probe_endpoint()
    assert result.status == OperationStatus.FAILED
    assert "EPIPE" in result.message
    caps = ctrl.capability_model().evaluate().capabilities
    assert not caps["hid_available"].available
    assert not caps["hardware_dpi_available"].available
    assert "EPIPE" in caps["hid_available"].reason
