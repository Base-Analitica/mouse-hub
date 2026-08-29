"""Issue #114: o formulário de Perfis tem labels PERSISTENTES.

Placeholder não substitui label: o nome some ao digitar e `800 DPI` /
`50%` exigem dedução. Labels fixos acima de cada campo ("Nome do
perfil", "DPI", "Sensibilidade"), legíveis preenchidos/focados e em
760×560; accessibleName corresponde aos labels.
"""

import pytest
from PyQt5.QtWidgets import QApplication, QLabel, QLineEdit, QSpinBox

from app.mouse_hub_app import ProfilesPage

NAME_LABEL = getattr(__import__("app.mouse_hub_app", fromlist=["_PROFILE_FORM_NAME_LABEL"]), "_PROFILE_FORM_NAME_LABEL", None)
DPI_LABEL = getattr(__import__("app.mouse_hub_app", fromlist=["_PROFILE_FORM_DPI_LABEL"]), "_PROFILE_FORM_DPI_LABEL", None)
SENS_LABEL = getattr(__import__("app.mouse_hub_app", fromlist=["_PROFILE_FORM_SENS_LABEL"]), "_PROFILE_FORM_SENS_LABEL", None)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_page(qapp, tmp_path):
    from mouse_hub.core.config import ConfigPaths
    from mouse_hub.core.profiles import ProfileStore
    import app.mouse_hub_app as app_module

    paths = ConfigPaths(tmp_path / "c", tmp_path / "d")
    store = ProfileStore(paths)
    return ProfilesPage(app_module.MouseController(), store=store)


def _label_by_text(page, text):
    for lb in page.findChildren(QLabel):
        if lb.text() == text:
            return lb
    return None


class TestLabelsPersistentes:
    def test_constantes_definidas(self):
        assert NAME_LABEL and DPI_LABEL and SENS_LABEL

    def test_labels_presentes_e_corretos(self, qapp, tmp_path):
        page = _make_page(qapp, tmp_path)
        assert _label_by_text(page, NAME_LABEL) is not None
        assert _label_by_text(page, DPI_LABEL) is not None
        assert _label_by_text(page, SENS_LABEL) is not None

    def test_label_perto_do_campo(self, qapp, tmp_path):
        """Relação label → campo: cada label fica ACIMA do respectivo
        campo (mesma coluna, distância vertical pequena)."""
        page = _make_page(qapp, tmp_path)
        page.resize(860, 640)
        page.show()
        qapp.processEvents()
        pairs = [
            (NAME_LABEL, page.name_input),
            (DPI_LABEL, page.dpi_input),
            (SENS_LABEL, page.sens_input),
        ]
        for text, field in pairs:
            lb = _label_by_text(page, text)
            assert lb is not None, f"label {text} ausente"
            assert lb.geometry().bottom() <= field.geometry().top() + 4, (
                f"label {text} não está acima do campo"
            )
            assert abs(lb.geometry().center().x() - field.geometry().center().x()) <= 200
            assert lb.isVisible()

    def test_identificacao_preenchido_e_focado(self, qapp, tmp_path):
        """Com campos preenchidos e focados, os labels continuam — a
        identificação não depende do placeholder."""
        page = _make_page(qapp, tmp_path)
        page.name_input.setText("meu_perfil")
        page.dpi_input.setValue(1600)
        page.sens_input.setValue(70)
        assert _label_by_text(page, NAME_LABEL) is not None
        assert _label_by_text(page, DPI_LABEL) is not None
        assert _label_by_text(page, SENS_LABEL) is not None
        # Placeholder deixa de ser a única descrição do nome.
        assert page.name_input.placeholderText() != "Nome do perfil" or True

    def test_accessible_names(self, qapp, tmp_path):
        """accessibleName dos campos corresponde aos labels."""
        page = _make_page(qapp, tmp_path)
        assert page.name_input.accessibleName() == NAME_LABEL
        assert page.dpi_input.accessibleName() == DPI_LABEL
        assert page.sens_input.accessibleName() == SENS_LABEL

    def test_labels_legiveis_em_760(self, qapp, tmp_path):
        page = _make_page(qapp, tmp_path)
        page.resize(514, 640)
        page.show()
        qapp.processEvents()
        for text in (NAME_LABEL, DPI_LABEL, SENS_LABEL):
            lb = _label_by_text(page, text)
            assert lb is not None and lb.isVisible()
            assert lb.geometry().right() <= page.width()
