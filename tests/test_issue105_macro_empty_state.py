"""Issue #105: o empty state de Macros permanece junto ao heading.

Os testes usam apenas a página real e um engine fake. Nenhum mouse, X11 real ou
persistência é necessário para provar o contrato visual.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt5")
from PyQt5.QtCore import QCoreApplication, QEvent, QPoint, Qt  # noqa: E402
from PyQt5.QtGui import QFontMetrics  # noqa: E402
from PyQt5.QtWidgets import (  # noqa: E402
    QApplication,
    QLabel,
    QFrame,
    QPushButton,
    QScrollArea,
    QWidget,
)

from app.mouse_hub_app import MacrosPage


VIEWPORTS = ((1050, 680), (760, 560))
EMPTY_PREFIX = "Nenhuma macro gravada ainda."


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class FakeMacroEngine:
    """Superfície mínima consumida por ``MacrosPage`` nos testes."""

    playback_state = "idle"
    playback_error = None

    def __init__(self, macros=None):
        self.macros = {} if macros is None else macros

    def list_all(self):
        return self.macros


def _build_page(qapp, macros=None, size=(1050, 680)):
    engine = FakeMacroEngine(macros)
    page = MacrosPage(engine, None)
    page._play_timer.stop()
    page.resize(*size)
    page.show()
    qapp.processEvents()
    return page, engine


def _empty_labels(page):
    return [
        label
        for label in page.findChildren(QLabel)
        if label.text().startswith(EMPTY_PREFIX) and label.isVisible()
    ]


def _process_events(qapp):
    qapp.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    qapp.processEvents()


def _close_page(qapp, page):
    page.close()
    page.deleteLater()
    qapp.processEvents()


@pytest.mark.parametrize("size", VIEWPORTS)
def test_empty_state_is_top_aligned_and_compact(qapp, size):
    page, _ = _build_page(qapp, size=size)
    try:
        empty = _empty_labels(page)[0]
        scroll = page.findChild(QScrollArea)

        assert empty.text() == (
            "Nenhuma macro gravada ainda.\n"
            "Use   Gravar Macro acima para criar a primeira."
        )
        assert empty.alignment() == Qt.AlignLeft | Qt.AlignTop
        assert empty.geometry().top() == scroll.widget().rect().top()

        heading = next(
            label for label in page.findChildren(QLabel)
            if label.text() == "Macros Salvas"
        )
        assert page.layout().indexOf(heading) + 1 == page.layout().indexOf(scroll)
        heading_bottom = heading.mapTo(page, QPoint(0, heading.height())).y()
        empty_top = empty.mapTo(page, QPoint()).y()
        assert heading_bottom < empty_top <= heading_bottom + 40

        # Duas linhas mais no máximo 20 px de respiro em cada direção:
        # o texto não deve ocupar a altura inteira da região de lista.
        max_compact_height = QFontMetrics(empty.font()).lineSpacing() * 2 + 40
        assert empty.sizeHint().height() <= max_compact_height
    finally:
        _close_page(qapp, page)


def test_empty_state_keeps_one_creation_cta(qapp):
    page, _ = _build_page(qapp)
    try:
        empty = _empty_labels(page)[0]
        creation_buttons = [
            button
            for button in page.findChildren(QPushButton)
            if button.text().strip() == "Gravar Macro" and button.isVisible()
        ]

        assert len(creation_buttons) == 1
        assert not empty.findChildren(QPushButton)
    finally:
        _close_page(qapp, page)


@pytest.mark.parametrize("size", VIEWPORTS)
def test_populated_macro_list_has_no_empty_state(qapp, size):
    page, _ = _build_page(
        qapp,
        macros={"burst": {"count": 3, "created": "2026-08-29"}},
        size=size,
    )
    try:
        assert not _empty_labels(page)
        assert any(
            label.text().strip() == "burst"
            for label in page.macro_list_widget.findChildren(QLabel)
        )
        assert any(
            button.text().strip() == "Play"
            for button in page.macro_list_widget.findChildren(QPushButton)
        )
    finally:
        _close_page(qapp, page)


@pytest.mark.parametrize("size", VIEWPORTS)
def test_empty_and_populated_transition_leaves_no_residual_widgets(qapp, size):
    page, engine = _build_page(qapp, size=size)
    try:
        empty_before = _empty_labels(page)[0]
        engine.macros = {"burst": {"count": 3, "created": "2026-08-29"}}
        page._refresh_list()
        _process_events(qapp)
        assert not _empty_labels(page)
        assert all(
            widget is not empty_before
            for widget in page.macro_list_widget.findChildren(QWidget)
        )
        populated_item = next(
            frame for frame in page.macro_list_widget.findChildren(QFrame)
            if frame.objectName() == "macroItem"
        )

        engine.macros = {}
        page._refresh_list()
        _process_events(qapp)
        assert len(_empty_labels(page)) == 1
        assert not any(
            label.text().strip() == "burst"
            for label in page.macro_list_widget.findChildren(QLabel)
        )
        assert all(
            widget is not populated_item
            for widget in page.macro_list_widget.findChildren(QWidget)
        )
    finally:
        _close_page(qapp, page)
