"""Issue #113: a página de Macros fala em tarefas, não em backends.

Os testes cobrem copy de capacidade e feedback operacional usando fakes. Nomes
internos podem existir na causa técnica, mas não devem chegar ao usuário final.
"""

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from mouse_hub.core.capabilities import (  # noqa: E402
    CAPABILITY_NAMES,
    CapabilityModel,
    with_overrides,
)


@pytest.fixture(scope="module")
def qapp():
    from PyQt5.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _all_capabilities():
    return CapabilityModel(
        **{name: (lambda: True) for name in CAPABILITY_NAMES}
    ).evaluate()


def _page(qapp, caps):
    from app import mouse_hub_app as app_module
    from tests.test_issue4_macro_recording import FakeMe

    page = app_module.MacrosPage(
        FakeMe(), None, caps_provider=lambda: caps
    )
    page.show()
    qapp.processEvents()
    return page


def _drain(page, qapp, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        page._poll_op()
        if page._op_kind is None and page._op_result is None:
            return
        time.sleep(0.02)
    pytest.fail("operação fake de Macros não terminou")


def test_capacidade_disponivel_usa_copy_de_produto(qapp):
    page = _page(qapp, _all_capabilities())

    text = page.caps_hint.text()
    assert "Gravação de macros disponível" in text
    assert "X11" not in text
    assert "XRecord" not in text
    assert "XTest" not in text
    page.close()


def test_capacidade_indisponivel_explica_sessao_sem_backend(qapp):
    caps = with_overrides(
        _all_capabilities(),
        {"macro_capture_available": (False, "sessão sem X11 (DISPLAY ausente)")},
    )
    page = _page(qapp, caps)

    text = page.caps_hint.text()
    assert "indisponível" in text
    assert "sessão gráfica" in text.lower()
    assert "X11" not in text
    assert "XRecord" not in text
    assert "XTest" not in text
    page.close()


def test_inicio_de_gravacao_nao_expõe_backend(qapp):
    from tests.test_issue4_macro_recording import FakeMe
    from app import mouse_hub_app as app_module

    me = FakeMe()
    me.start_delay = 0.2
    page = app_module.MacrosPage(
        me, None, caps_provider=lambda: _all_capabilities()
    )
    page.name_input.setText("minha_macro")
    page._toggle_record()

    text = page.record_status.text()
    assert "XRecord" not in text
    assert "sessão gráfica" in text.lower()
    _drain(page, qapp)
    page.close()


def test_falha_tecnica_e_traduzida_no_status_operacional(qapp):
    from app import mouse_hub_app as app_module
    from tests.test_issue4_macro_recording import FakeMe

    class TechnicalFailureMe(FakeMe):
        def start_recording(self, name):
            self.capture_failed = "XRecord indisponível: BadAccess"
            return False

    me = TechnicalFailureMe()
    page = app_module.MacrosPage(
        me, None, caps_provider=lambda: _all_capabilities()
    )
    page._toggle_record()
    _drain(page, qapp)

    text = page.record_status.text()
    assert "Não foi possível iniciar a gravação" in text
    assert "sessão gráfica" in text.lower()
    assert "XRecord" not in text
    assert me.capture_failed == "XRecord indisponível: BadAccess"
    page.close()


def test_falha_de_playback_sanitiza_backend(qapp):
    from app import mouse_hub_app as app_module
    from tests.test_issue4_macro_recording import FakeMe

    me = FakeMe()
    me.playback_state = "failed"
    me.playback_error = "extensão XTEST indisponível"
    page = app_module.MacrosPage(
        me, None, caps_provider=lambda: _all_capabilities()
    )
    page._update_play_status()

    text = page.play_status.text()
    assert text.startswith("Playback falhou:")
    assert "sessão gráfica" in text.lower()
    assert "XTEST" not in text
    page.close()
