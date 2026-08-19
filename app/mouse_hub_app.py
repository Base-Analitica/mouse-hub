#!/usr/bin/env python3
"""
Mouse Hub — Aplicativo Nativo Desktop
======================================
App nativo estilo Feather Client para controle do Logitech G403 HERO
DPI, Sensibilidade, Macros e Auto-Clicker (Minecraft Only)
"""

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

# Bootstrap: o launcher executa este script a partir de app/;
# o pacote mouse_hub (automation) vive no repositório raiz.
_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QFrame, QGraphicsDropShadowEffect,
    QScrollArea, QStackedWidget, QLineEdit, QSpinBox, QComboBox,
    QMessageBox, QProgressBar, QSystemTrayIcon, QMenu, QAction,
    QGroupBox, QGridLayout, QTextEdit
)
from PyQt5.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QSize,
    pyqtSignal, QObject, QThread, QPoint, QRect
)
from PyQt5.QtGui import (
    QFont, QColor, QPalette, QIcon, QPainter, QPainterPath,
    QLinearGradient, QPixmap, QFontDatabase, QBrush, QPen,
    QCursor
)


# ═══════════════════════════════════════════════════════════════════════════════
#  TEMA / CORES
# ═══════════════════════════════════════════════════════════════════════════════

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
    "success":       "#22c55e",
    "success_dark":  "#166534",
    "danger":        "#ef4444",
    "danger_dark":   "#7f1d1d",
    "warning":       "#f59e0b",
    "warning_dark":  "#78350f",
    "text_primary":  "#e2e8f0",
    "text_secondary":"#94a3b8",
    "text_muted":    "#64748b",
    "text_dim":      "#475569",
    "mc_green":      "#4ade80",
    "mc_dark":       "#166534",
    "sidebar_bg":    "#0b0b14",
    "sidebar_hover": "#15152a",
    "sidebar_active":"#1c1c38",
    "scrollbar":     "#2a2a4a",
    "scrollbar_bg":  "#0e0e18",
}

STYLESHEET = f"""
/* ─── Global ────────────────────────────────────────────── */
* {{
    font-family: 'Segoe UI', 'Ubuntu', 'Noto Sans', sans-serif;
}}
QMainWindow {{
    background-color: {COLORS['bg_darkest']};
}}
QWidget {{
    color: {COLORS['text_primary']};
}}

/* ─── Scrollbar ─────────────────────────────────────────── */
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: {COLORS['scrollbar_bg']};
    width: 8px;
    margin: 0;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['scrollbar']};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COLORS['border_light']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    height: 8px;
    background: {COLORS['scrollbar_bg']};
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {COLORS['scrollbar']};
    border-radius: 4px;
    min-width: 30px;
}}

/* ─── Slider ────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    background: {COLORS['bg_input']};
    height: 6px;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {COLORS['accent']};
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
    border: 2px solid {COLORS['accent_light']};
}}
QSlider::handle:horizontal:hover {{
    background: {COLORS['accent_light']};
    border-color: white;
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {COLORS['accent_dark']}, stop:1 {COLORS['accent']});
    border-radius: 3px;
}}

/* ─── Buttons ───────────────────────────────────────────── */
QPushButton {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {COLORS['bg_card_hover']};
    border-color: {COLORS['accent']};
}}
QPushButton:pressed {{
    background-color: {COLORS['accent_dark']};
}}
QPushButton:disabled {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text_dim']};
    border-color: {COLORS['bg_mid']};
}}

/* ─── Input ─────────────────────────────────────────────── */
QLineEdit, QSpinBox, QComboBox {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {COLORS['accent']};
}}
QComboBox::drop-down {{
    border: none;
    width: 30px;
}}
QComboBox::down-arrow {{
    image: none;
    border: none;
}}
QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_primary']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['accent']};
    border-radius: 8px;
    padding: 4px;
}}

/* ─── Label ─────────────────────────────────────────────── */
QLabel {{
    background: transparent;
}}

/* ─── GroupBox ──────────────────────────────────────────── */
QGroupBox {{
    background-color: {COLORS['bg_card']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
    margin-top: 8px;
    padding: 20px 16px 16px 16px;
    font-weight: 700;
    font-size: 14px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 8px;
    color: {COLORS['accent_light']};
}}

/* ─── QTextEdit ─────────────────────────────────────────── */
QTextEdit {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text_secondary']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 8px;
    font-size: 12px;
}}

/* ─── Progress Bar ──────────────────────────────────────── */
QProgressBar {{
    background-color: {COLORS['bg_input']};
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {COLORS['accent_dark']}, stop:1 {COLORS['accent']});
    border-radius: 4px;
}}
"""


# ═══════════════════════════════════════════════════════════════════════════════
#  MOUSE CONTROLLER (DPI / Sensitivity / AutoClicker / Macros)
# ═══════════════════════════════════════════════════════════════════════════════

MOUSE_NAME = "Logitech G403 HERO Gaming Mouse"
DPI_MIN, DPI_MAX, DPI_STEP = 100, 25600, 50
CONFIG_PATH = Path.home() / "mouse-hub" / "config.json"
MACROS_PATH = Path.home() / "mouse-hub" / "macros.json"


