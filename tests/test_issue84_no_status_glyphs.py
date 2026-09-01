"""Issue #84: nenhum glifo Unicode de status (✔/⚠) como iconografia
de UI em `app/mouse_hub_app.py` — migração vector-only completa.

Semântica preservada: as mensagens mantêm texto + cor semântica
(mc_green para sucesso, warning para parcial/atenção, danger para
falha). O subconjunto vetorial (app/ui/icons.py) cobre títulos de
página; os avisos pontuais ficam em texto puro — sem fallback
dependente de fonte.
"""

import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "app" / "mouse_hub_app.py"


class TestSemGlifosDeStatus:
    def test_nenhuma_ocorrencia_de_check_ou_warning(self):
        """Critério de aceite do issue: zero `✔`/`⚠` no app."""
        src = APP.read_text(encoding="utf-8")
        for ch in ("✔", "⚠"):
            assert ch not in src, (
                f"glifo {ch!r} encontrado — iconografia de status deve ser "
                "vetorial (app/ui/icons.py) ou texto puro"
            )

    def test_nenhum_emoji_de_mao_apos_migracao(self):
        """A substituição não pode trocar um glifo por outro emoji."""
        src = APP.read_text(encoding="utf-8")
        assert "✋" not in src, "substituição deve ser texto puro, não outro emoji"

    def test_sem_condicionais_vazias_de_prefixo(self):
        """Padrão residual `("" if ... else "")` não pode sobrar."""
        src = APP.read_text(encoding="utf-8")
        assert not re.search(
            r'\("" if .+? else ""\)', src
        ), "condicional de prefixo vazia é resíduo da migração"

    def test_semantica_de_cor_preservada(self):
        """As mensagens antes marcadas por glifo continuam coloridas
        (mc_green/warning/danger) — honestidade visual mantida."""
        src = APP.read_text(encoding="utf-8")
        assert "PARCIALMENTE" in src, "estado parcial continua explícito"
        for token in ('COLORS["mc_green"]', 'COLORS["warning"]',
                      'COLORS["danger"]'):
            assert token in src, f"cor semântica {token} preservada"

    def test_erro_do_clicker_usa_alerta_vetorial(self):
        """O indicador isolado de erro usa o ícone vetorial `alert`."""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication

        import app.mouse_hub_app as app_module

        qapp = QApplication.instance() or QApplication([])

        class FailedState:
            value = "failed"

        class FailedAc:
            cps = 10
            button = 1
            state = FailedState()
            running = False
            error = "falha fake"

        class Focused:
            focused = False

        class Service:
            class window_service:
                @staticmethod
                def is_focused(patterns):
                    return Focused()

        page = app_module.AutoClickerPage(None, FailedAc(), Service())
        page._update()
        qapp.processEvents()

        assert page.status_title.text() == "Auto-Clicker com erro"
        assert not page.status_icon.pixmap().isNull()

    def test_erro_do_clicker_fallback_sem_subset_nao_quebra(self, monkeypatch):
        """Sem a fonte subset, o texto de erro continua sendo exibido."""
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication

        import app.mouse_hub_app as app_module

        class FailedState:
            value = "failed"

        class FailedAc:
            cps = 10
            button = 1
            state = FailedState()
            running = False
            error = "falha fake"

        class Focused:
            focused = False

        class Service:
            class window_service:
                @staticmethod
                def is_focused(patterns):
                    return Focused()

        monkeypatch.setattr(app_module.ui_icons, "icon", lambda *args, **kwargs: None)
        qapp = QApplication.instance() or QApplication([])
        page = app_module.AutoClickerPage(None, FailedAc(), Service())
        page._update()
        qapp.processEvents()

        assert page.status_title.text() == "Auto-Clicker com erro"
        assert page.status_sub.text() == "Falha: falha fake"
        assert page.status_icon.text() == ""
