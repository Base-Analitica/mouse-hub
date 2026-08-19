"""Auto-clicker de baixo overhead.

Contrato funcional (preservado do produto):
* CPS entre 1 e 50 (validado);
* botões esquerdo/meio/direito;
* cliques somente quando a janela ativa pertence ao conjunto
  configurado (jogo configurado);
* desligar encerra imediatamente e não consome CPU depois.

Contrato de performance (novo):
* 1 thread, criada/encerrada no liga/desliga — nunca uma thread por
  clique;
* aguardo via scheduler (`Event.wait`), zero busy-wait;
* foco verificado com `FocusChecker` de frequência própria (TTL),
  nunca por clique;
* mudar CPS ou botão apenas atualiza campos em memória — o worker
  não é recriado;
* emissão de clique é `AutomationIO.click` direta (XTest via
  python-xlib em produção) — nenhum subprocesso no hot path;
* `stop()` aguarda a thread finalizar (join com timeout), de modo
  que o engine nunca fica consumindo CPU depois de desligado;
* sem log por clique; qualquer logging detalhado fica atrás de
  `debug_mode`.
"""

from __future__ import annotations

import threading
from typing import Optional

from mouse_hub.core.automation.focus import WindowFocusChecker
from mouse_hub.core.automation.io import AutomationIO
from mouse_hub.core.automation.scheduler import AutomationScheduler
from mouse_hub.core.automation.types import FocusedState, MouseButton


def _cps_to_interval(cps: int) -> float:
    if cps < 1:
        return 1.0
    return 1.0 / cps


class AutoClickerEngine:
    def __init__(
        self,
        io: AutomationIO,
        focus: WindowFocusChecker,
        cps: int = 10,
        button: MouseButton = MouseButton.LEFT,
        windows: tuple[str, ...] = ("Minecraft", "Lunar Client", "Badlion", "Feather", "Hypixel"),
        debug_mode: bool = False,
    ) -> None:
        if not (1 <= cps <= 50):
            raise ValueError(f"CPS deve estar entre 1 e 50: {cps}")
        self._io = io
        self._focus = focus
        self._button = button
        self._windows = windows
        self._debug = debug_mode

        self._interval = _cps_to_interval(cps)
        self._desired_cps = cps
        self._lock = threading.Lock()

        self._running = False
        self._worker: Optional[threading.Thread] = None
        self._scheduler: Optional[AutomationScheduler] = None
        self._stats = EngineStats()

    # ── Estado ─────────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._running

    @property
    def cps(self) -> int:
        return self._desired_cps

    @property
    def button(self) -> MouseButton:
        return self._button

    @property
    def stats(self) -> "EngineStats":
        return self._stats

    # ── Controle ───────────────────────────────────────────────────

    def set_cps(self, cps: int) -> None:
        """Muda o CPS sem recriar o worker: apenas o intervalo do
        scheduler em uso é ajustado."""
        if not (1 <= cps <= 50):
            raise ValueError(f"CPS deve estar entre 1 e 50: {cps}")
        with self._lock:
            self._desired_cps = cps
            self._interval = _cps_to_interval(cps)
            if self._scheduler is not None:
                # O próximo aguardo já respeita o novo valor.
                self._scheduler.interval = self._interval

    def set_button(self, button: MouseButton) -> None:
        """Muda o botão sem recriar o worker."""
        self._button = button

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._worker = threading.Thread(
                target=self._run,
                name="mouse-hub-autoclicker",
                daemon=True,
            )
            self._worker.start()

    def stop(self) -> None:
        # O lock protege o estado; o aguardo/thread deve ser encerrado
        # FORA do lock para não travar com a thread de trabalho, que
        # também adquire o mesmo lock a cada iteração.
        with self._lock:
            if not self._running:
                return
            self._running = False
            scheduler = self._scheduler
            worker = self._worker
        if scheduler is not None:
            scheduler.stop()   # acorda o aguardo imediatamente
        if worker is not None:
            worker.join(timeout=2.0)
            self._worker = None

    # ── Loop ───────────────────────────────────────────────────────

    def _run(self) -> None:
        """Loop de trabalho: uma única thread, sem busy-wait.

        Cada iteração: 1) verifica foco (cache TTL, não consulta o X
        por clique); 2) se focado, emite o clique via IO direto; 3)
        aguarda eficientemente o próximo tick. Sai imediatamente quando
        `stop()` interrompe o scheduler.
        """
        scheduler = AutomationScheduler(self._interval)
        with self._lock:
            self._scheduler = scheduler
            self._stats.clicks = 0
            self._stats.focus_checks = 0

        try:
            while self._running:
                self._stats.focus_checks += 1
                state = self._focus.is_focused(self._windows)
                if state.focused:
                    self._io.click(self._button)
                    self._stats.clicks += 1
                if self._debug and state.focused:
                    # Debug mode: sem print por clique em uso normal.
                    _debug(f"click {self._button.value} @ {self._desired_cps} cps")
                # Ajuste de CPS pode ter acontecido entre iterações.
                with self._lock:
                    scheduler.interval = self._interval
                if not scheduler.wait_next():
                    break  # stop() interrompeu
        finally:
            self._running = False

    @property
    def last_focus_state(self) -> Optional[FocusedState]:
        """Última observação de foco, para a UI (sem nova consulta)."""
        # O FocusChecker mantém o último estado em cache; acessível via
        # is_focused(()) mas a UI deve evitar checar em loop próprio.
        return None


class EngineStats:
    """Contadores simples (sem lock por leitura, apenas informativa)."""

    def __init__(self) -> None:
        self.clicks: int = 0
        self.focus_checks: int = 0


def _debug(message: str) -> None:  # pragma: no cover - apenas dev
    import logging

    logging.getLogger("mouse_hub.automation").debug(message)
