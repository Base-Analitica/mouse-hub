"""Issue #90 — text_muted só para estados realmente despriorizados.

O tema documenta que text_muted/text_dim não atingem o contraste alvo
sobre superfícies escuras. Labels de leitura devem usar text_secondary
ou cor semântica; OFF e pontos decorativos continuam permitidos.
"""

import os
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
    """Janela real com fakes e configuração isolada do ambiente local."""
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


class TestCopyLegivel:
    def test_labels_de_leitura_nao_usam_text_muted(self, window):
        """Todo QLabel com copy legível deve ter contraste de leitura;
        `OFF` é a única exceção de estado desligado nesta superfície."""
        from app.ui.theme import COLORS
        from PyQt5.QtWidgets import QLabel

        muted = COLORS["text_muted"]
        allowed = {"OFF"}
        offenders = []
        for label in window.findChildren(QLabel):
            text = label.text().strip()
            if text and muted in label.styleSheet() and text not in allowed:
                offenders.append(text)
        assert offenders == [], (
            "labels de leitura em text_muted: " + repr(offenders)
        )

    def test_copy_conhecida_nao_volta_para_muted_no_source(self):
        """Protege os pontos de copy citados no issue mesmo quando o estado
        inicial vazio não deixa a violação visível no runtime."""
        src = APP.read_text(encoding="utf-8")
        readable_widgets = (
            "self.subtitle.setStyleSheet",
            "self.hid_hint.setStyleSheet",
            "self.polling_hint.setStyleSheet",
            "self.status_sub.setStyleSheet",
            "cps_unit.setStyleSheet",
            "self.play_status.setStyleSheet",
            "empty.setStyleSheet",
            "self.config_hint.setStyleSheet",
            "self.apply_hint.setStyleSheet",
            "self._permission_status.setStyleSheet",
        )
        for widget in readable_widgets:
            lines = [
                line for line in src.splitlines()
                if widget in line and "text_muted" in line
            ]
            assert lines == [], f"{widget} usa text_muted em copy: {lines}"

        # A seleção de cor do Dashboard para "sem mouse" também é copy,
        # embora a atribuição esteja em uma linha separada do stylesheet.
        assert 'color = COLORS["text_muted"]' not in src
