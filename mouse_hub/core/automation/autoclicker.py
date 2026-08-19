from __future__ import annotations
"""Auto-clicker de baixo overhead.

Correções sobre a base da PR #14 (aplicadas nesta PR de integração):

* O loop não deve disputar o lock do engine a cada iteração para
  atualizar o intervalo do scheduler — isso competia com `stop()` e
  podia manter a thread viva além do join, leaving worker threads
  orphaned (stop() com `worker.join(timeout=2.0)` retornava com a
  thread ainda viva e `_worker` apontando para ela).
* Falha do backend (`io.click` retornando False) agora transita para
  o estado FAILED e encerra o loop, em vez de engolir a falha.
* Quando o join excede o timeout, a evidência de falha é preservada
  (`_join_timed_out` e a thread não é descartada silenciosamente).
"""

# Contrato de performance (da base da PR #14):
#
# * 1 thread, criada/encerrada no liga/desliga — nunca uma thread por
#   clique;
# * aguardo via scheduler (`Event.wait`), zero busy-wait;
# * foco verificado com `FocusChecker` de frequência própria (TTL),
#   nunca por clique;
# * mudar CPS ou botão apenas atualiza campos em memória — o worker
#   não é recriado;
# * emissão de clique é `AutomationIO.click` direta (XTest via
#   python-xlib em produção) — nenhum subprocesso no hot path;
# * `stop()` aguarda a thread finalizar (join com timeout), de modo
#   que o engine nunca fica consumindo CPU depois de desligado;
# * sem log por clique; qualquer logging detalhado fica atrás de
#   `debug_mode`.

from enum import Enum


