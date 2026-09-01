"""Issue #79: os rótulos do seletor não dependem de whitespace manual.

Os testes usam uma AutoClickerPage real, controlador fake e Qt offscreen.
A seleção, o gating e a geometria existente também devem permanecer intactos.
"""

from __future__ import annotations

import os

import pytest

from mouse_hub.core.capabilities import (
    CAPABILITY_NAMES,
    CapabilityModel,
    CapabilityState,
    with_overrides,
)

pytest.importorskip("PyQt5")
from PyQt5.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    yield app


def all_available_state() -> CapabilityState:
    model = CapabilityModel(**{name: (lambda: True) for name in CAPABILITY_NAMES})
    return model.evaluate()


def state_with_autoclicker(available: bool, reason: str = "") -> CapabilityState:
    return with_overrides(
        all_available_state(),
        {"autoclick_available": (available, reason)},
    )


class FakeMC:
    current_dpi = 800
    current_sensitivity = 50


class FakeAcState:
    value = "stopped"


class FakeAc:
    def __init__(self, button=1):
        self.cps = 10
        self.button = button
        self.state = FakeAcState()
        self.running = False
        self.error = None

    def start(self):
        pass

    def stop(self):
        pass

    def cleanup(self):
        pass


def make_page(state_provider, button=1):
    import app.mouse_hub_app as app_module

    ac = FakeAc(button=button)
    page = app_module.AutoClickerPage(
        FakeMC(),
        ac,
        None,
        caps_provider=state_provider,
    )
    return page


def dispose_page(page):
    page.timer.stop()
    page.close()
    page.deleteLater()


def style_background(button):
    for line in button.styleSheet().splitlines():
        line = line.strip()
        if line.startswith("background:"):
            return line.split(":", 1)[1].strip().rstrip(";")
    raise AssertionError("background não encontrado no estilo do botão")


def button_row(page):
    for index in range(page.layout().count()):
        candidate = page.layout().itemAt(index).layout()
        if candidate is not None and all(
            candidate.indexOf(button) >= 0 for button, _ in page.btn_buttons
        ):
            return candidate
    raise AssertionError("linha de seleção dos botões não encontrada")


def test_button_labels_are_exact_names_without_manual_whitespace(qapp):
    page = make_page(lambda: state_with_autoclicker(True))
    try:
        labels = [button.text() for button, _ in page.btn_buttons]

        assert labels == ["Esquerdo", "Meio", "Direito"]
        assert all(label == label.strip() for label in labels)
        assert all("  " not in label for label in labels)
    finally:
        dispose_page(page)


def test_button_codes_and_active_style_remain_stable(qapp):
    from app.mouse_hub_app import COLORS

    page = make_page(lambda: state_with_autoclicker(True))
    try:
        assert [code for _, code in page.btn_buttons] == [1, 2, 3]
        assert style_background(page.btn_buttons[0][0]) == COLORS["accent"]
        assert style_background(page.btn_buttons[1][0]) == COLORS["bg_card"]
        assert style_background(page.btn_buttons[2][0]) == COLORS["bg_card"]
        assert button_row(page).spacing() == 12

        page._set_button(3)

        assert page.ac.button == 3
        assert style_background(page.btn_buttons[0][0]) == COLORS["bg_card"]
        assert style_background(page.btn_buttons[1][0]) == COLORS["bg_card"]
        assert style_background(page.btn_buttons[2][0]) == COLORS["accent"]
    finally:
        dispose_page(page)


@pytest.mark.parametrize("selected", [1, 2, 3])
def test_initial_selection_style_matches_controller(qapp, selected):
    from app.mouse_hub_app import COLORS

    page = make_page(lambda: state_with_autoclicker(True), button=selected)
    try:
        active_codes = [
            code
            for button, code in page.btn_buttons
            if style_background(button) == COLORS["accent"]
        ]
        assert active_codes == [selected]
    finally:
        dispose_page(page)


def test_button_clicks_keep_selection_flow(qapp):
    from app.mouse_hub_app import COLORS

    page = make_page(lambda: state_with_autoclicker(True))
    try:
        for button, code in page.btn_buttons:
            button.click()
            assert page.ac.button == code
            assert page.status_sub.text() == f"10 CPS — Botão {code}"
            active_codes = [
                selected_code
                for selected_button, selected_code in page.btn_buttons
                if style_background(selected_button) == COLORS["accent"]
            ]
            assert active_codes == [code]
    finally:
        dispose_page(page)


def test_button_gating_still_targets_all_three_widgets(qapp):
    unavailable = make_page(
        lambda: state_with_autoclicker(False, "automação indisponível")
    )
    available = make_page(lambda: state_with_autoclicker(True))
    try:
        assert all(button.isEnabled() is False for button, _ in unavailable.btn_buttons)
        assert all(button.isEnabled() is True for button, _ in available.btn_buttons)
    finally:
        dispose_page(unavailable)
        dispose_page(available)


@pytest.mark.parametrize("size", [(1050, 680), (760, 560)])
def test_button_layout_stays_balanced_in_official_viewports(qapp, size):
    page = make_page(lambda: state_with_autoclicker(True))
    try:
        page.resize(*size)
        page.show()
        qapp.processEvents()

        geometries = [button.geometry() for button, _ in page.btn_buttons]
        assert all(rect.height() == 44 for rect in geometries)
        assert all(rect.left() >= 0 and rect.right() <= page.width() for rect in geometries)
        assert geometries[0].left() < geometries[1].left() < geometries[2].left()
        assert not geometries[0].intersects(geometries[1])
        assert not geometries[1].intersects(geometries[2])
    finally:
        dispose_page(page)
