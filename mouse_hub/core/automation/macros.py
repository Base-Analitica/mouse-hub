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

import json
import time
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from mouse_hub.core.automation.io import AutomationIO
from mouse_hub.core.automation.scheduler import AutomationScheduler
from mouse_hub.core.automation.types import EventType, MouseButton, RecordedEvent

MAX_EVENTS = 100_000  # teto defensivo: 100k eventos ~ poucos MB


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

    # ── Persistência ───────────────────────────────────────────────

    @staticmethod
    def save(events: List[RecordedEvent], path: Path, name: str) -> None:
        """Salva em um arquivo JSON de macros (formato relativo)."""
        data: Dict[str, Any] = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
        if not isinstance(data, dict):
            data = {}
        data[name] = [
            {
                "kind": event.kind.value,
                "button": event.button,
                "keycode": event.keycode,
                "delta_ms": round(event.delta_ms, 2),
            }
            for event in events
        ]
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def load(path: Path, name: str) -> Optional[List[RecordedEvent]]:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict) or name not in data:
            return None
        entries = data[name]
        if not isinstance(entries, list):
            return None
        events: List[RecordedEvent] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                events.append(
                    RecordedEvent(
                        kind=EventType(entry["kind"]),
                        button=int(entry.get("button", 0)),
                        keycode=int(entry.get("keycode", 0)),
                        delta_ms=float(entry.get("delta_ms", 0)),
                    )
                )
            except (KeyError, ValueError):
                continue
        return events if events else None


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
        self._playing = False
        self._worker: Optional[threading.Thread] = None
        self._cancel_event = threading.Event()

    @property
    def playing(self) -> bool:
        return self._playing

    def play(self, events: List[RecordedEvent], repeat: int = 1) -> None:
        if self._playing or repeat < 1 or not events:
            return
        # Teto defensivo: macros gigantes não devem virar travamento.
        events = events[:MAX_EVENTS]
        self._playing = True
        self._cancel_event.clear()
        self._worker = threading.Thread(
            target=self._run,
            args=(events, repeat),
            name="mouse-hub-macro-player",
            daemon=True,
        )
        self._worker.start()

    def cancel(self) -> None:
        """Acorda e encerra o worker imediatamente."""
        self._cancel_event.set()
        if self._worker is not None:
            self._worker.join(timeout=2.0)
            self._worker = None

    # ── Loop ───────────────────────────────────────────────────────

    def _run(self, events: List[RecordedEvent], repeat: int) -> None:
        scheduler = AutomationScheduler(0.01)
        try:
            for _ in range(repeat):
                for event in events:
                    if self._cancel_event.is_set():
                        return
                    if event.delta_ms > 0:
                        scheduler.interval = min(event.delta_ms / 1000.0, 30.0)
                        if not scheduler.wait_next():
                            return
                    self._emit(event)
        finally:
            self._playing = False

    def _emit(self, event: RecordedEvent) -> None:
        """Emissão direta (hot path sem subprocesso)."""
        if event.kind == EventType.MOUSE_PRESS:
            self._io.press(MouseButton.from_id(event.button))
        elif event.kind == EventType.MOUSE_RELEASE:
            self._io.release(MouseButton.from_id(event.button))
        elif event.kind == EventType.MOUSE_MOVE:
            self._io.move(event.button, event.keycode)  # x,y em button/keycode
        elif event.kind == EventType.KEY_PRESS:
            self._io.key_press(event.keycode)
        elif event.kind == EventType.KEY_RELEASE:
            self._io.key_release(event.keycode)
