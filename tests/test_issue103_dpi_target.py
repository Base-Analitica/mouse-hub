"""Issue #103: o slider de DPI é controle de ENTRADA ("valor desejado"),
não representação implícita do estado aplicado.

Estados a manter separados:
  * valor atual/aplicado  → hero (readback confirmado ou "aguardando");
  * valor solicitado/editável → slider + legenda de papel explícito;
  * valor persistido      → nunca exibido como hardware aplicado sem
    confirmação (issue #4 / persister).

A legenda do papel é PERMANENTE: o slider nunca é readback, mesmo com
valor confirmado. Em 760×560 a semântica não pode desaparecer.
"""

import pytest
from PyQt5.QtWidgets import QApplication, QLabel

from mouse_hub.core.dpi_persistence import NeverDpiPersister
from mouse_hub.core.mouse_controller import MouseController as CoreMouseController
from tests.fakes import FakeSystemInput, fake_g403_device

import app.mouse_hub_app as app_module
from app.mouse_hub_app import DPIPage, MouseController, MouseCoreState

DPI_TARGET_LABEL = getattr(app_module, "_DPI_TARGET_LABEL", None)
HERO_WAITING = "AGUARDANDO LEITURA DO HARDWARE"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _discovered(hidraw="/dev/hidraw2"):
    return fake_g403_device(hidraw=hidraw)


def _make_page(qapp, monkeypatch, hid=None):
    from tests.fakes import FakeHidAccess

    hid = hid if hid is not None else FakeHidAccess()
    core = CoreMouseController(
        hid=hid,
        system_input=FakeSystemInput(),
        dpi_persister=NeverDpiPersister(),
    )
    state = MouseCoreState(core)
    monkeypatch.setattr(
        app_module, "discover_candidates", lambda: [_discovered()]
    )
    state.refresh()
    page = DPIPage(MouseController(), state=state)
    return state, hid, page


def _find_target_label(page):
    """Localiza o QLabel com a legenda de papel do slider."""
    assert DPI_TARGET_LABEL, (
        "app.mouse_hub_app._DPI_TARGET_LABEL não definido (T2.1)"
    )
    labels = page.findChildren(QLabel)
    return [
        lb for lb in labels if lb.text().strip() == DPI_TARGET_LABEL.strip()
    ]


class TestSliderTemPapelExplicito:
    """A legenda de papel existe nos dois estados do readback."""

    def test_legenda_presente_sem_readback(self, qapp, monkeypatch):
        """Readback desconhecido: slider posicionado não pode ser lido
        como DPI atual — a legenda de 'valor desejado' está visível."""
        state, hid, page = _make_page(qapp, monkeypatch)
        assert state.applied_dpi is None
        page.show()
        try:
            qapp.processEvents()
            matches = _find_target_label(page)
            assert matches, "legenda de valor desejado ausente sem readback"
            assert matches[0].isVisible()
        finally:
            page.hide()

    def test_legenda_presente_com_readback_confirmado(
        self, qapp, monkeypatch
    ):
        """Com valor confirmado a legenda continua: o slider segue sendo
        entrada, não readback."""
        state, hid, page = _make_page(qapp, monkeypatch)
        page.dpi_input.setText("1200")
        page.apply_btn.click()
        assert state.applied_dpi == 1200
        page.show()
        try:
            qapp.processEvents()
            matches = _find_target_label(page)
            assert matches, "legenda de valor desejado ausente com readback"
            assert matches[0].isVisible()
        finally:
            page.hide()


class TestHeroReservadoAoReadback:
    """O hero não é promovido a 'aplicado' pelo movimento do slider."""

    def test_preview_nao_promove_hero_sem_confirmacao(
        self, qapp, monkeypatch
    ):
        """Arrastar (valueChanged sem commit) atualiza o valor em
        consideração, mas o sub-rótulo continua 'aguardando leitura' —
        a posição do slider não vira estado aplicado."""
        state, hid, page = _make_page(qapp, monkeypatch)
        assert state.applied_dpi is None
        page.slider.setValue(1600)  # preview apenas
        assert page.dpi_value.text() == "1600"
        # Sub-rótulo do hero permanece honesto.
        assert page.dpi_state.text() == HERO_WAITING
        # E nada foi aplicado fisicamente.
        assert state.applied_dpi is None

    def test_legenda_nao_some_apos_falha(self, qapp, monkeypatch):
        """Falha real de escrita: hero volta a UNKNOWN; legenda segue
        descrevendo o papel de entrada."""
        from tests.fakes import FakeHidAccess

        hid = FakeHidAccess()
        hid.ack_timeout = True
        state, hid2, page = _make_page(qapp, monkeypatch, hid=hid)
        page.dpi_input.setText("1400")
        page.apply_btn.click()
        assert state.applied_dpi is None
        assert page.dpi_value.text() == "—"
        matches = _find_target_label(page)
        assert matches, "legenda de valor desejado ausente após falha"


class TestSemanticaNaJanelaPequena:
    """760×560: a mesma semântica (issue #103 — desktop e small)."""

    def test_legenda_visivel_em_760x560(self, qapp, monkeypatch):
        state, hid, page = _make_page(qapp, monkeypatch)
        page.resize(700, 500)
        page.show()
        try:
            qapp.processEvents()
            matches = _find_target_label(page)
            assert matches, "legenda ausente em janela pequena"
            assert matches[0].isVisible()
        finally:
            page.hide()
