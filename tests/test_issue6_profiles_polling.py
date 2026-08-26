# -*- coding: utf-8 -*-
"""Suíte da issue #6 — [P1] Unificar perfis, presets e polling rate
com o estado real do hardware.

Cobre os cenários obrigatórios:

Perfis:
  1. ProfilesPage lê a fonte única (ProfileStore), não lista hardcoded;
  2. presets oficiais continuam disponíveis;
  3. perfil customizado persiste na fonte real;
  4. reload recupera o perfil;
  5. arquivo corrompido não é sobrescrito;
  6. erro de I/O não vira sucesso;
  7. aplicação de perfil usa os serviços reais de DPI e sensibilidade;
  8. falha de DPI não vira sucesso global;
  9. sensibilidade não é alterada como fallback de DPI;
 10. perfil só aparece ativo quando o estado conhecido é compatível.

Polling rate:
 11. capability é falsa com razão explícita;
 12. UI não apresenta nenhuma frequência como confirmadamente ativa;
 13. clicar/interagir não gera sucesso falso nem efeito HID.
"""
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

from mouse_hub.core.config import ConfigError, ConfigPaths
from mouse_hub.core.dpi_persistence import NeverDpiPersister
from mouse_hub.core.mouse_controller import MouseController as CoreMouseController
from mouse_hub.core.profiles import ProfileStore
from tests.fakes import FakeHidAccess, FakeSystemInput, fake_g403_device

