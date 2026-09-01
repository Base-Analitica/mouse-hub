"""Issue #110 — estado desconhecido deve ser explícito, não um traço colorido."""

import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "app" / "mouse_hub_app.py"
EXPECTED_UNKNOWN = "Aguardando leitura"


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _make_state():
    from mouse_hub.core.dpi_persistence import NeverDpiPersister
    from mouse_hub.core.mouse_controller import MouseController
    from tests.fakes import FakeHidAccess, FakeSystemInput
    import app.mouse_hub_app as app_module

    core = MouseController(
        hid=FakeHidAccess(),
        system_input=FakeSystemInput(),
        dpi_persister=NeverDpiPersister(),
    )
    return app_module.MouseCoreState(core)


def _dashboard(qapp, state):
    import app.mouse_hub_app as app_module

    class FakeWindowService:
        def is_focused(self, patterns):
            class Result:
                focused = False

            return Result()

    class FakeService:
        window_service = FakeWindowService()

    class FakeClicker:
        class State:
            value = "stopped"

        state = State()

    page = app_module.DashboardPage(
        app_module.MouseController(),
        FakeClicker(),
        None,
        FakeService(),
        state=state,
    )
    page.timer.stop()
    page._update()
    return page


class TestExplicitUnknownState:
    def test_dashboard_nao_usa_traco_colorido(self, qapp):
        """Cards sem leitura exibem copy explícita e cor neutra."""
        from app.ui.theme import COLORS

        page = _dashboard(qapp, _make_state())
        assert page.dpi_card.value_label.text() == EXPECTED_UNKNOWN
        assert page.sens_card.value_label.text() == EXPECTED_UNKNOWN
        assert "—" not in page.dpi_card.value_label.text()
        assert "—" not in page.sens_card.value_label.text()
        assert COLORS["text_secondary"] in page.dpi_card.value_label.styleSheet()
        assert COLORS["text_secondary"] in page.sens_card.value_label.styleSheet()

    def test_herois_nao_usa_traco_colorido(self, qapp):
        """DPI e sensibilidade comunicam o unknown sem aparência de medidor."""
        import app.mouse_hub_app as app_module
        from app.ui.theme import COLORS

        state = _make_state()
        dpi_page = app_module.DPIPage(app_module.MouseController(), state=state)
        sens_page = app_module.SensitivityPage(
            app_module.MouseController(), state=state
        )
        assert dpi_page.dpi_value.text() == EXPECTED_UNKNOWN
        assert sens_page.sens_value.text() == EXPECTED_UNKNOWN
        assert COLORS["text_secondary"] in dpi_page.dpi_value.styleSheet()
        assert COLORS["text_secondary"] in sens_page.sens_value.styleSheet()

    def test_codigo_separa_unknown_de_input_editavel(self):
        """O traço segue reservado ao input neutro, não aos displays."""
        src = APP.read_text(encoding="utf-8")
        assert 'UNKNOWN_STATE_TEXT = "Aguardando leitura"' in src
        assert "UNKNOWN_VALUE_TEXT if dpi is None" not in src
        assert "UNKNOWN_VALUE_TEXT if sens is None" not in src
        assert "self.dpi_value.setText(UNKNOWN_VALUE_TEXT)" not in src
        assert "self.sens_value.setText(UNKNOWN_VALUE_TEXT)" not in src
