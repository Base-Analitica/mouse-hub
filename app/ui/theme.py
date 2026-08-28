"""Design system central do Mouse Hub (issue #66).

Fonte ÚNICA de verdade visual: cores, escala tipográfica, espaçamento,
raios e estilos globais. Nenhum widget inventa valores fora daqui —
o que um dia precisar de exceção entra como token nomeado, não como
número mágico inline.

Modo da superfície (impeccable): **Operate** — app de tarefa.
Scanability, consistência e previsibilidade acima de expressão."""

from __future__ import annotations

# ── Cores ────────────────────────────────────────────────────
COLORS = {
    "bg_darkest":    "#08080e",
    "bg_dark":       "#0e0e18",
    "bg_mid":        "#141422",
    "bg_card":       "#1a1a2e",
    "bg_card_hover": "#20203a",
    "bg_input":      "#252540",
    "border":        "#2a2a4a",
    "border_light":  "#3a3a6a",
    "accent":        "#7c3aed",
    "accent_light":  "#a78bfa",
    "accent_dark":   "#5b21b6",
    "accent_glow":   "rgba(124, 58, 237, 0.3)",
    "accent_lighter": "#c4b5fd",
    "danger_light":  "#f87171",
    "danger_lighter": "#fca5a5",
    "success":       "#22c55e",
    "success_dark":  "#166534",
    "danger":        "#ef4444",
    "danger_dark":   "#7f1d1d",
    "warning":       "#f59e0b",
    "warning_dark":  "#78350f",
    "text_primary":  "#e2e8f0",
    "text_secondary": "#94a3b8",
    "text_muted":    "#64748b",
    "text_dim":      "#475569",
    # NOTA (audit impeccable): text_muted/text_dim NÃO passam 4.5:1
    # sobre bg_card/bg_dark — use apenas em estados DESABILITADOS ou
    # decoração; texto real de leitura usa text_secondary ou acima.
    "mc_green":      "#4ade80",
    "mc_dark":       "#166534",
    "sidebar_bg":    "#0b0b14",
    "sidebar_hover": "#15152a",
    "sidebar_active": "#1c1c38",
    "scrollbar":     "#2a2a4a",
    "scrollbar_bg":  "#0e0e18",
}

# ── Escala tipográfica (px) ─────────────────────────────────
# 8 passos nomeados; NADA fora deles. (craft floor: escala óbvia,
# passos perceptíveis; 10px é ilegível — piso 11.)
TYPE_SCALE = {
    "micro":    11,   # versão, hints, metadados
    "caption":  12,   # legendas, status secundário
    "body":     13,   # texto padrão de botão/label
    "body_lg":  14,   # corpo com ênfase
    "subtitle": 16,   # títulos de seção
    "title":    20,   # título de página
    "display":  24,   # título hero
    "hero":     44,   # números grandes (detector MC)
}

# ── Espaçamento (px) — base 4 ───────────────────────────────
SPACE = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
    "xxl": 32,
}

# ── Raios ────────────────────────────────────────────────────
RADIUS = {"sm": 6, "md": 8, "lg": 10, "xl": 12, "pill": 18}


def normal_font_size(px: int) -> int:
    """Mapeia qualquer tamanho para o degrau mais próximo da escala."""
    steps = sorted(TYPE_SCALE.values())
    return min(steps, key=lambda s: (abs(s - px), s))


