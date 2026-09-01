# -*- coding: utf-8 -*-
"""Issue #101 — Polling Rate não expõe mensagem de desenvolvedor.

A superfície operacional não pode conter stack, feature ID (0x8060),
processo de implementação nem referência de issue. A causa técnica
permanece no core (diagnóstico); a copy exibida pertence à camada de UI.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt5")
from PyQt5.QtWidgets import QApplication  # noqa: E402

from mouse_hub.core import mouse_controller as core_module  # noqa: E402
from tests.fakes import FakeHidAccess, FakeSystemInput  # noqa: E402
from mouse_hub.core.mouse_controller import (  # noqa: E402
    MouseController as CoreMouseController,
)
from mouse_hub.core.dpi_persistence import NeverDpiPersister  # noqa: E402

import app.mouse_hub_app as app_module  # noqa: E402
from app.mouse_hub_app import MouseController, SensitivityPage  # noqa: E402

POLLING_COPY = (
    "Polling Rate não pode ser configurado neste dispositivo nesta "
    "versão do Mouse Hub."
)

FORBIDDEN_TERMS = (
    "0x8060",
    "HID++",
    "HID++ 2.0",
    "issue #",
    "#6",
    "stack",
    "descoberta de features",
    "Report Rate",
    "G403 HERO físico",
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _page(qapp):
    core = CoreMouseController(
        hid=FakeHidAccess(),
        system_input=FakeSystemInput(),
        dpi_persister=NeverDpiPersister(),
    )
    page = SensitivityPage(MouseController(), state=app_module.MouseCoreState(core))
    return page


def _assert_user_safe(text: str) -> None:
    low = text.lower()
    for term in FORBIDDEN_TERMS:
        assert term.lower() not in low, (
            f"jargão interno {term!r} exposto ao usuário: {text!r}"
        )


def test_polling_copy_belongs_to_ui_layer():
    assert getattr(app_module, "POLLING_UNAVAILABLE_COPY", None) == POLLING_COPY
    assert "USER_POLLING_UNAVAILABLE" not in core_module.__dict__


def test_polling_hint_uses_user_copy(qapp):
    page = _page(qapp)
    assert POLLING_COPY in page.polling_hint.text()
    _assert_user_safe(page.polling_hint.text())


def test_polling_hint_is_short_and_fits_small_window(qapp):
    """A copy cabe confortavelmente em 760×560 (uma frase curta)."""
    page = _page(qapp)
    visible = page.polling_hint.text().replace("●", "").strip()
    assert len(visible) <= 120
    # Indisponibilidade honesta, sem prometer suporte futuro.
    assert "não pode ser configurado" in visible


def test_core_reason_keeps_technical_cause():
    """A causa técnica permanece no core (diagnóstico), não na UI."""
    core = CoreMouseController(
        hid=FakeHidAccess(),
        system_input=FakeSystemInput(),
        dpi_persister=NeverDpiPersister(),
    )
    caps = core.capability_model().evaluate()
    assert not caps.is_available("polling_rate_available")
    assert "0x8060" in caps.reason_for("polling_rate_available")


def test_no_technical_term_in_sensitivity_page_strings(qapp):
    """Nenhum QLabel da página contém jargão de implementação."""
    page = _page(qapp)
    for label in page.findChildren(type(page.polling_hint)):
        _assert_user_safe(label.text())
    # A copy pertence à UI; o core fornece apenas a razão técnica.
    source = page.polling_hint.text()
    assert POLLING_COPY in source
