#!/usr/bin/env python3
"""
Mouse Hub — Aplicativo Nativo Desktop
======================================
App nativo estilo Feather Client para controle do Logitech G403 HERO
DPI, Sensibilidade, Macros e Auto-Clicker (Minecraft Only)
"""

import queue
import signal
import os
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
    APP_VERSION,
    DPI_DEFAULT,
    DPI_MAX,
    DPI_MIN,
    DPI_PRESETS,
    DPI_STEP,
    G403_NAME,
    SENSITIVITY_DEFAULT,
)
from mouse_hub.core.discovery import discover, discover_candidates
from mouse_hub.core.mouse_controller import (
    MouseController as CoreMouseController,
    make_linux_controller,
)
from mouse_hub.core.config import ConfigError, ConfigPaths, migrate_legacy_config
from mouse_hub.core.dpi import round_to_step
from mouse_hub.core.sensitivity import clamp_sensitivity
from mouse_hub.core.capabilities import CapabilityState, with_overrides
from mouse_hub.core.profiles import ProfileStore
from mouse_hub.platform.linux import LinuxHidAccess
from mouse_hub.platform.linux.udev_monitor import HotplugDebouncer, UdevHidrawMonitor
from mouse_hub.platform.linux.privileges import (
    fix_hid_permissions,
    is_hid_permission_issue,
)
from app.ui import icons as ui_icons
from app.ui.theme import (
    COLORS,
    build_app_stylesheet,
    TYPE_SCALE,
    SPACE,
    normal_font_size,
)
from mouse_hub.platform.linux.input import LinuxSystemInput

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QFrame, QGraphicsDropShadowEffect,
    QScrollArea, QStackedWidget, QLineEdit, QSpinBox, QComboBox,
    QMessageBox, QProgressBar, QSystemTrayIcon, QMenu, QAction,
    QGroupBox, QGridLayout, QTextEdit, QSizePolicy,
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

COLORS = dict(COLORS)  # alias local (fonte única: app/ui/theme.py)
POLLING_UNAVAILABLE_COPY = (
    "Polling Rate não pode ser configurado neste dispositivo nesta "
    "versão do Mouse Hub."
)

STYLESHEET = build_app_stylesheet()


# ═══════════════════════════════════════════════════════════════════════════════
#  MOUSE CONTROLLER (DPI / Sensitivity / AutoClicker / Macros)
# ═══════════════════════════════════════════════════════════════════════════════

MOUSE_NAME = "Logitech G403 HERO Gaming Mouse"
# DPI_MIN/DPI_MAX/DPI_STEP vêm de mouse_hub.core.constants (issue #2):
# nenhum limite de domínio é redefinido na UI.
# Caminhos de macro: exatamente os mesmos do core (XDG), sem path
# paralelo na UI (issue #2). A migração do legado ~/mouse-hub/ roda
# uma vez no startup, antes de qualquer acesso ao MacroStore.


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
        # A matemática de domínio é a mesma implementação do core.
        self.current_sensitivity = clamp_sensitivity(value)
        return True

    def get_sensitivity(self):
        return self.current_sensitivity

    def set_dpi(self, dpi):
        # Sem efeito de hardware — a UI usa MouseCoreState no core.
        # clamp + alinhamento de step vêm do core (issue #2).
        self.current_dpi = round_to_step(int(dpi))
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
_PERMISSION_BTN_LABEL = " Conceder acesso ao hardware  (senha de administrador)"

# Issue #103: o slider de DPI é controle de ENTRADA — "valor desejado a
# aplicar" — nunca representação implícita do estado aplicado. A legenda
# é permanente: o slider não é readback mesmo com valor confirmado.
_DPI_TARGET_LABEL = "Valor desejado (aplicar ao hardware)"
# Sub-rótulo do hero enquanto o DPI físico não tem readback confirmado.
_DPI_WAITING_TEXT = "AGUARDANDO LEITURA DO HARDWARE"

# Issue #102: a página de Sensibilidade descreve ESTADO DO SISTEMA —
# nunca leitura do hardware do mouse. Os textos do hero são separados
# do unknown de DPI para os dois domínios não se fundirem na UI.
_SENS_STATE_TEXT = "VELOCIDADE DO PONTEIRO NO SISTEMA"
_SENS_UNKNOWN_TEXT = "valor atual do sistema indisponível"


# Issue #88: ação destrutiva não pode ser um botão vazio — rótulo
# textual curto (o subset de ícones não tem lixeira; ícone ausente
# nunca derruba a UI), tooltip e acessibilidade identificam a função
# ANTES do clique, sem depender só da cor.
_MACRO_DELETE_LABEL = "Excluir"
_MACRO_DELETE_TOOLTIP = "Excluir esta macro (ação destrutiva)"

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
                # Issue #68: o G403 expõe vários hidraw (input, vendor);
                # selecionar exige sondar TODOS e escolher o que confirma
                # HID++ — pegar o primeiro faz o DPI morrer em EPIPE.
                candidates = discover_candidates()
                device = self._core.select_endpoint(candidates)
                if device is None and candidates:
                    # Mouse PRESENTE mas nenhum endpoint elegível
                    # (permissão, EPIPE ou ambiguidade): registra o
                    # primeiro só para o diagnóstico ficar honesto
                    # ("detectado, sem acesso"), nunca para efeitos —
                    # o probe bloqueia escrita em seleção ambígua e só
                    # confirma feature index em endpoint único.
                    device = candidates[0]
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



class AutoClickerFacade:
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
        # (estado inicial == preferências persistidas do config XDG,
        # issue #5), então as leituras em idle NÃO criam o engine —
        # só mutações (start/stop/set_*) disparam a criação.
        self._started = False
        try:
            cps, button_name = svc.initial_clicker_settings()
        except Exception:  # noqa: BLE001
            cps, button_name = 10, "left"
        self._default_cps = cps
        self._default_button_id = {"left": 1, "middle": 2, "right": 3}.get(
            button_name, 1)

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
            return self._default_cps  # preferência persistida (issue #5)
        return self._native.cps

    @cps.setter
    def cps(self, value):
        self._ensure_started()
        self._native.set_cps(value)
        self._svc.save_clicker_settings()

    @property
    def button(self):
        """Compat: UI usa botão como int (1/2/3)."""
        if not self._started:
            return self._default_button_id  # preferência persistida
        return self._native.button.button_id

    @button.setter
    def button(self, value):
        self._ensure_started()
        self._native.set_button(MouseButton.from_id(int(value)))
        self._svc.save_clicker_settings()

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
        # issue #66 (craft): cards EXPANDEM para preencher o grid —
        # setFixedSize(140, 88) deixava 4 caixinhas perdidas no meio.
        self.setMinimumHeight(96)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setObjectName("statCard")
        self        .setStyleSheet(f"""
            QFrame#statCard {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
            QFrame#statCard:hover {{
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
            font-size: 24px;
            font-weight: 900;
            background: transparent;
        """)
        layout.addWidget(self.value_label)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            color: {COLORS['text_secondary']};
            font-size: 11px;
            font-weight: 600;
            background: transparent;
            text-transform: uppercase;
        """)
        layout.addWidget(title_label)

    def set_value(self, val):
        self.value_label.setText(str(val))


class SidebarButton(QPushButton):
    """Botão da sidebar — ícone vetorial (Remix, fonte embutida) +
    pill de gradiente no estado ativo. Sem emoji (tofu na fonte do
    usuário; decisão do mantenedor: ícones profissionais apenas)."""

    def __init__(self, icon_key, text, index):
        super().__init__(text)
        self.index = index
        self._icon_key = icon_key
        self.setMinimumHeight(42)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self._apply_style(False)

    def _apply_style(self, active: bool):
        from app.ui import icons
        color = COLORS["text_primary"] if active else COLORS["text_secondary"]
        ic = icons.icon(self._icon_key, color, 18) if self._icon_key else None
        if ic is not None:
            self.setIcon(ic)
            self.setIconSize(QSize(18, 18))
        if active:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {COLORS['sidebar_active']}, stop:1 {COLORS['bg_mid']});
                    color: {COLORS['text_primary']};
                    border-left: 3px solid {COLORS['accent']};
                    border-radius: 10px;
                    text-align: left;
                    padding-left: 15px;
                    font-size: 13px;
                    font-weight: 800;
                    letter-spacing: 0.4px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {COLORS['text_secondary']};
                    border: none;
                    border-radius: 10px;
                    text-align: left;
                    padding-left: 18px;
                    font-size: 13px;
                    font-weight: 600;
                    letter-spacing: 0.3px;
                }}
                QPushButton:hover {{
                    background: {COLORS['sidebar_hover']};
                    color: {COLORS['text_primary']};
                }}
            """)

    def set_active(self, active):
        self._apply_style(active)