import app.mouse_hub_app as app_module
from app.mouse_hub_app import (
    MouseController,
    MouseCoreState,
    ProfilesPage,
    SensitivityPage,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _discovered(hidraw="/dev/hidraw2"):
    return fake_g403_device(hidraw=hidraw)


def _make_state(hid=None, system_input=None):
    hid = hid if hid is not None else FakeHidAccess()
    si = system_input if system_input is not None else FakeSystemInput()
    core = CoreMouseController(hid=hid, system_input=si, dpi_persister=NeverDpiPersister())
    return MouseCoreState(core), core, hid, si


# ═══════════════════════════════════════════════════════════════════════════════
#  Perfis — fonte única (ProfileStore)
# ═══════════════════════════════════════════════════════════════════════════════

class TestProfilesSingleSource:
    """A UI usa ProfileStore como fonte única de perfis (issue #6)."""

    def test_page_consumes_profile_store_not_hardcoded(self, qapp, tmp_path):
        """A página reflete o ProfileStore: remover um preset do store
        remove o card — a página não mantém lista própria."""
        paths = ConfigPaths(tmp_path / "c", tmp_path / "d")
        store = ProfileStore(paths)
        store.delete_profile("csgo")
        page = ProfilesPage(MouseController(), store=store)
        names = set(page.profile_cards.keys())
        assert "csgo" not in names
        assert "minecraft" in names
        assert "default" in names

    def test_presets_available_from_store(self, qapp, tmp_path):
        """Presets oficiais continuam disponíveis."""
        paths = ConfigPaths(tmp_path / "c", tmp_path / "d")
        store = ProfileStore(paths)
        page = ProfilesPage(MouseController(), store=store)
        names = set(page.profile_cards.keys())
        assert {"minecraft", "csgo", "default", "fortnite"} <= names

    def test_custom_profile_persists_and_reloads(self, qapp, tmp_path):
        """Perfil customizado persiste no disco e é recuperado no
        reload (nova instância de ProfileStore)."""
        paths = ConfigPaths(tmp_path / "c", tmp_path / "d")
        store = ProfileStore(paths)
        outcome = store.save_profile("my_custom", 1500, 65)
        assert outcome.success
        store2 = ProfileStore(paths)
        page = ProfilesPage(MouseController(), store=store2)
        assert "my_custom" in page.profile_cards

    def test_custom_profile_save_via_ui_form(self, qapp, tmp_path):
        """Salvar perfil pelo formulário da UI persiste na fonte
        real (ProfileStore)."""
        paths = ConfigPaths(tmp_path / "c", tmp_path / "d")
        store = ProfileStore(paths)
        page = ProfilesPage(MouseController(), store=store)
        page.name_input.setText("ui_custom")
        page.dpi_input.setValue(2000)
        page.sens_input.setValue(80)
        page.save_btn.click()
        assert "ui_custom" in page.profile_cards
        saved = store.get_profile("ui_custom")
        assert saved is not None
        assert saved.dpi == 2000
        assert saved.sensitivity == 80

    def test_corrupted_config_shows_error_and_does_not_overwrite(self, qapp, tmp_path):
        """Arquivo corrompido não é sobrescrito silenciosamente:
        a UI informa a falha e o arquivo permanece intacto."""
        config_dir = tmp_path / "c"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.json"
        config_file.write_text("{corrupt json", encoding="utf-8")
        paths = ConfigPaths(config_dir, tmp_path / "d")
        store = ProfileStore(paths)
        page = ProfilesPage(MouseController(), store=store)
        assert "Nao foi possivel ler os perfis" in page.config_hint.text()
        # arquivo ainda intacto
        assert config_file.read_text(encoding="utf-8") == "{corrupt json"
        # formulario desabilitado (mutacao bloqueada)
        assert not page.save_btn.isEnabled()

    def test_io_error_does_not_become_success(self, qapp, tmp_path):
        """Erro de I/O não vira sucesso: a UI informa a falha e
        mutacões são bloqueadas."""
        import os as osmod
        config_dir = tmp_path / "c"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.json"
        config_file.write_text('{"dpi": 1200}', encoding="utf-8")
        osmod.chmod(str(config_file), 0o000)
        try:
            paths = ConfigPaths(config_dir, tmp_path / "d")
            store = ProfileStore(paths)
            page = ProfilesPage(MouseController(), store=store)
            assert "Nao foi possivel ler os perfis" in page.config_hint.text()
            # tentativa programatica de salvar nao vira sucesso
            page.name_input.setText("x")
            page.dpi_input.setValue(1000)
            page.sens_input.setValue(50)
            page._save_custom()
            assert "Nao foi possivel salvar" in page.apply_hint.text()
        finally:
            osmod.chmod(str(config_file), 0o644)


# ═══════════════════════════════════════════════════════════════════════════════
#  Perfis — aplicação via serviços reais
# ═══════════════════════════════════════════════════════════════════════════════

class _CountingInput(FakeSystemInput):
    """FakeSystemInput com contador de chamadas a set_accel_speed."""

    def __init__(self):
        super().__init__()
        self.set_calls = 0

    def set_accel_speed(self, pointer_id, accel):
        self.set_calls += 1
        return super().set_accel_speed(pointer_id, accel)


class TestProfileApplyServices:
    """Aplicacao de perfil usa os servicos reais de DPI e sensibilidade."""

    def _ready(self, qapp, tmp_path, monkeypatch, hid=None, si=None):
        hid = hid if hid is not None else FakeHidAccess()
        si = si if si is not None else _CountingInput()
        core = CoreMouseController(
            hid=hid, system_input=si, dpi_persister=NeverDpiPersister()
        )
        state = MouseCoreState(core)
        monkeypatch.setattr(app_module, "discover", lambda: _discovered())
        state.refresh()
        paths = ConfigPaths(tmp_path / "c", tmp_path / "d")
        store = ProfileStore(paths)
        page = ProfilesPage(MouseController(), state=state, store=store)
        return state, core, hid, si, store, page

    def test_apply_uses_dpi_and_sensitivity_services(self, qapp, tmp_path, monkeypatch):
        """Aplicar perfil executa uma operacao HID (SetSensorDPI) e uma
        operacao de sensibilidade (set_accel_speed)."""
        state, core, hid, si, store, page = self._ready(
            qapp, tmp_path, monkeypatch
        )
        before_dpi = len(hid._dpi_commands)
        profile = store.get_profile("default")  # 800/50
        page._apply(profile)
        # DPI: exatamente um comando SetSensorDPI
        assert len(hid._dpi_commands) == before_dpi + 1
        assert state.applied_dpi == 800
        # Sensibilidade: exatamente uma chamada ao servico
        assert si.set_calls == 1
        assert state.applied_sensitivity == 50
        # Feedback de sucesso
        assert "confirmados" in page.apply_hint.text()

    def test_dpi_failure_not_global_success(self, qapp, tmp_path, monkeypatch):
        """Falha de DPI nao vira sucesso global: capability invalidada,
        sensibilidade aplicada independentemente, UI mostra estado
        parcial."""
        hid = FakeHidAccess()
        state, core, hid2, si, store, page = self._ready(
            qapp, tmp_path, monkeypatch, hid=hid
        )
        hid.dpi_set_rejected = True  # FAP error no SetSensorDPI
        profile = store.get_profile("default")
        page._apply(profile)
        # DPI: nada aplicado, capability invalidada
        assert state.applied_dpi is None
        caps = state.capability_state()
        assert not caps.is_available("hardware_dpi_available")
        # Sensibilidade: aplicada de forma INDEPENDENTE (nao e fallback)
        assert si.set_calls == 1
        assert state.applied_sensitivity == 50
        # UI nao afirma sucesso global
        assert "confirmados" not in page.apply_hint.text()
        assert "PARCIALMENTE" in page.apply_hint.text()

    def test_sensitivity_not_used_as_dpi_fallback(self, qapp, tmp_path, monkeypatch):
        """Falha de DPI nao dispara operacao extra de sensibilidade.
        Cada servico e chamado exatamente uma vez, independentemente."""
        hid = FakeHidAccess()
        state, core, hid2, si, store, page = self._ready(
            qapp, tmp_path, monkeypatch, hid=hid
        )
        hid.dpi_set_rejected = True
        profile = store.get_profile("default")
        page._apply(profile)
        # sensibilidade chamada exatamente uma vez (como operacao
        # independente, nao como fallback apos falha de DPI)
        assert si.set_calls == 1
        assert state.applied_sensitivity == 50

    def test_partial_state_dpi_ok_sens_fail(self, qapp, tmp_path, monkeypatch):
        """Estado parcial explicito: DPI confirmado, sensibilidade
        falhou."""
        si = _CountingInput()
        si.set_succeeds = False  # set_accel_speed falha
        state, core, hid, si2, store, page = self._ready(
            qapp, tmp_path, monkeypatch, si=si
        )
        profile = store.get_profile("default")
        page._apply(profile)
        assert state.applied_dpi == 800
        assert state.applied_sensitivity is None
        assert "PARCIALMENTE" in page.apply_hint.text()
        assert "DPI confirmado" in page.apply_hint.text()
        assert "falhou" in page.apply_hint.text().lower()


# ═══════════════════════════════════════════════════════════════════════════════
#  Perfis — indicador de ativo
# ═══════════════════════════════════════════════════════════════════════════════

class TestActiveProfile:
    """Perfil ativo so e indicado quando o estado confirmado corresponde."""

    def _ready(self, qapp, tmp_path, monkeypatch):
        hid = FakeHidAccess()
        si = _CountingInput()
        core = CoreMouseController(
            hid=hid, system_input=si, dpi_persister=NeverDpiPersister()
        )
        state = MouseCoreState(core)
        monkeypatch.setattr(app_module, "discover", lambda: _discovered())
        state.refresh()
        paths = ConfigPaths(tmp_path / "c", tmp_path / "d")
        store = ProfileStore(paths)
        page = ProfilesPage(MouseController(), state=state, store=store)
        return state, core, hid, si, store, page

    def test_no_active_before_any_confirmation(self, qapp, tmp_path, monkeypatch):
        """Sem estado confirmado, nenhum perfil e exibido como ativo."""
        state, core, hid, si, store, page = self._ready(
            qapp, tmp_path, monkeypatch
        )
        assert page.active_profile() is None

    def test_active_after_successful_apply(self, qapp, tmp_path, monkeypatch):
        """Apos aplicar um perfil com sucesso confirmado, o perfil
        aparece como ativo."""
        state, core, hid, si, store, page = self._ready(
            qapp, tmp_path, monkeypatch
        )
        profile = store.get_profile("default")
        page._apply(profile)
        assert page.active_profile() == "default"

    def test_active_changes_when_different_profile_applied(self, qapp, tmp_path, monkeypatch):
        """Aplicar outro perfil muda o indicador de ativo."""
        state, core, hid, si, store, page = self._ready(
            qapp, tmp_path, monkeypatch
        )
        page._apply(store.get_profile("default"))
        assert page.active_profile() == "default"
        page._apply(store.get_profile("minecraft"))
        assert page.active_profile() == "minecraft"

    def test_not_active_after_partial_state_change(self, qapp, tmp_path, monkeypatch):
        """Alterar apenas DPI faz com que o perfil deixe de ser ativo
        (sensibilidade ainda corresponde, mas DPI nao)."""
        state, core, hid, si, store, page = self._ready(
            qapp, tmp_path, monkeypatch
        )
        page._apply(store.get_profile("default"))
        assert page.active_profile() == "default"
        # Muda DPI para 1200 (minecraft), mas sensibilidade continua 50
        state.set_hardware_dpi(1200)
        page._refresh_active()
        # Nenhum perfil tem (1200, 50) — minecraft e (1200, 60)
        assert page.active_profile() is None


# ═══════════════════════════════════════════════════════════════════════════════
#  Polling rate — indisponível com verdade
# ═══════════════════════════════════════════════════════════════════════════════

class TestPollingRateUnavailable:
    """Polling rate nao e alteravel/confirmaável pelo stack atual."""

    def test_capability_false_with_explicit_reason(self):
        """Core declara polling_rate_available=False com razao precisa."""
        from mouse_hub.core.mouse_controller import (
            MouseController as CoreMC,
        )
        core = CoreMC(
            hid=FakeHidAccess(),
            system_input=FakeSystemInput(),
            dpi_persister=NeverDpiPersister(),
        )
        caps = core.capability_model().evaluate()
        assert not caps.is_available("polling_rate_available")
        reason = caps.reason_for("polling_rate_available")
        assert "0x8060" in reason or "Report Rate" in reason

    def test_ui_shows_no_frequency_as_active(self, qapp):
        """A UI nao apresenta nenhuma frequencia como ativa (nenhum
        botao com estado ativo, todos desabilitados)."""
        state, core, hid, si = _make_state()
        page = SensitivityPage(MouseController(), state=state)
        assert len(page.polling_buttons) == 4
        for btn in page.polling_buttons:
            assert not btn.isEnabled()
        assert "indispon" in page.polling_hint.text().lower()

    def test_no_1000hz_active_by_default_in_source(self):
        """O codigo-fonte nao define 'active = hz == "1000 Hz"'."""
        import inspect
        source = inspect.getsource(SensitivityPage)
        assert "active = hz" not in source

    def test_polling_interaction_no_hid_effect(self, qapp, monkeypatch):
        """Clicar nos botoes de polling NAO gera comandos HID."""
        hid = FakeHidAccess()
        state, core, hid2, si = _make_state(hid=hid)
        monkeypatch.setattr(app_module, "discover", lambda: _discovered())
        state.refresh()
        page = SensitivityPage(MouseController(), state=state)
        before = len(hid.raw_written_reports)
        for btn in page.polling_buttons:
            btn.click()  # desabilitado: nenhum sinal, nenhum efeito
        assert len(hid.raw_written_reports) == before


# ═══════════════════════════════════════════════════════════════════════════════
#  Web legado — fonte concorrente removida
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebLegacyNoConcurrentSource:
    """A fonte concorrente web foi removida integralmente pela issue #10."""

    def test_web_html_source_is_absent(self):
        """Não existe mais HTML web capaz de manter perfis/presets próprios."""
        assert not Path("static/index.html").exists()

    def test_web_server_source_is_absent(self):
        """Não existe mais servidor web capaz de expor endpoints paralelos."""
        assert not Path("mouse_hub.py").exists()
