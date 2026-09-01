# -*- coding: utf-8 -*-
"""Regressões de copy visível da página de Perfis (issue #97)."""

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

from mouse_hub.core.config import ConfigPaths
from mouse_hub.core.dpi_persistence import NeverDpiPersister
from mouse_hub.core.mouse_controller import MouseController as CoreMouseController
from mouse_hub.core.profiles import ProfileStore
from tests.fakes import FakeHidAccess, FakeSystemInput, fake_g403_device

import app.mouse_hub_app as app_module
from app.mouse_hub_app import MouseController, MouseCoreState, ProfilesPage


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _ready(qapp, tmp_path, monkeypatch, hid=None, system_input=None):
    hid = hid if hid is not None else FakeHidAccess()
    system_input = system_input if system_input is not None else FakeSystemInput()
    core = CoreMouseController(
        hid=hid,
        system_input=system_input,
        dpi_persister=NeverDpiPersister(),
    )
    state = MouseCoreState(core)
    monkeypatch.setattr(
        app_module,
        "discover_candidates",
        lambda: [fake_g403_device(hidraw="/dev/hidraw2")],
    )
    state.refresh()
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    store = ProfileStore(paths)
    page = ProfilesPage(MouseController(), state=state, store=store)
    return state, hid, system_input, store, page


class _WriteFailingProfileStore(ProfileStore):
    """ProfileStore real com falha de escrita determinística."""

    def _write(self, config):
        raise OSError("falha de escrita simulada")


def test_read_error_copy_is_accented_and_form_remains_blocked(qapp, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.json"
    original = "{json corrompido"
    config_file.write_text(original, encoding="utf-8")
    page = ProfilesPage(
        MouseController(),
        store=ProfileStore(ConfigPaths(config_dir, tmp_path / "data")),
    )

    text = page.config_hint.text()
    assert "Não foi possível ler os perfis" in text
    assert "O arquivo de configuração NÃO foi alterado." in text
    assert "Nao foi possivel ler os perfis" not in text
    assert "configuracao NAO foi alterado" not in text
    assert config_file.read_text(encoding="utf-8") == original
    assert not page.save_btn.isEnabled()


def test_total_apply_failure_copy_is_accented_and_causes_remain_visible(
    qapp, tmp_path, monkeypatch
):
    hid = FakeHidAccess()
    system_input = FakeSystemInput()
    state, hid, system_input, store, page = _ready(
        qapp, tmp_path, monkeypatch, hid=hid, system_input=system_input
    )
    hid.dpi_set_rejected = True
    system_input.set_succeeds = False

    page._apply(store.get_profile("default"))

    text = page.apply_hint.text()
    assert "NÃO aplicado" in text
    assert "NAO aplicado" not in text
    assert "DPI falhou" in text
    assert "sensibilidade falhou" in text
    assert "confirmados" not in text
    assert state.applied_dpi is None
    assert state.applied_sensitivity is None


def test_partial_apply_keeps_explicit_state_copy(qapp, tmp_path, monkeypatch):
    system_input = FakeSystemInput()
    system_input.set_succeeds = False
    state, hid, system_input, store, page = _ready(
        qapp, tmp_path, monkeypatch, system_input=system_input
    )

    page._apply(store.get_profile("default"))

    text = page.apply_hint.text()
    assert "PARCIALMENTE" in text
    assert "DPI confirmado" in text
    assert "sensibilidade falhou" in text
    assert "NAO aplicado" not in text
    assert state.applied_dpi == 800
    assert state.applied_sensitivity is None


def test_save_failure_copy_is_accented_and_does_not_claim_success(qapp, tmp_path):
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    page = ProfilesPage(MouseController(), store=_WriteFailingProfileStore(paths))
    page.name_input.setText("profile_error")
    page._save_custom()

    text = page.apply_hint.text()
    assert "Não foi possível salvar o perfil 'profile_error'" in text
    assert "Nao foi possivel salvar" not in text
    assert "salvo na configuração" not in text


def test_active_profile_badge_uses_text_without_status_glyph(qapp, tmp_path):
    state = SimpleNamespace(
        applied_dpi=800, applied_sensitivity=50, refresh=lambda: None
    )
    page = ProfilesPage(
        MouseController(),
        state=state,
        store=ProfileStore(ConfigPaths(tmp_path / "config", tmp_path / "data")),
    )
    page.show()
    qapp.processEvents()

    badge = page.profile_cards["default"]["active_badge"]
    assert badge.text() == "Ativo"
    assert "✔" not in badge.text()


def test_save_success_copy_is_accented_and_profile_is_persisted(qapp, tmp_path):
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    store = ProfileStore(paths)
    page = ProfilesPage(MouseController(), store=store)
    page.name_input.setText("profile_ok")
    page.dpi_input.setValue(1600)
    page.sens_input.setValue(70)
    page._save_custom()

    text = page.apply_hint.text()
    assert "Perfil 'profile_ok' salvo na configuração." in text
    assert "salvo na configuracao" not in text
    saved = store.get_profile("profile_ok")
    assert saved is not None
    assert saved.dpi == 1600
    assert saved.sensitivity == 70