def build_app_stylesheet() -> str:
    """Stylesheet global da aplicação, 100% a partir dos tokens."""
    c = COLORS
    body = TYPE_SCALE["body"]
    micro = TYPE_SCALE["micro"]
    return f"""
/* ─── Global ────────────────────────────────────────────── */
* {{
    font-family: 'Segoe UI', 'Ubuntu', 'Noto Sans', sans-serif;
}}
QMainWindow {{
    background-color: {c['bg_darkest']};
}}
QWidget {{
    color: {c['text_primary']};
}}

/* ─── Scrollbar ─────────────────────────────────────────── */
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: {c['scrollbar_bg']};
    width: 8px;
    margin: 0;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {c['scrollbar']};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c['border_light']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    height: 8px;
    background: {c['scrollbar_bg']};
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {c['scrollbar']};
    border-radius: 4px;
    min-width: 30px;
}}

/* ─── Slider ────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    background: {c['bg_input']};
    height: 6px;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {c['accent']};
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
    border: 2px solid {c['accent_light']};
}}
QSlider::handle:horizontal:hover {{
    background: {c['accent_light']};
    border-color: white;
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {c['accent_dark']}, stop:1 {c['accent']});
    border-radius: 3px;
}}

/* ─── Buttons ───────────────────────────────────────────── */
QPushButton {{
    background-color: {c['bg_card']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: {RADIUS['md']}px;
    padding: {SPACE['sm']}px {SPACE['lg']}px;
    font-size: {body}px;
    font-weight: 600;
}}
QPushButton:hover {{
    border-color: {c['accent']};
    background-color: {c['bg_card_hover']};
}}
QPushButton:pressed {{
    background-color: {c['bg_mid']};
}}
QPushButton:disabled {{
    color: {c['text_muted']};
    border-color: {c['border']};
}}

/* ─── Inputs ────────────────────────────────────────────── */
QLineEdit {{
    background-color: {c['bg_input']};
    border: 1px solid {c['border']};
    border-radius: {RADIUS['md']}px;
    padding: {SPACE['sm']}px {SPACE['md']}px;
    font-size: {body}px;
    color: {c['text_primary']};
    selection-background-color: {c['accent_dark']};
}}
QLineEdit:focus {{
    border-color: {c['accent']};
}}

/* ─── Foco por teclado visível (audit impeccable B-6) ───── */
QPushButton:focus {{
    border: 1px solid {c['accent_light']};
}}
QComboBox:focus {{
    border: 1px solid {c['accent']};
}}
QSlider::handle:horizontal:focus {{
    border: 2px solid {c['accent_light']};
}}
QTextEdit {{
    background-color: {c['bg_card']};
    border: 1px solid {c['border']};
    border-radius: {RADIUS['lg']}px;
    padding: {SPACE['md']}px;
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    font-size: {micro + 1}px;
    color: {c['text_secondary']};
    selection-background-color: {c['accent_dark']};
}}

/* ─── Group box ─────────────────────────────────────────── */
QGroupBox {{
    background-color: {c['bg_dark']};
    border: 1px solid {c['border']};
    border-radius: {RADIUS['xl']}px;
    margin-top: {SPACE['lg']}px;
    padding: {SPACE['lg']}px {SPACE['lg']}px {SPACE['md']}px {SPACE['lg']}px;
    font-size: {TYPE_SCALE['subtitle']}px;
    font-weight: 700;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: {SPACE['lg']}px;
    padding: 0 {SPACE['sm']}px;
    color: {c['accent_light']};
}}

/* ─── Tooltip ───────────────────────────────────────────── */
QToolTip {{
    background-color: {c['bg_mid']};
    color: {c['text_primary']};
    border: 1px solid {c['border_light']};
    border-radius: {RADIUS['sm']}px;
    padding: {SPACE['xs']}px {SPACE['sm']}px;
    font-size: {micro}px;
}}

/* ─── Combobox ──────────────────────────────────────────── */
QComboBox {{
    background-color: {c['bg_input']};
    border: 1px solid {c['border']};
    border-radius: {RADIUS['md']}px;
    padding: {SPACE['sm']}px {SPACE['md']}px;
    font-size: {body}px;
}}
QComboBox:hover {{
    border-color: {c['accent']};
}}
QComboBox::drop-down {{
    border: none;
    width: {SPACE['xl']}px;
}}
QComboBox QAbstractItemView {{
    background-color: {c['bg_mid']};
    border: 1px solid {c['border_light']};
    border-radius: {RADIUS['md']}px;
    selection-background-color: {c['accent_dark']};
    color: {c['text_primary']};
}}
"""
