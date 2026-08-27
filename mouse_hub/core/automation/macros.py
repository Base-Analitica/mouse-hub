"""Gravador e reprodutor de macros de baixo overhead.

Gravação — orientada a eventos, nunca polling:
* o listener é chamado diretamente a cada evento (callback);
* o gravador existe apenas entre `start` e `stop`; ao parar,
  listeners são desconectados e o timer de gravação é liberado;
* eventos são acumulados incrementalmente em uma lista — memória
  proporcional ao tamanho da macro, sem estrutura fixa por
  dispositivo.

Reprodução — scheduling eficiente:
* o player dorme com `threading.Event.wait(delta)` entre eventos
  (o mesmo mecanismo do auto-clicker); não há loop girando até o
  timestamp;
* UI nunca bloqueia: o playback roda em thread dedicada;
* `cancel()` acorda e encerra o worker imediatamente.

Emissão de eventos usa `AutomationIO` (XTest direto em produção) —
nenhum subprocesso por evento de macro.

Persistência usa o formato relativo existente (`delta_ms`),
compatível com o `macros.json` do produto.
"""

from __future__ import annotations

import contextlib
import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from mouse_hub.core.automation.io import AutomationIO
from mouse_hub.core.automation.scheduler import AutomationScheduler
from mouse_hub.core.automation.types import EventType, MouseButton, RecordedEvent

MAX_EVENTS = 100_000  # teto defensivo: 100k eventos ~ poucos MB


class PlaybackState(str, Enum):
    """Estado do reprodutor de macros.

    * STOPPED — nenhum playback ativo (nunca iniciado ou concluído);
    * RUNNING — thread de playback ativa;
    * FAILED — emissão falhou (backend/XTest retornou False); o último
      erro fica em `last_error`.

    A UI lê este estado para reportar sucesso/erro sem mentir sobre
    o que o XTest realmente emitiu.
    """

    STOPPED = "stopped"
    RUNNING = "running"
    FAILED = "failed"


class MacroRecorder:
    """Gravador orientado a eventos com lifecycle curto.

    Uso:

        recorder = MacroRecorder()
        recorder.start()
        on_event = recorder.make_handler()
        display.record_all_events(on_event)   # python-xlib listener
        # ... usuário grava ...
        recorder.stop()
        events = recorder.events
    """

    def __init__(self) -> None:
        self._recording = False
        self._start_mono: float = 0.0
        self._events: List[RecordedEvent] = []
        self._last_at: float = 0.0

    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def events(self) -> List[RecordedEvent]:
        return list(self._events)  # snapshot imutável

    def start(self) -> None:
        if self._recording:
            return
        self._recording = True
        self._events.clear()
        self._start_mono = time.monotonic()
        self._last_at = 0.0

    def stop(self) -> None:
        """Encerra listeners e libera estado de gravação."""
        self._recording = False

    def make_handler(self) -> Callable[[Dict[str, Any]], None]:
        """Fábrica de callback compatível com listeners genéricos.

        Espera dict com: kind (EventType|str), button (int, opcional),
        keycode (int, opcional). O delta é calculado contra o tempo
        de gravação — armazenamento incremental, sem pós-processamento.
        """

        def handler(payload: Dict[str, Any]) -> None:
            if not self._recording:
                return
            now = time.monotonic() - self._start_mono
            if not self._events:
                delta_ms = 0.0  # primeiro evento ancora a linha do tempo
            else:
                delta_ms = (now - self._last_at) * 1000.0
            self._last_at = now
            kind = payload.get("kind")
            if isinstance(kind, EventType):
                kind = kind.value
            self._events.append(
                RecordedEvent(
                    kind=EventType(kind),
                    button=int(payload.get("button", 0)),
                    keycode=int(payload.get("keycode", 0)),
                    delta_ms=delta_ms,
                )
            )

        return handler

# Persistência é responsabilidade EXCLUSIVA do MacroStore
# (mouse_hub.core.automation.store) — gravador e reprodutor leem e
# escrevem pelo mesmo container transacional (issue #2: nenhuma
# segunda implementação de persistência/leitura de macros).

