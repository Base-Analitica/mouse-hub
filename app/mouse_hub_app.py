#!/usr/bin/env python3
"""
Mouse Hub — Aplicativo Nativo Desktop
======================================
App nativo estilo Feather Client para controle do Logitech G403 HERO
DPI, Sensibilidade, Macros e Auto-Clicker (Minecraft Only)
"""

import signal
import sys
import threading
import time
from pathlib import Path
from typing import Optional

# Bootstrap: o launcher executa este script a partir de app/;
# o pacote mouse_hub (automation) vive no repositório raiz.
_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
from datetime import datetime

# ── Core seguro (issue #3): DPI físico e sensibilidade separados, ──
# discovery real por VID/PID, OperationResult tipado e capacidades    ──
# granulares. A UI NUNCA mais acessa /dev/hidrawX ou subprocesso.     ──
from mouse_hub.core import (
    OperationResult,
    OperationStatus,
)
from mouse_hub.core.constants import (
    DPI_DEFAULT,
    DPI_PRESETS,
    G403_NAME,
    SENSITIVITY_DEFAULT,
)
from mouse_hub.core.discovery import discover
from mouse_hub.core.mouse_controller import (
    MouseController as CoreMouseController,
    make_linux_controller,
)
from mouse_hub.core.config import ConfigError, ConfigPaths
from mouse_hub.core.capabilities import CapabilityState
from mouse_hub.core.profiles import ProfileStore
from mouse_hub.platform.linux import LinuxHidAccess
from mouse_hub.platform.linux.input import LinuxSystemInput

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QFrame, QGraphicsDropShadowEffect,
    QScrollArea, QStackedWidget, QLineEdit, QSpinBox, QComboBox,
    QMessageBox, QProgressBar, QSystemTrayIcon, QMenu, QAction,
    QGroupBox, QGridLayout, QTextEdit
)
from PyQt5.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QSize,
    pyqtSignal, QObject, QPoint, QRect
)
# ── Core único de automação (arquitetura PR #14) ─────────────
# O AutomationService centraliza foco, gravação, playback e clicker —
# nada é criado no startup (lazy) e o hot path usa XTest/XRecord
# nativos, sem subprocessos (xdotool/xinput foram removidos do caminho
# de alta frequência).
from mouse_hub.core.automation.service import AutomationService
from mouse_hub.core.automation.types import MouseButton
from mouse_hub.platform.linux.automation import focus_patterns

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


# ── Controller legado DEPRECIADO (issue #3) ─────────────────────
# O controller abaixo vive na UI e é a fonte de TODOS os defeitos da
# issue #3: assume /dev/hidraw0, escreve em hardware não confirmado,
# mistura DPI físico com sensibilidade, altera a sensibilidade como
# fallback de falha de DPI e persiste o valor solicitado sem
# confirmação do hardware. Ele NÃO é mais usado — foi substituído por
# MouseCoreState (core seguro de mouse_hub.core) e pela composição
# make_linux_controller. A classe permanece apenas como stub inerte
# (defaults e no-op) para que as páginas que ainda recebem a instância
# como `mc` não quebrem; nenhum método dela tem efeito de hardware.
# Todo o acesso real passa pelo core.

class MouseController:
    """Stub legado do controller da UI (issue #3). DEPRECIADO.

    Não abre /dev/hidraw, não chama xinput e não persiste nada — os
    atributos de compatibilidade (current_dpi/current_sensitivity)
    existem só para as páginas que já foram migradas para ler o
    estado real de MouseCoreState. As páginas usam o core para os
    efeitos; este stub nunca mais executa nenhum caminho de hardware.
    """

    def __init__(self):
        self.current_dpi = DPI_DEFAULT
        self.current_sensitivity = SENSITIVITY_DEFAULT
        self.mouse_id = None
        self.config = {"dpi": DPI_DEFAULT, "sensitivity": SENSITIVITY_DEFAULT}

    def set_sensitivity(self, value):
        # Sem efeito de hardware — a UI usa MouseCoreState no core.
        self.current_sensitivity = max(0, min(100, int(value)))
        return True

    def get_sensitivity(self):
        return self.current_sensitivity

    def set_dpi(self, dpi):
        # Sem efeito de hardware — a UI usa MouseCoreState no core.
        dpi = max(DPI_MIN, min(DPI_MAX, int(dpi)))
        dpi = round(dpi / DPI_STEP) * DPI_STEP
        self.current_dpi = dpi
        return True

    # Observação de arquitetura (Issue #12): a detecção de foco não
    # vive mais aqui — consulta xdotool duplicava subprocess em cada
    # tick do dashboard. O foco agora é centralizado no
    # AutomationService (X11TitleSource + WindowFocusChecker com
    # cache TTL), compartilhado por Dashboard, Auto-Clicker e Macros.


# Valor exibido quando o estado físico NÃO é conhecido (nenhum ACK
# confirmou o valor). Unknown NUNCA vira default na UI (revisão PR #21):
# requested != applied != persisted; sem confirmação, não há valor a exibir.
UNKNOWN_VALUE_TEXT = "—"


# ═══════════════════════════════════════════════════════════════════════════════
#  CORE STATE (issue #3)
# ═══════════════════════════════════════════════════════════════════════════════

