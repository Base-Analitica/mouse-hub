# -*- coding: utf-8 -*-
"""Contratos das issues #85 e #86 para os cards de Perfis.

Os testes exercitam somente a projeção PyQt da página. A identidade dos
perfis continua sendo a chave fornecida pelo ProfileStore.
"""

from __future__ import annotations

import inspect
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton

import app.mouse_hub_app as app_module
from app.mouse_hub_app import ProfilesPage
from mouse_hub.core.config import ConfigPaths
from mouse_hub.core.profiles import ProfileStore


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _store(tmp_path):
    return ProfileStore(ConfigPaths(tmp_path / "config", tmp_path / "data"))


def _title_label(card):
    labels = [label for label in card.findChildren(QLabel) if label.text()]
    titles = [
        label for label in labels
        if not label.text().startswith("DPI:") and label.text() != "✔ Ativo"
    ]
    assert len(titles) == 1, [label.text() for label in labels]
    return titles[0]


def _header(card):
    item = card.layout().itemAt(0)
    header = item.layout()
    assert isinstance(header, QHBoxLayout)
    return header


def _cards_page(qapp, store, state=None):
    page = ProfilesPage(app_module.MouseController(), state=state, store=store)
    page.show()
    qapp.processEvents()
    return page


class _RecordingProfilesPage(ProfilesPage):
    def __init__(self, *args, **kwargs):
        self.applied = []
        self.edited = []
        super().__init__(*args, **kwargs)

    def _apply(self, profile):
        self.applied.append(profile)

    def _start_edit(self, profile):
        self.edited.append(profile)


def test_official_profile_keys_have_product_display_labels(qapp, tmp_path):
    store = _store(tmp_path)
    page = _cards_page(qapp, store)
    expected = {
        "minecraft": "Minecraft",
        "csgo": "CS:GO",
        "fortnite": "Fortnite",
        "default": "Padrão",
    }

    assert set(page.profile_cards) >= set(expected)
    for key, display_name in expected.items():
        assert _title_label(page.profile_cards[key]["card"]).text() == display_name


def test_custom_profile_name_is_not_transformed(qapp, tmp_path):
    store = _store(tmp_path)
    outcome = store.save_profile("stream_2026", 1800, 65)
    assert outcome.success

    page = _cards_page(qapp, store)

    assert _title_label(page.profile_cards["stream_2026"]["card"]).text() == "stream_2026"


def test_display_labels_do_not_replace_profile_identity_in_callbacks(qapp, tmp_path):
    store = _store(tmp_path)
    page = _RecordingProfilesPage(app_module.MouseController(), store=store)
    page.show()
    qapp.processEvents()

    for key in ("default", "minecraft"):
        profile = next(item for item in page.profiles if item.name == key)
        card = page.profile_cards[key]["card"]
        buttons = card.findChildren(QPushButton)
        next(button for button in buttons if button.text() == "Aplicar").click()
        next(button for button in buttons if button.text() == "Editar").click()
        assert page.applied[-1] is profile
        assert page.edited[-1] is profile
        assert key in page.profile_cards


def test_inactive_card_has_no_empty_header_or_icon_placeholder(qapp, tmp_path):
    page = _cards_page(qapp, _store(tmp_path))
    source = inspect.getsource(ProfilesPage)

    assert 'ic = QLabel("")' not in source
    for key, widgets in page.profile_cards.items():
        header = _header(widgets["card"])
        header_labels = []
        for index in range(header.count()):
            widget = header.itemAt(index).widget()
            if isinstance(widget, QLabel):
                header_labels.append(widget)
        assert any(label.text() == _title_label(widgets["card"]).text() for label in header_labels)
        assert all(label.text().strip() for label in header_labels)


def test_active_badge_is_visible_only_for_confirmed_matching_profile(qapp, tmp_path):
    state = SimpleNamespace(
        applied_dpi=800,
        applied_sensitivity=50,
        refresh=lambda: None,
    )
    page = _cards_page(qapp, _store(tmp_path), state=state)

    assert page.active_profile() == "default"
    assert page.profile_cards["default"]["active_badge"].isVisible()
    assert page.profile_cards["default"]["active_badge"].text() == "✔ Ativo"
    assert not page.profile_cards["minecraft"]["active_badge"].isVisible()

    state.applied_dpi = None
    page._refresh_active()
    assert page.active_profile() is None
    assert not any(widgets["active_badge"].isVisible() for widgets in page.profile_cards.values())


def test_active_badge_moves_with_confirmed_profile_without_empty_row(qapp, tmp_path):
    state = SimpleNamespace(
        applied_dpi=800,
        applied_sensitivity=50,
        refresh=lambda: None,
    )
    page = _cards_page(qapp, _store(tmp_path), state=state)

    state.applied_dpi = 1200
    state.applied_sensitivity = 60
    page._refresh_active()

    assert page.active_profile() == "minecraft"
    assert page.profile_cards["minecraft"]["active_badge"].isVisible()
    assert not page.profile_cards["default"]["active_badge"].isVisible()
    for key, widgets in page.profile_cards.items():
        assert _title_label(widgets["card"]).text()
        assert _header(widgets["card"]).count() >= 2


@pytest.mark.parametrize("width,height", [(1050, 680), (760, 560)])
def test_profile_cards_are_contained_and_coherent_in_official_viewports(
    qapp, tmp_path, width, height
):
    page = _cards_page(qapp, _store(tmp_path))
    page.resize(width, height)
    qapp.processEvents()

    cards = [page.grid.itemAt(i).widget() for i in range(page.grid.count())]
    assert cards
    assert len({card.height() for card in cards}) == 1
    assert page.grid.geometry().right() <= page.width()
    assert max(card.geometry().right() for card in cards) <= page.width()

    for index, card in enumerate(cards):
        assert _title_label(card).geometry().right() <= card.contentsRect().right() + 2
        for other in cards[index + 1 :]:
            overlap = card.geometry().intersected(other.geometry())
            assert overlap.width() <= 0 or overlap.height() <= 0
