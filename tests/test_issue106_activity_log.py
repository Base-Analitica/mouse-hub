# -*- coding: utf-8 -*-
"""Regressões da issue #106 para a densidade do Log de Atividade."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import QApplication

from app.mouse_hub_app import DashboardPage, MouseHubApp, STYLESHEET


EMPTY_LOG_HEIGHT = 64
CONTENT_LOG_HEIGHT = 120
EMPTY_LOG_MESSAGE = (
    "Nenhuma atividade ainda — as ações do app aparecem aqui."
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    previous_stylesheet = app.styleSheet()
    app.setStyleSheet(STYLESHEET)
    yield app
    app.setStyleSheet(previous_stylesheet)


class _FakeMC:
    current_dpi = 800
    current_sensitivity = 50


class _FakeAc:
    class _State:
        value = "stopped"

    state = _State()


class _FakeWindowService:
    def is_focused(self, patterns):
        class _Result:
            focused = False

        return _Result()


class _FakeSvc:
    window_service = _FakeWindowService()


def _page():
    page = DashboardPage(_FakeMC(), _FakeAc(), None, _FakeSvc())
    page.timer.stop()
    return page


def _wrapped_page(qapp, window_width, window_height):
    page = _page()
    scroll = MouseHubApp._wrap_scrollable(page)
    scroll.resize(window_width - 190, window_height)
    scroll.show()
    qapp.processEvents()
    return page, scroll


def test_empty_log_is_compact_and_keeps_placeholder(qapp):
    page = _page()

    assert page.log.toPlainText() == ""
    assert page.log.placeholderText() == EMPTY_LOG_MESSAGE
    assert page.log.maximumHeight() == EMPTY_LOG_HEIGHT
    assert page.log.minimumHeight() == EMPTY_LOG_HEIGHT


def test_real_entries_restore_height_and_remain_in_order(qapp):
    page = _page()
    page.resize(760, 560)
    page.show()
    qapp.processEvents()
    page.log_msg("primeira atividade")
    page.log_msg("segunda atividade")
    qapp.processEvents()

    text = page.log.toPlainText()
    assert page.log.maximumHeight() == CONTENT_LOG_HEIGHT
    assert page.log.minimumHeight() == CONTENT_LOG_HEIGHT
    assert text.index("primeira atividade") < text.index("segunda atividade")

    for index in range(30):
        page.log_msg("atividade longa %02d %s" % (index, "x" * 80))
    qapp.processEvents()

    assert page.log.verticalScrollBar().maximum() > 0
    assert page.log.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded

    page.close()


def test_clearing_real_entries_returns_to_compact_empty_state(qapp):
    page = _page()
    page.log_msg("atividade temporária")
    assert page.log.maximumHeight() == CONTENT_LOG_HEIGHT

    page.log.clear()
    qapp.processEvents()

    assert page.log.toPlainText() == ""
    assert page.log.maximumHeight() == EMPTY_LOG_HEIGHT
    assert page.log.minimumHeight() == EMPTY_LOG_HEIGHT
    assert page.log.placeholderText() == EMPTY_LOG_MESSAGE


def test_empty_log_reduces_page_scroll_contribution_in_small_viewport(qapp):
    page, scroll = _wrapped_page(qapp, 760, 560)
    compact_scroll = scroll.verticalScrollBar().maximum()

    page.log.setFixedHeight(CONTENT_LOG_HEIGHT)
    qapp.processEvents()
    content_scroll = scroll.verticalScrollBar().maximum()

    assert page.log.height() == CONTENT_LOG_HEIGHT
    assert content_scroll > compact_scroll
    assert content_scroll - compact_scroll == (
        CONTENT_LOG_HEIGHT - EMPTY_LOG_HEIGHT
    )
    assert compact_scroll < CONTENT_LOG_HEIGHT - EMPTY_LOG_HEIGHT

    scroll.close()


def test_empty_log_stays_visible_in_integrated_small_dashboard(qapp):
    window = MouseHubApp()
    try:
        window.setStyleSheet(STYLESHEET)
        window.resize(760, 560)
        window.show()
        qapp.processEvents()

        scroll = window.stack.currentWidget()
        page = window.dashboard_page
        log_top_left = page.log.mapTo(scroll.viewport(), QPoint(0, 0))

        assert page.log.height() == EMPTY_LOG_HEIGHT
        assert scroll.verticalScrollBar().maximum() < (
            CONTENT_LOG_HEIGHT - EMPTY_LOG_HEIGHT
        )
        assert log_top_left.y() + page.log.height() <= scroll.viewport().height()
    finally:
        window.close()
        window.me.cleanup()
        window.ac.cleanup()
        window.svc.cleanup()


@pytest.mark.parametrize("width,height", [(1050, 680), (760, 560)])
def test_empty_log_fits_both_official_viewports(qapp, width, height):
    page, scroll = _wrapped_page(qapp, width, height)

    assert page.log.isVisible()
    assert page.log.height() == EMPTY_LOG_HEIGHT
    assert page.log.maximumHeight() == EMPTY_LOG_HEIGHT
    assert page.log.placeholderText() == EMPTY_LOG_MESSAGE

    scroll.close()


@pytest.mark.parametrize("width,height", [(1050, 680), (760, 560)])
def test_filled_log_remains_scrollable_in_both_official_viewports(
    qapp, width, height
):
    page, scroll = _wrapped_page(qapp, width, height)
    for index in range(30):
        page.log_msg("evento %02d %s" % (index, "x" * 80))
    qapp.processEvents()

    assert page.log.height() == CONTENT_LOG_HEIGHT
    assert page.log.verticalScrollBar().maximum() > 0
    text = page.log.toPlainText()
    assert "evento 00" in text
    assert "evento 29" in text

    scroll.close()
