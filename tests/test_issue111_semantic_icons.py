"""Regressões visuais dos ícones de DPI e Macros da issue #111."""

from __future__ import annotations

from pathlib import Path

import pytest
from PyQt5.QtGui import QFont, QFontDatabase, QImage, QRawFont
from PyQt5.QtWidgets import QApplication

from app.ui import icons

REPO = Path(__file__).resolve().parents[1]
FONT_FILE = REPO / "app" / "ui" / "fonts" / "remixicon-subset.ttf"
EXPECTED_CODEPOINTS = {
    "dpi": 0xED4C,     # ri-focus-3-line
    "macros": 0xEE75,  # ri-keyboard-line
}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _subset_font(qapp):
    """Carrega o asset real e retorna a fonte Qt correspondente."""
    font_id = QFontDatabase.addApplicationFont(str(FONT_FILE))
    assert font_id >= 0, "subset Remix não pôde ser carregado"
    families = QFontDatabase.applicationFontFamilies(font_id)
    assert families, "subset Remix não expôs uma família Qt"
    return QRawFont.fromFont(QFont(families[0]))


def test_semantic_codepoints_replace_media_glyphs():
    """DPI e Macros apontam para os dois glifos aprovados."""
    assert icons._CODEPOINTS["dpi"] == EXPECTED_CODEPOINTS["dpi"]
    assert icons._CODEPOINTS["macros"] == EXPECTED_CODEPOINTS["macros"]
    assert icons._CODEPOINTS["dpi"] != 0xF177  # ri-speed-line
    assert icons._CODEPOINTS["macros"] != 0xED21  # ri-film-line


@pytest.mark.parametrize("name", ["dpi", "macros"])
def test_subset_supports_each_semantic_codepoint(qapp, name):
    """O TTF entregue contém o codepoint solicitado, não apenas um fallback."""
    raw_font = _subset_font(qapp)
    codepoint = EXPECTED_CODEPOINTS[name]
    assert raw_font.supportsCharacter(chr(codepoint)), (
        f"subset sem {name} U+{codepoint:04X}"
    )
    assert raw_font.glyphIndexesForString(chr(codepoint))[0] != 0


@pytest.mark.parametrize("name", ["dpi", "macros"])
@pytest.mark.parametrize("size", [18, 24])
def test_semantic_icons_render_at_sidebar_and_heading_sizes(qapp, name, size):
    """Cada ícone produz pixels visíveis nos tamanhos oficiais."""
    rendered = icons.icon(name, "#ffffff", size)
    assert rendered is not None
    pixmap = rendered.pixmap(size, size)
    assert not pixmap.isNull()
    image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    assert any(
        image.pixelColor(x, y).alpha() > 0
        for y in range(image.height())
        for x in range(image.width())
    )


def test_sidebar_and_page_headings_keep_semantic_keys():
    """Os call sites reais compartilham as chaves dpi e macros."""
    source = (REPO / "app" / "mouse_hub_app.py").read_text(encoding="utf-8")
    assert '("dpi", "DPI", 1)' in source
    assert '("macros", "Macros", 4)' in source
    assert 'ui_icons.icon_label("dpi"' in source
    assert 'ui_icons.icon_label("macros"' in source


def test_icon_fallback_remains_safe_when_font_is_unavailable(qapp, monkeypatch):
    """Fonte ausente ou nome desconhecido continua sem derrubar a UI."""
    monkeypatch.setattr(icons, "_FONT_FAMILY", "")
    assert icons.icon("dpi") is None
    assert icons.icon_label("macros") is None
    assert icons.icon("unknown-icon") is None


@pytest.fixture(autouse=True)
def reset_icon_font_cache():
    previous = icons._FONT_FAMILY
    yield
    icons._FONT_FAMILY = previous