class MouseCoreState:
    """Estado observável do core para a UI.

    Fonte única de verdade para DPI físico, sensibilidade e capacidades:
    * os valores exibidos são os EFETIVAMENTE CONFIRMADOS pelo hardware
      (core.MouseController.applied_dpi/applied_sensitivity) — nunca o
      valor solicitado;
    * o refresh() roda discovery real (VID 046d / PID c08f), registra o
      dispositivo no controller (validação de identidade antes de
      qualquer efeito), probeia o endpoint HID++ e reavalia as
      capacidades granulares;
    * capacidades de HID/DPI são invalidadas após falha real de acesso
      (open/write/read sem ACK) — o core é fail closed.

    DPI físico e sensibilidade são operações independentes: esta classe
    nunca altera a sensibilidade como consequência de uma operação de
    DPI, e nunca reporta sucesso de DPI quando o hardware não confirmou.
    """

    def __init__(self, core: CoreMouseController):
        self._core = core
        # Lock único de acesso ao controller (revisão PR #21): refresh/
        # probe e operações nunca executam simultaneamente. RLock porque
        # _evaluate() percorre capability_model() dentro do mesmo ciclo.
        self._lock = threading.RLock()
        self._caps: CapabilityState = self._evaluate()

    # ── Valores confirmados ─────────────────────────────────────

    @property
    def applied_dpi(self) -> Optional[int]:
        """DPI físico confirmado pelo hardware, ou None = desconhecido.

        A UI NUNCA converte unknown em default (revisão PR #21):
        requested != applied != persisted — sem ACK confirmado, não há
        valor aplicado a exibir."""
        return self._core.applied_dpi

    @property
    def applied_sensitivity(self) -> Optional[int]:
        return self._core.applied_sensitivity

    # ── Descoberta / probe / capacidades ────────────────────────

    def refresh(self) -> None:
        """Reexecuta discovery + probe e reavalia as capacidades.

        Nunca lança exceção para a UI: falhas de discovery/probe ficam
        refletidas nas capacidades (mouse_detected/hid_available etc.)
        e nos OperationResult das operações."""
        with self._lock:
            try:
                device = discover()
                register = self._core.refresh_device(device)
                if register.status == OperationStatus.UNSUPPORTED and device is not None:
                    # Dispositivo do G403 presente mas sem interface hidraw
                    # — não é falha de discovery, é capacidade ausente.
                    pass
                try:
                    self._core.probe_endpoint()
                except OSError:
                    # Falha real de acesso durante o probe: o core já
                    # invalidou hid_available/hardware_dpi_available.
                    pass
            except OSError:
                # Ambiente sem /sys/hidraw legível: core fica sem device.
                pass
            self._caps = self._evaluate()

    def capability_state(self) -> CapabilityState:
        # Última avaliação granular de capacidades (imutável).
        return self._caps

    def capability(self, name: str) -> bool:
        try:
            return self._caps.is_available(name)
        except Exception:
            return False

    # ── Operações com OperationResult real ──────────────────────

    def set_hardware_dpi(self, value: int) -> OperationResult:
        """Único caminho da UI para alterar DPI físico.

        Nunca toca na sensibilidade: o core.set_hardware_dpi não altera
        nem consulta pointer_sensitivity (separação issue #3)."""
        with self._lock:
            try:
                result = self._core.set_hardware_dpi(value)
            except OSError:
                result = OperationResult.failed(
                    "Falha de transporte no descritor hidraw"
                )
            # Snapshot de capacidades reavaliado IMEDIATAMENTE após a
            # operação (revisão PR #21): falha real de acesso invalida
            # hid_available/hardware_dpi_available na hora — a UI nunca
            # continua alegando disponibilidade antiga.
            self._caps = self._evaluate()
            return result

    def set_sensitivity(self, value: int) -> OperationResult:
        """Ação separada: altera SOMENTE a sensibilidade do ponteiro.

        Operacao independente — não consulta nem altera o DPI físico.
        Capacidades reavaliadas imediatamente após a operação."""
        with self._lock:
            try:
                result = self._core.set_sensitivity(value)
            except OSError:
                result = OperationResult.failed(
                    "Falha ao aplicar sensibilidade"
                )
            self._caps = self._evaluate()
            return result

    # ── Internos ────────────────────────────────────────────────

    def _evaluate(self) -> CapabilityState:
        return self._core.capability_model().evaluate()


def build_mouse_state() -> MouseCoreState:
    """Composição de produção: discovery real + controller do core.

    Usa a infraestrutura existente da main: LinuxHidAccess/SystemInput
    Linux, make_linux_controller (persister real XDG) e probe_endpoint
    antes de qualquer efeito HID.

    SEM thread de background (revisão PR #21): discovery+probe rodam no
    startup, após operações (reavaliação de capacidades) e por refresh
    EXPLÍCITO (ex.: abrir uma página de hardware) — nunca em loop
    periódico, sem polling HID++ permanente."""
    hid = LinuxHidAccess()
    system_input = LinuxSystemInput()
    core = make_linux_controller(hid, system_input)
    return MouseCoreState(core)


# Formatação de OperationResult para a UI (texto curto legível).
def _result_text(result: OperationResult) -> str:
    return result.message if result.message else result.status.value



class AutoClickerEngine:
    """Fachada mínima sobre o AutoClickerEngine do core único
    (mouse_hub.core.automation.autoclicker), mantendo o contrato que as
    páginas PyQt já usam (cps, button como int, running, state, start).

    O engine do core usa `MouseButton` (enum) e o estado real vem dele —
    a UI NÃO deve manter estado espelho.
    """

    def __init__(self, svc):
        self._svc = svc
        # O engine do core é lazy no serviço (nada criado antes do
        # usuário usar a feature). As páginas leem estado no _build
        # (estado inicial == defaults do core), então as leituras em
        # idle NÃO criam o engine — só mutações (start/stop/set_*)
        # disparam a criação.
        self._started = False

    @property
    def _native(self):
        if self._started:
            return self._svc.clicker
        # Estado padrão antes do primeiro uso: espelha os defaults do
        # core (STOPPED, CPS 5, botão esquerdo) sem instanciar nada.
        return self

    @property
    def running(self):
        """Fonte de verdade: estado real do motor, não o botão da UI."""
        from mouse_hub.core.automation.autoclicker import AutoClickerState
        if not self._started:
            return False
        return self._native.state in (
            AutoClickerState.RUNNING,
            AutoClickerState.BLOCKED_BY_FOCUS,
        )

    @property
    def state(self):
        from mouse_hub.core.automation.autoclicker import AutoClickerState
        if not self._started:
            return AutoClickerState.STOPPED
        return self._native.state

    @property
    def error(self):
        """Compat com a UI: o core chama o campo de `last_error`."""
        return self._native.last_error

    @property
    def cps(self):
        if not self._started:
            return 10  # default do core
        return self._native.cps

    @cps.setter
    def cps(self, value):
        self._ensure_started()
        self._native.set_cps(value)

    @property
    def button(self):
        """Compat: UI usa botão como int (1/2/3)."""
        if not self._started:
            return 1  # default do core (MouseButton.LEFT)
        return self._native.button.button_id

    @button.setter
    def button(self, value):
        self._ensure_started()
        self._native.set_button(MouseButton.from_id(int(value)))

    def _ensure_started(self):
        if self._started:
            return
        self._started = True
        # Cria o engine do core sob demanda (display X + scheduler) —
        # primeira ação do usuário na página do clicker.
        self._svc.clicker

    def start(self):
        self._ensure_started()
        self._native.start()

    def stop(self):
        if not self._started:
            return
        self._native.stop()

    def cleanup(self):
        if self._started:
            self._native.stop()