class MouseController:
    """Controle do mouse via xinput/HID"""

    def __init__(self):
        self.current_dpi = 800
        self.current_sensitivity = 50
        self.mouse_id = self._find_mouse_id()
        self.config = self._load_config()
        self.current_dpi = self.config.get("dpi", 800)
        self.current_sensitivity = self.config.get("sensitivity", 50)

    def _find_mouse_id(self):
        try:
            result = subprocess.run(["xinput", "list"], capture_output=True, text=True, timeout=5)
            for line in result.stdout.split("\n"):
                if "G403" in line and "slave  pointer" in line:
                    m = re.search(r"id=(\d+)", line)
                    if m:
                        return int(m.group(1))
        except Exception:
            pass
        return None

    def set_sensitivity(self, value):
        """Define sensibilidade 0-100"""
        value = max(0, min(100, int(value)))
        self.current_sensitivity = value
        if self.mouse_id:
            accel = (value / 100.0) * 2.0 - 1.0
            try:
                subprocess.run(
                    ["xinput", "set-prop", str(self.mouse_id),
                     "libinput Accel Speed", f"{accel:.3f}"],
                    capture_output=True, timeout=5
                )
            except Exception:
                pass
        self.config["sensitivity"] = value
        self._save_config()
        return True

    def get_sensitivity(self):
        if self.mouse_id:
            try:
                result = subprocess.run(
                    ["xinput", "list-props", str(self.mouse_id)],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split("\n"):
                    if "libinput Accel Speed" in line and "Default" not in line:
                        val = float(line.split(":")[-1].strip())
                        return round((val + 1.0) / 2.0 * 100)
            except Exception:
                pass
        return self.current_sensitivity

    def set_dpi(self, dpi):
        """Define DPI (ajusta via sensibilidade do sistema)"""
        dpi = max(DPI_MIN, min(DPI_MAX, int(dpi)))
        dpi = round(dpi / DPI_STEP) * DPI_STEP
        self.current_dpi = dpi
        # Tenta via HID++
        self._try_hid_dpi(dpi)
        # Fallback: ajusta sensibilidade proporcional
        sens = int(((dpi - DPI_MIN) / (DPI_MAX - DPI_MIN)) * 100)
        self.set_sensitivity(max(10, min(90, 50 + (dpi - 800) // 100)))
        self.config["dpi"] = dpi
        self._save_config()
        return True

    def _try_hid_dpi(self, dpi):
        """Tenta ajustar DPI via HID++"""
        hidraw = "/dev/hidraw0"
        if not os.path.exists(hidraw) or not os.access(hidraw, os.W_OK):
            return False
        try:
            fd = os.open(hidraw, os.O_RDWR | os.O_NONBLOCK)
            report = bytearray(7)
            report[0] = 0x10
            report[1] = 0x10
            report[2] = 0x00
            report[3] = (dpi >> 8) & 0xFF
            report[4] = dpi & 0xFF
            os.write(fd, bytes(report))
            os.close(fd)
            return True
        except Exception:
            return False

    def _load_config(self):
        if CONFIG_PATH.exists():
            try:
                return json.loads(CONFIG_PATH.read_text())
            except Exception:
                pass
        return {"dpi": 800, "sensitivity": 50}

    def _save_config(self):
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(json.dumps(self.config, indent=2))
        except Exception:
            pass

    def is_minecraft_focused(self):
        """Detecta se Minecraft/Lunar Client esta em foco"""
        try:
            result = subprocess.run(["xdotool", "getactivewindow"],
                                    capture_output=True, text=True, timeout=2)
            if result.returncode != 0:
                return False
            wid = result.stdout.strip()
            result = subprocess.run(["xdotool", "getwindowname", wid],
                                    capture_output=True, text=True, timeout=2)
            if result.returncode != 0:
                return False
            name = result.stdout.strip().lower()
            keywords = ["minecraft", "lunar client", "lunar",
                        "badlion", "feather", "hypixel", "mina launcher",
                        "prismarine", "salwyrr", "vanilla"]
            return any(k in name for k in keywords)
        except Exception:
            return False


class AutoClickerEngine:
    """Motor do auto-clicker — delega ao engine nativo compartilhado
    (mouse_hub.automation.autoclicker), que mantém o estado real
    (stopped/running/blocked_by_focus/failed) e a regra atual de foco.

    Esta classe permanece como fachada mínima para não quebrar as páginas
    existentes que acessam self.ac.cps / .button / .running.
    """

    def __init__(self, mouse_controller):
        from mouse_hub.automation import (
            AutoClickerEngine as _NativeEngine,
            XdotoolFocusDetector,
        )
        # Mantém o detector atual do produto (xdotool, janela permitida
        # em foco) via componente injetável e testável.
        self._native = _NativeEngine(focus_detector=XdotoolFocusDetector())
        self._mc = mouse_controller

    # ── compatibilidade com a UI existente ──
    @property
    def running(self):
        """Fonte de verdade: estado real do motor, não o botão da UI."""
        from mouse_hub.automation import AutoClickerState
        return self._native.state in (
            AutoClickerState.RUNNING,
            AutoClickerState.BLOCKED_BY_FOCUS,
        )

    @property
    def state(self):
        return self._native.state

    @property
    def error(self):
        return self._native.error

    @property
    def cps(self):
        return self._native.cps

    @cps.setter
    def cps(self, value):
        self._native.set_cps(value)

    @property
    def button(self):
        return self._native.button

    @button.setter
    def button(self, value):
        self._native.set_button(value)

    def start(self):
        return self._native.start()

    def stop(self):
        return self._native.stop()

    def cleanup(self):
        self._native.cleanup()


class MacroEngine:
    """Motor de macros — delega ao pacote nativo compartilhado
    (mouse_hub.automation): modelo versionável, captura real via XRecord,
    playback com relógio monotônico e persistência validada.

    A interface pública mantém o formato usado pelas páginas PyQt
    (recording, start_recording, stop_recording, play, delete, list_all),
    adicionando o capturador real e o controller de playback.
    """

    def __init__(self):
        # Lazy initialization (Issue #12): store, capturador e player só
        # são criados quando a primeira operação de macro acontece,
        # para o app abrir a janela sem carregar XRecord nem ler disco
        # antes de o usuário usar a feature.
        self._store = None
        self._player = None
        self._capture = None
        self._events = []
        self._initialized = False

    def _init_if_needed(self):
        if self._initialized:
            return
        self._initialized = True
        from mouse_hub.automation import (
            MacroStore,
            PlaybackController,
            InputCapture,
        )
        self._store = MacroStore(MACROS_PATH)
        self._player = PlaybackController(self._store)
        self._capture = InputCapture(sink=self._on_captured_event)
        if self._store.load_warnings:
            for w in self._store.load_warnings:
                print(f"[MACRO] {w}")

    @property
    def recording(self):
        self._init_if_needed()
        return self._capture.state.value == "active"

    @property
    def capture_failed(self):
        self._init_if_needed()
        return self._capture.failed_reason

    @property
    def macros(self):
        """Compat: dict {nome: info} usado por MacrosPage."""
        self._init_if_needed()
        return self._store.list_all()

    @property
    def player(self):
        self._init_if_needed()
        return self._player

    @property
    def store(self):
        self._init_if_needed()
        return self._store

    def start_recording(self, name):
        """Inicia gravação real. Se o capturador não conseguir abrir o
        display X, gravação não inicia e o motivo fica acessível em
        self.capture_failed."""
        self._init_if_needed()
        if self.recording:
            return
        self._events = []
        # limpa estado de falha anterior para nova tentativa
        if self._capture.state.value == "failed":
            self._capture = InputCapture(sink=self._on_captured_event)
        self._capture.start()
        self._capture_name = name
        self._capture_start = time.monotonic()

    def _on_captured_event(self, event):
        """Sink do capturador: acumula eventos com timing monotônico."""
        self._events.append(event)

    def stop_recording(self):
        if not self.recording:
            return None
        self._capture.stop()
        name = getattr(self, "_capture_name", "macro")
        ok, result = self._store.upsert_events(name, self._events)
        self._capture.cleanup()
        if not ok:
            print(f"[MACRO] gravação descartada: {result}")
            return None
        return result

    def play(self, name, repeat=1):
        """Inicia reprodução no worker de playback; valida antes."""
        self._init_if_needed()
        if not self._player.start(name, repeat=repeat):
            print(f"[MACRO] play rejeitado: {self._player.error}")
            return False
        return True

    def delete(self, name):
        self._init_if_needed()
        return self._store.delete(name)

    def list_all(self):
        self._init_if_needed()
        return self._store.list_all()

    def cleanup(self):
        """Encerramento completo: para captura e playback.
        Safe quando a engine nunca foi usada (nada foi criado)."""
        if self._capture is not None:
            self._capture.cleanup()
        if self._player is not None:
            self._player.cleanup()


# ═══════════════════════════════════════════════════════════════════════════════
#  UI COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

class GlowLabel(QLabel):
    """Label com efeito glow"""
    def __init__(self, text, color=COLORS["accent_light"], size=14, bold=True):
        super().__init__(text)
        self.setStyleSheet(f"""
            color: {color};
            font-size: {size}px;
            font-weight: {'700' if bold else '400'};
            background: transparent;
        """)


class StatCard(QFrame):
    """Card de estatistica"""
    def __init__(self, icon, title, value, color=COLORS["accent"]):
        super().__init__()
        self.setFixedSize(140, 88)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
            QFrame:hover {{
                border-color: {color};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)

        top = QHBoxLayout()
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"font-size: 20px; background: transparent;")
        top.addWidget(icon_label)
        top.addStretch()
        layout.addLayout(top)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"""
            color: {color};
            font-size: 22px;
            font-weight: 900;
            background: transparent;
        """)
        layout.addWidget(self.value_label)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            color: {COLORS['text_muted']};
            font-size: 11px;
            font-weight: 600;
            background: transparent;
            text-transform: uppercase;
        """)
        layout.addWidget(title_label)

    def set_value(self, val):
        self.value_label.setText(str(val))


class SidebarButton(QPushButton):
    """Botao da sidebar"""
    def __init__(self, icon, text, index):
        super().__init__(f"  {icon}  {text}")
        self.index = index
        self.setFixedHeight(40)
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_secondary']};
                border: none;
                border-radius: 8px;
                text-align: left;
                padding-left: 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {COLORS['sidebar_hover']};
                color: {COLORS['text_primary']};
            }}
        """)

    def set_active(self, active):
        if active:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['sidebar_active']};
                    color: {COLORS['accent_light']};
                    border-left: 3px solid {COLORS['accent']};
                    border-radius: 8px;
                    text-align: left;
                    padding-left: 13px;
                    font-size: 13px;
                    font-weight: 700;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {COLORS['text_secondary']};
                    border: none;
                    border-radius: 8px;
                    text-align: left;
                    padding-left: 16px;
                    font-size: 13px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {COLORS['sidebar_hover']};
                    color: {COLORS['text_primary']};
                }}
            """)


class AccentButton(QPushButton):
    """Botao de acao principal (estilo Feather Client)"""
    def __init__(self, text, color=COLORS["accent"], icon=""):
        super().__init__(f"{icon}  {text}" if icon else text)
        self.setMinimumHeight(38)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self._color = color
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {color}, stop:1 {COLORS['accent_light']});
                color: white;
                border: none;
                border-radius: 10px;
                padding: 8px 20px;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['accent_light']}, stop:1 #c4b5fd);
            }}
            QPushButton:pressed {{
                background: {COLORS['accent_dark']};
            }}
        """)


