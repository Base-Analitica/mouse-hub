"""Issue #100: a página de Perfis precisa reflowar sem overlap em 760x560."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QLabel

from mouse_hub.core.config import ConfigPaths
from mouse_hub.core.profiles import ProfileStore

import app.mouse_hub_app as app_module
from scripts.capture_screenshots import _build_app


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def small_profiles_page(qapp, tmp_path, monkeypatch):
    """Página no mesmo QStackedWidget/scroll do capturador oficial."""
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    ProfileStore(paths).save_profile("custom", 900, 40)
    monkeypatch.setattr(
        app_module.ConfigPaths, "xdg", staticmethod(lambda: paths)
    )
    window, built_qapp, internal_patch = _build_app()
    window.resize(1050, 680)
    window.show()
    qapp.processEvents()
    for index in range(len(window.nav_buttons)):
        window._switch_page(index)
        qapp.processEvents()
    window.resize(760, 560)
    qapp.processEvents()
    window._switch_page(5)
    qapp.processEvents()
    try:
        yield window.stack.widget(5), window.profiles_page
    finally:
        window.close()
        internal_patch.undo()


def _rects_intersecting(rects):
    return [
        (left_name, right_name)
        for index, (left_name, left_rect) in enumerate(rects)
        for right_name, right_rect in rects[index + 1 :]
        if left_rect.intersects(right_rect)
    ]


class TestProfilesResponsiveLayout:
    def test_small_layout_has_no_card_or_form_overlap(
        self, small_profiles_page
    ):
        """Cards, heading e controles devem ocupar regiões distintas."""
        scroll, page = small_profiles_page
        cards = [
            (name, widgets["card"].geometry())
            for name, widgets in page.profile_cards.items()
        ]
        assert not _rects_intersecting(cards)

        form_label = next(
            label
            for label in page.findChildren(QLabel)
            if label.text() == "Criar / Editar Perfil"
        )
        form_widgets = [
            ("form-heading", form_label.geometry()),
            ("name", page.name_input.geometry()),
            ("dpi", page.dpi_input.geometry()),
            ("sensitivity", page.sens_input.geometry()),
            ("save", page.save_btn.geometry()),
            ("cancel", page.clear_btn.geometry()),
        ]
        assert not _rects_intersecting(
            cards + form_widgets
        ), "cards e formulário não podem se sobrepor"
        assert form_label.geometry().top() > max(
            rect.bottom() for _, rect in cards
        )

    def test_small_layout_keeps_controls_inside_page(self, small_profiles_page):
        """Nenhum controle do formulário pode sair pela borda da página."""
        scroll, page = small_profiles_page
        page_rect = page.rect()
        controls = [
            page.name_input,
            page.dpi_input,
            page.sens_input,
            page.save_btn,
            page.clear_btn,
        ]
        for widget in controls:
            assert page_rect.contains(widget.geometry()), (
                widget.objectName() or widget.__class__.__name__,
                widget.geometry(),
                page_rect,
            )
            assert widget.isVisible()

    def test_small_layout_does_not_overflow_horizontally(
        self, small_profiles_page
    ):
        """O conteúdo deve rolar verticalmente, nunca criar barra horizontal."""
        scroll, page = small_profiles_page
        page_rect = page.rect()
        for name, widgets in page.profile_cards.items():
            assert page_rect.contains(widgets["card"].geometry()), name
        assert scroll.horizontalScrollBar().maximum() == 0
        assert not scroll.horizontalScrollBar().isVisible()
