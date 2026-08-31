# -*- coding: utf-8 -*-
"""Issue #95 — controles de DPI físico só com `hardware_dpi_available`.

Estado correto → ação autorizada: quando a capability de DPI físico não
está confirmada, TODA affordance que causaria efeito físico (slider,
valor manual, Aplicar, presets da página e ações rápidas do dashboard)
fica desabilitada/gated, com a causa real exibida. `hid_available` e
`hardware_dpi_available` permanecem estados distintos — o segundo NÃO é
inferido do primeiro.

Matriz coberta (Qt offscreen, fakes de hardware, sem validação física):

* mouse detectado + HID + DPI confirmado  → controles habilitados;
* mouse detectado + HID + DPI NÃO confirmado → desabilitados + causa;
* sem acesso HID                          → desabilitados (regressão
  do comportamento já existente);
* falha real de SetSensorDPI (timeout)    → controles saem da tela
  imediatamente após a falha (invalidação pela operação);
* ações rápidas do dashboard não partem sem capability confirmada.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt5")
from PyQt5.QtWidgets import QApplication  # noqa: E402

import app.mouse_hub_app as app_module  # noqa: E402
from app.mouse_hub_app import DPIPage, MouseController, MouseCoreState  # noqa: E402
from mouse_hub.core.dpi_persistence import NeverDpiPersister  # noqa: E402
from mouse_hub.core.mouse_controller import (  # noqa: E402
    MouseController as CoreMouseController,
)
from tests.fakes import FakeHidAccess, FakeSystemInput, fake_g403_device  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_page(qapp, monkeypatch, hid=None):
    """DPIPage sobre state REAL do app com discovery por fake.

    O caminho de produção (state.refresh com discovery patcheado) é
    usado para que o snapshot de capacidades reflita o probe real."""
    hid = hid if hid is not None else FakeHidAccess()
    core = CoreMouseController(
        hid=hid,
        system_input=FakeSystemInput(),
        dpi_persister=NeverDpiPersister(),
    )
    state = MouseCoreState(core)
    monkeypatch.setattr(
        app_module, "discover_candidates", lambda: [fake_g403_device()]
    )
    state.refresh()
    page = DPIPage(MouseController(), state=state)
    return state, hid, page


def _dpi_controls(page):
    """Toda affordance que causaria efeito físico de DPI."""
    return [
        page.slider,
        page.dpi_input,
        page.apply_btn,
        *[btn for _, _, btn in page.preset_buttons],
    ]


# ── Matriz mouse/HID/DPI ────────────────────────────────────────

def test_dpi_confirmado_habilita_controles(qapp, monkeypatch):
    state, hid, page = _make_page(qapp, monkeypatch)
    caps = state.capability_state()
    assert caps.is_available("hid_available")
    assert caps.is_available("hardware_dpi_available")
    for w in _dpi_controls(page):
        assert w.isEnabled(), f"controle habilitado esperado: {w}"


def test_hid_sem_dpi_desabilita_todos_os_controles_com_causa(
    qapp, monkeypatch
):
    """hid_available=True + hardware_dpi_available=False: a UI NÃO
    autoriza efeito físico — e a causa real aparece no indicador."""
    hid = FakeHidAccess()
    # HID++ 2.0 legado confirmado (major 0x02), feature 0x2201 ausente:
    # transporte acessível, DPI não confirmado.
    hid.protocol_major = 0x02
    hid.dpi_feature_index = 0
    state, hid, page = _make_page(qapp, monkeypatch, hid=hid)
    caps = state.capability_state()
    assert caps.is_available("hid_available")
    assert not caps.is_available("hardware_dpi_available")

    for w in _dpi_controls(page):
        assert not w.isEnabled(), (
            f"controle de DPI habilitado sem capability confirmada: {w}"
        )
    hint = page.hid_hint.text().lower()
    assert "não confirmado" in hint
    assert "adjustable dpi (0x2201) ausente" in hint


def test_sem_acesso_hid_desabilita_controles(qapp, monkeypatch):
    hid = FakeHidAccess()
    hid.open_permission_denied = True
    state, hid, page = _make_page(qapp, monkeypatch, hid=hid)
    caps = state.capability_state()
    assert not caps.is_available("hid_available")
    assert not caps.is_available("hardware_dpi_available")
    for w in _dpi_controls(page):
        assert not w.isEnabled()
    assert "Sem acesso HID" in page.hid_hint.text()


def test_falha_de_set_invalida_capability_e_desabilita_controles(
    qapp, monkeypatch
):
    """Capability viva no build; timeout REAL do SetSensorDPI mata
    hardware_dpi_available e a UI retira a autorização na hora."""
    hid = FakeHidAccess()
    state, hid, page = _make_page(qapp, monkeypatch, hid=hid)
    assert page.apply_btn.isEnabled()

    hid.ack_timeout = True  # timeout APENAS no SetSensorDPI
    page.dpi_input.setText("1200")
    page.apply_btn.click()

    caps = state.capability_state()
    assert not caps.is_available("hardware_dpi_available")
    assert caps.is_available("hid_available")  # estados permanecem distintos
    for w in _dpi_controls(page):
        assert not w.isEnabled(), (
            "controle de DPI permaneceu autorizado após falha real"
        )
    assert "timeout" in page.hid_hint.text().lower()


def test_recuperacao_por_reprobe_reautoriza_controles(qapp, monkeypatch):
    """Após falha, nova evidência (re-probe bem-sucedido) reautoriza os
    controles — a invalidação não é permanente."""
    hid = FakeHidAccess()
    state, hid, page = _make_page(qapp, monkeypatch, hid=hid)
    hid.ack_timeout = True
    page.dpi_input.setText("1200")
    page.apply_btn.click()
    assert not page.apply_btn.isEnabled()

    hid.ack_timeout = False
    page.showEvent(None)  # refresh explícito (mesma via da UI real)
    assert page.apply_btn.isEnabled()
    assert page.slider.isEnabled()


# ── Ações rápidas do Dashboard não partem sem capability ────────

class _FakeWindowService:
    def is_focused(self, patterns):
        class _R:
            focused = False

        return _R()


class _FakeSvc:
    window_service = _FakeWindowService()


class _FakeClicker:
    class _State:
        value = "stopped"

    state = _State()


def _dashboard_with_state(state):
    return app_module.DashboardPage(
        MouseController(), _FakeClicker(), None, _FakeSvc(), state=state
    )


def test_quick_dpi_nao_parte_sem_hardware_dpi(qapp, monkeypatch):
    hid = FakeHidAccess()
    hid.dpi_feature_index = 0  # HID confirmado, DPI não
    core = CoreMouseController(
        hid=hid,
        system_input=FakeSystemInput(),
        dpi_persister=NeverDpiPersister(),
    )
    state = MouseCoreState(core)
    monkeypatch.setattr(
        app_module, "discover_candidates", lambda: [fake_g403_device()]
    )
    state.refresh()
    assert not state.capability_state().is_available("hardware_dpi_available")

    page = _dashboard_with_state(state)
    page.timer.stop()
    before = len(hid.applied_dpi_history)
    page._quick_dpi(1200)
    # Nenhum comando parte da UI sem a capability confirmada.
    assert len(hid.applied_dpi_history) == before
    assert "não aplicado" in page.log.toPlainText().lower()


def test_quick_dpi_funciona_com_capability_confirmada(qapp, monkeypatch):
    hid = FakeHidAccess()
    core = CoreMouseController(
        hid=hid,
        system_input=FakeSystemInput(),
        dpi_persister=NeverDpiPersister(),
    )
    state = MouseCoreState(core)
    monkeypatch.setattr(
        app_module, "discover_candidates", lambda: [fake_g403_device()]
    )
    state.refresh()
    assert state.capability_state().is_available("hardware_dpi_available")

    page = _dashboard_with_state(state)
    page.timer.stop()
    page._quick_dpi(1200)
    assert hid.last_dpi_command() is not None
    assert state.applied_dpi == 1200
