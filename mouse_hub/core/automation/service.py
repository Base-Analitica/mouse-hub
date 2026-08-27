"""AutomationService — serviço central de automação do app.

Concentra a descoberta do ambiente e o ciclo de vida dos motores de
automação, atendendo à orientação de arquitetura da PR (um único
ponto de descoberta/estado, sem cada tela consultar o dispositivo ou o
sistema individualmente):

* `focus` é descoberto UMA vez (X11TitleSource com TTL interno) e
  compartilhado por todos os consumidores — Dashboard, AutoClicker e
  Macros usam o mesmo checker, sem subprocesso adicional;
* tudo é **lazy**: o serviço não abre display X, não cria workers e
  não lê disco no startup — apenas na primeira operação de cada
  recurso;
* o **mutex record/playback** vive aqui: gravar e reproduzir ao mesmo
  tempo se sobrepõem no mesmo canal de eventos; `play` rejeita durante
  gravação e `start_recording` rejeita durante playback;
* sem polling em idle: o único "tick" do Dashboard continua existindo
  (leitura de DPI/hidraw), mas a informação de foco vem do checker
  com cache TTL próprio — zero subprocessos enquanto o clicker está
  desligado e zero queries quando o valor não mudou.

O serviço é dependência-ausente (não conhece Qt) e testável: os
adapters XRecord/XDisplay e o foco são injetáveis.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, List, Optional

from mouse_hub.core.automation.autoclicker import AutoClickerEngine
from mouse_hub.core.automation.focus import WindowFocusChecker
from mouse_hub.core.automation.io import AutomationIO
from mouse_hub.core.automation.macros import MacroPlayer
from mouse_hub.core.automation.scheduler import AutomationScheduler
from mouse_hub.core.automation.store import MacroStore, MacroStoreError
from mouse_hub.core.config import ConfigPaths, load_autoclicker_settings, save_autoclicker_settings
from mouse_hub.core.automation.types import MouseButton, RecordedEvent
from mouse_hub.platform.linux.automation import (
    LinuxAutomationIO,
    X11TitleSource,
    focus_patterns,
)
from mouse_hub.platform.linux.capture import InputCapture, XRecordBackend


class AutomationService:
    """Ponto único de descoberta e estado de automação.

    Uso pelo app:

        service = AutomationService(macros_path=...)
        svc = service.window_service        # título/foco com TTL
        ok = service.start_recording("nome")
        events = service.stop_recording()
        service.play("nome", repeat=1)      # rejeita durante gravação
        service.clicker.start()             # AutoClickerEngine do core
    """

    def __init__(
        self,
        macros_path: Path,
        title_source=None,
        capture_backend: Optional[XRecordBackend] = None,
        io: Optional[AutomationIO] = None,
        config_paths: Optional["ConfigPaths"] = None,
    ) -> None:
        self._macros_path = macros_path
        # Caminhos XDG para carregar/persistir preferências do
        # auto-clicker (issue #5). None = lê/salva no XDG padrão.
        self._config_paths = config_paths
        self._capture_backend = capture_backend
        # Ownership explícito: quando o IO/TitleSource é injetado, o
        # serviço NÃO o fecha no cleanup — a responsabilidade é do
        # injetor. Só fecha o que ele mesmo criou.
        self._io = io
        self._io_owned = io is None
        self._title_source_owned = title_source is None

        self._lock = threading.Lock()

        # Componentes lazy — criados sob demanda, nunca no startup.
        self._title_source = title_source
        self._focus: Optional[WindowFocusChecker] = None
        self._store: Optional[MacroStore] = None
        self._player: Optional[MacroPlayer] = None
        self._capture: Optional[InputCapture] = None
        self._clicker: Optional[AutoClickerEngine] = None

        self._events: List[RecordedEvent] = []
        self._record_name: Optional[str] = None
        self._last_recording_truncated: bool = False
        self._loaded = False

    # ── Foco (discovert once, consumers share) ─────────────────────

    @property
    def window_service(self) -> WindowFocusChecker:
        """Única fonte do título da janela ativa + estado de foco.

        O checker tem TTL interno (500ms) — nenhum consumidor faz
        query extra, e com o clicker desligado o cache nunca é
        consultado (zero subprocesso em idle)."""
        if self._focus is None:
            source = self._title_source or X11TitleSource()
            self._focus = WindowFocusChecker(source, ttl_ms=500)
        return self._focus

    def invalidate_focus(self) -> None:
        """Invalida o cache de foco quando a informação expirar
        deliberadamente (ex.: o usuário mudou de janela via Alt+Tab
        dentro do jogo)."""
        self.window_service.invalidate()

    # ── Persistência ───────────────────────────────────────────────

    @property
    def store(self) -> MacroStore:
        if self._store is None:
            self._store = MacroStore(self._macros_path)
            if not self._loaded:
                self._loaded = True
                self._store.load()
        return self._store

    def list_macros(self) -> List[str]:
        return self.store.list()

    # ── Gravação ───────────────────────────────────────────────────

    @property
    def recording(self) -> bool:
        if self._capture is None:
            return False
        return self._capture.recording

    @property
    def capture_failure(self) -> Optional[str]:
        if self._capture is None:
            return None
        return self._capture.failure

    def start_recording(self, name: str) -> bool:
        """Inicia gravação real. Rejeita durante playback (mutex) ou
        quando já grava. Retorna False (sem exceção) quando o XRecord
        falha — o motivo fica em `capture_failure`."""
        with self._lock:
            if self._player is not None and self._player.playing:
                return False
            if self.recording:
                return False
            self._events = []
            self._record_name = name

        capture = InputCapture(self._on_event, backend=self._capture_backend)
        with self._lock:
            # Registrado ANTES do handshake (issue #4): cancelar durante
            # o estado `starting` encontra a captura e aborta o start —
            # antes, o pedido era silenciosamente ignorado.
            self._capture = capture
        if not capture.start():
            with self._lock:
                self._record_name = None
            return False
        return True

    def stop_recording(self) -> bool:
        """Encerra a gravação e persiste a macro. Retorna False se não
        havia gravação ou se a gravação é vazia (rejeitada pelo store
        transacional)."""
        with self._lock:
            if self._capture is None or not self._capture.recording:
                return False
            capture = self._capture
            self._capture = None
            name = self._record_name or "macro"
            self._record_name = None

        # DRAIN PRIMEIRO: stop() para o worker da captura e devolve o
        # contador final — o snapshot de self._events só é seguro
        # DEPOIS, quando nenhum evento da gravação pode mais chegar.
        capture.stop()
        with self._lock:
            events = self._events
            self._events = []
        if not events:
            # resources do capture já foram fechados pelo stop() acima
            return False

        try:
            self.store.add(name, events)
            self.store.flush()
        except MacroStoreError:
            return False
        return True

    def cancel_recording(self) -> None:
        """Aborta a gravação descartando os eventos acumulados."""
        with self._lock:
            if self._capture is None:
                return
            capture = self._capture
            self._capture = None
            self._events = []
            self._record_name = None
        capture.cancel()
        with self._lock:
            # A captura cancelada permanece registrada: o motivo do
            # aborto (ex.: "cancelado durante inicialização") fica
            # legível em capture_failure para a UI (issue #4). O estado
            # interno é stopped — recording/stop seguem coerentes.
            self._capture = capture

    def delete_macro(self, name: str) -> bool:
        if not self.store.delete(name):
            return False
        self.store.flush()
        return True

    # ── Playback ───────────────────────────────────────────────────

    @property
    def playing(self) -> bool:
        return self._player is not None and self._player.playing

    @property
    def player(self) -> Optional[MacroPlayer]:
        return self._player

    @property
    def playback_state(self) -> str:
        """Estado do playback (STOPPED/RUNNING/FAILED) — a UI lê direto
        daqui sem depender da referência do player (que vira None após
        o cancel)."""
        if self._player is None:
            return "stopped"
        return self._player.state

    @property
    def playback_error(self) -> Optional[str]:
        """Último motivo de falha do playback — ex.: tecla/botão que o
        backend recusou."""
        if self._player is None:
            return None
        return self._player.last_error

    def play(self, name: str, repeat: int = 1) -> bool:
        """Reproduz uma macro no XTest nativo (zero subprocesso no hot
        path). Rejeita durante gravação (mutex), durante playback já
        ativo (nunca sobrescreve o worker em curso) e quando não há
        macro válida."""
        with self._lock:
            if self.recording:
                return False
            if self._player is not None and self._player.playing:
                # Playback já em curso — o caller não recebe exceção
                # nem um worker substituído no meio da emissão; o
                # estado FAILED/last_error continua acessível.
                return False
            events = self.store.get(name)
            if not events:
                return False
            # IO do playback é um recurso único do serviço — criado
            # uma vez e reutilizado entre play()s (display X não é
            # aberto/fechado a cada macro). O cancel() apenas encerra
            # a emissão em curso, nunca o IO.
            io = self._io or LinuxAutomationIO()
            self._io = io
            player = MacroPlayer(io)
            self._player = player

        started = player.play(events, repeat=repeat)
        if not started:
            # repeat inválido/sem eventos pós-validação: libera o
            # player — o IO continua vivo para o próximo play().
            with self._lock:
                if self._player is player:
                    self._player = None
            return False
        return True

    def cancel_playback(self) -> bool:
        if self._player is None:
            return False
        try:
            self._player.cancel()
        finally:
            # Espera o worker morrer (cancel joina) e limpa a
            # referência — a próxima play() cria um player novo, mas
            # reutiliza o mesmo IO (não cria display X de novo).
            with self._lock:
                self._player = None
        return True

    def _on_event(self, event: RecordedEvent) -> None:
        """Sink da captura — append thread-safe (GIL) à lista local."""
        with self._lock:
            self._events.append(event)

    # ── Auto-clicker (engine do core, foco compartilhado) ──────────

    @property
    def clicker(self) -> AutoClickerEngine:
        if self._clicker is None:
            with self._lock:
                io = self._io
                if io is None:
                    # Clicker-first: o IO criado aqui vira o IO
                    # oficial do serviço — o playback posterior
                    # reutiliza EXATAMENTE a mesma instância (mesmo
                    # display X, um open por processo de vida).
                    io = LinuxAutomationIO()
                    self._io = io
            cps, button_name = self.initial_clicker_settings()
            self._clicker = AutoClickerEngine(
                io=io,
                focus=self.window_service,
                windows=tuple(focus_patterns()),
                cps=cps,
                button=MouseButton(button_name),
            )
        return self._clicker

    def initial_clicker_settings(self) -> tuple[int, str]:
        """Preferências persistidas do auto-clicker (issue #5).

        Sem `config_paths` (testes/embedding), retorna os defaults do
        core sem tocar em disco — a suíte permanece hermética. Com
        caminhos configurados, falha de leitura/config inválida cai no
        default dentro do próprio leitor — nunca impede o motor."""
        if self._config_paths is None:
            return 10, "left"
        try:
            return load_autoclicker_settings(self._config_paths)
        except Exception:  # noqa: BLE001 — config não pode derrubar o motor
            return 10, "left"

    def save_clicker_settings(self) -> bool:
        """Persiste CPS/botão atuais do engine (best-effort: falha de
        I/O não derruba o motor nem a UI). Sem `config_paths`, é no-op
        (nada é escrito em disco)."""
        clicker = self._clicker
        if clicker is None or self._config_paths is None:
            return False
        try:
            save_autoclicker_settings(
                clicker.cps, clicker.button.value, self._config_paths
            )
            return True
        except Exception:  # noqa: BLE001
            return False

    def cleanup(self) -> None:
        """Encerramento completo e seguro: gravação cancelada, playback
        e clicker parados (join), e TODO recurso owned fechado — IO e
        TitleSource criados pelo próprio serviço. O que foi injetado
        de fora fica com o injetor. Idempotente."""
        self.cancel_recording()
        player = None
        clicker = None
        with self._lock:
            io_owned = self._io_owned
            title_source_owned = self._title_source_owned
            player = self._player
            clicker = self._clicker
            self._player = None
            self._clicker = None
            # O IO compartilhado vive enquanto o serviço vive; no
            # cleanup ele é encerrado para liberar o display X — mas
            # APENAS se o próprio serviço o criou.
            if io_owned:
                io = self._io
                self._io = None
            else:
                io = None
            # Mesmo princípio para o TitleSource: o serviço só fecha
            # o display X que ele mesmo criou (injetado = injetor).
            if title_source_owned:
                title_source = self._title_source
                self._title_source = None
            else:
                title_source = None
        if player is not None:
            try:
                player.cancel()
            except Exception:  # noqa: BLE001
                pass
        if clicker is not None:
            try:
                if clicker.running:
                    clicker.stop()
            except Exception:  # noqa: BLE001
                pass
        if io is not None:
            try:
                io.close()
            except Exception:  # noqa: BLE001
                pass
        # Fecha o TitleSource owned (idempotente: se nunca foi
        # usado, _cached_title está vazio e não há display a fechar).
        if title_source is not None:
            try:
                if getattr(title_source, "close", None) is not None:
                    title_source.close()
            except Exception:  # noqa: BLE001
                pass
