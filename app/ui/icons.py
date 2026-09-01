"""Ícones vetoriais do Mouse Hub — Remix Icon, fonte EMBUTIDA.

Decisão do mantenedor: em vez de depender do qtawesome (que instala
~10 MB de fontes de todos os sets), embutimos um SUBSET da Remix
Icon com apenas os glifos que o app usa (2,7 KB), carregado via
QFontDatabase no primeiro uso. Zero dependência nova no runtime;
ícones vetoriais nítidos em qualquer máquina — a fonte viaja no
bundle do app.

Fonte: Remix Icon (https://remixicon.com), Apache-2.0 — ver
app/ui/fonts/LICENSE-RemixIcon.txt.

CONTRATO: ícone indisponível NUNCA derruba a UI — `icon()` e
`icon_label()` retornam None e o chamador fica em texto puro."""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QFontDatabase, QFont, QPainter, QColor, QPixmap
from PyQt5.QtWidgets import QLabel

from app.ui.theme import COLORS

_FONT_FILE = Path(__file__).parent / "fonts" / "remixicon-subset.ttf"
_FONT_FAMILY = None  # cache; "" = tentou e falhou (modo texto)

# nome semântico -> codepoint no subset (remixicon v5, Apache-2.0)
_CODEPOINTS = {
    "dashboard":   0xEC14,  # ri-dashboard-line
    "dpi":         0xED4C,  # ri-focus-3-line
    "sensitivity": 0xEC0A,  # ri-cursor-line
    "clicker":     0xEF7D,  # ri-mouse-line
    "macros":      0xEE75,  # ri-keyboard-line
    "profiles":    0xF264,  # ri-user-line
    "settings":    0xF0E6,  # ri-settings-3-line
    "shield":      0xF100,  # ri-shield-check-line
    "info":        0xEE59,  # ri-information-line
    "activity":    0xF035,  # ri-pulse-line
    "lock":        0xEED0,  # ri-lock-password-line
    "alert":       0xEA21,  # ri-alert-line
}


def _family() -> str | None:
    """Carrega a fonte embutida uma única vez. None = indisponível."""
    global _FONT_FAMILY
    if _FONT_FAMILY is None:
        try:
            font_id = QFontDatabase.addApplicationFont(str(_FONT_FILE))
            families = (
                QFontDatabase.applicationFontFamilies(font_id)
                if font_id >= 0 else []
            )
            _FONT_FAMILY = families[0] if families else ""
        except Exception:  # noqa: BLE001 — fonte ausente/corrompida
            _FONT_FAMILY = ""
    return _FONT_FAMILY or None


def icon(name: str, color: str | None = None, size: int = 20) -> QIcon | None:
    """QIcon vetorial do glifo desenhado com a cor dada.

    None se a fonte não carregou ou o nome é desconhecido."""
    cp = _CODEPOINTS.get(name)
    family = _family()
    if cp is None or family is None:
        return None

    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)
    font = QFont(family)
    font.setPixelSize(int(size * 0.94))
    painter.setFont(font)
    painter.setPen(QColor(color or COLORS["text_secondary"]))
    painter.drawText(pm.rect(), Qt.AlignCenter, chr(cp))
    painter.end()
    return QIcon(pm)


def icon_label(name: str, color: str | None = None,
               size: int = 20) -> QLabel | None:
    """QLabel com o pixmap do ícone; None se indisponível."""
    ic = icon(name, color, size)
    if ic is None:
        return None
    pm = ic.pixmap(QSize(size, size))
    if pm.isNull():
        return None
    lab = QLabel()
    lab.setPixmap(pm)
    lab.setFixedSize(size, size)
    lab.setStyleSheet("background: transparent;")
    return lab


def title_row(name: str, text: str, color: str | None = None,
              icon_size: int = 22) -> "tuple[QLabel, QLabel | None]":
    """(label_título, ícone|None) para cabeçalhos de página.

    O chamador monta a linha: addWidget(ícone) + addWidget(título);
    ícone None = só título (modo texto)."""
    title = QLabel(text)
    title.setStyleSheet(
        f"font-size: 24px; font-weight: 900; background: transparent;")
    return title, icon_label(name, color, icon_size)