class MacroPlayer:
    """Reprodutor com scheduler eficiente e cancelamento imediato.

    Uso:

        player = MacroPlayer(io)
        player.play(events, repeat=3)
        # ...
        player.cancel()
    """

    def __init__(self, io: AutomationIO) -> None:
        self._io = io
        self._lock = threading.Lock()
        self._state = PlaybackState.STOPPED
        self._last_error: Optional[str] = None
        self._worker: Optional[threading.Thread] = None
        self._cancel_event = threading.Event()

    @property
    def playing(self) -> bool:
        """Playback ativo em execução (RUNNING) — a UI usa este nome
        por compatibilidade com o contrato existente."""
        return self._state == PlaybackState.RUNNING

    @property
    def state(self) -> PlaybackState:
        with self._lock:
            return self._state

    @property
    def last_error(self) -> Optional[str]:
        """Última falha de emissão observada (somente em FAILED)."""
        with self._lock:
            return self._last_error

    def play(self, events: List[RecordedEvent], repeat: int = 1) -> bool:
        """Inicia o playback. Retorna False quando já houver um
        playback ativo (mutex por player), repeat inválido ou lista
        vazia — nunca sobrescreve o worker de um playback em curso."""
        with self._lock:
            if self._state == PlaybackState.RUNNING:
                return False
            if repeat < 1 or not events:
                return False
            # Teto defensivo: macros gigantes não devem virar travamento.
            events = events[:MAX_EVENTS]
            self._state = PlaybackState.RUNNING
            self._last_error = None
            self._cancel_event.clear()
            worker = threading.Thread(
                target=self._run,
                args=(events, repeat),
                name="mouse-hub-macro-player",
                daemon=True,
            )
            self._worker = worker
        worker.start()
        return True

    def cancel(self) -> None:
        """Acorda e encerra o worker exato; release defensivo de teclas
        e botões pendentes acontece dentro do worker (finally)."""
        self._cancel_event.set()
        with self._lock:
            worker = self._worker
        if worker is not None:
            worker.join(timeout=2.0)

    # ── Loop ───────────────────────────────────────────────────────

    def _run(self, events: List[RecordedEvent], repeat: int) -> None:
        """Loop de reprodução com release defensivo: em qualquer saída
        (cancel, falha de backend, exceção, encerramento antecipado) os
        teclas e botões que receberam press sem release são liberados
        — o jogador nunca fica com um botão lógico "preso"."""
        scheduler = AutomationScheduler(0.01)
        pending_keys: List[int] = []
        pending_buttons: List[int] = []
        try:
            for _ in range(repeat):
                for event in events:
                    if self._cancel_event.is_set():
                        return
                    if event.delta_ms > 0:
                        scheduler.interval = min(event.delta_ms / 1000.0, 30.0)
                        if not scheduler.wait_next():
                            return
                    if not self._emit(event, pending_keys, pending_buttons):
                        self._fail("emissão falhou (backend/XTest)")
                        return
        except Exception as exc:  # noqa: BLE001
            self._fail(f"exceção no playback: {exc}")
        finally:
            # Release defensivo: soltar TUDO que ficou pressionado,
            # mesmo quando o IO já está em pane — a tentativa é a
            # melhor recuperação disponível e falhas aqui não levantam.
            for keycode in list(pending_keys):
                with contextlib.suppress(Exception):
                    self._io.key_release(keycode)
            for button in list(pending_buttons):
                try:
                    self._io.release(MouseButton.from_id(button))
                except (KeyError, ValueError):
                    pass
            pending_keys.clear()
            pending_buttons.clear()
            with self._lock:
                # RUNNING → STOPPED (sucesso) ou FAILED (falha já
                # registrada pelo _fail).
                if self._state != PlaybackState.FAILED:
                    self._state = PlaybackState.STOPPED
                self._worker = None

    def _fail(self, reason: str) -> None:
        with self._lock:
            if self._state != PlaybackState.FAILED:
                self._state = PlaybackState.FAILED
                self._last_error = reason

    def _emit(
        self,
        event: RecordedEvent,
        pending_keys: List[int],
        pending_buttons: List[int],
    ) -> bool:
        """Emissão direta (hot path sem subprocesso). Retorna False
        quando o backend falha — o loop converte em FAILED."""
        if event.kind == EventType.MOUSE_PRESS:
            if not self._io.press(MouseButton.from_id(event.button)):
                return False
            pending_buttons.append(event.button)
            return True
        if event.kind == EventType.MOUSE_RELEASE:
            ok = self._io.release(MouseButton.from_id(event.button))
            if event.button in pending_buttons:
                pending_buttons.remove(event.button)
            return ok
        if event.kind == EventType.MOUSE_MOVE:
            return self._io.move(event.button, event.keycode)  # x,y em button/keycode
        if event.kind == EventType.KEY_PRESS:
            if not self._io.key_press(event.keycode):
                return False
            pending_keys.append(event.keycode)
            return True
        if event.kind == EventType.KEY_RELEASE:
            ok = self._io.key_release(event.keycode)
            try:
                pending_keys.remove(event.keycode)
            except ValueError:
                pass
            return ok
        return True