class DangerButton(QPushButton):
    """Botao de perigo"""
    def __init__(self, text, icon=""):
        super().__init__(f"{icon}  {text}" if icon else text)
        self.setMinimumHeight(38)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['danger']}, stop:1 #f87171);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 8px 20px;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #f87171, stop:1 #fca5a5);
            }}
        """)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGES
# ═══════════════════════════════════════════════════════════════════════════════

class DashboardPage(QWidget):
    """Pagina principal - Dashboard"""
    def __init__(self, mc, ac, me):
        super().__init__()
        self.mc = mc
        self.ac = ac
        self.me = me
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(12)

        # Title
        title = QLabel("🖱️  Mouse Hub Dashboard")
        title.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {COLORS['text_primary']}; background: transparent;")
        layout.addWidget(title)

        subtitle = QLabel(f"Mouse: {MOUSE_NAME}  •  Conectado via xinput")
        subtitle.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; background: transparent;")
        layout.addWidget(subtitle)

        # Stats row
        stats = QHBoxLayout()
        stats.setSpacing(16)

        self.dpi_card = StatCard("🎯", "DPI", str(self.mc.current_dpi), COLORS["accent"])
        self.sens_card = StatCard("🎚️", "SENSIBILIDADE", f"{self.mc.current_sensitivity}%", COLORS["success"])
        self.mc_card = StatCard("⛏️", "MINECRAFT", "OFF", COLORS["text_muted"])
        self.clicker_card = StatCard("⚡", "AUTO-CLICKER", "OFF", COLORS["danger"])

        stats.addWidget(self.dpi_card)
        stats.addWidget(self.sens_card)
        stats.addWidget(self.mc_card)
        stats.addWidget(self.clicker_card)
        stats.addStretch()
        layout.addLayout(stats)

        # Quick actions
        layout.addWidget(self._spacer(10))

        actions_title = QLabel("⚡  Ações Rápidas")
        actions_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text_primary']}; background: transparent;")
        layout.addWidget(actions_title)

        presets = QHBoxLayout()
        presets.setSpacing(12)

        for name, dpi in [("CS:GO AWP", 400), ("FPS Geral", 800),
                          ("Minecraft PvP", 1200), ("Flick Shots", 1600)]:
            btn = AccentButton(f"{name}\n{dpi} DPI", COLORS["bg_card"])
            btn.setFixedSize(130, 52)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['bg_card']};
                    color: {COLORS['text_primary']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 12px;
                    padding: 8px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    border-color: {COLORS['accent']};
                    background: {COLORS['bg_card_hover']};
                }}
            """)
            btn.clicked.connect(lambda _, d=dpi: self.mc.set_dpi(d))
            presets.addWidget(btn)
        presets.addStretch()
        layout.addLayout(presets)

        # Log area
        layout.addWidget(self._spacer(10))

        log_title = QLabel("📋  Log de Atividade")
        log_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text_primary']}; background: transparent;")
        layout.addWidget(log_title)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        self.log.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                padding: 12px;
                font-family: 'Cascadia Code', 'Fira Code', monospace;
                font-size: 12px;
                color: {COLORS['text_secondary']};
            }}
        """)
        layout.addWidget(self.log)

        layout.addStretch()

        # Timer to update
        self.timer = QTimer()
        self.timer.timeout.connect(self._update)
        self.timer.start(2000)

        self._update()

    def _update(self):
        self.dpi_card.set_value(str(self.mc.current_dpi))
        self.sens_card.set_value(f"{self.mc.current_sensitivity}%")

        mc_active = self.mc.is_minecraft_focused()
        self.mc_card.set_value("ON" if mc_active else "OFF")
        self.mc_card.value_label.setStyleSheet(f"""
            color: {COLORS['mc_green'] if mc_active else COLORS['text_muted']};
            font-size: 24px; font-weight: 900; background: transparent;
        """)

        # Estado real do motor (running | blocked_by_focus contam como ON)
        clicker_on = self.ac.state.value in ("running", "blocked_by_focus")
        self.clicker_card.set_value("ON" if clicker_on else "OFF")
        self.clicker_card.value_label.setStyleSheet(f"""
            color: {COLORS['danger'] if clicker_on else COLORS['text_muted']};
            font-size: 24px; font-weight: 900; background: transparent;
        """)

    def log_msg(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.append(f"[{ts}] {msg}")

    def _spacer(self, h):
        s = QLabel()
        s.setFixedHeight(h)
        return s


class DPIPage(QWidget):
    """Pagina de controle de DPI"""
    def __init__(self, mc):
        super().__init__()
        self.mc = mc
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(12)

        title = QLabel("🎯  Controle de DPI")
        title.setStyleSheet(f"font-size: 24px; font-weight: 900; background: transparent;")
        layout.addWidget(title)

        # DPI Display
        display = QFrame()
        display.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {COLORS['bg_card']}, stop:1 {COLORS['bg_mid']});
                border: 1px solid {COLORS['border']};
                border-radius: 16px;
                padding: 20px;
            }}
        """)
        dl = QVBoxLayout(display)
        dl.setAlignment(Qt.AlignCenter)

        self.dpi_value = QLabel(str(self.mc.current_dpi))
        self.dpi_value.setAlignment(Qt.AlignCenter)
        self.dpi_value.setStyleSheet(f"""
            color: {COLORS['accent_light']};
            font-size: 56px;
            font-weight: 900;
            background: transparent;
        """)
        dl.addWidget(self.dpi_value)

        dpi_label = QLabel("DOTS PER INCH")
        dpi_label.setAlignment(Qt.AlignCenter)
        dpi_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 700; letter-spacing: 2px; background: transparent;")
        dl.addWidget(dpi_label)

        layout.addWidget(display)

        # Slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(DPI_MIN)
        self.slider.setMaximum(DPI_MAX)
        self.slider.setSingleStep(DPI_STEP)
        self.slider.setPageStep(200)
        self.slider.setValue(self.mc.current_dpi)
        self.slider.valueChanged.connect(self._on_slider)
        layout.addWidget(self.slider)

        range_row = QHBoxLayout()
        min_l = QLabel(f"Min: {DPI_MIN}")
        min_l.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; background: transparent;")
        max_l = QLabel(f"Max: {DPI_MAX}")
        max_l.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; background: transparent;")
        range_row.addWidget(min_l)
        range_row.addStretch()
        range_row.addWidget(max_l)
        layout.addLayout(range_row)

        # Manual input
        input_row = QHBoxLayout()
        input_label = QLabel("Valor manual:")
        input_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px; background: transparent;")
        self.dpi_input = QLineEdit(str(self.mc.current_dpi))
        self.dpi_input.setFixedWidth(120)
        self.dpi_input.setAlignment(Qt.AlignCenter)
        self.dpi_input.setStyleSheet(f"""
            QLineEdit {{
                font-size: 18px;
                font-weight: 700;
                padding: 10px;
                border-radius: 10px;
            }}
        """)
        apply_btn = AccentButton("Aplicar")
        apply_btn.setFixedWidth(120)
        apply_btn.clicked.connect(self._apply_manual)
        input_row.addWidget(input_label)
        input_row.addWidget(self.dpi_input)
        input_row.addWidget(apply_btn)
        input_row.addStretch()
        layout.addLayout(input_row)

        # Presets
        presets_label = QLabel("⚡  Presets Rápidos")
        presets_label.setStyleSheet(f"font-size: 16px; font-weight: 700; background: transparent;")
        layout.addWidget(presets_label)

        presets = QHBoxLayout()
        presets.setSpacing(12)

        preset_data = [
            ("🎯 CS:GO AWP", 400, COLORS["success"]),
            ("🔫 FPS Geral", 800, COLORS["accent"]),
            ("⛏️ Minecraft PvP", 1200, COLORS["warning"]),
            ("⚡ Flick Shots", 1600, COLORS["danger"]),
            ("🚀 Máximo", 25600, COLORS["text_muted"]),
        ]

        for name, dpi, color in preset_data:
            btn = QPushButton(f"{name}\n{dpi} DPI")
            btn.setFixedHeight(70)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['bg_card']};
                    color: {color};
                    border: 1px solid {COLORS['border']};
                    border-radius: 12px;
                    padding: 10px;
                    font-size: 12px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    border-color: {color};
                    background: {COLORS['bg_card_hover']};
                }}
            """)
            btn.clicked.connect(lambda _, d=dpi: self._set_preset(d))
            presets.addWidget(btn)
        layout.addLayout(presets)

        layout.addStretch()

    def _on_slider(self, val):
        val = round(val / DPI_STEP) * DPI_STEP
        self.dpi_value.setText(str(val))
        self.dpi_input.setText(str(val))

    def _apply_manual(self):
        try:
            val = int(self.dpi_input.text())
            self.mc.set_dpi(val)
            self.slider.setValue(val)
            self.dpi_value.setText(str(val))
        except ValueError:
            pass

    def _set_preset(self, dpi):
        self.mc.set_dpi(dpi)
        self.slider.setValue(dpi)
        self.dpi_value.setText(str(dpi))
        self.dpi_input.setText(str(dpi))


class SensitivityPage(QWidget):
    """Pagina de sensibilidade"""
    def __init__(self, mc):
        super().__init__()
        self.mc = mc
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(12)

        title = QLabel("🎚️  Sensibilidade")
        title.setStyleSheet(f"font-size: 20px; font-weight: 900; background: transparent;")
        layout.addWidget(title)

        # Display
        display = QFrame()
        display.setFixedHeight(130)
        display.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 16px;
            }}
        """)
        dl = QVBoxLayout(display)

        self.sens_value = QLabel(f"{self.mc.current_sensitivity}%")
        self.sens_value.setAlignment(Qt.AlignCenter)
        self.sens_value.setStyleSheet(f"""
            color: {COLORS['success']};
            font-size: 48px;
            font-weight: 900;
            background: transparent;
        """)
        dl.addWidget(self.sens_value)

        sl = QLabel("VELOCIDADE DO SISTEMA (libinput)")
        sl.setAlignment(Qt.AlignCenter)
        sl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 700; background: transparent;")
        dl.addWidget(sl)

        layout.addWidget(display)

        # Slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.setValue(self.mc.current_sensitivity)
        self.slider.valueChanged.connect(self._on_slider)
        layout.addWidget(self.slider)

        hint = QHBoxLayout()
        hint.addWidget(QLabel("🐢 Lento"))
        hint.addStretch()
        hint.addWidget(QLabel("🐇 Rápido"))
        for i in range(hint.count()):
            w = hint.itemAt(i).widget()
            if w:
                w.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; background: transparent;")
        layout.addLayout(hint)

        # Speed bar
        bar_frame = QFrame()
        bar_frame.setFixedHeight(8)
        bar_frame.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_input']};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(bar_frame)

        layout.addStretch()

        # Polling rate
        pr_title = QLabel("📡  Polling Rate")
        pr_title.setStyleSheet(f"font-size: 16px; font-weight: 700; background: transparent;")
        layout.addWidget(pr_title)

        pr_row = QHBoxLayout()
        pr_row.setSpacing(12)
        for hz in ["125 Hz", "250 Hz", "500 Hz", "1000 Hz"]:
            btn = QPushButton(hz)
            btn.setFixedHeight(44)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            active = hz == "1000 Hz"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['accent'] if active else COLORS['bg_card']};
                    color: {'white' if active else COLORS['text_secondary']};
                    border: 1px solid {COLORS['accent'] if active else COLORS['border']};
                    border-radius: 10px;
                    font-size: 13px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    border-color: {COLORS['accent']};
                }}
            """)
            pr_row.addWidget(btn)
        pr_row.addStretch()
        layout.addLayout(pr_row)

        layout.addStretch()

    def _on_slider(self, val):
        self.sens_value.setText(f"{val}%")
        self.mc.set_sensitivity(val)


class AutoClickerPage(QWidget):
    """Pagina do Auto-Clicker"""
    def __init__(self, mc, ac):
        super().__init__()
        self.mc = mc
        self.ac = ac
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(12)

        title = QLabel("⚡  Auto-Clicker")
        title.setStyleSheet(f"font-size: 24px; font-weight: 900; background: transparent;")
        layout.addWidget(title)

        badge = QLabel("⛏️  FUNCIONA APENAS NO MINECRAFT / LUNAR CLIENT")
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"""
            background: rgba(74, 222, 128, 0.1);
            color: {COLORS['mc_green']};
            border: 1px solid rgba(74, 222, 128, 0.3);
            border-radius: 10px;
            padding: 10px;
            font-size: 12px;
            font-weight: 700;
        """)
        layout.addWidget(badge)

        # Status
        self.status_frame = QFrame()
        self.status_frame.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border: 2px solid {COLORS['border']};
                border-radius: 16px;
                padding: 20px;
            }}
        """)
        sl = QHBoxLayout(self.status_frame)

        self.status_icon = QLabel("🖱️")
        self.status_icon.setStyleSheet("font-size: 36px; background: transparent;")
        sl.addWidget(self.status_icon)

        info = QVBoxLayout()
        self.status_title = QLabel("Auto-Clicker Desligado")
        self.status_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text_primary']}; background: transparent;")
        self.status_sub = QLabel("Clique em iniciar para começar")
        self.status_sub.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']}; background: transparent;")
        info.addWidget(self.status_title)
        info.addWidget(self.status_sub)
        sl.addLayout(info)
        sl.addStretch()

        layout.addWidget(self.status_frame)

        # Minecraft detection
        self.mc_status = QLabel("⛏️  Minecraft não detectado")
        self.mc_status.setStyleSheet(f"""
            background: rgba(239, 68, 68, 0.1);
            color: {COLORS['danger']};
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 10px;
            padding: 10px;
            font-size: 12px;
            font-weight: 600;
        """)
        layout.addWidget(self.mc_status)

        # CPS Control
        cps_title = QLabel("🔥  CPS (Clicks Por Segundo)")
        cps_title.setStyleSheet(f"font-size: 16px; font-weight: 700; background: transparent;")
        layout.addWidget(cps_title)

        cps_row = QHBoxLayout()
        self.cps_slider = QSlider(Qt.Horizontal)
        self.cps_slider.setMinimum(1)
        self.cps_slider.setMaximum(50)
        self.cps_slider.setValue(self.ac.cps)
        self.cps_slider.valueChanged.connect(self._on_cps)
        cps_row.addWidget(self.cps_slider)

        self.cps_display = QLabel(f"{self.ac.cps}")
        self.cps_display.setFixedWidth(80)
        self.cps_display.setAlignment(Qt.AlignCenter)
        self.cps_display.setStyleSheet(f"""
            color: {COLORS['warning']};
            font-size: 30px;
            font-weight: 900;
            background: transparent;
        """)
        cps_row.addWidget(self.cps_display)

        cps_unit = QLabel("CPS")
        cps_unit.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 14px; font-weight: 600; background: transparent;")
        cps_row.addWidget(cps_unit)
        layout.addLayout(cps_row)

        # Button selector
        btn_title = QLabel("👆  Botão")
        btn_title.setStyleSheet(f"font-size: 16px; font-weight: 700; background: transparent;")
        layout.addWidget(btn_title)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.btn_buttons = []
        for i, (name, icon) in enumerate([(  "Esquerdo", "🖱️"), ("Meio", "🔘"), ("Direito", "🖱️")]):
            btn = QPushButton(f"{icon}  {name}")
            btn.setFixedHeight(44)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            active = (i + 1) == self.ac.button
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['accent'] if active else COLORS['bg_card']};
                    color: {'white' if active else COLORS['text_secondary']};
                    border: 1px solid {COLORS['accent'] if active else COLORS['border']};
                    border-radius: 10px;
                    font-size: 13px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    border-color: {COLORS['accent']};
                }}
            """)
            btn.clicked.connect(lambda _, b=i+1: self._set_button(b))
            btn_row.addWidget(btn)
            self.btn_buttons.append((btn, i+1))
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Start / Stop
        self.toggle_btn = AccentButton("▶️  Iniciar Auto-Clicker")
        self.toggle_btn.setMinimumHeight(44)
        self.toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self.toggle_btn)

        layout.addStretch()

        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._update)
        self.timer.start(1000)

    def _on_cps(self, val):
        self.ac.cps = val
        self.cps_display.setText(str(val))
        self.status_sub.setText(f"{val} CPS — Botão {self.ac.button}")

    def _set_button(self, btn):
        self.ac.button = btn
        for widget, b in self.btn_buttons:
            active = b == btn
            widget.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['accent'] if active else COLORS['bg_card']};
                    color: {'white' if active else COLORS['text_secondary']};
                    border: 1px solid {COLORS['accent'] if active else COLORS['border']};
                    border-radius: 10px;
                    font-size: 13px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    border-color: {COLORS['accent']};
                }}
            """)
        self.status_sub.setText(f"{self.ac.cps} CPS — Botão {btn}")

    def _toggle(self):
        if self.ac.running:
            self.ac.stop()
            self.toggle_btn.setText("▶️  Iniciar Auto-Clicker")
            self.toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {COLORS['accent']}, stop:1 {COLORS['accent_light']});
                    color: white;
                    border: none;
                    border-radius: 10px;
                    padding: 8px 20px;
                    font-size: 14px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {COLORS['accent_light']}, stop:1 #c4b5fd);
                }}
            """)
            self.status_title.setText("Auto-Clicker Desligado")
            self.status_sub.setText("Clique em iniciar para começar")
            self.status_icon.setText("🖱️")
            self.status_frame.setStyleSheet(f"""
                QFrame {{
                    background: {COLORS['bg_card']};
                    border: 2px solid {COLORS['border']};
                    border-radius: 16px;
                    padding: 20px;
                }}
            """)
        else:
            self.ac.start()
            self.toggle_btn.setText("⏹️  Parar Auto-Clicker")
            self.toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {COLORS['danger']}, stop:1 #f87171);
                    color: white;
                    border: none;
                    border-radius: 10px;
                    padding: 8px 20px;
                    font-size: 14px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #f87171, stop:1 #fca5a5);
                }}
            """)
            self.status_title.setText("Auto-Clicker Ativo!")
            self.status_icon.setText("🔥")
            self.status_frame.setStyleSheet(f"""
                QFrame {{
                    background: {COLORS['bg_card']};
                    border: 2px solid {COLORS['danger']};
                    border-radius: 16px;
                    padding: 20px;
                }}
            """)

    def _update(self):
        mc_active = self.mc.is_minecraft_focused()
        if mc_active:
            self.mc_status.setText("⛏️  Minecraft Detectado!")
            self.mc_status.setStyleSheet(f"""
                background: rgba(74, 222, 128, 0.1);
                color: {COLORS['mc_green']};
                border: 1px solid rgba(74, 222, 128, 0.3);
                border-radius: 10px;
                padding: 10px;
                font-size: 12px;
                font-weight: 600;
            """)
        else:
            self.mc_status.setText("⛏️  Minecraft não detectado — auto-clicker não vai clicar")
            self.mc_status.setStyleSheet(f"""
                background: rgba(239, 68, 68, 0.1);
                color: {COLORS['danger']};
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 10px;
                padding: 10px;
                font-size: 12px;
                font-weight: 600;
            """)

        # Estado real do motor como fonte de verdade (não o botão da UI)
        state = self.ac.state
        if state.value == "running":
            btn_name = {1: "esquerdo", 2: "meio", 3: "direito"}.get(
                self.ac.button, "?")
            self.status_title.setText("Auto-Clicker Ativo!")
            self.status_sub.setText(f"{self.ac.cps} CPS — Botão {btn_name}")
            self.status_icon.setText("🔥")
            self.toggle_btn.setText("⏹️  Parar Auto-Clicker")
        elif state.value == "blocked_by_focus":
            self.status_title.setText("Aguardando jogo em foco...")
            self.status_sub.setText(
                "Ligado, mas só clica com Minecraft/Lunar Client ativo")
            self.status_icon.setText("⏳")
            self.toggle_btn.setText("⏹️  Parar Auto-Clicker")
        elif state.value == "failed":
            self.status_title.setText("Auto-Clicker com erro")
            self.status_sub.setText(f"Falha: {self.ac.error or 'desconhecida'}")
            self.status_icon.setText("⚠️")
            self.toggle_btn.setText("▶️  Iniciar Auto-Clicker")
        else:
            self.status_title.setText("Auto-Clicker Desligado")
            self.status_sub.setText("Clique em iniciar para começar")
            self.status_icon.setText("🖱️")
            self.toggle_btn.setText("▶️  Iniciar Auto-Clicker")


