"""Issue #100: Perfis em 760×560 — sem overlap, sem h-scrollbar, form
abaixo da grade, NO ESTADO DE CAPTURA (a mesma sequência do pipeline:
switch de páginas → resize → switch → UM processEvents → grab), que é
o frame que vira artefato visual.

Causa raiz medida: 3 colunas fixas de cards (mín 140px + 2×16px de
espaço + margens) não cabem em viewport ~562px; o relayout transitório
do QGridLayout é capturado com cards sobrepostos, widget 570px > 562px
(h-bar pisca) e formulário subindo sobre a grade.

Fix: colunas derivadas da largura disponível (3/2/1). Desktop mantém 3.
"""

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QScrollArea

import app.mouse_hub_app as app_module


def _settle(qapp, window, ms=150):
    """Dá ao event loop tempo para assentar layouts (deleteLater,
    invalidações de relayout). O frame assentado é o que interessa."""
    qapp.processEvents()
    QTest.qWait(ms)
    qapp.processEvents()


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(scope="module")
def window(qapp):
    from tests.fakes import FakeHidAccess, FakeSystemInput, fake_g403_device
    from mouse_hub.core.mouse_controller import MouseController
    from mouse_hub.core.dpi_persistence import NeverDpiPersister

    class DummyMonitor:
        def __init__(self, out):
            pass

        def start(self):
            return True

        def stop(self):
            pass

    mp = pytest.MonkeyPatch()
    mp.setattr(app_module, "UdevHidrawMonitor", DummyMonitor)
    mp.setattr(
        app_module, "discover_candidates", lambda: [fake_g403_device()]
    )

    def make_state():
        core = MouseController(
            hid=FakeHidAccess(),
            system_input=FakeSystemInput(),
            dpi_persister=NeverDpiPersister(),
        )
        return app_module.MouseCoreState(core)

    mp.setattr(app_module, "build_mouse_state", make_state)
    w = app_module.MouseHubApp()
    yield w
    w.close()
    mp.undo()


def _scroll_area(page):
    p = page.parentWidget()
    while p is not None and not isinstance(p, QScrollArea):
        p = p.parentWidget()
    return p


def _card_overlaps(page):
    cards = [d["card"] for d in page.profile_cards.values()]
    rects = [c.geometry() for c in cards]
    pairs = []
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            it = rects[i].intersected(rects[j])
            if it.width() > 0 and it.height() > 0:
                pairs.append((i, j))
    return cards, rects, pairs


def _form_label(page):
    lay = page.layout()
    for k in range(lay.count()):
        wd = lay.itemAt(k).widget()
        if wd is not None and wd.text() == "Criar / Editar Perfil":
            return wd
    return None


class TestEstadoDeCaptura:
    """A sequência exata do pipeline de screenshots não pode capturar
    overlap/overflow na página de Perfis."""

    def test_small_760_primeiro_frame_sem_overlap_nem_hbar(
        self, qapp, window
    ):
        window.resize(1050, 680)
        window.show()
        qapp.processEvents()
        for i in range(window.stack.count()):
            window._switch_page(i)
            qapp.processEvents()
        window.resize(760, 560)
        qapp.processEvents()
        for i in range(window.stack.count()):
            window._switch_page(i)
            _settle(qapp, window)
            if i != 5:
                continue
            page = window.profiles_page
            cards, rects, pairs = _card_overlaps(page)
            assert not pairs, f"cards sobrepostos no frame de captura: {pairs}"
            sa = _scroll_area(page)
            assert sa is not None
            hbar = sa.horizontalScrollBar()
            assert not hbar.isVisible(), "h-scrollbar visível no frame"
            assert sa.widget().width() <= sa.viewport().width() + 1, (
                "conteúdo mais largo que o viewport no frame de captura"
            )
            fl = _form_label(page)
            assert fl is not None
            grid_bottom = max(r.bottom() for r in rects)
            assert fl.geometry().top() >= grid_bottom, (
                "heading Criar / Editar Perfil começa antes do fim da grade"
            )
            assert fl.isVisible()

    def test_desktop_1050_sem_overlap(self, qapp, window):
        window.resize(1050, 680)
        window.show()
        qapp.processEvents()
        window._switch_page(5)
        _settle(qapp, window)
        page = window.profiles_page
        cards, rects, pairs = _card_overlaps(page)
        assert not pairs
        # 3 colunas no desktop (largura útil ~812 ≥ 3×140+2×16)
        assert len({c.geometry().x() for c in cards}) == 3


class TestReflowPorLargura:
    def test_colunas_respondem_a_resize(self, qapp, window):
        window.resize(1050, 680)
        window.show()
        qapp.processEvents()
        window._switch_page(5)
        _settle(qapp, window)
        page = window.profiles_page
        cards_desktop = [d["card"] for d in page.profile_cards.values()]
        assert len({c.geometry().x() for c in cards_desktop}) == 3
        window.resize(760, 560)
        _settle(qapp, window)
        cards_small = [d["card"] for d in page.profile_cards.values()]
        xs = {c.geometry().x() for c in cards_small}
        assert len(xs) <= 2, f"esperado <= 2 colunas em 760px, veio {len(xs)}"
