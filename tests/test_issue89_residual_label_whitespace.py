"""Issue #89 — whitespace residual não pode fazer parte da apresentação.

A antiga iconografia deixou padding textual em labels, títulos e botões.
O layout deve ser responsável pelo espaçamento; `Play` e `Cancel` continuam
sendo estados limpos e sincronizados com o playback.
"""

import os
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "app" / "mouse_hub_app.py"


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    """Janela real com fakes e XDG isolado para a auditoria de texto."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))

    import app.mouse_hub_app as app_module
    from mouse_hub.core.dpi_persistence import NeverDpiPersister
    from mouse_hub.core.mouse_controller import MouseController
    from tests.fakes import FakeHidAccess, FakeSystemInput, fake_g403_device

    class DummyMonitor:
        def __init__(self, out):
            pass

        def start(self):
            return True

        def stop(self):
            pass

    monkeypatch.setattr(app_module, "UdevHidrawMonitor", DummyMonitor)
    monkeypatch.setattr(
        app_module, "discover_candidates", lambda: [fake_g403_device()]
    )

    def make_state():
        core = MouseController(
            hid=FakeHidAccess(),
            system_input=FakeSystemInput(),
            dpi_persister=NeverDpiPersister(),
        )
        return app_module.MouseCoreState(core)

    monkeypatch.setattr(app_module, "build_mouse_state", make_state)
    w = app_module.MouseHubApp()
    qapp.processEvents()
    yield w
    w.close()
    w.me.cleanup()
    w.ac.cleanup()
    w.svc.cleanup()


class PlaybackFake:
    """Serviço mínimo para exercitar os botões de uma macro salva."""

    def __init__(self):
        self.macros = {
            "macro_demo": {
                "count": 2,
                "created": "2026-08-29T00:00:00",
            }
        }
        self.playback_state = "stopped"
        self.playback_error = None
        self.playing = False

    def list_all(self):
        return self.macros

    def play(self, name):
        self.playing = True
        self.playback_state = "running"
        return True

    def cancel_playback(self):
        self.playing = False
        self.playback_state = "stopped"

    def delete(self, name):
        self.macros.pop(name, None)


def _visible_texts(window):
    from PyQt5.QtWidgets import QGroupBox, QLabel, QPushButton

    widgets = list(window.findChildren(QLabel))
    widgets.extend(window.findChildren(QPushButton))
    widgets.extend(window.findChildren(QGroupBox))
    texts = [widget.text() if hasattr(widget, "text") else widget.title()
             for widget in widgets]
    texts.append(window.windowTitle())
    return [text for text in texts if text]


class TestResidualWhitespace:
    def test_texto_visivel_nao_tem_padding_textual(self, window):
        """Texto visível não usa espaços como substituto de layout."""
        offenders = []
        for text in _visible_texts(window):
            if text[:1].isspace() or re.search(r"[ \t]{2,}", text):
                offenders.append(repr(text))
        assert offenders == [], "whitespace de apresentação: " + repr(offenders)

    def test_pontos_conhecidos_e_playback_estao_limpos_no_source(self):
        """Protege os resíduos citados no issue e a comparação de estados."""
        src = APP.read_text(encoding="utf-8")
        forbidden = (
            '" CS:GO AWP"',
            '" FPS Geral"',
            '" Minecraft PvP"',
            '" Flick Shots"',
            '" Max Speed"',
            '" Gravar Macro"',
            '" Iniciando captura XRecord',
            '" Play"',
            '" Cancel"',
            '"⚠  Gravação',
            '" Perfil \'%s\' NAO aplicado',
            '" Nao foi possivel salvar o perfil',
            '"Use   Gravar Macro',
            '" Permissões HID',
            '" Conceder acesso ao hardware',
            '" Auto-Clicker — Segurança"',
            '" Informações do Sistema"',
            '" Mouse Hub — Controlador Gaymer"',
        )
        for fragment in forbidden:
            assert fragment not in src, f"resíduo de apresentação: {fragment}"
        assert 'if child.text() in ("Play", "Cancel")' in src
        assert 'child.setText("Cancel" if running else "Play")' in src

    def test_play_cancel_reflete_estado_real(self, qapp):
        """A limpeza não pode quebrar a transição Play ↔ Cancel."""
        import app.mouse_hub_app as app_module
        from PyQt5.QtWidgets import QPushButton

        fake = PlaybackFake()
        page = app_module.MacrosPage(fake, None)
        qapp.processEvents()
        buttons = [
            button for button in page.macro_list_widget.findChildren(QPushButton)
            if button.text() in {"Play", "Cancel"}
        ]
        assert [button.text() for button in buttons] == ["Play"]

        fake.playback_state = "running"
        page._update_play_status()
        assert [button.text() for button in buttons] == ["Cancel"]

        fake.playback_state = "stopped"
        page._update_play_status()
        assert [button.text() for button in buttons] == ["Play"]
        page._play_timer.stop()