class MacrosPage(QWidget):
    """Pagina de Macros"""
    def __init__(self, me):
        super().__init__()
        self.me = me
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(12)

        title = QLabel("🎬  Macros")
        title.setStyleSheet(f"font-size: 24px; font-weight: 900; background: transparent;")
        layout.addWidget(title)

        # Record controls
        rec_frame = QFrame()
        rec_frame.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        rl = QVBoxLayout(rec_frame)

        rl.addWidget(QLabel("Nome da macro:"))
        self.name_input = QLineEdit("minha_macro")
        self.name_input.setStyleSheet(f"padding: 10px; font-size: 14px;")
        rl.addWidget(self.name_input)

        self.record_btn = DangerButton("⏺️  Gravar Macro")
        self.record_btn.clicked.connect(self._toggle_record)
        rl.addWidget(self.record_btn)

        self.record_status = QLabel("")
        self.record_status.setStyleSheet(f"color: {COLORS['danger']}; font-size: 12px; font-weight: 600; background: transparent;")
        rl.addWidget(self.record_status)

        layout.addWidget(rec_frame)

        # Macro list
        list_title = QLabel("📋  Macros Salvas")
        list_title.setStyleSheet(f"font-size: 16px; font-weight: 700; background: transparent;")
        layout.addWidget(list_title)

        self.macro_list_widget = QWidget()
        self.macro_list_layout = QVBoxLayout(self.macro_list_widget)
        self.macro_list_layout.setContentsMargins(0, 0, 0, 0)
        self.macro_list_layout.setSpacing(6)

        scroll = QScrollArea()
        scroll.setWidget(self.macro_list_widget)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        self._refresh_list()

    def _toggle_record(self):
        if self.me.recording:
            name = self.me.stop_recording()
            self.record_btn.setText("⏺️  Gravar Macro")
            if name is None:
                self.record_status.setText(
                    "⚠️  Gravação descartada (sem eventos ou nome inválido)")
            else:
                count = self.me.macros.get(name, {}).get("count", 0)
                self.record_status.setText(
                    f"✅ Macro '{name}' salva! ({count} eventos)")
            self._refresh_list()
        else:
            name = self.name_input.text().strip() or \
                f"macro_{int(time.time())}"
            self.me.start_recording(name)
            if self.me.recording:
                self.record_btn.setText("⏹️  Parar Gravação")
                self.record_status.setText(
                    f"🔴 Gravando '{name}'... pressione parar quando "
                    "terminar. Teclas e cliques são capturados em "
                    "qualquer janela.")
            else:
                reason = self.me.capture_failed or "capturador indisponível"
                self.record_status.setText(
                    f"❌ Não foi possível iniciar a gravação: {reason}")

    def _refresh_list(self):
        # Clear
        while self.macro_list_layout.count():
            child = self.macro_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        macros = self.me.list_all()
        if not macros:
            empty = QLabel("Nenhuma macro gravada ainda")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color: {COLORS['text_muted']}; padding: 30px; font-size: 13px; background: transparent;")
            self.macro_list_layout.addWidget(empty)
            return

        for name, info in macros.items():
            item = QFrame()
            item.setStyleSheet(f"""
                QFrame {{
                    background: {COLORS['bg_card']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 10px;
                    padding: 12px;
                }}
                QFrame:hover {{
                    border-color: {COLORS['accent']};
                }}
            """)
            il = QHBoxLayout(item)

            info_col = QVBoxLayout()
            name_label = QLabel(f"🎬  {name}")
            name_label.setStyleSheet(f"font-size: 14px; font-weight: 700; background: transparent;")
            info_col.addWidget(name_label)

            meta = QLabel(f"{info['count']} eventos  •  {info['created'][:10]}")
            meta.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; background: transparent;")
            info_col.addWidget(meta)
            il.addLayout(info_col)

            il.addStretch()

            play_btn = QPushButton("▶️ Play")
            play_btn.setFixedSize(80, 32)
            play_btn.setCursor(QCursor(Qt.PointingHandCursor))
            play_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['accent']};
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 12px;
                    font-weight: 700;
                }}
                QPushButton:hover {{ background: {COLORS['accent_light']}; }}
            """)
            play_btn.clicked.connect(lambda _, n=name: self.me.play(n))
            il.addWidget(play_btn)

            del_btn = QPushButton("🗑️")
            del_btn.setFixedSize(32, 32)
            del_btn.setCursor(QCursor(Qt.PointingHandCursor))
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid {COLORS['border']};
                    border-radius: 8px;
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    border-color: {COLORS['danger']};
                    background: rgba(239, 68, 68, 0.1);
                }}
            """)
            del_btn.clicked.connect(lambda _, n=name: self._delete(n))
            il.addWidget(del_btn)

            self.macro_list_layout.addWidget(item)

        self.macro_list_layout.addStretch()

    def _delete(self, name):
        self.me.delete(name)
        self._refresh_list()

