"""Issue #107: o CTA do Auto-Clicker conta a MESMA história do banner.

Contrato real do motor (core): iniciar sem o jogo em foco ARMA o engine
(BLOCKED_BY_FOCUS — cliques suprimidos até a janela permitida ganhar
foco). O CTA precisa comunicar isso — nunca parecer uma ação que entra
clicando, nem parecer inválida. Estados blocked/ready/running têm
representações distintas; desktop e small compartilham a semântica.
"""

import pytest
from PyQt5.QtWidgets import QApplication

import app.mouse_hub_app as app_module
from app.mouse_hub_app import AutoClickerPage

ARM_TEXT = getattr(app_module, "_CLICKER_ARM_TEXT", None)
START_TEXT = "Iniciar Auto-Clicker"
STOP_TEXT = "Parar Auto-Clicker"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _Focused:
    def __init__(self, focused):
        self.focused = focused


class FakeWindowService:
    def __init__(self, focused=False):
        self._focused = focused

    def is_focused(self, patterns):
        return _Focused(self._focused)


class FakeSvc:
    def __init__(self, focused=False):
        self.window_service = FakeWindowService(focused)


class FakeAcState:
    def __init__(self, value):
        self.value = value


class FakeAc:
    """Motor fake com estado mutável (superfície mínima da página)."""

    def __init__(self, state_value="stopped"):
        self._state_value = state_value
        self.running = state_value in ("running", "blocked_by_focus")
        self.cps = 10
        self.button = 1
        self.error = None

    @property
    def state(self):
        return FakeAcState(self._state_value)

    def start(self):
        pass

    def stop(self):
        self._state_value = "stopped"
        self.running = False


def _make_page(qapp, focused=False, state_value="stopped"):
    page = AutoClickerPage(
        None, FakeAc(state_value), FakeSvc(focused), caps_provider=None
    )
    page.timer.stop()
    page._update()  # render inicial com o estado do fake
    return page


@pytest.mark.parametrize(
    ("focused", "expected_text"),
    [(True, START_TEXT), (False, ARM_TEXT)],
)
def test_parar_reflete_cta_parado_imediatamente(qapp, focused, expected_text):
    """Parar deve renderizar a CTA do estado parado sem esperar o timer."""
    page = _make_page(qapp, focused=focused, state_value="running")

    page._toggle()

    assert page.ac.running is False
    assert page.toggle_btn.text() == expected_text


class TestCtaContaAMesmaHistoria:
    """Banner e CTA não podem comunicar instruções opostas."""

    def test_sem_minecraft_cta_diz_que_arma_e_aguarda(self, qapp):
        """Minecraft ausente + motor desligado: o CTA comunica ARMAR
        (o motor fica aguardando o jogo), não 'iniciar' genérico."""
        page = _make_page(qapp, focused=False)
        assert ARM_TEXT, "_CLICKER_ARM_TEXT não definido"
        assert "não detectado" in page.mc_status.text()
        assert page.toggle_btn.text() == ARM_TEXT

    def test_com_minecraft_cta_eh_iniciar(self, qapp):
        """Jogo em foco + motor desligado: CTA direto de iniciar."""
        page = _make_page(qapp, focused=True)
        assert "Detectado" in page.mc_status.text()
        assert page.toggle_btn.text() == START_TEXT

    def test_usuario_sabe_o_que_acontece_antes_de_clicar(self, qapp):
        """A copy do CTA explica o efeito real (armar e aguardar)."""
        page = _make_page(qapp, focused=False)
        text = page.toggle_btn.text().lower()
        assert "armar" in text or "aguarda" in text


class TestEstadosDistintos:
    """blocked/ready/running têm representações visuais distintas."""

    def test_running_mostra_parar(self, qapp):
        page = _make_page(qapp, focused=True, state_value="running")
        assert page.toggle_btn.text() == STOP_TEXT
        assert "Ativo" in page.status_title.text()

    def test_blocked_mostra_aguardando_jogo(self, qapp):
        page = _make_page(qapp, focused=False, state_value="blocked_by_focus")
        assert page.toggle_btn.text() == STOP_TEXT
        assert "Aguardando" in page.status_title.text()

    def test_stopped_sem_jogo_differe_de_ready(self, qapp):
        """O estado parado SEM jogo tem CTA próprio (não é o mesmo do
        estado pronto-com-jogo)."""
        page_no_game = _make_page(qapp, focused=False)
        page_ready = _make_page(qapp, focused=True)
        assert page_no_game.toggle_btn.text() != page_ready.toggle_btn.text()


class TestSemanticaNasJanelas:
    """Desktop e small compartilham o mesmo widget — a semântica não
    pode divergir entre tamanhos (checagem de sanidade)."""

    def test_texto_independe_do_tamanho(self, qapp):
        page = _make_page(qapp, focused=False)
        small = _make_page(qapp, focused=False)
        small.resize(700, 500)
        assert page.toggle_btn.text() == small.toggle_btn.text()
