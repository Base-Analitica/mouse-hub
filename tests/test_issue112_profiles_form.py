# -*- coding: utf-8 -*-
"""Regressões da issue #112: o formulário de Perfis expõe seu modo atual."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

from mouse_hub.core.config import ConfigPaths
from mouse_hub.core.constants import DPI_DEFAULT, SENSITIVITY_DEFAULT
from mouse_hub.core.profiles import ProfileOutcome, ProfileStore
from app.mouse_hub_app import MouseController, ProfilesPage


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _page(tmp_path):
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    store = ProfileStore(paths)
    return ProfilesPage(MouseController(), store=store), store, paths


def _persisted_page(tmp_path):
    page, store, paths = _page(tmp_path)
    outcome = store.save_profile("minecraft", 1200, 60)
    assert outcome.success
    page = ProfilesPage(MouseController(), store=store)
    return page, store, paths


def test_form_starts_in_create_mode(qapp, tmp_path):
    page, store, paths = _page(tmp_path)

    assert page.form_label.text() == "Criar Perfil"
    assert page.clear_btn.isHidden()
    assert page.name_input.text() == ""
    assert page.dpi_input.value() == DPI_DEFAULT
    assert page.sens_input.value() == SENSITIVITY_DEFAULT


def test_edit_mode_identifies_profile_and_shows_cancel(qapp, tmp_path):
    page, store, paths = _persisted_page(tmp_path)
    profile = store.get_profile("minecraft")

    page._start_edit(profile)

    assert page.form_label.text() == "Editar minecraft"
    assert not page.clear_btn.isHidden()
    assert page.name_input.text() == "minecraft"
    assert page.dpi_input.value() == 1200
    assert page.sens_input.value() == 60


def test_cancel_returns_to_create_without_persisting_changes(qapp, tmp_path):
    page, store, paths = _persisted_page(tmp_path)
    before = paths.config_file.read_bytes()
    profile = store.get_profile("minecraft")

    page._start_edit(profile)
    page.name_input.setText("perfil alterado")
    page.dpi_input.setValue(1600)
    page.sens_input.setValue(70)
    page.clear_btn.click()

    assert page.form_label.text() == "Criar Perfil"
    assert page.clear_btn.isHidden()
    assert page.name_input.text() == ""
    assert page.dpi_input.value() == DPI_DEFAULT
    assert page.sens_input.value() == SENSITIVITY_DEFAULT
    assert paths.config_file.read_bytes() == before
    saved = store.get_profile("minecraft")
    assert saved.name == "minecraft"
    assert saved.dpi == 1200
    assert saved.sensitivity == 60


def test_successful_edit_returns_to_create_and_persists(qapp, tmp_path):
    page, store, paths = _persisted_page(tmp_path)
    page._start_edit(store.get_profile("minecraft"))
    page.dpi_input.setValue(1400)
    page.sens_input.setValue(55)

    page.save_btn.click()

    assert page.form_label.text() == "Criar Perfil"
    assert page.clear_btn.isHidden()
    saved = store.get_profile("minecraft")
    assert saved.name == "minecraft"
    assert saved.dpi == 1400
    assert saved.sensitivity == 55


class _FailingStore(ProfileStore):
    def save_profile(self, name, dpi, sensitivity):
        return ProfileOutcome(success=False, message="falha de teste")


def test_failed_edit_keeps_edit_context(qapp, tmp_path):
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    base_store = ProfileStore(paths)
    assert base_store.save_profile("minecraft", 1200, 60).success
    store = _FailingStore(paths)
    page = ProfilesPage(MouseController(), store=store)
    page._start_edit(store.get_profile("minecraft"))
    page.dpi_input.setValue(1400)

    page.save_btn.click()

    assert page.form_label.text() == "Editar minecraft"
    assert not page.clear_btn.isHidden()
    assert page.dpi_input.value() == 1400
    assert "Nao foi possivel salvar" in page.apply_hint.text()


def test_edit_name_field_is_read_only_but_create_mode_allows_name(qapp, tmp_path):
    page, store, paths = _persisted_page(tmp_path)

    assert not page.name_input.isReadOnly()
    page._start_edit(store.get_profile("minecraft"))

    assert page.name_input.isReadOnly()


def test_edit_save_uses_original_profile_identity(qapp, tmp_path):
    page, store, paths = _persisted_page(tmp_path)
    page._start_edit(store.get_profile("minecraft"))
    page.name_input.setText("minecraft-copy")
    page.dpi_input.setValue(1400)
    page.sens_input.setValue(55)

    page.save_btn.click()

    saved = store.get_profile("minecraft")
    assert saved is not None
    assert saved.dpi == 1400
    assert saved.sensitivity == 55
    assert store.get_profile("minecraft-copy") is None
