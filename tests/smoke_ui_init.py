"""Smoke test: o app PyQt inicializa sob Xvfb sem exceção.

Executar: xvfb-run -a python3 -m unittest tests.smoke_ui_init
Não depende de mouse real nem de display físico.
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
        self.assertIsNotNone(window.me)
        self.assertIsNotNone(window.ac)
        # engines conectados ao pacote nativo
        from mouse_hub.automation import (
            AutoClickerState, PlaybackController, MacroStore)
        self.assertEqual(window.ac.state, AutoClickerState.STOPPED)
        self.assertIsInstance(window.me.player, PlaybackController)
        self.assertIsInstance(window.me.store, MacroStore)
        window.close()


if __name__ == "__main__":
    unittest.main()
