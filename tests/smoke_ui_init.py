"""Smoke test: o app PyQt inicializa sob Xvfb sem exceção.

Executar: QT_QPA_PLATFORM=offscreen python3 -m unittest tests.smoke_ui_init
Não depende de mouse real nem de display físico.

Valores verificados:
- a janela constrói sem exceção e as páginas estão conectadas
- o AutomationService (core único) começa 100% lazy: nenhum display X,
  worker ou acesso a disco é criado antes do usuário usar a feature
"""

import sys
import os
import unittest

# app importa o módulo por path relativo ao rodar via run_app.sh; aqui
# garantimos o mesmo sys.path que run_app.sh usaria
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))


class AppInitTest(unittest.TestCase):
    def test_app_instantiates_without_exception(self):
        from PyQt5.QtWidgets import QApplication
        from mouse_hub_app import MouseHubApp

        # QApplication precisa existir antes de qualquer widget
        app = QApplication.instance() or QApplication(sys.argv)
        window = MouseHubApp()
        self.assertIsNotNone(window)
        self.assertIsNotNone(window.svc)
        self.assertIsNotNone(window.me)
        self.assertIsNotNone(window.ac)

        # fundação leve: nada é criado no startup — display X, workers
        # e store só surgem sob demanda
        self.assertIsNone(window.svc._capture)
        self.assertIsNone(window.svc._clicker)

        # estado inicial do clicker via core único
        from mouse_hub.core.automation.autoclicker import AutoClickerState
        self.assertEqual(window.ac.state, AutoClickerState.STOPPED)
        self.assertFalse(window.ac.running)

        window.close()


if __name__ == "__main__":
    unittest.main()
