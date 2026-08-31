"""Issue #88: o botão de excluir macro NUNCA aparece vazio.

Antes: `QPushButton("")` 32×32 sem texto, ícone, tooltip ou accessible
name — um alvo destrutivo invisível. Agora: rótulo textual "Excluir"
(ícone vetorial do subset não inclui lixeira; ícone indisponível nunca
derruba a UI — contrato de app/ui/icons.py), tooltip explicativo,
accessible name e descrição — identificável sem depender só da cor,
função compreensível ANTES do clique. Semântica de persistência
(`me.delete`) inalterada.
"""

import pytest
from PyQt5.QtWidgets import QApplication, QPushButton

import app.mouse_hub_app as app_module
from app.mouse_hub_app import MacrosPage

DELETE_LABEL = getattr(app_module, "_MACRO_DELETE_LABEL", None)
DELETE_TOOLTIP = getattr(app_module, "_MACRO_DELETE_TOOLTIP", None)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class FakeMe:
    """Motor fake com UMA macro gravada (lista não vazia)."""

    playing = False
    playback_error = None

    def __init__(self):
        self.deleted = []

    def list_all(self):
        return {
            "combo_1": {"count": 12, "created": "2026-08-29T00:00:00"},
        }

    def delete(self, name):
        self.deleted.append(name)
        return True

    def cleanup(self):
        pass


def _make_page(qapp):
    page = MacrosPage(FakeMe(), None, caps_provider=None)
    return page


def _delete_buttons(page):
    return [
        b
        for b in page.macro_list_widget.findChildren(QPushButton)
        if b.text() == DELETE_LABEL
    ]


class TestBotaoExcluirNuncaVazio:
    def test_constantes_definidas(self):
        assert DELETE_LABEL, "_MACRO_DELETE_LABEL não definido"
        assert DELETE_TOOLTIP, "_MACRO_DELETE_TOOLTIP não definido"

    def test_botao_tem_rotulo_textual(self, qapp):
        """Com uma macro na lista, o botão de excluir tem rótulo
        compreensível — nunca vazio."""
        page = _make_page(qapp)
        matches = _delete_buttons(page)
        assert matches, "nenhum botão de excluir com rótulo encontrado"
        assert matches[0].text() == DELETE_LABEL
        assert matches[0].text().strip() != ""

    def test_tooltip_e_acessibilidade(self, qapp):
        """Função identificável ANTES do clique: tooltip + accessible
        name/description."""
        page = _make_page(qapp)
        btn = _delete_buttons(page)[0]
        assert btn.toolTip() == DELETE_TOOLTIP
        assert btn.accessibleName() != ""
        assert btn.accessibleDescription() != ""

    def test_hover_mantem_funcao_identificavel_sem_so_cor(self, qapp):
        """O botão tem borda própria e rótulo — a affordance não depende
        exclusivamente da cor no hover/focus (offscreen não testa paint,
        mas garante rótulo + tooltip presentes)."""
        page = _make_page(qapp)
        btn = _delete_buttons(page)[0]
        assert btn.text() != ""
        assert btn.toolTip() != ""

    def test_acao_destrutiva_preservada(self, qapp):
        """Semântica de persistência inalterada: clicar exclui via
        me.delete(name) e a lista é re-renderizada."""
        me = FakeMe()
        page = MacrosPage(me, None, caps_provider=None)
        btn = _delete_buttons(page)[0]
        btn.click()
        assert me.deleted == ["combo_1"]