class ProfilesPage(QWidget):
    """Pagina de Perfis"""
    def __init__(self, mc):
        super().__init__()
        self.mc = mc
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(12)

        title = QLabel("👤  Perfis")
        title.setStyleSheet(f"font-size: 24px; font-weight: 900; background: transparent;")
        layout.addWidget(title)

        profiles = [
            ("⛏️", "Minecraft PvP", 1200, 60, COLORS["mc_green"]),
            ("🔫", "CS:GO", 400, 30, COLORS["accent"]),
            ("⚙️", "Default", 800, 50, COLORS["text_secondary"]),
            ("✨", "Fortnite", 1600, 70, COLORS["warning"]),
        ]

        grid = QGridLayout()
        grid.setSpacing(16)

        for i, (icon, name, dpi, sens, color) in enumerate(profiles):
            card = QFrame()
            card.setFixedSize(180, 140)
            card.setCursor(QCursor(Qt.PointingHandCursor))
            card.setStyleSheet(f"""
                QFrame {{
                    background: {COLORS['bg_card']};
                    border: 2px solid {COLORS['border']};
                    border-radius: 16px;
                    padding: 16px;
                }}
                QFrame:hover {{
                    border-color: {color};
                }}
            """)
            cl = QVBoxLayout(card)

            ic = QLabel(icon)
            ic.setStyleSheet(f"font-size: 32px; background: transparent;")
            cl.addWidget(ic)

            nm = QLabel(name)
            nm.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {color}; background: transparent;")
            cl.addWidget(nm)

            det = QLabel(f"DPI: {dpi}  •  Sens: {sens}%")
            det.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; background: transparent;")
            cl.addWidget(det)

            cl.addStretch()

            # Button
            apply = QPushButton("Aplicar")
            apply.setCursor(QCursor(Qt.PointingHandCursor))
            apply.setStyleSheet(f"""
                QPushButton {{
                    background: {color};
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 6px;
                    font-size: 12px;
                    font-weight: 700;
                }}
                QPushButton:hover {{ opacity: 0.8; }}
            """)
            apply.clicked.connect(lambda _, d=dpi, s=sens: self._apply(d, s))
            cl.addWidget(apply)

            grid.addWidget(card, i // 2, i % 2)

        layout.addLayout(grid)
        layout.addStretch()

    def _apply(self, dpi, sens):
        self.mc.set_dpi(dpi)
        self.mc.set_sensitivity(sens)


class SettingsPage(QWidget):
    """Pagina de Configuracoes"""
    def __init__(self, mc, ac, me):
        super().__init__()
        self.mc = mc
        self.ac = ac
        self.me = me
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(12)

        title = QLabel("⚙️  Configurações")
        title.setStyleSheet(f"font-size: 24px; font-weight: 900; background: transparent;")
        layout.addWidget(title)

        # HID Permissions
        hid_group = QGroupBox("🔐  Permissões HID (DPI via Hardware)")
        hid_layout = QVBoxLayout(hid_group)

        hid_info = QLabel(
            "Para controle direto de DPI no hardware do mouse, "
            "execute o comando abaixo no terminal:"
        )
        hid_info.setWordWrap(True)
        hid_info.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
        hid_layout.addWidget(hid_info)

        cmd_frame = QFrame()
        cmd_frame.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_input']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        cmd_layout = QHBoxLayout(cmd_frame)
        cmd_text = QLabel("sudo chmod 666 /dev/hidraw0")
        cmd_text.setStyleSheet(f"font-family: monospace; font-size: 13px; color: {COLORS['mc_green']}; background: transparent;")
        cmd_layout.addWidget(cmd_text)
        cmd_layout.addStretch()
        hid_layout.addWidget(cmd_frame)

        layout.addWidget(hid_group)

        # Auto-clicker settings
        ac_group = QGroupBox("⚡  Auto-Clicker — Segurança")
        ac_layout = QVBoxLayout(ac_group)

        safety_text = QLabel(
            "✅ O auto-clicker só funciona quando Minecraft/Lunar Client está em foco.\n"
            "✅ O detector verifica o nome da janela ativa a cada ciclo.\n"
            "✅ Nenhum clique é feito fora do jogo."
        )
        safety_text.setWordWrap(True)
        safety_text.setStyleSheet(f"color: {COLORS['mc_green']}; font-size: 12px; background: transparent;")
        ac_layout.addWidget(safety_text)

        layout.addWidget(ac_group)

        # System info
        info_group = QGroupBox("💻  Informações do Sistema")
        info_layout = QVBoxLayout(info_group)

        info = QLabel(
            f"Mouse: {MOUSE_NAME}\n"
            f"Sistema: Linux (xinput)\n"
            f"Python: {sys.version.split()[0]}\n"
            f"Config: {CONFIG_PATH}\n"
            f"Macros: {MACROS_PATH}\n"
            f"Porta Web: 7777"
        )
        info.setStyleSheet(f"font-family: monospace; font-size: 12px; color: {COLORS['text_secondary']}; background: transparent;")
        info_layout.addWidget(info)

        layout.addWidget(info_group)

        layout.addStretch()


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════════════

class MouseHubApp(QMainWindow):
    """Janela principal do Mouse Hub"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🖱️ Mouse Hub — Controlador Gamer")
        self.setMinimumSize(900, 600)
        self.resize(1050, 680)

        # Centraliza na tela automaticamente
        screen = QApplication.primaryScreen().geometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)

        # Engines
        self.mc = MouseController()
        self.ac = AutoClickerEngine(self.mc)
        self.me = MacroEngine()

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ─── Sidebar ───
        sidebar = QFrame()
        sidebar.setFixedWidth(190)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['sidebar_bg']};
                border-right: 1px solid {COLORS['border']};
            }}
        """)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(10, 12, 10, 12)
        sb_layout.setSpacing(2)

        # Logo
        logo_frame = QFrame()
        logo_frame.setFixedHeight(50)
        logo_layout = QHBoxLayout(logo_frame)
        logo_layout.setContentsMargins(4, 0, 4, 0)
        icon = QLabel("🖱️")
        icon.setStyleSheet("font-size: 28px; background: transparent;")
        logo_layout.addWidget(icon)
        logo_text = QLabel("MOUSE\nHUB")
        logo_text.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 900;
            color: {COLORS['accent_light']};
            background: transparent;
            line-height: 1.1;
        """)
        logo_layout.addWidget(logo_text)
        logo_layout.addStretch()
        sb_layout.addWidget(logo_frame)

        sb_layout.addSpacing(10)

        # Status
        self.status_indicator = QFrame()
        self.status_indicator.setFixedHeight(32)
        self.status_indicator.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['bg_card']};
                border-radius: 18px;
                padding: 4px 12px;
            }}
        """)
        si_layout = QHBoxLayout(self.status_indicator)
        si_layout.setContentsMargins(8, 0, 8, 0)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {COLORS['success']}; font-size: 10px; background: transparent;")
        si_layout.addWidget(dot)
        si_text = QLabel("Online")
        si_text.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; font-weight: 600; background: transparent;")
        si_layout.addWidget(si_text)
        si_layout.addStretch()
        sb_layout.addWidget(self.status_indicator)

        sb_layout.addSpacing(8)

        # Nav buttons
        self.nav_buttons = []
        pages_data = [
            ("📊", "Dashboard", 0),
            ("🎯", "DPI", 1),
            ("🎚️", "Sensibilidade", 2),
            ("⚡", "Auto-Clicker", 3),
            ("🎬", "Macros", 4),
            ("👤", "Perfis", 5),
            ("⚙️", "Configurações", 6),
        ]

        for icon, text, idx in pages_data:
            btn = SidebarButton(icon, text, idx)
            btn.clicked.connect(lambda _, i=idx: self._switch_page(i))
            sb_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sb_layout.addStretch()

        # Version
        ver = QLabel("v1.0.0 — Freebuff")
        ver.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px; background: transparent;")
        sb_layout.addWidget(ver)

        main_layout.addWidget(sidebar)

        # ─── Pages ───
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {COLORS['bg_darkest']};")

        self.dashboard_page = DashboardPage(self.mc, self.ac, self.me)
        self.dpi_page = DPIPage(self.mc)
        self.sens_page = SensitivityPage(self.mc)
        self.clicker_page = AutoClickerPage(self.mc, self.ac)
        self.macros_page = MacrosPage(self.me)
        self.profiles_page = ProfilesPage(self.mc)
        self.settings_page = SettingsPage(self.mc, self.ac, self.me)

        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.dpi_page)
        self.stack.addWidget(self.sens_page)
        self.stack.addWidget(self.clicker_page)
        self.stack.addWidget(self.macros_page)
        self.stack.addWidget(self.profiles_page)
        self.stack.addWidget(self.settings_page)

        main_layout.addWidget(self.stack)

        # Set active
        self._switch_page(0)

    def _switch_page(self, index):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.set_active(i == index)

    def closeEvent(self, event):
        # Encerramento completo: captura, playback e worker do clicker
        self.me.cleanup()
        self.ac.cleanup()
        event.accept()


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    # High DPI
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)

    # Dark palette
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLORS["bg_darkest"]))
    palette.setColor(QPalette.WindowText, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.Base, QColor(COLORS["bg_dark"]))
    palette.setColor(QPalette.AlternateBase, QColor(COLORS["bg_mid"]))
    palette.setColor(QPalette.ToolTipBase, QColor(COLORS["bg_card"]))
    palette.setColor(QPalette.ToolTipText, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.Text, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.Button, QColor(COLORS["bg_card"]))
    palette.setColor(QPalette.ButtonText, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.BrightText, QColor(COLORS["danger"]))
    palette.setColor(QPalette.Highlight, QColor(COLORS["accent"]))
    palette.setColor(QPalette.HighlightedText, QColor("white"))
    app.setPalette(palette)

    window = MouseHubApp()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
