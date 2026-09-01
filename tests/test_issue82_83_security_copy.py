"""Issue #82/#83: a segurança do Auto-Clicker deve ser clara e neutra.

Os testes exercitam a superfície pública da SettingsPage sem hardware real:
- a explicação mantém o foco permitido e o bloqueio fora do jogo;
- remove detalhes de implementação que não orientam o usuário;
- usa cor neutra, sem sinalizar a explicação inteira como sucesso;
- permanece legível nos dois viewports oficiais.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PyQt5")
from PyQt5.QtWidgets import QApplication, QLabel, QGroupBox  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    yield app


def _settings_page():
    from app import mouse_hub_app as app_module

    return app_module.SettingsPage(None, None, None, None, state=None)


def _security_group(page):
    groups = [
        group
        for group in page.findChildren(QGroupBox)
        if "Auto-Clicker" in group.title()
    ]
    assert len(groups) == 1
    return groups[0]


def _safety_label(page):
    group = _security_group(page)
    labels = [
        label
        for label in group.findChildren(QLabel)
        if "auto-clicker" in label.text().casefold()
    ]
    assert len(labels) == 1
    return labels[0], group


def test_security_copy_explains_allowed_focus_and_fail_closed_behavior(qapp):
    page = _settings_page()
    try:
        label, _ = _safety_label(page)
        text = " ".join(label.text().split()).casefold()

        assert "minecraft" in text
        assert "lunar client" in text
        assert "foco" in text
        assert "janela ativa" in text
        assert "fora do jogo" in text
        assert "nenhum clique" in text
    finally:
        page.close()
        page.deleteLater()
        qapp.processEvents()


def test_security_copy_has_no_implementation_jargon(qapp):
    page = _settings_page()
    try:
        label, _ = _safety_label(page)
        text = label.text().casefold()

        for forbidden in (
            "x11",
            "xrecord",
            "cache",
            "ttl",
            "500 ms",
            "xdotool",
            "python-xlib",
        ):
            assert forbidden not in text
    finally:
        page.close()
        page.deleteLater()
        qapp.processEvents()


def test_security_copy_uses_neutral_explanatory_color(qapp):
    from app.mouse_hub_app import COLORS

    page = _settings_page()
    try:
        label, _ = _safety_label(page)
        stylesheet = label.styleSheet()

        assert COLORS["text_secondary"] in stylesheet
        assert COLORS["mc_green"] not in stylesheet
    finally:
        page.close()
        page.deleteLater()
        qapp.processEvents()


@pytest.mark.parametrize(
    "size",
    [(1050, 680), (760, 560)],
    ids=["desktop", "small"],
)
def test_security_copy_is_visible_and_contained_in_official_viewports(qapp, size):
    page = _settings_page()
    try:
        page.resize(*size)
        page.show()
        qapp.processEvents()

        label, group = _safety_label(page)
        contents = group.contentsRect()

        assert label.isVisible()
        assert label.wordWrap() is True
        assert label.width() > 0
        assert label.height() > 0
        assert label.geometry().top() >= contents.top()
        assert label.geometry().bottom() <= contents.bottom()
    finally:
        page.close()
        page.deleteLater()
        qapp.processEvents()
