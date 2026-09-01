"""Issue #104 — o label do nome da macro não deve parecer outro input."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PyQt5")
from PyQt5.QtWidgets import QApplication, QLabel, QLineEdit  # noqa: E402


class FakeMacroService:
    """Superfície mínima para construir ``MacrosPage`` sem X11 ou hardware."""

    playback_state = "idle"
    playback_error = None

    def list_all(self):
        return {}

    def cleanup(self):
        pass


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _make_page(qapp, size):
    import app.mouse_hub_app as app_module

    page = app_module.MacrosPage(FakeMacroService(), None)
    page.resize(*size)
    page.show()
    qapp.processEvents()
    return page


def _name_label(page):
    labels = [
        widget
        for widget in page.findChildren(QLabel)
        if widget.text() == "Nome da macro:"
    ]
    assert len(labels) == 1
    return labels[0]


def _close_page(page, qapp):
    page._play_timer.stop()
    page.close()
    page.deleteLater()
    qapp.processEvents()


@pytest.mark.parametrize("size", [(1050, 680), (760, 560)])
def test_macro_name_label_is_plain_form_text(qapp, size):
    page = _make_page(qapp, size)
    try:
        label = _name_label(page)
        style = label.styleSheet().lower()

        assert "background: transparent" in style
        assert "padding: 0" in style
        assert "border:" not in style
        assert len(page.findChildren(QLineEdit)) == 1
    finally:
        _close_page(page, qapp)


@pytest.mark.parametrize("size", [(1050, 680), (760, 560)])
def test_macro_name_label_preserves_input_order_and_contract(qapp, size):
    page = _make_page(qapp, size)
    try:
        label = _name_label(page)
        assert label.geometry().bottom() < page.name_input.geometry().top()
        assert page.name_input.text() == "minha_macro"
        assert page.name_input.maxLength() == 32
    finally:
        _close_page(page, qapp)
