"""Issue #80: o valor normal de CPS não representa um estado de warning."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PyQt5")
from PyQt5.QtWidgets import QApplication, QLabel  # noqa: E402

from app import mouse_hub_app as app_module  # noqa: E402
from app.ui.theme import COLORS  # noqa: E402
from tests.test_hid_permission_helper import _make_page  # noqa: E402
from tests.test_issue7_ui_caps import (  # noqa: E402
    FakeAc,
    FakeMC,
    FakeSvc,
    all_available_model,
)


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _make_autoclicker_page(qapp, cps=10, caps=None):
    mc = FakeMC()
    ac = FakeAc()
    ac.cps = cps
    if caps is None:
        caps = all_available_model().evaluate()
    page = app_module.AutoClickerPage(
        mc,
        ac,
        FakeSvc(),
        caps_provider=lambda: caps,
    )
    return page, ac


def _dispose(widget, qapp):
    widget.timer.stop()
    widget.close()
    widget.deleteLater()
    qapp.processEvents()


@pytest.mark.parametrize("cps", [1, 25, 50])
def test_normal_cps_display_uses_accent_not_warning(qapp, cps):
    page, _ = _make_autoclicker_page(qapp, cps=cps)
    try:
        assert page.cps_display.text() == str(cps)
        style = page.cps_display.styleSheet()
        assert f"color: {COLORS['accent_light']};" in style
        assert COLORS["warning"] not in style
    finally:
        _dispose(page, qapp)


@pytest.mark.parametrize("cps", [1, 25, 50])
def test_cps_slider_preserves_display_unit_and_status(qapp, cps):
    page, _ = _make_autoclicker_page(qapp)
    try:
        page.cps_slider.setValue(cps)
        qapp.processEvents()
        assert page.cps_display.text() == str(cps)
        assert any(label.text() == "CPS" for label in page.findChildren(QLabel))
        assert f"{cps} CPS" in page.status_sub.text()
    finally:
        _dispose(page, qapp)


def test_unavailable_capability_keeps_cps_as_normal_value(qapp):
    caps = all_available_model(
        autoclick_available=(False, "X11 ausente")
    ).evaluate()
    page, _ = _make_autoclicker_page(qapp, caps=caps)
    try:
        assert not page.cps_slider.isEnabled()
        assert not page.toggle_btn.isEnabled()
        assert all(not button.isEnabled() for button, _ in page.btn_buttons)
        assert "indisponível" in page.caps_hint.text().lower()
        assert "X11 ausente" in page.caps_hint.text()
        assert COLORS["warning"] not in page.cps_display.styleSheet()
    finally:
        _dispose(page, qapp)


def test_settings_permission_attention_still_uses_warning(qapp, monkeypatch):
    page, state, _ = _make_page(qapp, monkeypatch, hid_available=False)
    try:
        assert COLORS["warning"] in page._permission_status.styleSheet()
        assert page._permission_btn.isEnabled()
    finally:
        page.close()
        page.deleteLater()
        qapp.processEvents()
