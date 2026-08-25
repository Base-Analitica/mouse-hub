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
import json
import threading
import time
from enum import Enum
from pathlib import Path
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
                "button": event.button,  # ID numérico X (1/2/3) —
                # mesmo contrato do MacroStore v1 (issue #16): nunca
                # gravar o botão como texto, ou o reload o descarta.
                "keycode": event.keycode,
                "delta_ms": round(event.delta_ms, 2),
            }
            for event in events
        ]
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    # ── Persistência ───────────────────────────────────────────────
    # Contrato de leitura (issue #17): o leitor aceita os formatos que
    # existem no ecossistema do produto e que o MacroStore já aceita —
    # gravação e reprodução precisam compartilhar o mesmo contrato:
    #
    #  1. container v1:      {schema_version: 1, macros: {name: [e..]}}
    #  2. wrapper main:      {name: {name, events: [...], created, count}}
    #  3. raiz direta v0/web: {name: [{kind, button, keycode, delta_ms}]}
    #
    # Entradas parcialmente inválidas não derrubam a macro inteira:
    # são puladas (a perda é mensurável — o caller pode comparar com
    # o `count` do wrapper quando existir). Uma macro com zero eventos
    # válidos retorna None (macro inexistente/vazia — a reprodução
    # nunca roda em cima de nada).

    @staticmethod
    def load(path: Path, name: str) -> Optional[List[RecordedEvent]]:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        entries = MacroRecorder._locate_entries(data, name)
        if entries is None:
            return None
        events = MacroRecorder._parse_events(entries)
        return events if events else None

    @staticmethod
    def _locate_entries(data: Dict[str, Any], name: str) -> Optional[Any]:
        """Localiza a lista de eventos de `name` nos formatos conhecidos.

        A busca tenta primeiro a raiz (formatos 1 e 3 compartilham a
        chave do nome); quando o valor é o wrapper do main (formato 2),
        desce no campo `events`. Retorna None quando o nome não existe
        ou o conteúdo não é uma lista."""
        raw = data.get(name)
        if raw is None:
            # Container v1 empacotado: a macro fica em data["macros"]
            # com a mesma estrutura interna do restante.
            macros = data.get("macros")
            if isinstance(macros, dict):
                raw = macros.get(name)
        if isinstance(raw, dict):
            # Wrapper do main legado: {name, events, created, count}.
            inner = raw.get("events")
            if isinstance(inner, list):
                return inner
            return None
        if isinstance(raw, list):
            return raw
        return None

    @staticmethod
    def _parse_events(entries: List[Any]) -> Optional[List[RecordedEvent]]:
        """Converte entradas JSON brutas em eventos canônicos.

        Tenta o schema v1 (entrada com `kind`) primeiro; entradas com
        `type`/`t` caem para o formato legado v0/web — o mesmo
        caminho do MacroStore, para que gravar e reproduzir concordem
        sobre o que um arquivo significa."""
        if not entries:
            return None
        first = entries[0]
        if isinstance(first, dict) and "kind" in first:
            events: List[RecordedEvent] = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                event = MacroRecorder._parse_v1_entry(entry)
                if event is None:
                    continue  # entrada inválida é pulada, não aborta
                events.append(event)
            return events if events else None
        return _macros_convert_legacy(entries)

    @staticmethod
    def _parse_v1_entry(entry: Dict[str, Any]) -> Optional[RecordedEvent]:
        """Entrada canônica v1 com tolerância de botão textual.

        `button` gravado como string ("left" etc.) é normalizado para
        o ID numérico X — compatibilidade com arquivos antigos; o
        formato corrente grava inteiro (issue #16). """
        kind_raw = entry.get("kind")
        if not isinstance(kind_raw, str):
            return None
        try:
            kind = EventType(kind_raw)
        except ValueError:
            return None
        button = _macros_button_id(entry.get("button", 0))
        if button is None:
            return None
        try:
            keycode = int(entry.get("keycode", 0))
            delta = float(entry.get("delta_ms", 0))
        except (TypeError, ValueError):
            return None
        if delta < 0:
            return None
        return RecordedEvent(kind=kind, button=button, keycode=keycode, delta_ms=delta)


def _macros_button_id(raw: Any) -> Optional[int]:
    """Normaliza o button de uma entrada de macro para o ID X (0..3).

    Aceita inteiro (contrato corrente), ponto-flutuante inteiro e o
    nome textual legado ("left"/"middle"/"right"). Inconvertível
    vira None — a entrada é então descartada sem travar o loader."""
    if isinstance(raw, int):
        return raw if raw in (0, 1, 2, 3) else None
    if isinstance(raw, float) and raw.is_integer() and int(raw) in (0, 1, 2, 3):
        return int(raw)
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if normalized in ("left", "middle", "right"):
            return MouseButton(normalized).button_id
        return None
    return None


def _macros_convert_legacy(entries: List[Any]) -> Optional[List[RecordedEvent]]:
    """Converte entradas do formato legado v0/web para canônicos.
    O legado usa timestamp absoluto `time`/`t` em SEGUNDOS e nomes
    de tipo distintos (key_press/mouse_click/mouse_move...); o delta
    relativo é reconstruído pela diferença de timestamps. Este é um
    subconjunto do _convert_legacy do store — apenas os tipos que
    o recorder/gravador original produz, para manter o contrato
    de leitura único entre componentes."""
    events: List[RecordedEvent] = []
    prev_t = 0.0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        kind_raw = entry.get("type") or entry.get("kind")
        if not isinstance(kind_raw, str):
            continue
        if kind_raw in ("mouse_down", "mouse_press", "click"):
            kind = EventType.MOUSE_PRESS
        elif kind_raw in ("mouse_up", "mouse_release"):
            kind = EventType.MOUSE_RELEASE
        elif kind_raw in ("key_press", "key"):
            kind = EventType.KEY_PRESS
        elif kind_raw in ("key_release",):
            kind = EventType.KEY_RELEASE
        elif kind_raw in ("mouse_move", "move"):
            kind = EventType.MOUSE_MOVE
        elif kind_raw == "mouse_click":
            # Clique completo legado: press + release imediato.
            kind = EventType.MOUSE_PRESS
        else:
            continue
        try:
            t_sec = float(entry.get("time", entry.get("t", 0)))
        except (TypeError, ValueError):
            continue
        button = _macros_button_id(entry.get("button", entry.get("click", 0)))
        if button is None:
            continue
        keycode_raw = entry.get("keycode")
        key_textual = entry.get("key")
        if isinstance(keycode_raw, int):
            keycode = keycode_raw
        elif isinstance(key_textual, str):
            keycode = _macros_textual_keycode(key_textual)
        else:
            keycode = 0
        delta_ms = max(0.0, (t_sec - prev_t) * 1000.0)
        prev_t = t_sec
        events.append(
            RecordedEvent(kind=kind, button=button, keycode=keycode, delta_ms=delta_ms)
        )
        if kind_raw == "mouse_click":
            events.append(
                RecordedEvent(kind=EventType.MOUSE_RELEASE, button=button, keycode=keycode, delta_ms=0.0)
            )
    return events if events else None


def _macros_textual_keycode(key: str) -> int:
    """Nome textual de tecla → keycode (fallback sem display X).

    Delega ao mesmo mapa determinístico do store — o mesmo nome
    precisa resolver para o mesmo keycode em gravação e reprodução."""
    from mouse_hub.core.automation.store import textual_key_to_keycode

    return textual_key_to_keycode(key)


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
