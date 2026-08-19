"""Motor de auto-clicker.

Preserva a intenção atual da feature:

- CPS configurável de 1 a 50
- Botões esquerdo (1), meio (2), direito (3)
- Execução em worker/background
- Condicionado à janela/jogo permitido em foco (regra atual do produto)
- Mudanças de CPS/botão valem imediatamente durante a execução

Estado real (não depende da UI):

    stopped            — motor parado
    running            — clicando
    blocked_by_focus   — ligado, mas janela permitida não está em foco
    failed             — erro no backend de clique

Foco e backend de clique são injetáveis para testes (fake) e troca de
implementação.
"""

import enum
import random
import threading
import time

from .focus import FocusDetector, XdotoolFocusDetector

CPS_MIN = 1
CPS_MAX = 50
VALID_BUTTONS = (1, 2, 3)
DEFAULT_ALLOWED_PATTERNS = (
    "Minecraft", "Lunar Client", "Lunar", "Badlion", "Feather", "Hypixel")


class AutoClickerState(enum.Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    BLOCKED_BY_FOCUS = "blocked_by_focus"
    FAILED = "failed"


class ClickBackend:
    """Backend default: xdotool click (stack atual do projeto)."""

    def click(self, button):
        # check=True para que falhas virem erro visível ao motor
        subprocess_run = __import__("subprocess").run
        subprocess_run(["xdotool", "click", str(button)],
                       capture_output=True, timeout=2, check=True)


class AutoClickerEngine:
    """Motor de auto-clicker com estado real e configuração hot."""

    def __init__(self, focus_detector=None, click_backend=None,
                 allowed_patterns=None):
        self._focus = focus_detector or XdotoolFocusDetector()
        self._backend = click_backend or ClickBackend()
        self._allowed = tuple(allowed_patterns) if allowed_patterns \
            else DEFAULT_ALLOWED_PATTERNS

        self._lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._cps = 10
        self._button = 1
        self._jitter_ms = 0
        self._state = AutoClickerState.STOPPED
        self._error = None
        self._thread = None
        self._stop_event = threading.Event()

    # ─── estado real ───

    @property
    def state(self):
        return self._state

    @property
    def error(self):
        return self._error

    # ─── configuração (hot, thread-safe) ───

    def set_cps(self, cps):
        cps = int(cps)
        self._cps = max(CPS_MIN, min(CPS_MAX, cps))
        return self._cps

    def set_button(self, button):
        button = int(button)
        if button not in VALID_BUTTONS:
            raise ValueError(f"botão inválido: {button} (use 1/2/3)")
        self._button = button
        return button

    @property
    def cps(self):
        return self._cps

    @property
    def button(self):
        return self._button

    # ─── lifecycle ───

    def start(self):
        """Inicia o motor. Idempotente: se já rodando/bloqueado, no-op.
        Retorna True se uma thread foi efetivamente iniciada."""
        with self._state_lock:
            if self._state in (AutoClickerState.RUNNING,
                               AutoClickerState.BLOCKED_BY_FOCUS):
                return False
            self._error = None
            self._stop_event.clear()
            self._state = AutoClickerState.RUNNING
            self._thread = threading.Thread(
                target=self._loop, name="autoclicker", daemon=True)
            self._thread.start()
        return True

    def stop(self):
        """Para o motor. Idempotente; aguarda a thread encerrar."""
        self._stop_event.set()
        with self._state_lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout=3)

    def cleanup(self):
        """Encerramento definitivo. Idiempotente."""
        self.stop()
        with self._state_lock:
            self._thread = None
            if self._state not in (AutoClickerState.STOPPED,
                                   AutoClickerState.FAILED):
                self._state = AutoClickerState.STOPPED

    # ─── worker ───

    def _loop(self):
        try:
            while not self._stop_event.is_set():
                if self._focus.is_allowed(self._allowed):
                    try:
                        self._backend.click(self._button)
                    except Exception as exc:
                        with self._state_lock:
                            self._error = str(exc)
                            self._state = AutoClickerState.FAILED
                        return  # erro: sai já com FAILED marcado
                    delay = 1.0 / self._cps
                    if self._jitter_ms > 0:
                        jitter = random.uniform(
                            -self._jitter_ms, self._jitter_ms) / 1000.0
                        delay = max(0.001, delay + jitter)

                    # sleep interrompível para respeitar stop/CPS change
                    deadline = time.monotonic() + delay
                    while time.monotonic() < deadline:
                        if self._stop_event.wait(
                                min(0.05, max(0.0, deadline - time.monotonic()))):
                            # parada solicitada: final block normaliza estado
                            break
                        if time.monotonic() >= deadline:
                            break
                    else:
                        # inner while não saiu por break/stop (não deveria
                        # acontecer): reinicia a iteração
                        continue
                    if self._stop_event.is_set():
                        break

                    # atualiza estado entre cliques quando em foco
                    with self._state_lock:
                        if self._state == AutoClickerState.BLOCKED_BY_FOCUS:
                            self._state = AutoClickerState.RUNNING
                else:
                    with self._state_lock:
                        if self._state == AutoClickerState.RUNNING:
                            self._state = AutoClickerState.BLOCKED_BY_FOCUS
                    # poll mais lento quando fora do jogo; evita subprocessos
                    # em alta frequência (comportamento atual do produto)
                    if self._stop_event.wait(0.2):
                        break
        except Exception:
            # loop nunca deve morrer silenciosamente sem marcar estado
            with self._state_lock:
                if self._state not in (AutoClickerState.FAILED,
                                       AutoClickerState.STOPPED):
                    self._state = AutoClickerState.FAILED

        # worker saiu do loop (stop() ou erro). Se ainda não marcou
        # FAILED, o destino é STOPPED — inclusive quando estava
        # BLOCKED_BY_FOCUS, pois o usuário pediu parada.
        with self._state_lock:
            if self._state != AutoClickerState.FAILED:
                self._state = AutoClickerState.STOPPED