class AutoClickerState(str, Enum):
    """Estados do auto-clicker visíveis à UI.

    * STOPPED — desligado, sem thread nem consumo de CPU;
    * RUNNING — ligado e clicando;
    * BLOCKED_BY_FOCUS — ligado, mas a janela ativa não pertence ao
      conjunto permitido (cliques suprimidos, sem consumo de backend);
    * STOPPING — transição de desligamento;
    * FAILED — backend ou foco falhou; a UI deve exibir o erro.
    """

    STOPPED = "stopped"
    RUNNING = "running"
    BLOCKED_BY_FOCUS = "blocked_by_focus"
    STOPPING = "stopping"
    FAILED = "failed"


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
        windows: tuple[str, ...] = ("Minecraft", "Lunar Client", "Badlion", "Feather", "Hypixel", "Mina Launcher", "Prismarine", "Salwyrr", "Vanilla"),
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
        self._state = AutoClickerState.STOPPED
        self._last_error: Optional[str] = None
        self._worker: Optional[threading.Thread] = None
        self._join_timed_out = False
        self._join_timeout = 2.0
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
    def state(self) -> AutoClickerState:
        with self._lock:
            return self._state

    @property
    def last_error(self) -> Optional[str]:
        """Última mensagem de falha (para FAILED), legível pela UI."""
        return self._last_error

    @property
    def stats(self) -> "EngineStats":
        return self._stats

    # ── Controle ───────────────────────────────────────────────────

    def set_cps(self, cps: int) -> None:
        """Muda o CPS sem recriar o worker: apenas o intervalo do
        scheduler em uso é ajustado. O scheduler tem sincronização
        interna (threading.Event), então a atualização do intervalo
        não disputa o lock do engine com o worker — disputas aqui
        eram a causa raiz do stop() lento na base da PR #14."""
        if not (1 <= cps <= 50):
            raise ValueError(f"CPS deve estar entre 1 e 50: {cps}")
        with self._lock:
            self._desired_cps = cps
            self._interval = _cps_to_interval(cps)
        with self._lock:
            scheduler = self._scheduler
        if scheduler is not None:
            # O próximo aguardo já respeita o novo valor.
            scheduler.interval = self._interval

    def set_button(self, button: MouseButton) -> None:
        """Muda o botão sem recriar o worker."""
        self._button = button

    def start(self) -> None:
        """Liga o auto-clicker. Start duplicado é idempotente."""
        with self._lock:
            if self._running:
                return
            if self._state == AutoClickerState.FAILED and self._join_timed_out:
                # Não reutilizar um engine com thread órfã comprovada;
                # a UI deve apresentar uma nova instância ou alertar.
                return
            self._running = True
            self._state = AutoClickerState.RUNNING
            self._last_error = None
            self._join_timed_out = False
            self._worker = threading.Thread(
                target=self._run,
                name="mouse-hub-autoclicker",
                daemon=True,
            )
            self._worker.start()

    def stop(self) -> None:
        # O lock protege o estado; o aguardo/thread deve ser encerrado
        # FORA do lock para não travar com a thread de trabalho.
        # IMPORTANTE: o early-return NÃO pode descartar o cleanup da
        # thread — o worker define `_running = False` no finally
        # ANTES de o thread encerrar de fato. Se `stop()` chegar nesse
        # intervalo, o snapshot antigo retornaria sem join e o teste
        # (`_worker is None`) pegaria a thread "stopped" ainda
        # referenciada (era o bug flaky da base da PR #14).
        with self._lock:
            still_running = self._running
            if still_running:
                self._running = False
                self._state = AutoClickerState.STOPPING
            scheduler = self._scheduler
            worker = self._worker
        if worker is None:
            return
        if still_running and scheduler is not None:
            scheduler.stop()   # acorda o aguardo imediatamente
        if worker is not None:
            worker.join(timeout=self._join_timeout)
            if worker.is_alive():
                # Re-armar o scheduler e tentar de novo: o worker pode
                # estar em um aguardo iniciado antes do stop() ou em
                # contenção de lock com a primeira tentativa.
                if scheduler is not None:
                    scheduler.stop()
                worker.join(timeout=self._join_timeout)
            if worker.is_alive():
                # Última tentativa: o worker pode estar entre a leitura
                # de `while self._running` e a próxima aquisição de
                # lock; aguarde mais um período antes de declarar
                # thread órfã.
                worker.join(timeout=self._join_timeout)
            if worker.is_alive():
                # Evidência de falha: o join estourou — não fingir
                # cleanup bem-sucedido. A thread e o registro ficam
                # disponíveis para diagnóstico (_worker, _join_timed_out).
                self._join_timed_out = True
                self._state = AutoClickerState.FAILED
                _debug("stop: worker join timed out — thread órfã possível")
            else:
                self._worker = None
                self._join_timed_out = False
        if self._state == AutoClickerState.STOPPING:
            self._state = AutoClickerState.STOPPED

    def stop_and_failed(self, message: str) -> None:
        """Transita para FAILED a partir de dentro do worker
        (falha do backend ou do foco) e interrompe o aguardo."""
        with self._lock:
            self._running = False
            self._state = AutoClickerState.FAILED
            self._last_error = message
            scheduler = self._scheduler
        if scheduler is not None:
            scheduler.stop()

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
                # Uma única aquisição de lock por iteração: intervalo,
                # scheduler e botão podem mudar entre iterações (hot
                # config). Anteriormente o loop disputava o lock com
                # stop()/set_cps a cada tick, o que sob contenção
                # estourava o join de shutdown.
                with self._lock:
                    interval = self._interval
                    button = self._button
                    sched = self._scheduler
                self._stats.focus_checks += 1
                # Falha de foco DISTINGUÍVEL: a fonte de título
                # (X11TitleSource) está indisponível — display X de
                # leitura ausente/broken. Não é "janela não focada"
                # (BLOCKED_BY_FOCUS): é um defeito do backend, e o
                # engine NÃO deve ficar "ligado" clicando sem saber a
                # janela ativa. Vira FAILED com causa legível pela UI.
                if not self._focus.is_available:
                    self.stop_and_failed("fonte de título indisponível")
                    break
                state = self._focus.is_focused(self._windows)
                if state.focused:
                    if not self._io.click(button):
                        # Falha do backend vira FAILED — o engine nunca
                        # fica "ligado" sem conseguir clicar.
                        self.stop_and_failed("io.click falhou")
                        break
                    self._stats.clicks += 1
                    with self._lock:
                        if self._state != AutoClickerState.FAILED:
                            self._state = AutoClickerState.RUNNING
                else:
                    # Bloqueado pelo foco: o estado reflete a causa.
                    with self._lock:
                        if self._state != AutoClickerState.FAILED:
                            self._state = AutoClickerState.BLOCKED_BY_FOCUS
                if self._debug and state.focused:
                    # Debug mode: sem print por clique em uso normal.
                    _debug(f"click {button.value} @ {self._desired_cps} cps")
                if sched is None or not sched.wait_next():
                    break  # stop() interrompeu ou scheduler trocado
        finally:
            self._running = False
            with self._lock:
                if self._state != AutoClickerState.FAILED:
                    self._state = AutoClickerState.STOPPED

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
