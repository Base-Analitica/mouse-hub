# -*- coding: utf-8 -*-
"""Issue #102 — Sensibilidade é estado do SISTEMA, não leitura de hardware.

O hero da página Sensibilidade representa a sensibilidade atual do
ponteiro (leitura via SystemInput/libinput), não um valor aguardado do
hardware do mouse. A leitura inicial vive no core (fonte de domínio):
MouseController.__init__ lê o valor real do sistema; falha de leitura
permanece None (desconhecido honesto), nunca default conveniente.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt5")
from PyQt5.QtWidgets import QApplication, QLabel  # noqa: E402

from mouse_hub.core.mouse_controller import (  # noqa: E402
    MouseController as CoreMouseController,
)
from mouse_hub.core.dpi_persistence import NeverDpiPersister  # noqa: E402
from tests.fakes import FakeHidAccess, FakeSystemInput, fake_g403_device  # noqa: E402

import app.mouse_hub_app as app_module  # noqa: E402
from app.mouse_hub_app import MouseController, SensitivityPage  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _page(si: FakeSystemInput) -> SensitivityPage:
    core = CoreMouseController(
        hid=FakeHidAccess(), system_input=si,
        dpi_persister=NeverDpiPersister(),
    )
    return SensitivityPage(MouseController(), state=app_module.MouseCoreState(core))


def test_hero_shows_system_read_value(qapp):
    """Leitura real do sistema (accel 0.5 -> 75%) aparece no hero."""
    si = FakeSystemInput()
    si.accel_state = 0.5
    page = _page(si)
    assert page.sens_value.text() == "75%"
    # O estado do hero descreve o SISTEMA, não o hardware do mouse.
    assert page.sens_state.text() == "VELOCIDADE DO PONTEIRO NO SISTEMA"


def test_hero_unknown_when_system_read_unavailable(qapp):
    """Sem leitura do sistema: unknown honesto com texto do SISTEMA."""
    si = FakeSystemInput()
    si.xinput_available = False
    page = _page(si)
    assert page.sens_value.text() == UNKNOWN_TEXT
    assert page.sens_state.text() == "valor atual do sistema indisponível"


def test_no_hardware_wait_wording_on_sensitivity_page(qapp):
    """Nenhum texto da página sugere leitura de hardware do mouse."""
    si = FakeSystemInput()
    si.accel_state = 0.25  # 62.5% -> 63%
    page = _page(si)
    for label in page.findChildren(QLabel):
        low = label.text().lower()
        assert "leitura do hardware" not in low, label.text()
        assert "aguardando leitura" not in low, label.text()


def test_dpi_unknown_remains_after_system_read(qapp):
    """A leitura de sensibilidade NÃO confirma DPI físico (domínios
    separados): sem ACK, applied_dpi permanece None."""
    si = FakeSystemInput()
    si.accel_state = 0.5
    core = CoreMouseController(
        hid=FakeHidAccess(), system_input=si,
        dpi_persister=NeverDpiPersister(),
    )
    state = app_module.MouseCoreState(core)
    assert state.applied_dpi is None
    assert state.applied_sensitivity == 75


def test_sensitivity_set_failure_does_not_claim_unconfirmed_value(qapp):
    """Falha real de set: o valor confirmado permanece o último lido/aplicado
    (a UI re-renderiza a partir do estado confirmado; nunca exibe o
    solicitado como aplicado)."""
    si = FakeSystemInput()
    si.accel_state = 0.5
    core = CoreMouseController(
        hid=FakeHidAccess(), system_input=si,
        dpi_persister=NeverDpiPersister(),
    )
    state = app_module.MouseCoreState(core)
    si.set_succeeds = False
    si.verify_after_write = False  # leitura pós-falha: None (honesto)
    result = state.set_sensitivity(30)
    assert not result.status.ok
    # Nada foi confirmado pela operação falha; o estado permanece o
    # último valor REAL do sistema (o lido no startup, 75%), nunca o
    # solicitado (30%).
    assert state.applied_sensitivity == 75


UNKNOWN_TEXT = "\u2014"  # UNKNOWN_VALUE_TEXT


def _discovered():
    return fake_g403_device()
