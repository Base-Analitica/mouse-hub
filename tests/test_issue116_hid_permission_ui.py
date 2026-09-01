"""Issue #116: a CTA HID não deve se passar por indicador de estado.

A página deve manter o motivo textual visível, mas só oferecer o botão quando
uma falha de permissão puder ser resolvida pelo fluxo polkit. Os cenários usam
os fakes existentes e não requerem um mouse físico.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PyQt5.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _show(page, qapp):
    page.show()
    qapp.processEvents()


def _close(page):
    page.close()
    page.deleteLater()


def test_granted_mantem_status_sem_cta(qapp, monkeypatch):
    from tests.test_hid_permission_helper import _make_page

    page, _, _ = _make_page(qapp, monkeypatch, hid_available=True)
    _show(page, qapp)

    assert "ativo" in page._permission_status.text().lower()
    assert not page._permission_btn.isVisible()
    assert not page._permission_btn.isEnabled()
    _close(page)


def test_falta_de_permissao_mantem_cta_acionavel(qapp, monkeypatch):
    from tests.test_hid_permission_helper import _make_page

    page, _, _ = _make_page(qapp, monkeypatch, hid_available=False)
    _show(page, qapp)

    assert page._permission_btn.isVisible()
    assert page._permission_btn.isEnabled()
    assert "permiss" in page._permission_status.text().lower() or \
        "regra udev" in page._permission_status.text().lower()
    _close(page)


def test_causa_nao_acionavel_oculta_cta_e_preserva_causa(qapp, monkeypatch):
    from mouse_hub.core.operation import OperationStatus
    from tests.test_hid_permission_helper import _make_page

    page, _, _ = _make_page(qapp, monkeypatch, hid_available=False)
    page.state._core._invalidate_access_state(OperationStatus.FAILED)
    page.state._caps = page.state._evaluate()
    page._sync_permission_ui()
    _show(page, qapp)

    assert "outra causa" in page._permission_status.text().lower()
    assert not page._permission_btn.isVisible()
    assert not page._permission_btn.isEnabled()
    _close(page)


def test_estado_de_hardware_ausente_oculta_cta(qapp):
    from app import mouse_hub_app as app_module

    page = app_module.SettingsPage(None, None, None, None, state=None)
    _show(page, qapp)

    assert "não disponível" in page._permission_status.text().lower()
    assert not page._permission_btn.isVisible()
    assert not page._permission_btn.isEnabled()
    _close(page)
