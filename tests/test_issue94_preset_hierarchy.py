# -*- coding: utf-8 -*-
"""Issue #94 — hierarquia visual dos presets de DPI.

Os presets continuam sendo um único alvo clicável, mas nome/contexto e
valor passam a ter pesos tipográficos independentes. Dashboard e DPI devem
usar a mesma composição sem duplicar os valores do core.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QScrollArea

from app.mouse_hub_app import (
    DashboardPage,
    DPIPage,
    MouseController,
    PresetButton,
)
from app.ui.theme import TYPE_SCALE
from mouse_hub.core.constants import DPI_PRESETS


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _FocusResult:
    focused = False


class _WindowService:
    def is_focused(self, patterns):
        return _FocusResult()


class _Service:
    window_service = _WindowService()


class _ClickerState:
    value = "stopped"


class _Clicker:
    state = _ClickerState()


def _dashboard(qapp):
    page = DashboardPage(MouseController(), _Clicker(), None, _Service())
    page.timer.stop()
    page.show()
    qapp.processEvents()
    return page


def _dpi_page(qapp):
    page = DPIPage(MouseController())
    page.show()
    qapp.processEvents()
    return page


def _expected_presets():
    return [
        ("CS:GO AWP", DPI_PRESETS["Low (CS:GO AWP)"]),
        ("FPS Geral", DPI_PRESETS["Medium (FPS Geral)"]),
        ("Minecraft PvP", DPI_PRESETS["High (Minecraft PvP)"]),
        ("Flick Shots", DPI_PRESETS["Ultra (Flick Shots)"]),
        ("Max Speed", DPI_PRESETS["Max Speed"]),
    ]


def test_preset_button_separates_context_and_value_typography(qapp):
    button = PresetButton("CS:GO AWP", 400)
    button.show()
    qapp.processEvents()

    assert isinstance(button, QPushButton)
    assert button.name_label.text() == "CS:GO AWP"
    assert button.value_label.text() == "400 DPI"
    assert button.name_label.objectName() == "presetName"
    assert button.value_label.objectName() == "presetValue"
    assert isinstance(button.findChild(QLabel, "presetName"), QLabel)
    assert isinstance(button.findChild(QLabel, "presetValue"), QLabel)

    name_style = button.name_label.styleSheet()
    value_style = button.value_label.styleSheet()
    assert name_style != value_style
    assert f"font-size: {TYPE_SCALE['caption']}px" in name_style
    assert f"font-size: {TYPE_SCALE['subtitle']}px" in value_style
    assert "font-weight: 900" in value_style
    assert "font-weight: 600" in name_style
    assert button.name_label.testAttribute(Qt.WA_TransparentForMouseEvents)
    assert button.value_label.testAttribute(Qt.WA_TransparentForMouseEvents)


def test_preset_button_remains_one_click_target(qapp):
    button = PresetButton("FPS Geral", 800)
    clicked = []
    button.clicked.connect(lambda *_: clicked.append(True))

    button.click()

    assert clicked == [True]
    assert button.accessibleName() == "FPS Geral, 800 DPI"


def test_dashboard_quick_actions_use_shared_component_and_source_values(qapp):
    page = _dashboard(qapp)

    buttons = page.quick_preset_buttons
    assert all(isinstance(button, PresetButton) for button in buttons)
    assert [
        (button.name_label.text(), int(button.value_label.text().split()[0]))
        for button in buttons
    ] == _expected_presets()[:4]


def test_dpi_presets_use_shared_component_and_source_values(qapp):
    page = _dpi_page(qapp)

    assert [
        (name.strip(), dpi)
        for name, dpi, _button in page.preset_buttons
    ] == _expected_presets()
    assert all(isinstance(button, PresetButton) for _name, _dpi, button in page.preset_buttons)
    assert [
        (button.name_label.text(), button.value_label.text())
        for _name, _dpi, button in page.preset_buttons
    ] == [(name, f"{dpi} DPI") for name, dpi in _expected_presets()]


def test_dashboard_and_dpi_share_the_same_preset_language(qapp):
    dashboard_button = _dashboard(qapp).quick_preset_buttons[0]
    dpi_button = _dpi_page(qapp).preset_buttons[0][2]

    assert dashboard_button.name_label.styleSheet() == dpi_button.name_label.styleSheet()
    assert dashboard_button.value_label.styleSheet() == dpi_button.value_label.styleSheet()
    assert dashboard_button.styleSheet() == dpi_button.styleSheet()
    assert not dashboard_button.findChildren(QPushButton)


@pytest.mark.parametrize("size", [(1050, 680), (760, 560)])
def test_shared_preset_buttons_fit_real_scroll_container(qapp, size):
    width, height = size
    for page_factory, buttons in (
        (_dashboard, lambda page: page.quick_preset_buttons),
        (_dpi_page, lambda page: [entry[2] for entry in page.preset_buttons]),
    ):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = page_factory(qapp)
        scroll.setWidget(page)
        scroll.resize(width, height)
        scroll.show()
        qapp.processEvents()

        page_buttons = buttons(page)
        assert not scroll.horizontalScrollBar().isVisible()
        assert page.width() <= scroll.viewport().width() + 2
        assert all(button.height() <= 70 for button in page_buttons)
        assert all(
            button.rect().contains(button.name_label.geometry())
            and button.rect().contains(button.value_label.geometry())
            for button in page_buttons
        )

        scroll.takeWidget()
        page.close()
        scroll.close()
