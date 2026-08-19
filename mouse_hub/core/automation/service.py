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
from mouse_hub.core.automation.macros import MacroPlayer, MacroRecorder
from mouse_hub.core.automation.scheduler import AutomationScheduler
from mouse_hub.core.automation.store import MacroStore, MacroStoreError
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
    ) -> None:
        self._macros_path = macros_path
        self._capture_backend = capture_backend
        self._io = io

        self._lock = threading.Lock()

        # Componentes lazy — criados sob demanda, nunca no startup.
        self._title_source = title_source
        self._focus: Optional[WindowFocusChecker] = None
        self._store: Optional[MacroStore] = None
        self._recorder: Optional[MacroRecorder] = None
        self._player: Optional[MacroPlayer] = None
        self._capture: Optional[InputCapture] = None
        self._clicker: Optional[AutoClickerEngine] = None

        self._events: List[RecordedEvent] = []
        self._record_name: Optional[str] = None
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
        if not capture.start():
            with self._lock:
                self._capture = capture
                self._record_name = None
            return False

        with self._lock:
            self._capture = capture
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
            events = self._events
            self._events = []
            self._record_name = None

        count = capture.stop()
        if not events:
            capture.cancel() if False else None  # resources já fechados
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

    def play(self, name: str, repeat: int = 1) -> bool:
        """Reproduz uma macro no XTest nativo (zero subprocesso no hot
        path). Rejeita durante gravação (mutex) e quando não há macro
        válida."""
        with self._lock:
            if self.recording:
                return False
            events = self.store.get(name)
            if not events:
                return False

        io = self._io or LinuxAutomationIO()
        self._player = MacroPlayer(io)
        try:
            self._player.play(events, repeat=repeat)
        except Exception:  # noqa: BLE001 — player rejeita (já playing,
            # repeat inválido) sem lançar por contrato; garantir
            # consistência mesmo que mude
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
            # referência — a próxima play() cria um player novo.
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
            io = self._io or LinuxAutomationIO()
            self._clicker = AutoClickerEngine(
                io=io,
                focus=self.window_service,
                windows=tuple(focus_patterns()),
            )
        return self._clicker

    def cleanup(self) -> None:
        """Encerramento completo e seguro quando nada foi usado."""
        self.cancel_recording()
        if self._player is not None and self._player.playing:
            self._player.cancel()
        if self._clicker is not None and self._clicker.running:
            self._clicker.stop()