class MacroEngine:
    """Fachada sobre o AutomationService (core único) — mantém o formato
    de API que as páginas PyQt esperam (recording, start_recording,
    stop_recording, play, delete, list_all, capture_failed).

    Tudo fica lazy no startup: o serviço só abre display/worker/disco
    quando a primeira operação de macro acontece.
    """

    def __init__(self, svc):
        self._svc = svc

    @property
    def recording(self):
        return self._svc.recording

    @property
    def capture_failed(self):
        return self._svc.capture_failure

    @property
    def macros(self):
        """Compat: dict {nome: info} usado por MacrosPage — derivado do
        store (que só expõe nomes) + contagem de eventos.

        Nota: o store transacional não guarda metadados por macro (a
        estrutura antiga inventava `count`/`created`); a contagem vem
        dos eventos reais, a data mostra a geração do arquivo.
        """
        names = self._svc.list_macros()
        try:
            created = datetime.fromtimestamp(
                self._svc.store.path.stat().st_mtime
            ).strftime("%Y-%m-%d")
        except Exception:  # noqa: BLE001
            created = "—"
        return {
            name: {
                "count": len(self._svc.store.get(name) or []),
                "created": created,
            }
            for name in names
        }

    def start_recording(self, name):
        """Inicia gravação real. Se o capturador não conseguir abrir o
        display X, gravação não inicia e o motivo fica acessível em
        self.capture_failed."""
        if self.recording:
            return
        if not self._svc.start_recording(name):
            return

    def stop_recording(self):
        if not self.recording:
            return None
        ok = self._svc.stop_recording()
        name = self._svc.list_macros()[-1] if ok else None
        return name if ok else None

    def play(self, name, repeat=1):
        """Inicia reprodução no worker de playback. Já em execução,
        rejeita silenciosamente (o serviço nunca sobrescreve o worker
        em curso) — a UI usa playback_state para o feedback."""
        return self._svc.play(name, repeat=repeat)

    def cancel_playback(self):
        return self._svc.cancel_playback()

    @property
    def playback_state(self):
        return self._svc.playback_state

    @property
    def playback_error(self):
        return self._svc.playback_error

    def cancel_recording(self):
        self._svc.cancel_recording()

    def delete(self, name):
        return self._svc.delete_macro(name)

    def list_all(self):
        return self.macros

    def cleanup(self):
        """Encerramento completo — delega ao serviço (mutex garante que
        capture e playback param sem corrida)."""
        self._svc.cleanup()


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
    def __init__(self, mc, ac, me, svc, state=None):
        super().__init__()
        self.mc = mc
        self.ac = ac
        self.me = me
        self.svc = svc
        self.state = state
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(12)

        # Title
        title = QLabel("🖱️  Mouse Hub Dashboard")
        title.setStyleSheet(f"font-size: 20px; font-weight: 900; color: {COLORS['text_primary']}; background: transparent;")
        layout.addWidget(title)

        self.subtitle = QLabel(f"Mouse: {MOUSE_NAME}  •  Conectado via xinput")
        self.subtitle.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; background: transparent;")
        layout.addWidget(self.subtitle)

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
            btn.clicked.connect(lambda _, d=dpi: self._quick_dpi(d))
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

    def showEvent(self, event):
        """Refresh explícito do estado do hardware ao abrir a página
        (revisão PR #21 — sem polling periódico)."""
        super().showEvent(event)
        if self.state is not None:
            self.state.refresh()
            self._update()

    def _update(self):
        self._sync_subtitle()
        if self.state is not None:
            # Unknown NUNCA vira default (revisão PR #21): sem valor
            # confirmado pelo hardware, exibe UNKNOWN.
            dpi = self.state.applied_dpi
            sens = self.state.applied_sensitivity
            self.dpi_card.set_value(
                UNKNOWN_VALUE_TEXT if dpi is None else str(dpi)
            )
            self.sens_card.set_value(
                UNKNOWN_VALUE_TEXT if sens is None else f"{sens}%"
            )
        else:
            self.dpi_card.set_value(str(self.mc.current_dpi))
            self.sens_card.set_value(f"{self.mc.current_sensitivity}%")

        # Foco consultado no checker compartilhado (TTL 500ms) — zero
        # subprocesso no tick do dashboard (era xdotool 2x).
        focused = self.svc.window_service.is_focused(tuple(focus_patterns()))
        mc_active = focused.focused
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

    def _sync_subtitle(self):
        """Reflete o estado real do mouse (core): presença e HID."""
        if self.state is None:
            return
        caps = self.state.capability_state()
        hid = caps.is_available("hid_available")
        detected = caps.is_available("mouse_detected")
        if detected and hid:
            text = f"{MOUSE_NAME}  •  Hardware DPI disponível"
            color = COLORS["mc_green"]
        elif detected:
            text = f"{MOUSE_NAME}  •  Detectado — sem acesso HID"
            color = COLORS["warning"]
        else:
            text = f"{MOUSE_NAME}  •  Sem G403 detectado no sistema"
            color = COLORS["text_muted"]
        self.subtitle.setText(text)
        self.subtitle.setStyleSheet(
            f"font-size: 11px; color: {color}; background: transparent;"
        )

    def _quick_dpi(self, dpi):
        """Ação rápida: só altera DPI físico pelo core — separação issue #3.

        A sensibilidade do ponteiro NUNCA é alterada aqui (nem como
        fallback): o resultado real da operação vai ao log, e a UI
        exibe apenas o valor confirmado pelo hardware."""
        if self.state is None:
            return
        result = self.state.set_hardware_dpi(dpi)
        self.log_msg(
            f"DPI {dpi}: {_result_text(result)} "
            f"(via hardware)"
        )
        # Os cards do dashboard atualizam sozinhos no próximo _update
        # com os valores confirmados pelo ACK (details.get('applied')).

    def _spacer(self, h):
        s = QLabel()
        s.setFixedHeight(h)
        return s


