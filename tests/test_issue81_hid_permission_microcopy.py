"""Regressão da microcopy do fluxo gráfico de permissões HID (issue #81)."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt5.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _permission_group(page):
    from PyQt5.QtWidgets import QGroupBox

    return next(
        group
        for group in page.findChildren(QGroupBox)
        if "Permissões HID" in group.title()
    )


def _hid_info(page):
    from PyQt5.QtWidgets import QLabel

    group = _permission_group(page)
    return group.findChildren(QLabel)[0]


def _destroy(page, qapp):
    page.deleteLater()
    qapp.processEvents()


def test_hid_intro_explains_graphical_authorization_flow(qapp, monkeypatch):
    from tests.test_hid_permission_helper import _make_page

    page, _state, _calls = _make_page(qapp, monkeypatch, hid_available=False)
    try:
        text = " ".join(_hid_info(page).text().split())
        lowered = text.lower()

        assert "dpi físico" in lowered
        assert "mouse hub" in lowered
        assert "acesso hid" in lowered
        assert "autorização administrativa" in lowered
        assert "regra necessária" in lowered
        assert "conceder acesso ao hardware" in lowered
    finally:
        _destroy(page, qapp)


def test_hid_intro_removes_obsolete_manual_instructions_and_orphan_punctuation(
    qapp, monkeypatch
):
    from tests.test_hid_permission_helper import _make_page

    page, _state, _calls = _make_page(qapp, monkeypatch, hid_available=False)
    try:
        text = _hid_info(page).text()
        lowered = text.lower()

        assert "crie uma regra" not in lowered
        assert "alterar permissões manualmente" not in lowered
        assert "terminal" not in lowered
        assert not text.rstrip().endswith(":")
    finally:
        _destroy(page, qapp)


def test_hid_permission_states_and_button_contract_remain_unchanged(
    qapp, monkeypatch
):
    from tests.test_hid_permission_helper import _make_page

    available_page, _state, _calls = _make_page(
        qapp, monkeypatch, hid_available=True
    )
    denied_page, _state, _calls = _make_page(
        qapp, monkeypatch, hid_available=False
    )
    try:
        assert not available_page._permission_btn.isEnabled()
        assert "Acesso HID já concedido" in available_page._permission_btn.text()
        assert "ativo" in available_page._permission_status.text().lower()

        assert denied_page._permission_btn.isEnabled()
        assert "Conceder acesso ao hardware" in denied_page._permission_btn.text()
        assert "Clique abaixo" in denied_page._permission_status.text()
    finally:
        _destroy(available_page, qapp)
        _destroy(denied_page, qapp)


@pytest.mark.parametrize("size", [(1050, 680), (760, 560)], ids=["desktop", "small"])
def test_hid_intro_fits_official_viewports(qapp, monkeypatch, size):
    from tests.test_hid_permission_helper import _make_page

    page, _state, _calls = _make_page(qapp, monkeypatch, hid_available=False)
    try:
        page.resize(*size)
        page.show()
        qapp.processEvents()

        group = _permission_group(page)
        info = _hid_info(page)
        assert info.isVisible()
        assert info.height() > 0
        assert info.geometry().left() >= 0
        assert info.geometry().right() <= group.rect().right()
        assert group.geometry().right() <= page.rect().right()
    finally:
        _destroy(page, qapp)
