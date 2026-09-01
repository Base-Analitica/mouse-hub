"""Issue #114: o formulário de Perfis precisa de labels persistentes."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

from mouse_hub.core.config import ConfigPaths
from mouse_hub.core.profiles import ProfileStore

from app.mouse_hub_app import MouseController, ProfilesPage


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def profiles_page(qapp, tmp_path):
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    page = ProfilesPage(MouseController(), store=ProfileStore(paths))
    page.resize(562, 800)
    page.show()
    qapp.processEvents()
    try:
        yield page
    finally:
        page.close()


FIELDS = (
    ("name_label", "Nome do perfil", "name_input"),
    ("dpi_label", "DPI", "dpi_input"),
    ("sens_label", "Sensibilidade", "sens_input"),
)


class TestProfilesPersistentFieldLabels:
    def test_fields_have_persistent_labels_and_buddies(self, profiles_page):
        """Cada campo deve continuar identificado quando está preenchido."""
        page = profiles_page
        page.name_input.setText("perfil pvp")
        page.dpi_input.setValue(1200)
        page.sens_input.setValue(65)

        for label_attr, expected, field_attr in FIELDS:
            label = getattr(page, label_attr)
            field = getattr(page, field_attr)
            assert label.text() == expected
            assert label.buddy() is field
            assert field.accessibleName() == expected
            assert label.isVisible()
            assert label.geometry().bottom() < field.geometry().top()

    @pytest.mark.parametrize("width", [562, 862])
    def test_labels_and_fields_fit_small_and_desktop(self, profiles_page, width):
        """Labels permanecem legíveis nas larguras de conteúdo suportadas."""
        page = profiles_page
        page.resize(width, 800)
        page.layout().activate()
        page.updateGeometry()
        page.repaint()

        for label_attr, expected, field_attr in FIELDS:
            label = getattr(page, label_attr)
            field = getattr(page, field_attr)
            assert label.text() == expected
            assert page.rect().contains(label.geometry())
            assert page.rect().contains(field.geometry())
            assert label.width() > 0
            assert field.width() > 0

    def test_units_remain_complementary_to_labels(self, profiles_page):
        """DPI e porcentagem seguem como unidade, não como único label."""
        assert profiles_page.dpi_input.suffix() == " DPI"
        assert profiles_page.sens_input.suffix() == "%"
        assert profiles_page.dpi_label.text() == "DPI"
        assert profiles_page.sens_label.text() == "Sensibilidade"