class DPIPage(QWidget):
    """Pagina de controle de DPI"""
    def __init__(self, mc, state=None, parent=None):
        super().__init__(parent)
        self.mc = mc
        self.state = state
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

        # Slider (revisão PR #21): valueChanged é APENAS preview visual;
        # o efeito físico acontece no commit (sliderReleased/Aplicar/
        # preset) — uma ação do usuário gera no MÁXIMO uma operação HID,
        # e arrastar o slider nunca spamma HID++.
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(DPI_MIN)
        self.slider.setMaximum(DPI_MAX)
        self.slider.setSingleStep(DPI_STEP)
        self.slider.setPageStep(200)
        self.slider.setValue(self.mc.current_dpi)
        self.slider.valueChanged.connect(self._on_slider_preview)
        self.slider.sliderReleased.connect(self._commit_slider)
        layout.addWidget(self.slider)

        # Indicador de capacidade HID/DPI (issue #3)
        self.hid_hint = QLabel("")
        self.hid_hint.setWordWrap(True)
        self.hid_hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; background: transparent;")
        layout.addWidget(self.hid_hint)
        if self.state is not None:
            initial = self.state.applied_dpi
            if initial is None:
                # Desconhecido: exibe UNKNOWN; o slider fica em posição
                # NEUTRA (controle de entrada — não alega estado aplicado).
                self.dpi_value.setText(UNKNOWN_VALUE_TEXT)
                self.slider.setValue(DPI_DEFAULT)
            else:
                self.dpi_value.setText(str(initial))
                self.slider.setValue(initial)
                self.mc.current_dpi = initial

        # Range labels
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
        self.apply_btn = AccentButton("Aplicar")
        self.apply_btn.setFixedWidth(120)
        self.apply_btn.clicked.connect(self._apply_manual)
        input_row.addWidget(input_label)
        input_row.addWidget(self.dpi_input)
        input_row.addWidget(self.apply_btn)
        input_row.addStretch()
        layout.addLayout(input_row)

        # Valores iniciais refletidos no state confirmado pelo hardware
        # (após a criação do dpi_input, que o _sync_hint desabilita).
        if self.state is not None:
            initial = self.state.applied_dpi
            self.dpi_input.setText(
                UNKNOWN_VALUE_TEXT if initial is None else str(initial)
            )
        # Aplicado depois da criação de slider/dpi_input (o indicador os
        # desabilita quando não há acesso HID).
        self._sync_hint()

        # Presets
        presets_label = QLabel("⚡  Presets Rápidos")
        presets_label.setStyleSheet(f"font-size: 16px; font-weight: 700; background: transparent;")
        layout.addWidget(presets_label)

        presets = QHBoxLayout()
        presets.setSpacing(12)

        # Presets com valores vindos da fonte unica de verdade
        # (DPI_PRESETS em core/constants) — issue #6.
        preset_data = [
            ("🎯 CS:GO AWP", DPI_PRESETS["Low (CS:GO AWP)"], COLORS["success"]),
            ("🔫 FPS Geral", DPI_PRESETS["Medium (FPS Geral)"], COLORS["accent"]),
            ("⛏️ Minecraft PvP", DPI_PRESETS["High (Minecraft PvP)"], COLORS["warning"]),
            ("⚡ Flick Shots", DPI_PRESETS["Ultra (Flick Shots)"], COLORS["danger"]),
            ("🚀 Max Speed", DPI_PRESETS["Max Speed"], COLORS["text_muted"]),
        ]

        # Botões expostos para a suíte de integração (QTest/direct emit).
        self.preset_buttons = []
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
            self.preset_buttons.append((name, dpi, btn))
            presets.addWidget(btn)
        layout.addLayout(presets)

        layout.addStretch()

    def _sync_hint(self):
        """Exibe o estado real da capacidade HID/DPI no hardware.

        (Correção estrutural da revisão PR #21: este método SÓ atualiza o
        indicador — a construção da página vive inteira em _build; antes,
        a construção estava aqui e o método nunca era chamado no build,
        deixando input manual e presets fora da página.)"""
        if self.state is None:
            self.hid_hint.setText("")
            return
        caps = self.state.capability_state()
        hid = caps.is_available("hid_available")
        hw_dpi = caps.is_available("hardware_dpi_available")
        if hid and hw_dpi:
            self.hid_hint.setText("🟢 DPI físico aplicável no hardware do mouse (HID++)")
            self.hid_hint.setStyleSheet(f"color: {COLORS['mc_green']}; font-size: 12px; background: transparent;")
            self.slider.setEnabled(True)
            self.dpi_input.setEnabled(True)
        elif hid:
            self.hid_hint.setText("🟡 Endpoint HID conhecido, mas DPI físico não confirmado — a configuração do sensor pode exigir nova detecção")
            self.hid_hint.setStyleSheet(f"color: {COLORS['warning']}; font-size: 12px; background: transparent;")
            self.slider.setEnabled(True)
            self.dpi_input.setEnabled(True)
        else:
            self.hid_hint.setText("🔴 Sem acesso HID ao mouse — controles de DPI físico indisponíveis")
            self.hid_hint.setStyleSheet(f"color: {COLORS['danger']}; font-size: 12px; background: transparent;")
            self.slider.setEnabled(False)
            self.dpi_input.setEnabled(False)

    def _on_slider_preview(self, val):
        """PREVIEW apenas (revisão PR #21): atualiza o display com o
        valor em consideração. NENHUM efeito físico aqui — o commit
        acontece em sliderReleased/Aplicar/preset. Arrastar o slider
        nunca gera dezenas de comandos HID++."""
        val = round(val / DPI_STEP) * DPI_STEP
        self.dpi_value.setText(str(val))
        self.dpi_input.setText(str(val))

    def _commit_slider(self):
        """sliderReleased: exatamente UMA operação HID por gesto."""
        if self.state is None or not self.slider.isEnabled():
            return
        val = round(self.slider.value() / DPI_STEP) * DPI_STEP
        result = self.state.set_hardware_dpi(val)
        self._render_result(result, val)

    def _render_result(self, result: OperationResult, requested: int) -> None:
        """Renderiza o desfecho CONFIRMADO da operação (revisão PR #21).

        * sucesso → exibe o valor aplicado confirmado (details.applied);
        * falha   → exibe o último valor confirmado ou UNKNOWN — nunca o
          solicitado como se fosse aplicado; nenhum sucesso falso."""
        ok = result.status.ok
        self.dpi_value.setStyleSheet(f"""
            color: {COLORS['accent_light'] if ok else COLORS['danger']};
            font-size: 56px;
            font-weight: 900;
            background: transparent;
        """)
        applied = result.details.get("applied")
        if ok and applied is not None:
            self.dpi_value.setText(str(applied))
            self.dpi_input.setText(str(applied))
            # setValue programático dispara valueChanged → preview sem
            # efeito físico (uma ação = uma operação).
            self.slider.setValue(applied)
        else:
            confirmed = (
                None if self.state is None else self.state.applied_dpi
            )
            if confirmed is not None:
                self.dpi_value.setText(str(confirmed))
                self.dpi_input.setText(str(confirmed))
                self.slider.setValue(confirmed)
            else:
                self.dpi_value.setText(UNKNOWN_VALUE_TEXT)
        self._sync_hint()

    def _apply_manual(self):
        """Valor manual: exatamente UMA operação de hardware (issue #3),
        sem qualquer ajuste automático de sensibilidade."""
        try:
            val = int(self.dpi_input.text())
        except ValueError:
            return
        if self.state is not None:
            result = self.state.set_hardware_dpi(val)
            self._render_result(result, val)
        else:
            self.mc.set_dpi(val)
            self.dpi_value.setText(str(val))

    def _set_preset(self, dpi):
        """Preset de DPI físico — exatamente UMA operação via core."""
        if self.state is not None:
            result = self.state.set_hardware_dpi(dpi)
            self._render_result(result, dpi)
        else:
            self.mc.set_dpi(dpi)
            self.dpi_value.setText(str(dpi))

    def showEvent(self, event):
        """Refresh explícito ao abrir a página (revisão PR #21 — sem
        polling periódico)."""
        super().showEvent(event)
        if self.state is not None:
            self.state.refresh()
            self._sync_from_state()
            self._sync_hint()

    def _sync_from_state(self) -> None:
        """Sincroniza display/slider com o valor confirmado (ou UNKNOWN)."""
        if self.state is None:
            return
        confirmed = self.state.applied_dpi
        if confirmed is not None:
            self.dpi_value.setText(str(confirmed))
            self.dpi_input.setText(str(confirmed))
            self.slider.setValue(confirmed)
        else:
            self.dpi_value.setText(UNKNOWN_VALUE_TEXT)


