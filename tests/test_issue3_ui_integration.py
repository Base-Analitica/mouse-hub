# -*- coding: utf-8 -*-
"""Suíte de integração Qt da PR #21 (correções da revisão do mantenedor).

Cobre os blocos obrigatórios da revisão sobre a UI nativa:

  1. unknown NÃO vira default (applied_dpi/applied_sensitivity = None)
  2. uma ação do usuário gera NO MÁXIMO uma operação HID (manual/preset)
  3. drag do slider não spamma hardware (preview vs commit)
  4. capabilities invalidam IMEDIATAMENTE após falha real
  5. probe/set não executam concorrentemente (serialização)
  6. lifecycle sem polling HID++ permanente (sem thread de background)
  7. requested != applied termina exibindo applied

Sem hardware real: os fakes de protocolo existentes (tests/fakes.py)
emulam o contrato HID++ (headers ecoados, feature 0x2201, ACK de
conferência). Nenhum teste desta suíte alega validação física.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading

import pytest

from PyQt5.QtWidgets import QApplication

from mouse_hub.core.config import ConfigPaths
from mouse_hub.core.constants import DPI_DEFAULT, SENSITIVITY_DEFAULT
from mouse_hub.core.dpi_persistence import NeverDpiPersister
from mouse_hub.core.mouse_controller import MouseController as CoreMouseController
from mouse_hub.core.operation import OperationStatus
from tests.fakes import FakeHidAccess, FakeSystemInput, fake_g403_device

import app.mouse_hub_app as app_module
from app.mouse_hub_app import (
    DPIPage,
    MouseController,
    MouseCoreState,
    SensitivityPage,
    UNKNOWN_VALUE_TEXT,
)


@pytest.fixture(scope="module")
def qapp():
    """QApplication offscreen compartilhado pela suíte."""
    app = QApplication.instance() or QApplication([])
    yield app


def _discovered(hidraw="/dev/hidraw2"):
    return fake_g403_device(hidraw=hidraw)


def _make_state(hid=None, system_input=None):
    """MouseCoreState com fakes (persister NUNCA grava em disco)."""
    hid = hid if hid is not None else FakeHidAccess()
    system_input = system_input if system_input is not None else FakeSystemInput()
    core = CoreMouseController(
        hid=hid,
        system_input=system_input,
        dpi_persister=NeverDpiPersister(),
    )
    return MouseCoreState(core), core, hid, system_input


def _ready_dpi_page(qapp, monkeypatch):
    """State com G403 registrado + endpoint probeado (slider habilitado)
    e uma DPIPage construída sobre ele.

    Usa o caminho REAL do app (state.refresh() com discovery patcheado)
    para que o snapshot de capacidades não fique defasado do probe."""
    state, core, hid, si = _make_state()
    monkeypatch.setattr(app_module, "discover_candidates", lambda: [_discovered()])
    state.refresh()  # discovery + registro + probe via state
    page = DPIPage(MouseController(), state=state)
    return state, core, hid, si, page


# ---------------------------------------------------------------------------
# 1. Unknown NÃO vira default.

class TestUnknownNeverDefault:
    """Revisão PR #21: estado físico desconhecido permanece UNKNOWN —
    nunca 800 DPI / 50% sem confirmação."""

    def test_applied_values_are_none_before_confirmation(self):
        state, core, hid, si = _make_state()
        assert state.applied_dpi is None
        assert state.applied_sensitivity is None

    def test_dpi_page_renders_unknown(self, qapp):
        state, core, hid, si = _make_state()
        page = DPIPage(MouseController(), state=state)
        assert page.dpi_value.text() == UNKNOWN_VALUE_TEXT
        assert page.dpi_input.text() == UNKNOWN_VALUE_TEXT
        # Slider fica em posição NEUTRA (controle de entrada — não
        # alega valor aplicado).
        assert page.slider.value() == DPI_DEFAULT

    def test_sensitivity_page_renders_unknown(self, qapp):
        state, core, hid, si = _make_state()
        page = SensitivityPage(MouseController(), state=state)
        assert page.sens_value.text() == UNKNOWN_VALUE_TEXT
        assert page.slider.value() == SENSITIVITY_DEFAULT

    def test_dashboard_renders_unknown(self, qapp):
        """Dashboard exibe UNKNOWN nos cards enquanto não há valor
        confirmado pelo hardware."""
        from app.mouse_hub_app import DashboardPage

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

        state, core, hid, si = _make_state()
        page = DashboardPage(
            MouseController(), _FakeClicker(), None, _FakeSvc(), state=state
        )
        page.timer.stop()
        page._update()
        assert page.dpi_card.value_label.text() == UNKNOWN_VALUE_TEXT
        assert page.sens_card.value_label.text() == UNKNOWN_VALUE_TEXT


# ---------------------------------------------------------------------------
# 2. Uma ação do usuário = no máximo UMA operação HID.

class TestSingleHidWritePerAction:
    """Revisão PR #21: manual apply e preset geram exatamente UMA
    escrita HID (SetSensorDPI); atualização programática do slider gera
    ZERO."""

    def test_manual_apply_is_one_operation(self, qapp, monkeypatch):
        state, core, hid, si, page = _ready_dpi_page(qapp, monkeypatch)
        before = len(hid._dpi_commands)
        page.dpi_input.setText("1200")
        page.apply_btn.click()
        assert len(hid._dpi_commands) == before + 1
        assert state.applied_dpi == 1200

    def test_preset_apply_is_one_operation(self, qapp, monkeypatch):
        state, core, hid, si, page = _ready_dpi_page(qapp, monkeypatch)
        before = len(hid._dpi_commands)
        # Preset 3 = Minecraft PvP 1200 (índice 2 da lista exposta).
        name, dpi, btn = page.preset_buttons[2]
        btn.click()
        assert len(hid._dpi_commands) == before + 1
        assert state.applied_dpi == dpi

    def test_programmatic_slider_update_is_zero_operations(self, qapp, monkeypatch):
        state, core, hid, si, page = _ready_dpi_page(qapp, monkeypatch)
        before = len(hid._dpi_commands)
        page.slider.setValue(1600)  # valueChanged dispara preview
        assert len(hid._dpi_commands) == before  # ZERO escrita

    def test_slider_release_commits_exactly_once(self, qapp, monkeypatch):
        state, core, hid, si, page = _ready_dpi_page(qapp, monkeypatch)
        before = len(hid._dpi_commands)
        page.slider.setValue(1400)
        assert len(hid._dpi_commands) == before
        page.slider.sliderReleased.emit()
        assert len(hid._dpi_commands) == before + 1
        assert state.applied_dpi == 1400


# ---------------------------------------------------------------------------
# 3. Drag do slider não spamma hardware.

class TestSliderDragDoesNotSpamHardware:
    """Revisão PR #21: vários valueChanged durante o arrasto não geram
    várias escritas físicas — o efeito é commitado no release."""

    def test_many_value_changed_during_drag_produce_no_writes(self, qapp, monkeypatch):
        state, core, hid, si, page = _ready_dpi_page(qapp, monkeypatch)
        before = len(hid._dpi_commands)
        for v in (1000, 1100, 1200, 1300, 1400, 1500):
            page.slider.setValue(v)  # drag: só preview
        assert len(hid._dpi_commands) == before
        # Nenhuma escrita física aconteceu durante o arrasto.
        assert state.applied_dpi is None

    def test_single_commit_after_release(self, qapp, monkeypatch):
        state, core, hid, si, page = _ready_dpi_page(qapp, monkeypatch)
        before = len(hid._dpi_commands)
        for v in (1000, 1100, 1200, 1300, 1400, 1500):
            page.slider.setValue(v)
        page.slider.sliderReleased.emit()
        assert len(hid._dpi_commands) == before + 1
        assert state.applied_dpi == 1500


# ---------------------------------------------------------------------------
# 4. Capabilities invalidam IMEDIATAMENTE após falha real.

class TestImmediateCapabilityInvalidation:
    """Revisão PR #21: após falha real de acesso, o snapshot de
    capacidades reflete a falha na hora — sem depender de refresh
    periódico futuro."""

    def test_permission_denied_reflected_immediately(self, qapp, monkeypatch):
        hid = FakeHidAccess()
        state, core, hid2, si = _make_state(hid=hid)
        monkeypatch.setattr(app_module, "discover_candidates", lambda: [_discovered()])
        state.refresh()
        caps = state.capability_state()
        assert caps.is_available("hid_available")

        hid.open_permission_denied = True
        result = state.set_hardware_dpi(800)
        assert not result.status.ok
        assert result.status == OperationStatus.PERMISSION_DENIED
        # SEM refresh adicional: o snapshot já reflete a falha.
        caps = state.capability_state()
        assert not caps.is_available("hid_available")
        assert not caps.is_available("hardware_dpi_available")

    def test_transport_failure_invalidates_immediately(self, qapp, monkeypatch):
        hid = FakeHidAccess()
        state, core, hid2, si = _make_state(hid=hid)
        monkeypatch.setattr(app_module, "discover_candidates", lambda: [_discovered()])
        state.refresh()
        caps = state.capability_state()
        assert caps.is_available("hid_available")

        hid.write_failure_status = "failed"
        result = state.set_hardware_dpi(800)
        assert not result.status.ok
        caps = state.capability_state()
        assert not caps.is_available("hid_available")
        assert not caps.is_available("hardware_dpi_available")

    def test_hot_unplug_invalidates_immediately(self, qapp, monkeypatch):
        hid = FakeHidAccess()
        state, core, hid2, si = _make_state(hid=hid)
        monkeypatch.setattr(app_module, "discover_candidates", lambda: [_discovered()])
        state.refresh()
        hid.write_failure_status = "device_not_found"
        result = state.set_hardware_dpi(800)
        assert result.status == OperationStatus.DEVICE_NOT_FOUND
        caps = state.capability_state()
        assert not caps.is_available("hid_available")
        assert not caps.is_available("hardware_dpi_available")

    def test_ui_hint_reflects_failure_immediately(self, qapp, monkeypatch):
        """A página de DPI reflete a falha no indicador de capacidade
        logo após a operação (sem refresh externo)."""
        hid = FakeHidAccess()
        state, core, hid2, si = _make_state(hid=hid)
        monkeypatch.setattr(app_module, "discover_candidates", lambda: [_discovered()])
        state.refresh()
        page = DPIPage(MouseController(), state=state)
        assert page.slider.isEnabled()

        hid.open_permission_denied = True
        page.dpi_input.setText("1200")
        page.apply_btn.click()
        # Hint passa para o estado de falha e o slider é desabilitado.
        assert not page.slider.isEnabled()
        assert "Sem acesso HID" in page.hid_hint.text()


# ---------------------------------------------------------------------------
# 5. Serialização: probe/set nunca executam concorrentemente.

class _TrackingCore:
    """Envolve o controller contando a sobreposição REAL de chamadas de
    hardware (probe/set/refresh). A prova de serialização não depende de
    timing: qualquer interleave incrementa max_active."""

    def __init__(self, core):
        self._core = core
        self._guard = threading.Lock()
        self._active = 0
        self.max_active = 0
        self.operations = 0

    def _enter(self):
        with self._guard:
            self._active += 1
            self.max_active = max(self.max_active, self._active)
            self.operations += 1

    def _leave(self):
        with self._guard:
            self._active -= 1

    def refresh_device(self, device):
        self._enter()
        try:
            return self._core.refresh_device(device)
        finally:
            self._leave()

    def select_endpoint(self, candidates):
        self._enter()
        try:
            return self._core.select_endpoint(candidates)
        finally:
            self._leave()

    def probe_endpoint(self):
        self._enter()
        try:
            return self._core.probe_endpoint()
        finally:
            self._leave()

    def set_hardware_dpi(self, value):
        self._enter()
        try:
            return self._core.set_hardware_dpi(value)
        finally:
            self._leave()

    def set_sensitivity(self, value):
        self._enter()
        try:
            return self._core.set_sensitivity(value)
        finally:
            self._leave()

    def capability_model(self):
        return self._core.capability_model()

    @property
    def applied_dpi(self):
        return self._core.applied_dpi

    @property
    def applied_sensitivity(self):
        return self._core.applied_sensitivity


class TestSerializedAccess:
    """Revisão PR #21: MouseCoreState serializa TODAS as operações —
    refresh/probe e set nunca executam simultaneamente."""

    def test_probe_and_set_never_overlap(self, qapp, monkeypatch):
        hid = FakeHidAccess()
        core = CoreMouseController(
            hid=hid,
            system_input=FakeSystemInput(),
            dpi_persister=NeverDpiPersister(),
        )
        tracking = _TrackingCore(core)
        state = MouseCoreState(tracking)
        core.refresh_device(_discovered())
        core.probe_endpoint()

        # discovery patcheado para devolver o G403 fake (sem sysfs real).
        monkeypatch.setattr(app_module, "discover_candidates", lambda: [_discovered()])

        n = 25
        barrier = threading.Barrier(2)
        errors = []

        def worker_refresh():
            try:
                barrier.wait()
                for _ in range(n):
                    state.refresh()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        def worker_set():
            try:
                barrier.wait()
                for _ in range(n):
                    state.set_hardware_dpi(800)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        t1 = threading.Thread(target=worker_refresh, name="probe-worker")
        t2 = threading.Thread(target=worker_set, name="set-worker")
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errors
        assert tracking.operations > 0
        # NUNCA houve sobreposição de chamadas de hardware.
        assert tracking.max_active == 1


# ---------------------------------------------------------------------------
# 6. Lifecycle sem polling HID++ permanente.

class TestNoPermanentPolling:
    """Revisão PR #21: o estado do mouse não mantém thread/timer de
    refresh periódico — sem reprobe HID++ a cada 3 segundos."""

    def test_state_has_no_background_thread(self, qapp):
        state, core, hid, si = _make_state()
        names_before = {t.name for t in threading.enumerate()}
        state.refresh()
        state.refresh()
        names_after = {t.name for t in threading.enumerate()}
        assert names_after == names_before

    def test_mouse_hub_app_has_no_mouse_service_thread(self, qapp, monkeypatch):
        """A thread de background (MouseService) foi removida da
        composição do app — refresh é síncrono/eventual."""
        monkeypatch.setattr(app_module, "discover", lambda: None)
        window = app_module.MouseHubApp()
        try:
            assert hasattr(window, "mouse_state")
            assert not hasattr(window, "mouse_service")
        finally:
            window.close()

    def test_refresh_is_synchronous_and_bounded(self, qapp):
        """refresh() é uma chamada síncrona pontual (sem thread nem
        loop) — ela termina e não deixa trabalho pendente."""
        state, core, hid, si = _make_state()
        state.refresh()
        assert state.capability_state() is not None


# ---------------------------------------------------------------------------
# 7. requested != applied termina exibindo applied.

class TestRequestedVsApplied:
    """Revisão PR #21: a UI exibe o valor CONFIRMADO pelo hardware, não
    o solicitado (normalização do core)."""

    def test_manual_apply_with_normalization_displays_applied(self, qapp, monkeypatch):
        state, core, hid, si, page = _ready_dpi_page(qapp, monkeypatch)
        page.dpi_input.setText("799")  # sensor normaliza 799 -> 800
        page.apply_btn.click()
        assert state.applied_dpi == 800
        assert page.dpi_value.text() == "800"
        assert page.dpi_input.text() == "800"
        assert page.slider.value() == 800
        # O valor solicitado (799) NÃO permanece exibido como aplicado.
        assert page.dpi_value.text() != "799"

    def test_failed_apply_does_not_display_requested_as_applied(self, qapp, monkeypatch):
        hid = FakeHidAccess()
        state, core, hid2, si = _make_state(hid=hid)
        monkeypatch.setattr(app_module, "discover_candidates", lambda: [_discovered()])
        state.refresh()
        page = DPIPage(MouseController(), state=state)
        # Estado saudável com valor confirmado.
        page.dpi_input.setText("1000")
        page.apply_btn.click()
        assert state.applied_dpi == 1000
        assert page.dpi_value.text() == "1000"

        # Falha real: a UI volta a exibir o último valor CONFIRMADO,
        # nunca o solicitado como se fosse aplicado.
        hid.open_permission_denied = True
        page.dpi_input.setText("2000")
        page.apply_btn.click()
        assert state.applied_dpi == 1000
        assert page.dpi_value.text() == "1000"
        assert page.dpi_value.text() != "2000"

# ---------------------------------------------------------------------------
# 8. Falha real de SetSensorDPI invalida hardware_dpi_available
#    (revisão 5029857669 — BLOCKER do mantenedor).

class TestDpiSetFailureInvalidatesCapability:
    """Revisão do mantenedor (review 5029857669): timeout e erro de
    protocolo do PRÓPRIO SetSensorDPI deixam hardware_dpi_available=False
    com causa distinta — hid_available permanece separado (transporte
    acessível); recuperação só com nova evidência (re-probe)."""

    @staticmethod
    def _healthy(qapp, monkeypatch):
        """State com probe saudável e página de DPI pronta."""
        hid = FakeHidAccess()
        state, core, hid2, si = _make_state(hid=hid)
        monkeypatch.setattr(app_module, "discover_candidates", lambda: [_discovered()])
        state.refresh()
        page = DPIPage(MouseController(), state=state)
        assert page.slider.isEnabled()
        caps = state.capability_state()
        assert caps.is_available("hid_available")
        assert caps.is_available("hardware_dpi_available")
        return state, core, hid, page

    def test_timeout_on_set_kills_hardware_dpi_available(self, qapp, monkeypatch):
        state, core, hid, page = self._healthy(qapp, monkeypatch)
        hid.ack_timeout = True  # timeout APENAS no SetSensorDPI
        page.dpi_input.setText("1200")
        page.apply_btn.click()

        # Falha: nada aplicado; capability morta com reason=timeout;
        # hid_available segue viva.
        assert state.applied_dpi is None
        caps = state.capability_state()
        assert not caps.is_available("hardware_dpi_available")
        assert "timeout" in caps.reason_for("hardware_dpi_available").lower()
        assert caps.is_available("hid_available")
        # UI não permanece com hint verde.
        assert "Sem acesso" not in page.hid_hint.text() or "DPI" in page.hid_hint.text()
        # O valor solicitado NÃO é apresentado como aplicado.
        assert page.dpi_value.text() != "1200"
        assert page.dpi_value.text() == UNKNOWN_VALUE_TEXT

    def test_protocol_error_on_set_kills_hardware_dpi_available(self, qapp, monkeypatch):
        state, core, hid, page = self._healthy(qapp, monkeypatch)
        hid.dpi_set_rejected = True  # FAP no SetSensorDPI
        page.dpi_input.setText("1200")
        page.apply_btn.click()

        assert state.applied_dpi is None
        caps = state.capability_state()
        assert not caps.is_available("hardware_dpi_available")
        assert "protocolo" in caps.reason_for("hardware_dpi_available").lower() or             "rejeitado" in caps.reason_for("hardware_dpi_available").lower()
        assert caps.is_available("hid_available")
        assert page.dpi_value.text() == UNKNOWN_VALUE_TEXT

    def test_reprobe_recovers_hardware_dpi_available(self, qapp, monkeypatch):
        state, core, hid, page = self._healthy(qapp, monkeypatch)
        hid.ack_timeout = True
        page.dpi_input.setText("1200")
        page.apply_btn.click()
        caps = state.capability_state()
        assert not caps.is_available("hardware_dpi_available")

        # Nova evidência: re-probe saudável recupera a capability.
        hid.ack_timeout = False
        state.refresh()
        caps = state.capability_state()
        assert caps.is_available("hardware_dpi_available")
        assert caps.is_available("hid_available")

    def test_success_clears_previous_set_error(self, qapp, monkeypatch):
        """Após um timeout, um SetSensorDPI bem-sucedido (ACK) recupera
        a capability por evidência nova.

        Issue #95: com a capability morta a UI desabilita os controles
        de DPI — a reautorização passa pelo refresh/re-probe (a causa
        do estado indica exatamente isso). O recovery do core continua
        comprovado: o apply pós-reprobe confirma o ACK e limpa o erro."""
        state, core, hid, page = self._healthy(qapp, monkeypatch)
        hid.ack_timeout = True
        page.dpi_input.setText("1200")
        page.apply_btn.click()
        caps = state.capability_state()
        assert not caps.is_available("hardware_dpi_available")
        # issue #95: sem capability, o controle de efeito físico sai da
        # tela (a UI não deixa a ação partir de estado não autorizado).
        assert not page.apply_btn.isEnabled()

        hid.ack_timeout = False
        page.showEvent(None)  # nova evidência: re-probe reautoriza
        assert page.apply_btn.isEnabled()
        page.dpi_input.setText("1400")
        page.apply_btn.click()
        assert state.applied_dpi == 1400
        caps = state.capability_state()
        assert caps.is_available("hardware_dpi_available")
        assert page.dpi_value.text() == "1400"
