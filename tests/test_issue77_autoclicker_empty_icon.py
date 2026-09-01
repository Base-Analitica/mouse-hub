"""Regressões da issue #77: o card não reserva coluna para ícone vazio."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt5")
from PyQt5.QtWidgets import QApplication, QLabel  # noqa: E402


class FakeState:
    def __init__(self, value: str = "stopped"):
        self.value = value


class FakeAutoClicker:
    def __init__(self):
        self.cps = 10
        self.button = 1
        self.state = FakeState()
        self.running = False
        self.error = None
        self.start_calls = 0
        self.stop_calls = 0

    def start(self):
        self.start_calls += 1
        self.running = True
        self.state.value = "running"

    def stop(self):
        self.stop_calls += 1
        self.running = False
        self.state.value = "stopped"

    def cleanup(self):
        pass


class FakeFocusResult:
    focused = False


class FakeWindowService:
    def is_focused(self, patterns):
        return FakeFocusResult()


class FakeService:
    window_service = FakeWindowService()


def _qapp():
    return QApplication.instance() or QApplication([])


def _make_page():
    from app.mouse_hub_app import AutoClickerPage

    ac = FakeAutoClicker()
    page = AutoClickerPage(None, ac, FakeService())
    return page, ac


def _close_page(page):
    page.timer.stop()
    page.close()
    _qapp().processEvents()


def _show_page(page, qapp, size=(1050, 680)):
    page.resize(*size)
    page.show()
    qapp.processEvents()


def _status_labels(page):
    return page.status_frame.findChildren(QLabel)


def _assert_status_composition(page):
    labels = _status_labels(page)
    assert labels == [page.status_title, page.status_sub]
    assert all(label.text().strip() for label in labels)
    assert all(label.isVisible() for label in labels)

    contents = page.status_frame.contentsRect()
    for label in labels:
        assert contents.contains(label.geometry().topLeft())
        assert contents.contains(label.geometry().bottomRight())

    first_item = page.status_frame.layout().itemAt(0)
    assert first_item.layout() is not None
    assert first_item.layout().itemAt(0).widget() is page.status_title
    assert not hasattr(page, "status_icon")


@pytest.fixture(scope="module")
def qapp():
    app = _qapp()
    yield app


@pytest.mark.parametrize("size", [(1050, 680), (760, 560)])
def test_status_card_has_no_empty_icon_column_in_official_viewports(qapp, size):
    page, _ = _make_page()
    try:
        page.resize(*size)
        page.show()
        qapp.processEvents()
        _assert_status_composition(page)
        assert page.status_frame.isVisible()
    finally:
        _close_page(page)


def test_production_has_no_status_icon_placeholder_reference():
    import app.mouse_hub_app as app_module

    source = Path(app_module.__file__).read_text(encoding="utf-8")
    assert "status_icon" not in source


@pytest.mark.parametrize(
    ("state_value", "running", "error", "title", "subtitle"),
    [
        (
            "stopped",
            False,
            None,
            "Auto-Clicker Desligado",
            "Clique em iniciar para começar",
        ),
        (
            "running",
            True,
            None,
            "Auto-Clicker Ativo!",
            "10 CPS — Botão esquerdo",
        ),
        (
            "blocked_by_focus",
            True,
            None,
            "Aguardando jogo em foco...",
            "Ligado, mas só clica com Minecraft/Lunar Client ativo",
        ),
        (
            "failed",
            False,
            "falha fake",
            "Auto-Clicker com erro",
            "Falha: falha fake",
        ),
    ],
)
def test_engine_states_keep_textual_status_without_placeholder(
    qapp, state_value, running, error, title, subtitle
):
    page, ac = _make_page()
    try:
        _show_page(page, qapp)
        ac.state.value = state_value
        ac.running = running
        ac.error = error
        page._update()
        assert page.status_title.text() == title
        assert page.status_sub.text() == subtitle
        _assert_status_composition(page)
    finally:
        _close_page(page)


def test_toggle_start_and_stop_preserve_status_composition(qapp):
    page, ac = _make_page()
    try:
        _show_page(page, qapp)
        page._toggle()
        assert ac.start_calls == 1
        assert ac.running is True
        assert page.toggle_btn.text() == "Parar Auto-Clicker"
        assert page.status_title.text() == "Auto-Clicker Ativo!"
        _assert_status_composition(page)

        page._toggle()
        assert ac.stop_calls == 1
        assert ac.running is False
        assert page.toggle_btn.text() == "Iniciar Auto-Clicker"
        assert page.status_title.text() == "Auto-Clicker Desligado"
        _assert_status_composition(page)
    finally:
        _close_page(page)