class SensitivityPage(QWidget):
    """Pagina de sensibilidade"""
    def __init__(self, mc, state=None):
        super().__init__()
        self.mc = mc
        self.state = state
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

        initial = self.mc.current_sensitivity
        if self.state is not None:
            initial = self.state.applied_sensitivity
            if initial is not None:
                self.mc.current_sensitivity = initial
        self.sens_value = QLabel(
            f"{initial}%" if initial is not None else UNKNOWN_VALUE_TEXT
        )
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

        # Slider (revisão PR #21): valueChanged = preview; commit
        # (set_sensitivity) apenas em sliderReleased — um gesto gera no
        # máximo uma operação, sem spammar libinput.
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.setValue(
            initial if initial is not None else SENSITIVITY_DEFAULT
        )
        self.slider.valueChanged.connect(self._on_slider_preview)
        self.slider.sliderReleased.connect(self._commit_slider)
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

        
        # Polling rate — issue #6. O G403 HERO não tem alteração de
        # polling rate confirmável pelo stack HID++ atual (feature
        # Report Rate 0x8060 não implementada na descoberta de
        # features; sem validação em hardware real). A capacidade
        # permanece indisponível: nenhuma frequência é apresentada
        # como ativa e os botões não executam NENHUM comando — sem
        # sucesso falso nem simulação visual.
        pr_title = QLabel("U0001f4e1  Polling Rate")
        pr_title.setStyleSheet("font-size: 16px; font-weight: 700; background: transparent;")
        layout.addWidget(pr_title)

        self.polling_hint = QLabel("")
        self.polling_hint.setWordWrap(True)
        self.polling_hint.setStyleSheet(
            "color: %s; font-size: 12px; background: transparent;"
            % COLORS["text_muted"]
        )
        layout.addWidget(self.polling_hint)

        self.polling_buttons = []
        pr_row = QHBoxLayout()
        pr_row.setSpacing(12)
        for hz in ["125 Hz", "250 Hz", "500 Hz", "1000 Hz"]:
            btn = QPushButton(hz)
            btn.setFixedHeight(44)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            # Nenhuma frequência é apresentada como ativa; os botões
            # ficam desabilitados até haver capacidade confirmada.
            btn.setEnabled(False)
            btn.setStyleSheet("""
                QPushButton {
                    background: %s;
                    color: %s;
                    border: 1px solid %s;
                    border-radius: 10px;
                    font-size: 13px;
                    font-weight: 700;
                }
            """ % (COLORS["bg_card"], COLORS["text_dim"], COLORS["border"]))
            pr_row.addWidget(btn)
            self.polling_buttons.append(btn)
        pr_row.addStretch()
        layout.addLayout(pr_row)

        layout.addStretch()

        # Estado real de polling rate refletido no build (issue #6).
        self._sync_polling()

    def _sync_polling(self):
        """Reflete o estado REAL da capacidade polling_rate_available
        (issue #6): indisponível → razão precisa exibida, botões
        desabilitados, nenhuma frequência ativa. Chamado no build e no
        showEvent (refresh explícito, sem polling periódico)."""
        if self.state is None:
            self.polling_hint.setText(
                "🔴 Polling rate indisponível: o stack HID++ atual não "
                "implementa a feature Report Rate do G403."
            )
            self.polling_hint.setStyleSheet(
                "color: %s; font-size: 12px; background: transparent;"
                % COLORS["danger"]
            )
            for btn in self.polling_buttons:
                btn.setEnabled(False)
            return
        caps = self.state.capability_state()
        available = caps.is_available("polling_rate_available")
        reason = caps.reason_for("polling_rate_available")
        if available:
            self.polling_hint.setText("🟢 Polling rate disponível")
            self.polling_hint.setStyleSheet(
                "color: %s; font-size: 12px; background: transparent;"
                % COLORS["mc_green"]
            )
            for btn in self.polling_buttons:
                btn.setEnabled(True)
        else:
            summary = (
                reason if reason else
                "capacidade não disponível no ambiente atual"
            )
            self.polling_hint.setText(
                "🔴 Polling rate indisponível: %s" % summary
            )
            self.polling_hint.setStyleSheet(
                "color: %s; font-size: 12px; background: transparent;"
                % COLORS["danger"]
            )
            for btn in self.polling_buttons:
                btn.setEnabled(False)

    def _on_slider_preview(self, val):
        """PREVIEW apenas: altera somente o display. O efeito no
        ponteiro (libinput) acontece no commit (sliderReleased) — um
        gesto gera no máximo uma operação de sensibilidade."""
        self.sens_value.setText(f"{val}%")

    def _commit_slider(self):
        """sliderReleased: uma operação de sensibilidade por gesto.
        Nunca toca no DPI físico — operação separada (issue #3)."""
        if self.state is None:
            self.mc.set_sensitivity(self.slider.value())
            return
        val = self.slider.value()
        result = self.state.set_sensitivity(val)
        ok = result.status.ok
        self.sens_value.setStyleSheet(f"""
            color: {COLORS['success'] if ok else COLORS['danger']};
            font-size: 48px;
            font-weight: 900;
            background: transparent;
        """)
        applied = result.details.get("applied")
        if ok and applied is not None:
            self.sens_value.setText(f"{applied}%")
            self.slider.setValue(applied)
        else:
            confirmed = self.state.applied_sensitivity
            if confirmed is not None:
                self.sens_value.setText(f"{confirmed}%")
                self.slider.setValue(confirmed)
            else:
                self.sens_value.setText(UNKNOWN_VALUE_TEXT)

    def showEvent(self, event):
        """Refresh explícito ao abrir a página (revisão PR #21 — sem
        polling periódico)."""
        super().showEvent(event)
        if self.state is not None:
            self.state.refresh()
            confirmed = self.state.applied_sensitivity
            if confirmed is not None:
                self.sens_value.setText(f"{confirmed}%")
                self.slider.setValue(confirmed)
            else:
                self.sens_value.setText(UNKNOWN_VALUE_TEXT)
        self._sync_polling()


