"""Issue #66 — design system central + layout responsivo.

Invariants do craft (impeccable, modo Operate):
* nenhuma fonte fora da escala tipográfica nomeada;
* nenhuma cor fora do token central;
* TODA página vive em scroll — janela pequena jamais sobrepõe widgets;
* o app é utilizável no tamanho mínimo da janela.

Testes determinísticos (offscreen, monitor de hotplug falso)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "app" / "mouse_hub_app.py"


@pytest.fixture(scope="module")
def qapp():
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def window(qapp):
    from app import mouse_hub_app as app_module
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
    mp.setattr(app_module, "discover_candidates", lambda: [fake_g403_device()])

    def make_state():
        core = MouseController(hid=FakeHidAccess(),
                               system_input=FakeSystemInput(),
                               dpi_persister=NeverDpiPersister())
        return app_module.MouseCoreState(core)

    mp.setattr(app_module, "build_mouse_state", make_state)
    w = app_module.MouseHubApp()
    w.show()
    qapp.processEvents()
    yield w
    w.close()
    mp.undo()


# ── Design system: fonte única de valores ────────────────────

def test_toda_fonte_do_app_esta_na_escala():
    src = APP.read_text()
    sizes = {int(x) for x in re.findall(r"font-size: (\d+)px", src)}
    from app.ui.theme import TYPE_SCALE
    assert sizes, "nenhuma fonte encontrada?"
    assert sizes <= set(TYPE_SCALE.values()), \
        f"tamanhos fora da escala: {sorted(sizes - set(TYPE_SCALE.values()))}"


def test_cores_do_app_sao_do_token_central():
    """O COLORS do app É o do tema — zero drift de cor."""
    from app.ui import theme
    from app import mouse_hub_app as app_module
    assert app_module.COLORS == theme.COLORS


def test_piso_de_legibilidade_respeitado():
    """10px é ilegível (craft floor) — piso da escala é 11."""
    src = APP.read_text()
    sizes = {int(x) for x in re.findall(r"font-size: (\d+)px", src)}
    assert min(sizes) >= 11


# ── Responsivo: scroll em tudo, nada sobreposto ──────────────

PAGES = 7  # dashboard, dpi, sens, clicker, macros, perfis, settings


def test_todas_as_paginas_em_scroll(window):
    from PyQt5.QtWidgets import QScrollArea
    for i in range(window.stack.count()):
        page = window.stack.widget(i)
        assert isinstance(page, QScrollArea), \
            f"página {i} não está em scroll: {type(page).__name__}"
        assert page.widgetResizable()


def test_janela_minima_nenhuma_pagina_estoura_largura(qapp, window):
    """No tamanho mínimo, o conteúdo de cada página nunca é mais largo
    que o viewport (sobreposição visual vinha daí)."""
    window.setMinimumSize(720, 520)
    window.resize(720, 520)
    for i in range(window.stack.count()):
        window._switch_page(i)
        qapp.processEvents()
        page = window.stack.widget(i)
        viewport_w = page.viewport().width()
        content_w = page.widget().width()
        assert content_w <= viewport_w + 2, \
            f"página {i}: conteúdo {content_w}px > viewport {viewport_w}px"


def test_sem_sobreposicao_entre_irmaos_no_tamanho_minimo(qapp, window):
    """Em cada página, filhos diretos do layout raiz não se intersectam
    (o bug original reportado pelo mantenedor)."""
    window.setMinimumSize(720, 520)
    window.resize(720, 520)
    for i in range(window.stack.count()):
        window._switch_page(i)
        qapp.processEvents()
        page = window.stack.widget(i).widget()  # conteúdo real
        lay = page.layout()
        if lay is None:
            continue
        rects = []
        for j in range(lay.count()):
            item = lay.itemAt(j)
            w = item.widget()
            if w is not None and w.isVisible():
                rects.append((j, w.geometry()))
        for a in range(len(rects)):
            for b in range(a + 1, len(rects)):
                ga, gb = rects[a][1], rects[b][1]
                inter = ga.intersected(gb)
                # contato de borda é ok; área é sobreposição
                assert inter.width() <= 0 or inter.height() <= 0, \
                    f"página {i}: itens {rects[a][0]} e {rects[b][0]} " \
                    f"sobrepostos: {ga} × {gb}"


def test_janela_minima_maior_que_o_piso_de_usabilidade(window):
    """720×520: sidebar (190) + pelo menos 500px de conteúdo útil."""
    assert window.minimumWidth() >= 720
    assert window.minimumHeight() >= 520
    assert 190 + 500 <= window.minimumWidth()


# ── Issue #117: microcopy do heading CPS ─────────────────────

def test_clicker_cps_heading_copy(qapp, window):
    """O heading do controle de velocidade expande a sigla em pt-BR
    consistente (sem mistura com inglês). O rótulo de unidade "CPS"
    do slider é outro widget e não faz parte da microcopy da issue."""
    from PyQt5.QtWidgets import QLabel
    window._switch_page(3)  # clicker
    qapp.processEvents()
    headings = [w for w in window.clicker_page.findChildren(QLabel)
                if "CPS (" in w.text()]
    assert headings, "heading CPS não encontrado na página do clicker"
    for w in headings:
        assert w.text() == "CPS (Cliques por segundo)", \
            f"microcopy inconsistente: {w.text()!r}"