class AccentButton(QPushButton):
    """Botao de acao principal (estilo Feather Client)"""
    def __init__(self, text, color=COLORS["accent"], icon=""):
        super().__init__(text)
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


_DPI_PRESET_LABEL_KEYS = (
    ("CS:GO AWP", "Low (CS:GO AWP)"),
    ("FPS Geral", "Medium (FPS Geral)"),
    ("Minecraft PvP", "High (Minecraft PvP)"),
    ("Flick Shots", "Ultra (Flick Shots)"),
    ("Max Speed", "Max Speed"),
)


def _dpi_preset_data():
    """Retorna labels de UI e valores da única fonte de presets do core."""
    return [
        (label, DPI_PRESETS[key])
        for label, key in _DPI_PRESET_LABEL_KEYS
    ]


class PresetButton(QPushButton):
    """Alvo clicável compacto com hierarquia tipográfica explícita.

    O botão permanece um único controle para preservar os callbacks de
    Dashboard e DPI. Os dois labels internos permitem que o contexto fique
    neutro e que o valor acionável seja escaneado primeiro.
    """

    def __init__(self, name, dpi, parent=None):
        super().__init__(parent)
        self.preset_name = name
        self.preset_dpi = dpi
        self.setAccessibleName(f"{name}, {dpi} DPI")
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(70)
        self.setMinimumWidth(96)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self.name_label = QLabel(name, self)
        self.name_label.setObjectName("presetName")
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.name_label.setStyleSheet(f"""
            color: {COLORS['text_secondary']};
            font-size: {TYPE_SCALE['caption']}px;
            font-weight: 600;
            background: transparent;
        """)

        self.value_label = QLabel(f"{dpi} DPI", self)
        self.value_label.setObjectName("presetValue")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.value_label.setStyleSheet(f"""
            color: {COLORS['accent_light']};
            font-size: {TYPE_SCALE['subtitle']}px;
            font-weight: 900;
            background: transparent;
        """)

        content = QVBoxLayout(self)
        content.setContentsMargins(8, 6, 8, 6)
        content.setSpacing(0)
        content.addWidget(self.name_label)
        content.addWidget(self.value_label)

        self.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
                padding: 0;
            }}
            QPushButton:hover {{
                border-color: {COLORS['accent']};
                background: {COLORS['bg_card_hover']};
            }}
            QPushButton:pressed {{
                background: {COLORS['accent_dark']};
            }}
        """)


class DangerButton(QPushButton):
    """Botao de perigo"""
    def __init__(self, text, icon=""):
        super().__init__(text)
        self.setMinimumHeight(38)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        # Audit impeccable: stops ≥4.5:1 contra branco (antes 2.77:1
        # no hover) + estado :disabled legível.
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['danger']}, stop:1 {COLORS['danger_dark']});
                color: white;
                border: none;
                border-radius: 10px;
                padding: 8px 20px;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['danger_dark']}, stop:1 {COLORS['danger_dark']});
            }}
            QPushButton:disabled {{
                background: {COLORS['bg_input']};
                color: {COLORS['text_muted']};
                border: none;
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
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel("Mouse Hub Dashboard")
        title.setStyleSheet(f"font-size: 24px; font-weight: 900; color: {COLORS['text_primary']}; background: transparent;")
        title_icon = ui_icons.icon_label("dashboard", COLORS["accent_light"], 24)
        title_row = QHBoxLayout()
        if title_icon is not None:
            title_row.addWidget(title_icon)
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        # issue #7: o texto real vem de _sync_subtitle() (capacidades do
        # core); nenhum estado é afirmado antes da avaliação.
        self.subtitle = QLabel(f"Mouse: {MOUSE_NAME}  •  Avaliando capacidades…")
        self.subtitle.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; background: transparent;")
        layout.addWidget(self.subtitle)

        # Stats em GRID 2×2 (issue #66): cabe em qualquer largura sem
        # espremer/overlap; colunas expansíveis igualmente.
        stats = QGridLayout()
        stats.setHorizontalSpacing(16)
        stats.setVerticalSpacing(12)

        self.dpi_card = StatCard("", "DPI", str(self.mc.current_dpi), COLORS["accent_light"])
        self.sens_card = StatCard("", "SENSIBILIDADE", f"{self.mc.current_sensitivity}%", COLORS["success"])
        self.mc_card = StatCard("", "MINECRAFT", "OFF", COLORS["text_muted"])
        self.clicker_card = StatCard("", "AUTO-CLICKER", "OFF", COLORS["danger"])

        stats.addWidget(self.dpi_card, 0, 0)
        stats.addWidget(self.sens_card, 0, 1)
        stats.addWidget(self.mc_card, 1, 0)
        stats.addWidget(self.clicker_card, 1, 1)
        stats.setColumnStretch(0, 1)
        stats.setColumnStretch(1, 1)
        layout.addLayout(stats)

        # issue #7: primeira renderização já parte do estado real.
        self._sync_subtitle()

        # Quick actions
        layout.addWidget(self._spacer(10))

        actions_title = QLabel("Ações Rápidas")
        actions_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text_primary']}; background: transparent;")
        layout.addWidget(actions_title)

        presets = QHBoxLayout()
        presets.setSpacing(12)

        self.quick_preset_buttons = []
        for name, dpi in _dpi_preset_data()[:4]:
            btn = PresetButton(name, dpi)
            # issue #66: largura mínima flexível — 4 presets nunca
            # estouram a linha (setFixedSize(130) somava 556px mínimos).
            btn.clicked.connect(lambda _, d=dpi: self._quick_dpi(d))
            self.quick_preset_buttons.append(btn)
            presets.addWidget(btn)
        presets.addStretch()
        layout.addLayout(presets)

        # Log area
        layout.addWidget(self._spacer(10))

        log_title = QLabel("Log de Atividade")
        log_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text_primary']}; background: transparent;")
        layout.addWidget(log_title)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        self.log.setPlaceholderText(
            "Nenhuma atividade ainda — as ações do app aparecem aqui.")
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
        dpi = caps.is_available("hardware_dpi_available")
        if detected and hid and dpi:
            text = f"{MOUSE_NAME}  •  Hardware DPI disponível"
            color = COLORS["mc_green"]
        elif detected and hid:
            # Acesso HID confirmado não implica DPI ajustável (issue #7):
            # o texto declara apenas o que o core evidenciou.
            reason = caps.reason_for("hardware_dpi_available")
            text = f"{MOUSE_NAME}  •  Acesso HID — DPI físico indisponível"
            if reason:
                text += f" ({reason})"
            color = COLORS["warning"]
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

        Autorização (issue #95): sem `hardware_dpi_available` confirmado,
        a ação NÃO parte da UI — nenhum comando parte de um estado não
        confirmado (o core já é fail-closed; a UI não oferece o caminho).

        A sensibilidade do ponteiro NUNCA é alterada aqui (nem como
        fallback): o resultado real da operação vai ao log, e a UI
        exibe apenas o valor confirmado pelo hardware."""
        if self.state is None:
            return
        caps = self.state.capability_state()
        if not caps.is_available("hardware_dpi_available"):
            self.log_msg(
                "DPI não aplicado: capacidade de DPI físico não "
                "confirmada neste momento."
            )
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
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        title = QLabel("Controle de DPI")
        title.setStyleSheet(f"font-size: 24px; font-weight: 900; color: {COLORS['text_primary']}; background: transparent;")
        title_icon = ui_icons.icon_label("dpi", COLORS["accent_light"], 24)
        title_row = QHBoxLayout()
        if title_icon is not None:
            title_row.addWidget(title_icon)
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        # DPI Display
        display = QFrame()
        display.setFixedHeight(150)
        display.setObjectName("dpiDisplay")
        display        .setStyleSheet(f"""
            QFrame#dpiDisplay {{
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
            font-size: 44px;
            font-weight: 900;
            background: transparent;
        """)
        dl.addWidget(self.dpi_value)

        self.dpi_state = QLabel("DOTS PER INCH")
        self.dpi_state.setAlignment(Qt.AlignCenter)
        self.dpi_state.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; font-weight: 700; letter-spacing: 2px; background: transparent;")
        dl.addWidget(self.dpi_state)

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

        # Issue #103: legenda PERMANENTE do papel do slider — controle
        # de entrada (valor desejado), distinto do readback do hero.
        self.target_hint = QLabel(_DPI_TARGET_LABEL)
        self.target_hint.setAlignment(Qt.AlignCenter)
        self.target_hint.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 11px; "
            "font-weight: 700; background: transparent;"
        )
        layout.addWidget(self.target_hint)

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
                self.dpi_state.setText(_DPI_WAITING_TEXT)
                self.slider.setValue(DPI_DEFAULT)
            else:
                self.dpi_value.setText(str(initial))
                self.dpi_state.setText("DOTS PER INCH")
                self.slider.setValue(initial)
                self.mc.current_dpi = initial

        # Range como UMA legenda centrada (labels colados nas bordas
        # opostas pairavam desconectados do slider).
        range_l = QLabel(f"Faixa suportada: {DPI_MIN} – {DPI_MAX} DPI")
        range_l.setAlignment(Qt.AlignCenter)
        range_l.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; background: transparent;")
        layout.addWidget(range_l)

        # Manual input
        input_row = QHBoxLayout()
        input_label = QLabel("Valor manual:")
        input_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px; background: transparent;")
        self.dpi_input = QLineEdit(str(self.mc.current_dpi))
        self.dpi_input.setFixedWidth(120)
        self.dpi_input.setAlignment(Qt.AlignCenter)
        self.dpi_input.setStyleSheet(f"""
            QLineEdit {{
                font-size: 16px;
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
        presets_label = QLabel("Presets Rápidos")
        presets_label.setStyleSheet(f"font-size: 16px; font-weight: 700; background: transparent;")
        layout.addWidget(presets_label)

        # Grid 2×3 (issue #66): 5 presets em linha somavam 607px
        # mínimos e estouravam a janela pequena; em grid cabem sempre.
        presets = QGridLayout()
        presets.setHorizontalSpacing(12)
        presets.setVerticalSpacing(12)

        # Presets com valores vindos da fonte unica de verdade
        # (DPI_PRESETS em core/constants) — issue #6.
        preset_data = _dpi_preset_data()

        # Botões expostos para a suíte de integração (QTest/direct emit).
        self.preset_buttons = []
        for pos, (name, dpi) in enumerate(preset_data):
            btn = PresetButton(name, dpi)
            btn.clicked.connect(lambda _, d=dpi: self._set_preset(d))
            self.preset_buttons.append((name, dpi, btn))
            presets.addWidget(btn, pos // 3, pos % 3)
        presets.setColumnStretch(3, 1)
        layout.addLayout(presets)

        # issue #95: o estado real manda — os presets (criados acima)
        # também só ficam autorizados com a capability confirmada.
        self._sync_hint()

        layout.addStretch()

    def _set_dpi_controls_enabled(self, enabled: bool) -> None:
        """Autoriza os controles de EFEITO FÍSICO de DPI (issue #95).

        Slider, valor manual, Aplicar e presets só ficam habilitados com
        `hardware_dpi_available` confirmado — estado correto → ação
        autorizada; hid_available sozinho NÃO autoriza escrita no
        sensor (o core é fail-closed e a UI acompanha)."""
        for widget in (self.slider, self.dpi_input, self.apply_btn):
            widget.setEnabled(enabled)
        for _, _, btn in getattr(self, "preset_buttons", []):
            btn.setEnabled(enabled)

    def _sync_hint(self):
        """Exibe o estado real da capacidade HID/DPI no hardware e
        alinha a autorização dos controles a `hardware_dpi_available`
        (issue #95), exibindo a causa real quando indisponível.

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
        self._set_dpi_controls_enabled(hid and hw_dpi)
        if hid and hw_dpi:
            self.hid_hint.setText("● DPI físico aplicável no hardware do mouse (HID++)")
            self.hid_hint.setStyleSheet(f"color: {COLORS['mc_green']}; font-size: 12px; background: transparent;")
        elif hid:
            reason = caps.reason_for("hardware_dpi_available") or \
                "DPI físico não confirmado neste endpoint"
            self.hid_hint.setText(
                f"● DPI físico não confirmado: {reason} — "
                "controles desabilitados por segurança"
            )
            self.hid_hint.setStyleSheet(f"color: {COLORS['warning']}; font-size: 12px; background: transparent;")
        else:
            self.hid_hint.setText("● Sem acesso HID ao mouse — controles de DPI físico indisponíveis")
            self.hid_hint.setStyleSheet(f"color: {COLORS['danger']}; font-size: 12px; background: transparent;")

    def _on_slider_preview(self, val):
        """PREVIEW apenas (revisão PR #21): atualiza o valor em
        consideração. NENHUM efeito físico aqui — o commit acontece em
        sliderReleased/Aplicar/preset. Arrastar o slider nunca gera
        dezenas de comandos HID++.

        Issue #103: o sub-rótulo do hero permanece reservado ao estado
        APLICADO — sem readback confirmado, o preview não promove a
        posição do slider a 'DOTS PER INCH' (estado aplicado)."""
        val = round_to_step(val)
        self.dpi_value.setText(str(val))
        confirmed = None if self.state is None else self.state.applied_dpi
        self.dpi_state.setText(
            "DOTS PER INCH" if confirmed is not None else _DPI_WAITING_TEXT
        )
        self.dpi_input.setText(str(val))

    def _commit_slider(self):
        """sliderReleased: exatamente UMA operação HID por gesto."""
        if self.state is None or not self.slider.isEnabled():
            return
        val = round_to_step(self.slider.value())
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
            font-size: 44px;
            font-weight: 900;
            background: transparent;
        """)
        applied = result.details.get("applied")
        if ok and applied is not None:
            self.dpi_value.setText(str(applied))
            self.dpi_state.setText("DOTS PER INCH")
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
                self.dpi_state.setText("DOTS PER INCH")
                self.dpi_input.setText(str(confirmed))
                self.slider.setValue(confirmed)
            else:
                self.dpi_value.setText(UNKNOWN_VALUE_TEXT)
                self.dpi_state.setText(_DPI_WAITING_TEXT)
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
            self.dpi_state.setText("DOTS PER INCH")

    def _set_preset(self, dpi):
        """Preset de DPI físico — exatamente UMA operação via core."""
        if self.state is not None:
            result = self.state.set_hardware_dpi(dpi)
            self._render_result(result, dpi)
        else:
            self.mc.set_dpi(dpi)
            self.dpi_value.setText(str(dpi))
            self.dpi_state.setText("DOTS PER INCH")

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
            self.dpi_state.setText("DOTS PER INCH")
            self.dpi_input.setText(str(confirmed))
            self.slider.setValue(confirmed)
        else:
            self.dpi_value.setText(UNKNOWN_VALUE_TEXT)
            self.dpi_state.setText(_DPI_WAITING_TEXT)


class SensitivityPage(QWidget):
    """Pagina de sensibilidade"""
    def __init__(self, mc, state=None):
        super().__init__()
        self.mc = mc
        self.state = state
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        title = QLabel("Sensibilidade")
        title.setStyleSheet(f"font-size: 24px; font-weight: 900; color: {COLORS['text_primary']}; background: transparent;")
        title_icon = ui_icons.icon_label("sensitivity", COLORS["accent_light"], 24)
        title_row = QHBoxLayout()
        if title_icon is not None:
            title_row.addWidget(title_icon)
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        # Display
        display = QFrame()
        display.setFixedHeight(130)
        display.setObjectName("sensDisplay")
        display        .setStyleSheet(f"""
            QFrame#sensDisplay {{
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
            font-size: 44px;
            font-weight: 900;
            background: transparent;
        """)
        dl.addWidget(self.sens_value)

        self.sens_state = QLabel(
            _SENS_STATE_TEXT if initial is not None else _SENS_UNKNOWN_TEXT
        )
        self.sens_state.setAlignment(Qt.AlignCenter)
        self.sens_state.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; font-weight: 700; background: transparent;")
        dl.addWidget(self.sens_state)

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

        # issue #7: a capacidade real manda — sem libinput/xinput, o
        # controle fica desabilitado COM a causa, nunca mascarado.
        self.caps_hint = QLabel("")
        self.caps_hint.setStyleSheet("color: %s; font-size: 12px; background: transparent;" % COLORS["text_muted"])
        self.caps_hint.setWordWrap(True)
        layout.addWidget(self.caps_hint)
        self._sync_sensitivity_caps()

        hint = QHBoxLayout()
        hint.addWidget(QLabel("Lento"))
        hint.addStretch()
        hint.addWidget(QLabel("Rápido"))
        for i in range(hint.count()):
            w = hint.itemAt(i).widget()
            if w:
                w.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; background: transparent;")
        layout.addLayout(hint)

        # Speed bar
        bar_frame = QFrame()
        bar_frame.setFixedHeight(8)
        bar_frame.setObjectName("speedBar")
        bar_frame        .setStyleSheet(f"""
            QFrame#speedBar {{
                background: {COLORS['bg_input']};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(bar_frame)

        # Polling rate — issue #6. O G403 HERO não tem alteração de
        # polling rate confirmável pelo stack HID++ atual (feature
        # Report Rate 0x8060 não implementada na descoberta de
        # features; sem validação em hardware real). A capacidade
        # permanece indisponível: nenhuma frequência é apresentada
        # como ativa e os botões não executam NENHUM comando — sem
        # sucesso falso nem simulação visual.
        pr_title = QLabel("Polling Rate")
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
        self.polling_controls = QWidget()
        self.polling_controls.setObjectName("pollingControls")
        pr_row = QHBoxLayout(self.polling_controls)
        pr_row.setContentsMargins(0, 0, 0, 0)
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
            """ % (COLORS["bg_card"], COLORS["text_muted"], COLORS["border"]))
            pr_row.addWidget(btn)
            self.polling_buttons.append(btn)
        pr_row.addStretch()
        layout.addWidget(self.polling_controls)

        layout.addStretch()

        # Estado real de polling rate refletido no build (issue #6).
        self._sync_polling()

    def _sync_polling(self):
        """Reflete o estado REAL da capacidade polling_rate_available
        (issue #6): indisponível → mensagem orientada ao usuário
        (issue #101 — sem stack, feature ID ou referência interna; a
        causa técnica permanece no core), botões desabilitados, nenhuma
        frequência ativa. Chamado no build e no showEvent (refresh
        explícito, sem polling periódico)."""
        if self.state is None:
            self.polling_hint.setText(
                f"● Polling rate indisponível: {POLLING_UNAVAILABLE_COPY}"
            )
            self.polling_hint.setStyleSheet(
                "color: %s; font-size: 12px; background: transparent;"
                % COLORS["warning"]
            )
            for btn in self.polling_buttons:
                btn.setEnabled(False)
            self.polling_controls.setEnabled(False)
            self.polling_controls.setVisible(False)
            return
        caps = self.state.capability_state()
        available = caps.is_available("polling_rate_available")
        # A capability do snapshot não é suficiente para habilitar uma ação.
        # O core mantém a causa técnica, mas a UI usa copy segura para o
        # usuário até existir uma operação Report Rate verificável.
        if available:
            summary = "alteração não disponível nesta versão"
        else:
            summary = POLLING_UNAVAILABLE_COPY
        self.polling_hint.setText(
            "● Polling rate indisponível: %s" % summary
        )
        self.polling_hint.setStyleSheet(
            "color: %s; font-size: 12px; background: transparent;"
            % COLORS["danger"]
        )
        for btn in self.polling_buttons:
            btn.setEnabled(False)
        self.polling_controls.setEnabled(False)
        self.polling_controls.setVisible(False)

    def _on_slider_preview(self, val):
        """PREVIEW apenas: altera somente o display. O efeito no
        ponteiro (libinput) acontece no commit (sliderReleased) — um
        gesto gera no máximo uma operação de sensibilidade."""
        self.sens_value.setText(f"{val}%")
        self.sens_state.setText(_SENS_STATE_TEXT)

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
            font-size: 44px;
            font-weight: 900;
            background: transparent;
        """)
        applied = result.details.get("applied")
        if ok and applied is not None:
            self.sens_value.setText(f"{applied}%")
            self.sens_state.setText(_SENS_STATE_TEXT)
            self.slider.setValue(applied)
        else:
            confirmed = self.state.applied_sensitivity
            if confirmed is not None:
                self.sens_value.setText(f"{confirmed}%")
                self.sens_state.setText(_SENS_STATE_TEXT)
                self.slider.setValue(confirmed)
            else:
                self.sens_value.setText(UNKNOWN_VALUE_TEXT)
                self.sens_state.setText(_SENS_UNKNOWN_TEXT)

    def showEvent(self, event):
        """Refresh explícito ao abrir a página (revisão PR #21 — sem
        polling periódico)."""
        super().showEvent(event)
        if self.state is not None:
            self.state.refresh()
            confirmed = self.state.applied_sensitivity
            if confirmed is not None:
                self.sens_value.setText(f"{confirmed}%")
                self.sens_state.setText(_SENS_STATE_TEXT)
                self.slider.setValue(confirmed)
            else:
                self.sens_value.setText(UNKNOWN_VALUE_TEXT)
                self.sens_state.setText(_SENS_UNKNOWN_TEXT)
        self._sync_sensitivity_caps()
        self._sync_polling()

    def _sync_sensitivity_caps(self):
        """Reflete sensitivity_available com a causa real (issue #7)."""
        if self.state is None:
            return
        caps = self.state.capability_state()
        available = caps.is_available("sensitivity_available")
        reason = caps.reason_for("sensitivity_available") or "capacidade não disponível no ambiente atual"
        self.slider.setEnabled(available)
        if available:
            self.caps_hint.setText("● Sensibilidade do sistema disponível")
            self.caps_hint.setStyleSheet("color: %s; font-size: 12px; background: transparent;" % COLORS["mc_green"])
        else:
            self.caps_hint.setText(f"● Sensibilidade indisponível: {reason}")
            self.caps_hint.setStyleSheet("color: %s; font-size: 12px; background: transparent;" % COLORS["danger"])


class AutoClickerPage(QWidget):
    """Pagina do Auto-Clicker"""
    def __init__(self, mc, ac, svc, caps_provider=None):
        super().__init__()
        self.mc = mc
        self.ac = ac
        self.svc = svc
        self.caps_provider = caps_provider
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        title = QLabel("Auto-Clicker")
        title.setStyleSheet(f"font-size: 24px; font-weight: 900; color: {COLORS['text_primary']}; background: transparent;")
        title_icon = ui_icons.icon_label("clicker", COLORS["accent_light"], 24)
        title_row = QHBoxLayout()
        if title_icon is not None:
            title_row.addWidget(title_icon)
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)


        # Status
        self.status_frame = QFrame()
        self.status_frame.setObjectName("clickerStatus")
        self.status_frame        .setStyleSheet(f"""
            QFrame#clickerStatus {{
                background: {COLORS['bg_card']};
                border: 2px solid {COLORS['border']};
                border-radius: 16px;
                padding: 20px;
            }}
        """)
        sl = QHBoxLayout(self.status_frame)

        self.status_icon = QLabel("")
        self.status_icon.setStyleSheet("font-size: 44px; background: transparent;")
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
        self.mc_status = QLabel("Minecraft não detectado")
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
        cps_title = QLabel("CPS (Cliques por segundo)")
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
            font-size: 24px;
            font-weight: 900;
            background: transparent;
        """)
        cps_row.addWidget(self.cps_display)

        cps_unit = QLabel("CPS")
        cps_unit.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 14px; font-weight: 600; background: transparent;")
        cps_row.addWidget(cps_unit)
        layout.addLayout(cps_row)

        # Button selector
        btn_title = QLabel("Botão")
        btn_title.setStyleSheet(f"font-size: 16px; font-weight: 700; background: transparent;")
        layout.addWidget(btn_title)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.btn_buttons = []
        for i, (name, icon) in enumerate([(  "Esquerdo", ""), ("Meio", ""), ("Direito", "")]):
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
        self.caps_hint = QLabel("")
        self.caps_hint.setStyleSheet("color: %s; font-size: 12px; background: transparent;" % COLORS["text_muted"])
        self.caps_hint.setWordWrap(True)

        self.toggle_btn = AccentButton("Iniciar Auto-Clicker")
        self.toggle_btn.setMinimumHeight(44)
        self.toggle_btn.setToolTip(
            "O clique só dispara com a janela do Minecraft em foco — "
            "fora dela o motor fica ocioso por segurança.")
        self.toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self.toggle_btn)

        layout.addStretch()

        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._update)
        self.timer.start(1000)

        # issue #7: disponibilidade real do clicker dirige os controles.
        self._sync_caps()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_caps()

    def _sync_caps(self):
        """Reflete autoclick_available com a causa real (issue #7)."""
        if self.caps_provider is None:
            return
        caps = self.caps_provider()
        available = caps.is_available("autoclick_available")
        reason = caps.reason_for("autoclick_available") or "capacidade não disponível no ambiente atual"
        button_widgets = [b for b, _ in self.btn_buttons]
        for w in [self.cps_slider, self.toggle_btn, *button_widgets]:
            w.setEnabled(available)
        if available:
            self.caps_hint.setText("● Auto-clicker disponível (X11/XTest)")
            self.caps_hint.setStyleSheet("color: %s; font-size: 12px; background: transparent;" % COLORS["mc_green"])
        else:
            self.caps_hint.setText(f"● Auto-clicker indisponível: {reason}")
            self.caps_hint.setStyleSheet("color: %s; font-size: 12px; background: transparent;" % COLORS["danger"])

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
            self._update()  # estado real como fonte (issue #5)
            self.toggle_btn.setText("Iniciar Auto-Clicker")
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
            self.status_icon.setText("")
            self.status_frame.setObjectName("clickerStatus")
            self.status_frame            .setStyleSheet(f"""
                QFrame#clickerStatus {{
                    background: {COLORS['bg_card']};
                    border: 2px solid {COLORS['border']};
                    border-radius: 16px;
                    padding: 20px;
                }}
            """)
        else:
            self.ac.start()
            self._update()  # estado real como fonte (issue #5)
            self.toggle_btn.setText("Parar Auto-Clicker")
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
            self.status_icon.setText("")
            self.status_frame.setObjectName("clickerStatus")
            self.status_frame            .setStyleSheet(f"""
                QFrame#clickerStatus {{
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
            self.mc_status.setText("Minecraft Detectado!")
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
            self.mc_status.setText("Minecraft não detectado — auto-clicker não vai clicar")
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
            self.status_icon.setText("")
            self.toggle_btn.setText("Parar Auto-Clicker")
        elif state.value == "blocked_by_focus":
            self.status_title.setText("Aguardando jogo em foco...")
            self.status_sub.setText(
                "Ligado, mas só clica com Minecraft/Lunar Client ativo")
            self.status_icon.setText("")
            self.toggle_btn.setText("Parar Auto-Clicker")
        elif state.value == "failed":
            self.status_title.setText("Auto-Clicker com erro")
            self.status_sub.setText(f"Falha: {self.ac.error or 'desconhecida'}")
            self.status_icon.setText("⚠")
            self.toggle_btn.setText("Iniciar Auto-Clicker")
        else:
            self.status_title.setText("Auto-Clicker Desligado")
            self.status_sub.setText("Clique em iniciar para começar")
            self.status_icon.setText("")
            self.toggle_btn.setText("Iniciar Auto-Clicker")


class MacrosPage(QWidget):
    """Pagina de Macros"""
    def __init__(self, me, svc, caps_provider=None):
        super().__init__()
        self.me = me
        self.svc = svc
        self.caps_provider = caps_provider
        # issue #4: start/stop/cancel de gravação rodam FORA da thread
        # da UI (o handshake XRecord espera até 5 s e o stop faz join
        # de até 2 s). A conclusão é aplicada pelo timer de 500 ms —
        # widgets só são tocados na main thread.
        self._op_kind: Optional[str] = None  # "start" | "stop" | "cancel"
        self._op_thread: Optional[threading.Thread] = None
        self._op_result: Optional[dict] = None
        self._op_ctx: dict = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        title = QLabel("Macros")
        title.setStyleSheet(f"font-size: 24px; font-weight: 900; color: {COLORS['text_primary']}; background: transparent;")
        title_icon = ui_icons.icon_label("macros", COLORS["accent_light"], 24)
        title_row = QHBoxLayout()
        if title_icon is not None:
            title_row.addWidget(title_icon)
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        # Record controls
        rec_frame = QFrame()
        rec_frame.setObjectName("recFrame")
        rec_frame        .setStyleSheet(f"""
            QFrame#recFrame {{
                background: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        rl = QVBoxLayout(rec_frame)

        rl.addWidget(QLabel("Nome da macro:"))
        self.name_input = QLineEdit("minha_macro")
        self.name_input.setMaxLength(32)
        self.name_input.setStyleSheet(f"padding: 10px; font-size: 14px;")
        rl.addWidget(self.name_input)

        row = QHBoxLayout()
        self.record_btn = DangerButton("Gravar Macro")
        self.record_btn.clicked.connect(self._toggle_record)
        row.addWidget(self.record_btn)

        self.cancel_btn = QPushButton("Cancelar")
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

        # issue #7: disponibilidade real da captura, com a causa.
        self.caps_hint = QLabel("")
        self.caps_hint.setStyleSheet("color: %s; font-size: 12px; background: transparent;" % COLORS["text_muted"])
        self.caps_hint.setWordWrap(True)
        rl.addWidget(self.caps_hint)

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
        self._play_timer.timeout.connect(self._poll_op)
        self._play_timer.start(500)

        layout.addWidget(rec_frame)

        # Macro list
        list_title = QLabel("Macros Salvas")
        list_title.setStyleSheet(f"font-size: 16px; font-weight: 700; background: transparent;")
        layout.addWidget(list_title)

        self.macro_list_widget = QWidget()
        self.macro_list_layout = QVBoxLayout(self.macro_list_widget)
        self.macro_list_layout.setContentsMargins(0, 0, 0, 0)
        self.macro_list_layout.setSpacing(6)

        scroll = QScrollArea()
        scroll.setWidget(self.macro_list_widget)
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(120)
        layout.addWidget(scroll, 1)
        # espaço sobrando vai pro rodapé, NÃO infla o card de gravação
        layout.addStretch()

        self._refresh_list()

        # issue #7: disponibilidade real da captura dirige os controles
        # (após a lista existir — botões por linha também são gated).
        self._sync_caps()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_caps()

    def _sync_caps(self):
        """Reflete macro_capture_available com a causa real (issue #7).

        Gravação exige captura XRecord; playback exige emissão XTest.
        Sem o ambiente, ambos ficam desabilitados com a causa visível —
        incluindo os botões por linha da lista de macros.
        """
        if self.caps_provider is None:
            return
        caps = self.caps_provider()
        available = caps.is_available("macro_capture_available")
        reason = caps.reason_for("macro_capture_available") or "capacidade não disponível no ambiente atual"
        self.name_input.setEnabled(available)
        self.record_btn.setEnabled(available)
        for child in self.macro_list_widget.findChildren(QPushButton):
            child.setEnabled(available)
        if available:
            self.caps_hint.setText("● Captura de macros disponível (X11/XRecord)")
            self.caps_hint.setStyleSheet("color: %s; font-size: 12px; background: transparent;" % COLORS["mc_green"])
        else:
            self.caps_hint.setText(f"● Captura de macros indisponível: {reason}")
            self.caps_hint.setStyleSheet("color: %s; font-size: 12px; background: transparent;" % COLORS["danger"])

    def _set_recording_ui(self, recording: bool) -> None:
        self.record_btn.setText("Parar Gravação" if recording else " Gravar Macro")
        self.cancel_btn.setVisible(recording)
        self.name_input.setEnabled(not recording)
        if not recording and self._op_kind is None:
            self.record_btn.setEnabled(True)

    def _cancel_record(self):
        """Aborta a gravação descartando os eventos acumulados.

        Funciona também DURANTE o handshake inicial (issue #4): o
        cancelamento aborta o start em andamento em vez de ser
        ignorado — e roda fora da thread da UI."""
        if self._op_kind == "start":
            # Cancelar DURANTE o handshake (issue #4): o pedido aborta
            # o start em curso — o desfecho ("cancelado durante
            # inicialização") aparece quando a op pendente conclui.
            threading.Thread(
                target=self.me.cancel_recording,
                name="mouse-hub-record-cancel-start",
                daemon=True,
            ).start()
            self.record_status.setText("Cancelando…")
            return
        if self._op_kind is not None:
            return  # já há operação em curso
        self.record_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.record_status.setText("Cancelando gravação…")
        self._start_async("cancel", self.me.cancel_recording)

    def _toggle_record(self):
        # Uma operação por vez: o handshake/stop nunca roda na thread
        # da UI e cliques repetidos não empilham operações (issue #4).
        if self._op_kind is not None:
            return
        if self.me.recording:
            self.record_btn.setEnabled(False)
            self.record_status.setText("Encerrando gravação…")
            self._start_async("stop", self.me.stop_recording)
        else:
            name = self.name_input.text().strip() or \
                f"macro_{int(time.time())}"
            self.record_btn.setEnabled(False)
            self.name_input.setEnabled(False)
            self.cancel_btn.setVisible(True)
            self.record_status.setText(
                " Iniciando captura XRecord… (aguardando o servidor X)")
            self._start_async("start", lambda: self.me.start_recording(name),
                              name=name)

    # ── Operações assíncronas de gravação (issue #4) ────────────

    def _start_async(self, kind: str, fn, **ctx) -> None:
        self._op_kind = kind
        self._op_ctx = ctx
        self._op_result = None
        def _work():
            result = None
            error = None
            try:
                result = fn()
            except Exception as exc:  # noqa: BLE001 — a UI decide o que mostrar
                error = exc
            self._op_result = {"result": result, "error": error}
        self._op_thread = threading.Thread(
            target=_work, name=f"mouse-hub-record-{kind}", daemon=True,
        )
        self._op_thread.start()

    def _poll_op(self) -> None:
        """Aplica o resultado da operação assíncrona na main thread
        (chamado pelo timer de 500 ms). Nenhum widget é tocado pela
        thread de trabalho."""
        if self._op_kind is None or self._op_result is None:
            return
        kind = self._op_kind
        ctx = self._op_ctx
        result = self._op_result["result"]
        error = self._op_result["error"]
        self._op_kind = None
        self._op_thread = None
        self._op_result = None
        self.record_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)

        if kind == "start":
            if error is not None:
                self._set_recording_ui(False)
                self.record_status.setText(
                    f"Erro ao iniciar a gravação: {error}")
            elif result:
                name = ctx.get("name", "")
                self._set_recording_ui(True)
                self.record_status.setText(
                    f"● Gravando '{name}'... pressione parar quando "
                    "terminar. Teclas e cliques são capturados em "
                    "qualquer janela.")
            else:
                self._set_recording_ui(False)
                reason = self.me.capture_failed or "capturador indisponível"
                self.record_status.setText(
                    f"Não foi possível iniciar a gravação: {reason}")
        elif kind == "stop":
            self._set_recording_ui(False)
            if error is not None:
                self.record_status.setText(
                    f"Erro ao encerrar a gravação: {error}")
            elif result is None:
                self.record_status.setText(
                    "⚠  Gravação descartada (sem eventos ou nome inválido)")
            else:
                count = self.me.macros.get(result, {}).get("count", 0)
                suffix = " — TRUNCADA no teto de eventos" \
                    if self.me.last_recording_truncated else ""
                self.record_status.setText(
                    f"Macro '{result}' salva! ({count} eventos){suffix}")
            self._refresh_list()
        elif kind == "cancel":
            self._set_recording_ui(False)
            self.record_status.setText(
                "⚠  Gravação cancelada — eventos descartados")

    def _update_play_status(self) -> None:
        """Reflete o estado real do playback: em execução ou FAILED com
        o motivo do último erro. Sincroniza também os botões Play —
        durante a reprodução qualquer botão vira ' Cancel'."""
        state = self.me.playback_state
        running = state == "running"
        if running:
            self.play_status.setText("Reproduzindo...")
        elif state == "failed":
            reason = self.me.playback_error or "falha de emissão"
            self.play_status.setText(f"Playback falhou: {reason}")
        else:
            self.play_status.setText("")
        for child in self.macro_list_widget.findChildren(QPushButton):
            if child.text() in (" Play", " Cancel") and child is not getattr(
                self, "_last_del_btn", None
            ):
                child.setText("Cancel" if running else " Play")

    def _refresh_list(self):
        # Clear
        while self.macro_list_layout.count():
            child = self.macro_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        macros = self.me.list_all()
        if not macros:
            empty = QLabel(
                "Nenhuma macro gravada ainda.\n"
                "Use   Gravar Macro acima para criar a primeira.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color: {COLORS['text_muted']}; padding: 30px; font-size: 13px; background: transparent;")
            self.macro_list_layout.addWidget(empty)
            return

        for name, info in macros.items():
            item = QFrame()
            item.setObjectName("macroItem")
            item            .setStyleSheet(f"""
                QFrame#macroItem {{
                    background: {COLORS['bg_card']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 10px;
                    padding: 12px;
                }}
                QFrame#macroItem:hover {{
                    border-color: {COLORS['accent']};
                }}
            """)
            il = QHBoxLayout(item)

            info_col = QVBoxLayout()
            name_label = QLabel(f" {name}")
            name_label.setStyleSheet(f"font-size: 14px; font-weight: 700; background: transparent;")
            info_col.addWidget(name_label)

            meta = QLabel(f"{info['count']} eventos  •  {info['created'][:10]}")
            meta.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; background: transparent;")
            info_col.addWidget(meta)
            il.addLayout(info_col)

            il.addStretch()

            play_btn = QPushButton("Play")
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
                durante a execução vira ' Cancel' e encerra a
                emissão em curso (worker exato, sem criar substituto)."""
                if self.me.playing:
                    self.me.cancel_playback()
                    btn.setText("Play")
                else:
                    if self.me.play(n):
                        btn.setText("Cancel")

            play_btn.clicked.connect(lambda _, b=play_btn: on_play(b))
            il.addWidget(play_btn)

            del_btn = QPushButton(_MACRO_DELETE_LABEL)
            del_btn.setFixedSize(80, 32)
            del_btn.setCursor(QCursor(Qt.PointingHandCursor))
            del_btn.setToolTip(_MACRO_DELETE_TOOLTIP)
            del_btn.setAccessibleName(f"Excluir macro {name}")
            del_btn.setAccessibleDescription(
                "Ação destrutiva: remove a macro gravada permanentemente"
            )
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid {COLORS['border']};
                    color: {COLORS['text_secondary']};
                    border-radius: 8px;
                    font-size: 12px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    border-color: {COLORS['danger']};
                    background: rgba(239, 68, 68, 0.1);
                    color: {COLORS['danger']};
                }}
                QPushButton:focus {{
                    border-color: {COLORS['danger']};
                    color: {COLORS['danger']};
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
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        title = QLabel("Perfis")
        title.setStyleSheet("font-size: 24px; font-weight: 900; background: transparent;")
        title_icon = ui_icons.icon_label("profiles", COLORS["accent_light"], 24)
        title_row = QHBoxLayout()
        if title_icon is not None:
            title_row.addWidget(title_icon)
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

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
        self._grid_cols = 3

        # ── Criacao/edicao de perfil customizado ────────────────────
        form_label = QLabel("Criar / Editar Perfil")
        form_label.setStyleSheet("font-size: 16px; font-weight: 700; background: transparent;")
        layout.addWidget(form_label)

        # Grid (issue #66): nome em linha própria, controles e botões
        # em duas colunas — nunca soma 668px de largura mínima.
        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(10)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Nome do perfil")
        self.name_input.setMinimumWidth(120)
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
        self.save_btn = AccentButton("Salvar Perfil")
        self.save_btn.clicked.connect(self._save_custom)
        self.clear_btn = QPushButton("Cancelar")
        self.clear_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.clear_btn.clicked.connect(self._clear_form)
        form.addWidget(self.name_input, 0, 0, 1, 2)
        form.addWidget(self.dpi_input, 1, 0)
        form.addWidget(self.sens_input, 1, 1)
        form.addWidget(self.save_btn, 2, 0)
        form.addWidget(self.clear_btn, 2, 1)
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
                "● Nao foi possivel ler os perfis: %s "
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
        # audit: cards flexíveis — 3 colunas têm de caber em 720px
        card.setMinimumSize(140, 185)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
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
        ic = QLabel("")
        ic.setStyleSheet("font-size: 20px; background: transparent;")
        top.addWidget(ic)
        top.addStretch()
        active_badge = QLabel("")
        active_badge.setStyleSheet("font-size: 11px; font-weight: 700; background: transparent;")
        top.addWidget(active_badge)
        cl.addLayout(top)

        nm = QLabel(profile.name)
        nm.setStyleSheet(
            "font-size: 14px; font-weight: 700; color: %s; background: transparent;"
            % COLORS["text_primary"]
        )
        cl.addWidget(nm)

        det = QLabel("DPI: %d  •  Sens: %d%%" % (profile.dpi, profile.sensitivity))
        det.setStyleSheet(
            "color: %s; font-size: 11px; background: transparent;" % COLORS["text_secondary"]
        )
        cl.addWidget(det)

        cl.addStretch()

        apply = QPushButton("Aplicar")
        apply.setCursor(QCursor(Qt.PointingHandCursor))
        apply.setStyleSheet(
            "QPushButton { background: %s; color: white; border: none;"
            "border-radius: 8px; padding: 5px; font-size: 12px; font-weight: 700; }"
            "QPushButton:hover { background: %s; }"
            % (COLORS["accent"], COLORS["accent_light"])
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

        self.grid.addWidget(card, index // self._grid_cols,
                     index % self._grid_cols)
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
            text = (" Perfil '%s' NAO aplicado: DPI falhou "
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
                " Nao foi possivel salvar o perfil '%s': %s" % (name, outcome.message)
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
    def __init__(self, mc, ac, me, svc, state=None):
        super().__init__()
        self.mc = mc
        self.ac = ac
        self.me = me
        self.svc = svc
        self.state = state
        self._permission_thread: Optional[threading.Thread] = None
        self._permission_result: Optional[object] = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        title = QLabel("Configurações")
        title.setStyleSheet(f"font-size: 24px; font-weight: 900; background: transparent;")
        title_icon = ui_icons.icon_label("settings", COLORS["accent_light"], 24)
        title_row = QHBoxLayout()
        if title_icon is not None:
            title_row.addWidget(title_icon)
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        # HID Permissions
        hid_group = QGroupBox(" Permissões HID (DPI via Hardware)")
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

        # Fluxo do usuário final (sem terminal): o próprio app aplica a
        # regra udev via prompt gráfico de senha (polkit/pkexec). O
        # estado do botão reflete a evidência real das capacidades.
        self._permission_status = QLabel("")
        self._permission_status.setWordWrap(True)
        self._permission_status.setStyleSheet("font-size: 12px; background: transparent;")
        hid_layout.addWidget(self._permission_status)

        self._permission_btn = QPushButton(
            " Conceder acesso ao hardware  (senha de administrador)"
        )
        self._permission_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_card']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                padding: 10px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{ border-color: {COLORS['accent']}; }}
            QPushButton:disabled {{ color: {COLORS['text_muted']}; }}
        """)
        self._permission_btn.clicked.connect(self._grant_hid_access)
        hid_layout.addWidget(self._permission_btn)

        self._sync_permission_ui()
        layout.addWidget(hid_group)

        # Auto-clicker settings
        ac_group = QGroupBox(" Auto-Clicker — Segurança")
        ac_layout = QVBoxLayout(ac_group)

        safety_text = QLabel(
            " O auto-clicker só funciona quando Minecraft/Lunar Client está em foco.\n"
            " O detector lê o nome da janela ativa direto via X11, "
            "com cache de 500 ms (TTL) entre consultas.\n"
            " Nenhum clique é feito fora do jogo."
        )
        safety_text.setWordWrap(True)
        safety_text.setStyleSheet(f"color: {COLORS['mc_green']}; font-size: 12px; background: transparent;")
        ac_layout.addWidget(safety_text)

        layout.addWidget(ac_group)

        # System info
        info_group = QGroupBox(" Informações do Sistema")
        info_layout = QVBoxLayout(info_group)

        paths = ConfigPaths.xdg()
        info = QLabel(
            f"Mouse: {MOUSE_NAME} (VID 046d / PID c08f)\n"
            f"Descoberta: identidades de hardware (sysfs/hidraw)\n"
            f"Sistema: Linux (X11/XWayland)\n"
            f"Python: {sys.version.split()[0]}\n"
            f"Config: {paths.config_file}\n"
            f"Macros: {paths.macros_file}"
        )
        info.setStyleSheet(f"font-family: monospace; font-size: 12px; color: {COLORS['text_secondary']}; background: transparent;")
        info_layout.addWidget(info)

        layout.addWidget(info_group)

        layout.addStretch()


# ═══════════════════════════════════════════════════════════════════════════════
    def _sync_permission_ui(self) -> None:
        """Botão/status refletem a evidência REAL de acesso HID —
        nunca genérico (issue #7: estado honesto de capacidades)."""
        if self.state is None:
            self._permission_btn.setText(_PERMISSION_BTN_LABEL)
            self._permission_status.setText(
                "Estado de hardware não disponível nesta página.")
            self._permission_status.setStyleSheet(
                f"font-size: 12px; color: {COLORS['text_muted']}; background: transparent;")
            self._permission_btn.setEnabled(False)
            return
        try:
            caps = self.state.capability_state()
        except Exception:  # noqa: BLE001
            self._permission_btn.setEnabled(False)
            return
        if caps.is_available("hid_available"):
            self._permission_status.setText(
                " Acesso HID ativo — controle de DPI físico operável.")
            self._permission_status.setStyleSheet(
                f"font-size: 12px; color: {COLORS['success']}; background: transparent;")
            self._permission_btn.setEnabled(False)
            self._permission_btn.setToolTip("Acesso já concedido")
            self._permission_btn.setText("✔  Acesso HID já concedido")
            return
        reason = caps.reason_for("hid_available")
        if self._permission_btn.text() != _PERMISSION_BTN_LABEL:
            self._permission_btn.setText(_PERMISSION_BTN_LABEL)
        if is_hid_permission_issue(reason):
            self._permission_status.setText(
                f"Sem acesso HID: {reason}. "
                "Clique abaixo e informe sua senha para o app resolver.")
            self._permission_status.setStyleSheet(
                f"font-size: 12px; color: {COLORS['warning']}; background: transparent;")
            self._permission_btn.setEnabled(True)
            self._permission_btn.setToolTip("")
        else:
            if self._permission_btn.text() != _PERMISSION_BTN_LABEL:
                self._permission_btn.setText(_PERMISSION_BTN_LABEL)
            self._permission_status.setText(
                f"⚠ Sem acesso HID por outra causa: {reason}")
            self._permission_status.setStyleSheet(
                f"font-size: 12px; color: {COLORS['text_secondary']}; background: transparent;")
            self._permission_btn.setEnabled(False)

    def _grant_hid_access(self) -> None:
        """Roda o pkexec (prompt gráfico de senha) em thread dedicada —
        a UI nunca trava esperando o usuário digitar a senha."""
        thread = self._permission_thread
        if thread is not None and thread.is_alive():
            return  # já em andamento
        self._permission_btn.setEnabled(False)
        self._permission_status.setText(
            " Aguardando autenticação de administrador…")
        self._permission_status.setStyleSheet(
            f"font-size: 12px; color: {COLORS['text_secondary']}; background: transparent;")
        self._permission_result = None

        def work():
            self._permission_result = fix_hid_permissions()

        self._permission_thread = threading.Thread(
            target=work, name="mouse-hub-hid-permission", daemon=True)
        self._permission_thread.start()
        QTimer.singleShot(150, self._poll_permission_result)

    def _poll_permission_result(self) -> None:
        thread = self._permission_thread
        if thread is not None and thread.is_alive():
            QTimer.singleShot(150, self._poll_permission_result)
            return
        result, self._permission_result = self._permission_result, None
        self._permission_thread = None
        if result is None:
            self._sync_permission_ui()
            return
        if result.status.ok:
            # Nova evidência REAL antes de afirmar sucesso: re-probe.
            try:
                if self.state is not None:
                    self.state.refresh()
            except Exception:  # noqa: BLE001
                pass
            self._permission_status.setText("" + result.message)
            self._permission_status.setStyleSheet(
                f"font-size: 12px; color: {COLORS['success']}; background: transparent;")
            self._permission_btn.setEnabled(False)
        else:
            self._permission_status.setText(
                (" " if result.status.value == "permission_denied" else "⚠ ")
                + result.message)
            self._permission_status.setStyleSheet(
                f"font-size: 12px; color: {COLORS['warning']}; background: transparent;")
            self._sync_permission_ui()


#  MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════════════

class MouseHubApp(QMainWindow):
    """Janela principal do Mouse Hub"""

class MouseHubApp(QMainWindow):
    """Janela principal do Mouse Hub"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(" Mouse Hub — Controlador Gaymer")
        # Mínimo coerente com o conteúdo (issue #66): abaixo disso as
        # páginas entram em scroll em vez de sobrepor widgets.
        self.setMinimumSize(720, 520)
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
        # issue #7: o refresh acima reavalia capacidades; o indicador
        # da sidebar parte delas (a chamada em _switch_page também
        # cobre as atualizações posteriores).

        # Core único de automação (PR #14): uma única instância
        # compartilhada por todas as páginas — foco, gravação, playback
        # e clicker centralizados (detect once, share state). Nada é
        # criado no startup (lazy): display, workers e disco só surgem
        # quando a feature é usada.
        migrate_legacy_config(ConfigPaths.xdg())
        self.svc = AutomationService(
            macros_path=ConfigPaths.xdg().macros_file,
            config_paths=ConfigPaths.xdg(),
        )
        self.ac = AutoClickerFacade(self.svc)
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
        sidebar.setObjectName("sidebar")
        sidebar.setStyleSheet(f"""
            QFrame#sidebar {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLORS['sidebar_bg']}, stop:1 {COLORS['bg_darkest']});
                border-right: 1px solid {COLORS['border']};
            }}
        """)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(12, 16, 12, 12)
        sb_layout.setSpacing(3)

        # Logo — bloco de marca com acento (sem emoji: tofu na fonte
        # do usuário; identidade vem de tipografia + barra de acento)
        logo_frame = QFrame()
        logo_frame.setFixedHeight(56)
        logo_layout = QHBoxLayout(logo_frame)
        logo_layout.setContentsMargins(4, 0, 4, 0)
        logo_layout.setSpacing(10)
        accent_bar = QFrame()
        accent_bar.setFixedSize(4, 36)
        accent_bar.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {COLORS['accent_light']}, stop:1 {COLORS['accent_dark']});
                border-radius: 2px;
        """)
        logo_layout.addWidget(accent_bar)
        logo_text = QLabel("MOUSE HUB")
        logo_text.setStyleSheet(f"""
            font-size: {TYPE_SCALE['logo']}px;
            font-weight: 900;
            color: {COLORS['text_primary']};
            background: transparent;
            letter-spacing: 1.5px;
        """)
        logo_layout.addWidget(logo_text)
        logo_layout.addStretch()
        sb_layout.addWidget(logo_frame)

        sb_layout.addSpacing(10)

        # Status
        self.status_indicator = QFrame()
        self.status_indicator.setFixedHeight(32)
        self.status_indicator.setObjectName("statusIndicator")
        self.status_indicator        .setStyleSheet(f"""
            QFrame#statusIndicator {{
                background: {COLORS['bg_card']};
                border-radius: 18px;
                padding: 4px 12px;
            }}
        """)
        si_layout = QHBoxLayout(self.status_indicator)
        si_layout.setContentsMargins(8, 0, 8, 0)
        # Ponto de estado: círculo PINTADO via QSS (não-glyph — não
        # depende da fonte do usuário; Pedido explícito: zero emoji).
        self._status_dot = QLabel()
        self._status_dot.setFixedSize(8, 8)
        self._status_dot.setStyleSheet(f"""
            background: {COLORS['text_muted']};
            border-radius: 4px;
        """)
        si_layout.addWidget(self._status_dot)
        self._status_text = QLabel("Offline")
        self._status_text.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; font-weight: 600; background: transparent;")
        si_layout.addWidget(self._status_text)
        si_layout.addStretch()
        sb_layout.addWidget(self.status_indicator)

        sb_layout.addSpacing(8)

        # Nav buttons
        self.nav_buttons = []
        pages_data = [
            ("dashboard", "Dashboard", 0),
            ("dpi", "DPI", 1),
            ("sensitivity", "Sensibilidade", 2),
            ("clicker", "Auto-Clicker", 3),
            ("macros", "Macros", 4),
            ("profiles", "Perfis", 5),
            ("settings", "Configurações", 6),
        ]

        for icon, text, idx in pages_data:
            btn = SidebarButton(icon, text, idx)
            btn.clicked.connect(lambda _, i=idx: self._switch_page(i))
            sb_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sb_layout.addStretch()

        # Version
        ver = QLabel(f"Mouse Hub v{APP_VERSION}")
        ver.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; background: transparent;")
        sb_layout.addWidget(ver)

        main_layout.addWidget(sidebar)

        # ─── Pages ───
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {COLORS['bg_darkest']};")

        self.dashboard_page = DashboardPage(self.mc, self.ac, self.me, self.svc, state=self.mouse_state)
        self.dpi_page = DPIPage(self.mc, state=self.mouse_state)
        self.sens_page = SensitivityPage(self.mc, state=self.mouse_state)
        self.clicker_page = AutoClickerPage(
            self.mc, self.ac, self.svc,
            caps_provider=self.full_capability_state,
        )
        self.macros_page = MacrosPage(
            self.me, self.svc,
            caps_provider=self.full_capability_state,
        )
        self.profiles_page = ProfilesPage(self.mc, state=self.mouse_state, store=ProfileStore(ConfigPaths.xdg()))
        self.settings_page = SettingsPage(self.mc, self.ac, self.me, self.svc, state=self.mouse_state)

        # Sem thread de estado do mouse (revisão PR #21): o refresh
        # roda no startup, após operações e em evento explícito — nunca
        # em loop periódico.

        # Issue #66: toda página vive dentro de um scroll frameless —
        # janela pequena NUNCA mais sobrepõe widgets; conteúdo rola.
        for page in (
            self.dashboard_page, self.dpi_page, self.sens_page,
            self.clicker_page, self.macros_page, self.profiles_page,
            self.settings_page,
        ):
            self.stack.addWidget(self._wrap_scrollable(page))

        main_layout.addWidget(self.stack)

        # Set active
        self._switch_page(0)

        # Hotplug (issue #67): monitor de uevents hidraw em thread
        # dedicada + debounce (plug emite rajada) — orientado a evento,
        # sem polling de /sys e sem polling HID++. Se o ambiente não
        # suportar netlink, o app segue funcionando sem hotplug.
        self._hotplug_queue: "queue.Queue" = queue.Queue()
        self._hotplug_debouncer = HotplugDebouncer()
        self._hotplug_monitor = UdevHidrawMonitor(self._hotplug_queue)
        self._hotplug_monitor.start()
        self._hotplug_timer = QTimer(self)
        self._hotplug_timer.timeout.connect(self._poll_hotplug)
        self._hotplug_timer.start(200)

    @staticmethod
    def _wrap_scrollable(page):
        """Envolve a página em QScrollArea transparente (issue #66).

        Todo QLabel da página recebe wordWrap: texto longo deixa a
        página ENCOLHER em vez de empurrar a largura mínima do layout
        (causa raiz da sobreposição em janela pequena)."""
        for lab in page.findChildren(QLabel):
            lab.setWordWrap(True)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(page)
        return scroll

    def _switch_page(self, index):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.set_active(i == index)
        self._update_sidebar_status()

    # ── Estado global dirigido por capacidades (issue #7) ───────

    def _automation_overrides(self):
        """Evidências de automação da instância real do serviço.

        O modelo de capacidades do MouseController marca automações
        como "fronteira: outra instância"; a instância de automação
        deste processo decide a partir do ambiente (X11 presente ⇒
        XTest/XRecord utilizáveis). Sem X11, a causa real aparece no
        motivo — a UI nunca simula disponibilidade.
        """
        if os.environ.get("DISPLAY"):
            return {
                "autoclick_available": (True, ""),
                "macro_capture_available": (True, ""),
                "active_window_detection_available": (True, ""),
            }
        reason = "sessão sem X11 (DISPLAY ausente)"
        return {
            "autoclick_available": (False, reason),
            "macro_capture_available": (False, reason),
            "active_window_detection_available": (False, reason),
        }

    def full_capability_state(self) -> CapabilityState:
        """Estado combinado: evidências de hardware (core) + evidências
        da instância de automação (issue #7)."""
        return with_overrides(
            self.mouse_state.capability_state(), self._automation_overrides()
        )

    def _poll_hotplug(self, now: Optional[float] = None) -> None:
        """Drena a fila do monitor (main thread) e aplica o debounce.

        Só a CHEGADA de evento importa — o devpath vem do discovery no
        refresh, que reescaneia o sysfs atual. Rajada vira um único
        refresh após a janela de silêncio."""
        clock = time.monotonic if now is None else (lambda: now)
        drained = False
        try:
            while True:
                self._hotplug_queue.get_nowait()
                drained = True
        except queue.Empty:
            pass
        if drained:
            self._hotplug_debouncer.event_received(clock())
        if self._hotplug_debouncer.should_refresh(clock()):
            self._on_device_changed()

    def _on_device_changed(self) -> None:
        """Conexão/desconexão do G403: reavalia capacidades e sincroniza
        a UI inteira (sidebar, dashboard e caps das páginas)."""
        try:
            self.mouse_state.refresh()
        except Exception:  # noqa: BLE001 — refresh nunca derruba a UI
            pass
        self._update_sidebar_status()
        for sync in (
            getattr(self.dashboard_page, "_sync_subtitle", None),
            getattr(self.dpi_page, "_sync_from_state", None),
            getattr(self.sens_page, "_sync_sensitivity_caps", None),
            getattr(self.clicker_page, "_sync_caps", None),
            getattr(self.macros_page, "_sync_caps", None),
        ):
            if sync is None:
                continue
            try:
                sync()
            except Exception:  # noqa: BLE001 — uma página não derruba as outras
                pass

    def _update_sidebar_status(self):
        """Indicador da sidebar reflete o estado combinado real —
        nunca "Online" incondicional."""
        caps = self.full_capability_state()
        if caps.is_available("mouse_detected") and caps.is_available("hid_available"):
            text, color = "Online", COLORS["success"]
        elif caps.is_available("mouse_detected"):
            text, color = "Detectado", COLORS["warning"]
        else:
            text, color = "Offline", COLORS["text_muted"]
        self._status_dot.setStyleSheet(f"""
            background: {color};
            border-radius: 4px;
        """)
        self._status_text.setText(text)

    def closeEvent(self, event):
        # Encerramento completo: captura, playback e worker do clicker
        # (o mutex do serviço garante a parada sem corrida; a chamada é
        # idempotente quando nada foi usado). Não há thread de estado
        # do mouse para parar (revisão PR #21 — sem polling periódico).
        # Ordem correta (auditoria #4/#5): para as engines ENQUANTO o
        # IO compartilhado ainda vive, depois encerra o serviço UMA
        # única vez (me.cleanup delega ao svc.cleanup, idempotente).
        # Hotplug (issue #67): para o monitor ANTES das engines —
        # idempotente, seguro sem start (fail soft do netlink).
        monitor = getattr(self, "_hotplug_monitor", None)
        if monitor is not None:
            monitor.stop()
        self.ac.cleanup()
        self.me.cleanup()
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