class AutoClickerPage(QWidget):
    """Pagina do Auto-Clicker"""
    def __init__(self, mc, ac, svc):
        super().__init__()
        self.mc = mc
        self.ac = ac
        self.svc = svc
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
        # Foco via checker compartilhado (TTL 500ms) — o xdotool era
        # consultado a cada segundo; agora é memória até o cache expirar.
        focused = self.svc.window_service.is_focused(tuple(focus_patterns()))
        mc_active = focused.focused
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
    def __init__(self, me, svc):
        super().__init__()
        self.me = me
        self.svc = svc
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

        row = QHBoxLayout()
        self.record_btn = DangerButton("⏺️  Gravar Macro")
        self.record_btn.clicked.connect(self._toggle_record)
        row.addWidget(self.record_btn)

        self.cancel_btn = QPushButton("❌ Cancelar")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_card']};
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                border-color: {COLORS['danger']};
                background: rgba(239, 68, 68, 0.1);
            }}
        """)
        self.cancel_btn.clicked.connect(self._cancel_record)
        row.addWidget(self.cancel_btn)
        row.addStretch()
        rl.addLayout(row)

        self.record_status = QLabel("")
        self.record_status.setStyleSheet(f"color: {COLORS['danger']}; font-size: 12px; font-weight: 600; background: transparent;")
        rl.addWidget(self.record_status)

        # Feedback do playback (estado real do worker, incl. FAILED):
        # refresh leve a cada 500ms — sem polling de subprocesso,
        # apenas leitura de estado em memória do serviço.
        self.play_status = QLabel("")
        self.play_status.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: 12px; "
            "font-weight: 600; background: transparent;"
        )
        rl.addWidget(self.play_status)

        self._play_timer = QTimer()
        self._play_timer.timeout.connect(self._update_play_status)
        self._play_timer.start(500)

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

    def _set_recording_ui(self, recording: bool) -> None:
        self.record_btn.setText("⏹️  Parar Gravação" if recording else "⏺️  Gravar Macro")
        self.cancel_btn.setVisible(recording)
        self.name_input.setEnabled(not recording)

    def _cancel_record(self):
        """Aborta a gravação descartando os eventos acumulados."""
        self.me.cancel_recording()
        self._set_recording_ui(False)
        self.record_status.setText("⚠️  Gravação cancelada — eventos descartados")

    def _toggle_record(self):
        if self.me.recording:
            name = self.me.stop_recording()
            self._set_recording_ui(False)
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
                self._set_recording_ui(True)
                self.record_status.setText(
                    f"🔴 Gravando '{name}'... pressione parar quando "
                    "terminar. Teclas e cliques são capturados em "
                    "qualquer janela.")
            else:
                reason = self.me.capture_failed or "capturador indisponível"
                self.record_status.setText(
                    f"❌ Não foi possível iniciar a gravação: {reason}")

    def _update_play_status(self) -> None:
        """Reflete o estado real do playback: em execução ou FAILED com
        o motivo do último erro. Sincroniza também os botões Play —
        durante a reprodução qualquer botão vira '❌ Cancel'."""
        state = self.me.playback_state
        running = state == "running"
        if running:
            self.play_status.setText("▶️  Reproduzindo...")
        elif state == "failed":
            reason = self.me.playback_error or "falha de emissão"
            self.play_status.setText(f"❌ Playback falhou: {reason}")
        else:
            self.play_status.setText("")
        for child in self.macro_list_widget.findChildren(QPushButton):
            if child.text() in ("▶️ Play", "❌ Cancel") and child is not getattr(
                self, "_last_del_btn", None
            ):
                child.setText("❌ Cancel" if running else "▶️ Play")

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

            def on_play(btn, n=name):
                """Play/Cancel — o botão espelha o estado do playback:
                durante a execução vira '❌ Cancel' e encerra a
                emissão em curso (worker exato, sem criar substituto)."""
                if self.me.playing:
                    self.me.cancel_playback()
                    btn.setText("▶️ Play")
                else:
                    if self.me.play(n):
                        btn.setText("❌ Cancel")

            play_btn.clicked.connect(lambda _, b=play_btn: on_play(b))
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
    """Pagina de Perfis

    Fonte unica de verdade: ProfileStore do core (config.json XDG).
    A pagina NUNCA mantem lista propria de perfis/presets — consulta o
    store e aplica perfis pelos MESMOS servicos das telas de DPI
    (set_hardware_dpi) e sensibilidade (set_sensitivity), como duas
    operacoes independentes (issue #3/#6).

    Regras (issue #6):
    * arquivo corrompido/ilegivel → estado de erro visivel, sem
      sobrescrever nada;
    * perfil ativo so e indicado quando o estado confirmado do
      sistema/hardware corresponde ao perfil (quando determinavel);
    * falha de DPI nunca vira sucesso global nem altera sensibilidade
      automaticamente; estado parcial explicito quando apenas parte
      pode ser confirmada.
    """

    def __init__(self, mc, state=None, store=None):
        super().__init__()
        self.mc = mc
        self.state = state
        self.store = store if store is not None else ProfileStore(ConfigPaths.xdg())
        self.profiles = []
        self.profile_cards = {}  # name -> dict de widgets do card
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(12)

        title = QLabel("👤  Perfis")
        title.setStyleSheet("font-size: 24px; font-weight: 900; background: transparent;")
        layout.addWidget(title)

        # Estado da configuracao (fonte de verdade).
        self.config_hint = QLabel("")
        self.config_hint.setWordWrap(True)
        self.config_hint.setStyleSheet(
            "color: %s; font-size: 12px; background: transparent;" % COLORS["text_muted"]
        )
        layout.addWidget(self.config_hint)

        # Feedback de aplicacao de perfil (desfecho confirmado).
        self.apply_hint = QLabel("")
        self.apply_hint.setWordWrap(True)
        self.apply_hint.setStyleSheet(
            "color: %s; font-size: 12px; background: transparent;" % COLORS["text_muted"]
        )
        layout.addWidget(self.apply_hint)

        # Grid de perfis (recarregado do ProfileStore a cada refresh).
        self.grid = QGridLayout()
        self.grid.setSpacing(16)
        layout.addLayout(self.grid)

        # ── Criacao/edicao de perfil customizado ────────────────────
        form_label = QLabel("✏️  Criar / Editar Perfil")
        form_label.setStyleSheet("font-size: 16px; font-weight: 700; background: transparent;")
        layout.addWidget(form_label)

        form = QHBoxLayout()
        form.setSpacing(10)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Nome do perfil")
        self.name_input.setFixedWidth(180)
        self.name_input.setStyleSheet(
            "QLineEdit { background: %s; border: 1px solid %s;"
            "border-radius: 8px; padding: 8px; font-size: 13px; }"
            % (COLORS["bg_input"], COLORS["border"])
        )
        self.dpi_input = QSpinBox()
        self.dpi_input.setRange(DPI_MIN, DPI_MAX)
        self.dpi_input.setSingleStep(DPI_STEP)
        self.dpi_input.setValue(DPI_DEFAULT)
        self.dpi_input.setSuffix(" DPI")
        self.sens_input = QSpinBox()
        self.sens_input.setRange(0, 100)
        self.sens_input.setValue(SENSITIVITY_DEFAULT)
        self.sens_input.setSuffix("%")
        self.save_btn = AccentButton("💾 Salvar Perfil")
        self.save_btn.clicked.connect(self._save_custom)
        self.clear_btn = QPushButton("✖ Cancelar")
        self.clear_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.clear_btn.clicked.connect(self._clear_form)
        form.addWidget(self.name_input)
        form.addWidget(self.dpi_input)
        form.addWidget(self.sens_input)
        form.addWidget(self.save_btn)
        form.addWidget(self.clear_btn)
        form.addStretch()
        layout.addLayout(form)

        layout.addStretch()

        # Fonte de verdade carregada somente depois de o formulario
        # existir (o estado de erro da config desabilita os campos).
        self._reload()

    def _reload(self):
        """Rele a fonte unica (ProfileStore). Config corrompida ou
        ilegivel → estado de erro visivel, sem sobrescrever o arquivo
        nem apresentar valores nao confirmados."""
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.profile_cards = {}
        self.profiles = []
        try:
            profiles = self.store.list_profiles()
        except ConfigError as exc:
            self.config_hint.setText(
                "🔴 Nao foi possivel ler os perfis: %s "
                "O arquivo de configuracao NAO foi alterado." % str(exc)
            )
            self.config_hint.setStyleSheet(
                "color: %s; font-size: 12px; background: transparent;" % COLORS["danger"]
            )
            self._set_form_enabled(False)
            return
        self._set_form_enabled(True)
        self.config_hint.setText("")
        self.profiles = profiles
        for i, profile in enumerate(profiles):
            self._add_card(profile, i)
        self._refresh_active()

    def _set_form_enabled(self, enabled):
        """Desabilita o formulario quando a configuracao nao e
        legivel (mutacao bloqueada por config corrompida/ilegivel)."""
        for widget in (self.name_input, self.dpi_input,
                       self.sens_input, self.save_btn):
            widget.setEnabled(enabled)

    def _add_card(self, profile, index):
        """Cria o card de um perfil lido do store."""
        color = COLORS["accent"]
        if profile.name == "minecraft":
            color = COLORS["mc_green"]
        elif profile.name == "csgo":
            color = COLORS["accent"]
        elif profile.name == "default":
            color = COLORS["text_secondary"]
        elif profile.name == "fortnite":
            color = COLORS["warning"]

        card = QFrame()
        card.setFixedSize(200, 185)
        card.setCursor(QCursor(Qt.PointingHandCursor))
        card.setObjectName("profileCard")
        card.setStyleSheet(
            "QFrame#profileCard { background: %s; border: 2px solid %s;"
            "border-radius: 16px; padding: 12px; }"
            "QFrame#profileCard:hover { border-color: %s; }"
            % (COLORS["bg_card"], COLORS["border"], color)
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 10, 12, 10)
        cl.setSpacing(4)

        top = QHBoxLayout()
        ic = QLabel("🖱️")
        ic.setStyleSheet("font-size: 22px; background: transparent;")
        top.addWidget(ic)
        top.addStretch()
        active_badge = QLabel("")
        active_badge.setStyleSheet("font-size: 11px; font-weight: 700; background: transparent;")
        top.addWidget(active_badge)
        cl.addLayout(top)

        nm = QLabel(profile.name)
        nm.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: %s; background: transparent;" % color
        )
        cl.addWidget(nm)

        det = QLabel("DPI: %d  •  Sens: %d%%" % (profile.dpi, profile.sensitivity))
        det.setStyleSheet(
            "color: %s; font-size: 11px; background: transparent;" % COLORS["text_muted"]
        )
        cl.addWidget(det)

        cl.addStretch()

        apply = QPushButton("Aplicar")
        apply.setCursor(QCursor(Qt.PointingHandCursor))
        apply.setStyleSheet(
            "QPushButton { background: %s; color: white; border: none;"
            "border-radius: 8px; padding: 5px; font-size: 12px; font-weight: 700; }"
            "QPushButton:hover { opacity: 0.8; }" % color
        )
        apply.clicked.connect(lambda _, p=profile: self._apply(p))
        cl.addWidget(apply)

        edit = QPushButton("Editar")
        edit.setCursor(QCursor(Qt.PointingHandCursor))
        edit.setStyleSheet(
            "QPushButton { background: transparent; color: %s;"
            "border: 1px solid %s; border-radius: 8px; padding: 4px;"
            "font-size: 11px; font-weight: 600; }"
            "QPushButton:hover { border-color: %s; color: %s; }"
            % (COLORS["text_secondary"], COLORS["border"], color, color)
        )
        edit.clicked.connect(lambda _, p=profile: self._start_edit(p))
        cl.addWidget(edit)

        self.grid.addWidget(card, index // 2, index % 2)
        self.profile_cards[profile.name] = {
            "card": card,
            "active_badge": active_badge,
        }

    def _refresh_active(self):
        """Marca o card do perfil ativo (estado confirmado corresponde
        ao perfil) ou limpa todos quando nao determinavel."""
        active = self.active_profile()
        for name, widgets in self.profile_cards.items():
            badge = widgets["active_badge"]
            card = widgets["card"]
            if name == active:
                badge.setText("✔ Ativo")
                badge.setStyleSheet(
                    "color: %s; font-size: 11px; font-weight: 700; background: transparent;"
                    % COLORS["mc_green"]
                )
                card.setStyleSheet(
                    "QFrame#profileCard { background: %s; border: 2px solid %s;"
                    "border-radius: 16px; padding: 12px; }"
                    % (COLORS["bg_card"], COLORS["mc_green"])
                )
            else:
                badge.setText("")
                card.setStyleSheet(
                    "QFrame#profileCard { background: %s; border: 2px solid %s;"
                    "border-radius: 16px; padding: 12px; }"
                    "QFrame#profileCard:hover { border-color: %s; }"
                    % (COLORS["bg_card"], COLORS["border"], COLORS["accent"])
                )

    def active_profile(self):
        """Nome do perfil ativo, ou None quando nao determinavel.

        Um perfil so e considerado ativo quando o estado CONFIRMADO do
        sistema/hardware corresponde exatamente ao perfil: applied_dpi
        == profile.dpi E applied_sensitivity == profile.sensitivity.
        Se qualquer valor confirmado for None (desconhecido), nao ha
        como afirmar que o perfil esta ativo."""
        if self.state is None:
            return None
        dpi = self.state.applied_dpi
        sens = self.state.applied_sensitivity
        if dpi is None or sens is None:
            return None
        for profile in self.profiles:
            if profile.dpi == dpi and profile.sensitivity == sens:
                return profile.name
        return None

    def _apply(self, profile):
        """Aplica um perfil: DPI fisico e sensibilidade como operacoes
        INDEPENDENTES (issue #3/#6).

        A sensibilidade nunca e alterada como fallback de falha de
        DPI; falha de DPI nao vira sucesso global; estado parcial
        explicito quando apenas parte e confirmada."""
        if self.state is None:
            self.mc.set_dpi(profile.dpi)
            self.mc.set_sensitivity(profile.sensitivity)
            return
        dpi_result = self.state.set_hardware_dpi(profile.dpi)
        sens_result = self.state.set_sensitivity(profile.sensitivity)
        self._render_apply_feedback(profile, dpi_result, sens_result)
        self._refresh_active()

    def _render_apply_feedback(self, profile, dpi_result, sens_result):
        """Exibe o desfecho confirmado da aplicacao do perfil.

        * ambos confirmados → sucesso;
        * apenas um confirmado → estado parcial explicito;
        * ambos falharam → falha, nunca sucesso."""
        dpi_ok = dpi_result.status.ok
        sens_ok = sens_result.status.ok
        if dpi_ok and sens_ok:
            text = "✔ Perfil '%s' aplicado: DPI e sensibilidade confirmados." % profile.name
            color = COLORS["mc_green"]
        elif dpi_ok:
            text = ("⚠ Perfil '%s' aplicado PARCIALMENTE: DPI "
                    "confirmado; sensibilidade falhou (%s)." %
                    (profile.name, _result_text(sens_result)))
            color = COLORS["warning"]
        elif sens_ok:
            text = ("⚠ Perfil '%s' aplicado PARCIALMENTE: "
                    "sensibilidade confirmada; DPI falhou (%s)." %
                    (profile.name, _result_text(dpi_result)))
            color = COLORS["warning"]
        else:
            text = ("✘ Perfil '%s' NAO aplicado: DPI falhou "
                    "(%s); sensibilidade falhou (%s)." %
                    (profile.name, _result_text(dpi_result),
                     _result_text(sens_result)))
            color = COLORS["danger"]
        self.apply_hint.setText(text)
        self.apply_hint.setStyleSheet(
            "color: %s; font-size: 12px; background: transparent;" % color
        )

    def _save_custom(self):
        """Cria/atualiza um perfil atraves do ProfileStore (fonte
        persistente real). Falha (incluindo config corrompida ou
        ilegivel) nunca vira sucesso e nunca sobrescreve o arquivo."""
        name = self.name_input.text().strip()
        if not name:
            self.apply_hint.setText("⚠ Informe um nome para o perfil.")
            self.apply_hint.setStyleSheet(
                "color: %s; font-size: 12px; background: transparent;" % COLORS["warning"]
            )
            return
        outcome = self.store.save_profile(
            name, self.dpi_input.value(), self.sens_input.value()
        )
        if not outcome.success:
            self.apply_hint.setText(
                "✘ Nao foi possivel salvar o perfil '%s': %s" % (name, outcome.message)
            )
            self.apply_hint.setStyleSheet(
                "color: %s; font-size: 12px; background: transparent;" % COLORS["danger"]
            )
            return
        self.apply_hint.setText("✔ Perfil '%s' salvo na configuracao." % name)
        self.apply_hint.setStyleSheet(
            "color: %s; font-size: 12px; background: transparent;" % COLORS["mc_green"]
        )
        self._clear_form()
        self._reload()

    def _start_edit(self, profile):
        """Carrega os valores do perfil no formulario de edicao."""
        self.name_input.setText(profile.name)
        self.dpi_input.setValue(profile.dpi)
        self.sens_input.setValue(profile.sensitivity)

    def _clear_form(self):
        self.name_input.clear()
        self.dpi_input.setValue(DPI_DEFAULT)
        self.sens_input.setValue(SENSITIVITY_DEFAULT)

    def showEvent(self, event):
        """Refresh explicito das capacidades e da fonte de perfis ao
        abrir a pagina (revisao PR #21 — sem polling periodico)."""
        super().showEvent(event)
        if self.state is not None:
            self.state.refresh()
        self._reload()


class SettingsPage(QWidget):
    """Pagina de Configuracoes"""
    def __init__(self, mc, ac, me, svc):
        super().__init__()
        self.mc = mc
        self.ac = ac
        self.me = me
        self.svc = svc
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
            "Para controle direto de DPI no hardware do mouse, o "
            "aplicativo detecta o G403 HERO por identidade (VID/PID). "
            "Sem permissão de escrita no nó hidraw, o acesso HID fica "
            "indisponível — crie uma regra udev permanente em vez de "
            "alterar permissões manualmente:"
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
        cmd_layout = QVBoxLayout(cmd_frame)
        rule_text = QLabel(
            '# /etc/udev/rules.d/99-logitech-g403.rules\n'
            'SUBSYSTEM=="hidraw", ATTRS{{idVendor}}=="046d", '
            'ATTRS{{idProduct}}=="c08f", MODE="0664", '
            'GROUP="plugdev"'
        )
        rule_text.setStyleSheet(f"font-family: monospace; font-size: 11px; color: {COLORS['mc_green']}; background: transparent;")
        cmd_layout.addWidget(rule_text)
        reload_hint = QLabel(
            "Depois: sudo udevadm control --reload-rules && "
            "sudo udevadm trigger"
        )
        reload_hint.setStyleSheet(f"font-family: monospace; font-size: 11px; color: {COLORS['text_secondary']}; background: transparent;")
        cmd_layout.addWidget(reload_hint)
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

        paths = ConfigPaths.xdg()
        info = QLabel(
            f"Mouse: {MOUSE_NAME} (VID 046d / PID c08f)\n"
            f"Descoberta: identidades de hardware (sysfs/hidraw)\n"
            f"Sistema: Linux (xinput)\n"
            f"Python: {sys.version.split()[0]}\n"
            f"Config: {paths.config_file}\n"
            f"Macros: {paths.macros_file}\n"
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
        self.mc = MouseController()  # stub legado inerte (issue #3)

        # Controle real do mouse (issue #3): discovery por identidade
        # (VID 046d / PID c08f) + core seguro da main. Sem thread de
        # atualização periódica (revisão PR #21): o refresh roda no
        # startup, após operações (reavaliação de capacidades) e por
        # evento explícito (ex.: abrir página de hardware) — nunca em
        # polling HID++ permanente.
        self.mouse_state = build_mouse_state()
        try:
            # Primeira avaliação síncrona para o dashboard exibir o
            # estado real imediatamente.
            self.mouse_state.refresh()
        except Exception:  # noqa: BLE001
            pass

        # Core único de automação (PR #14): uma única instância
        # compartilhada por todas as páginas — foco, gravação, playback
        # e clicker centralizados (detect once, share state). Nada é
        # criado no startup (lazy): display, workers e disco só surgem
        # quando a feature é usada.
        self.svc = AutomationService(macros_path=MACROS_PATH)
        self.ac = AutoClickerEngine(self.svc)
        self.me = MacroEngine(self.svc)

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

        self.dashboard_page = DashboardPage(self.mc, self.ac, self.me, self.svc, state=self.mouse_state)
        self.dpi_page = DPIPage(self.mc, state=self.mouse_state)
        self.sens_page = SensitivityPage(self.mc, state=self.mouse_state)
        self.clicker_page = AutoClickerPage(self.mc, self.ac, self.svc)
        self.macros_page = MacrosPage(self.me, self.svc)
        self.profiles_page = ProfilesPage(self.mc, state=self.mouse_state, store=ProfileStore(ConfigPaths.xdg()))
        self.settings_page = SettingsPage(self.mc, self.ac, self.me, self.svc)

        # Sem thread de estado do mouse (revisão PR #21): o refresh
        # roda no startup, após operações e em evento explícito — nunca
        # em loop periódico.

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
        # (o mutex do serviço garante a parada sem corrida; a chamada é
        # idempotente quando nada foi usado). Não há thread de estado
        # do mouse para parar (revisão PR #21 — sem polling periódico).
        self.me.cleanup()
        self.ac.cleanup()
        self.svc.cleanup()
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
