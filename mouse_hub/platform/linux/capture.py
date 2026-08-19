"""Captura de eventos de input via XRecord — lifecycle correto.

A gravação de macros observa os eventos da sessão X inteira (nada de
polling): cada evento relevante chega ao listener registrado no
contexto XRecord e é entregue ao handler do gravador por callback.

Contrato de lifecycle desta implementação (corrigido em relação à
versão anterior, que marcava a flag de gravação e nunca preenchia
eventos, e cuja parada fechava displays antes de o worker terminar):

* `start()` cria o contexto XRecord, inicia o worker que habilita o
  contexto (bloqueante — o callback é chamado enquanto ativo) e
  aguarda o handshake `_ready` (pronto ou falha) — a UI sabe exatamente
  quando a gravação está ativa;
* o handshake só é declarado pronto quando o worker já determinou
  chamar `enable_context` — o sinal de prontidão é disparado
  imediatamente ANTES da chamada (mesma thread, instrução seguinte:
  não há janela entre "recording" e o listener ativo); anunciar depois
  de a chamada retornar é impossível em produção, pois
  `record_enable_context` é bloqueante até a parada;
* o callback preserva o **keycode** X verdadeiro (`event.detail`) e
  o tipo real do evento (KeyPress/KeyRelease/ButtonPress/
  ButtonRelease/MotionNotify), sem colapsar press em release;
* deltas são calculados contra `time.monotonic()` e normalizados para
  o primeiro evento ter delta 0;
* `stop()` desabilita o contexto (o callback para de ser chamado),
  aguarda o worker encerrar com `join`, fecha displays e o contexto
  exatamente uma vez, e só então libera o estado — o handler nunca
  recebe evento de gravação depois de `stop()`;
* `cancel()` aborta imediatamente e descarta eventos acumulados;
* tudo idempotente e thread-safe (estado sob lock).

Testável sem display real: as primitivas XRecord/XDisplay são
injetáveis (`XRecordBackend`), e os testes montam um backend fake
determinístico que simula a ordem callback→desabilitar→stop.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from Xlib import X
from Xlib.display import Display
from Xlib.ext import record as xrecord

from mouse_hub.core.automation.types import EventType, RecordedEvent

MAX_EVENTS = 100_000  # teto defensivo — um worker que acumula em lista


@dataclass(frozen=True)
class XRecordHandles:
    """Handles X que o lifecycle controla — um por contexto de gravação."""

    ctl_display: Display
    data_display: Display
    ctx: int


class XRecordBackend:
    """Abstração testável das primitivas XRecord/XDisplay.

    Produção: `default_backend()` retorna implementações reais que
    abrem os displays e criam o contexto com todos os clients e a
    máscara completa de device_events (KeyPress..ButtonRelease).
    Teste: um backend fake injeta eventos simulados e verifica que a
    parada desabilita o contexto antes de fechar os displays.
    """

    def open_display(self) -> Display:
        return Display()

    def create_context(
        self, ctx_spec: int, data_display: Display, ctl_display: Display, callback: Callable
    ) -> int:
        return ctl_display.record_create_context(
            0,
            [xrecord.AllClients],
            [
                {
                    "core_requests": (0, 0),
                    "core_replies": (0, 0),
                    "ext_requests": (0, 0),
                    "ext_replies": (0, 0),
                    "delivered_events": (0, 0),
                    "device_events": (X.KeyPress, X.ButtonRelease),
                    "errors": (0, 0),
                    "client_started": False,
                    "client_died": False,
                }
            ],
        )

    def enable_context(
        self, ctx: int, data_display: Display, ctl_display: Display, callback: Callable
    ) -> None:
        # `record_enable_context` é bloqueante: o callback é invocado
        # continuamente enquanto o contexto estiver ativo e só retorna
        # quando disable_context é chamado (o worker fica preso aqui).
        ctl_display.record_enable_context(ctx, callback)

    def disable_context(self, ctx: int, ctl_display: Display) -> None:
        ctl_display.record_disable_context(ctx)

    def free_context(self, ctx: int, ctl_display: Display) -> None:
        ctl_display.record_free_context(ctx)

    def close_display(self, display: Display) -> None:
        display.close()


def default_backend() -> XRecordBackend:
    return XRecordBackend()


# Mapas de evento X -> tipo de macro, preservando X.KeyPress/X.Release
# distintos (gravação press/release real para playback nativo XTest).
_EVENT_KIND = {
    X.KeyPress: EventType.KEY_PRESS,
    X.KeyRelease: EventType.KEY_RELEASE,
    X.ButtonPress: EventType.MOUSE_PRESS,
    X.ButtonRelease: EventType.MOUSE_RELEASE,
    X.MotionNotify: EventType.MOUSE_MOVE,
}


class InputCapture:
    """Capturador XRecord com lifecycle completo e handshake de prontidão.

    Uso:

        capture = InputCapture(on_event)
        if not capture.start():        # aguarda ready ou falha
            print(capture.failure)     # motivo detectado
        # ... usuário grava ...
        events = capture.stop()        # snapshot + cleanup
        # ou capture.cancel() para descartar e abortar
    """

    def __init__(
        self,
        on_event: Callable[[RecordedEvent], None],
        backend: Optional[XRecordBackend] = None,
    ) -> None:
        self._on_event = on_event
        self._backend = backend or default_backend()

        self._lock = threading.Lock()
        self._state = "idle"  # idle | starting | recording | stopping | stopped
        self._failure: Optional[str] = None

        self._handles: Optional[XRecordHandles] = None
        self._worker: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._stop_event = threading.Event()

        self._start_mono: float = 0.0
        self._last_at: float = 0.0
        self._count: int = 0

    # ── Estado ─────────────────────────────────────────────────────

    @property
    def recording(self) -> bool:
        with self._lock:
            return self._state == "recording"

    @property
    def failure(self) -> Optional[str]:
        with self._lock:
            return self._failure

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    # ── Lifecycle ──────────────────────────────────────────────────

    def start(self) -> bool:
        """Inicia a captura e aguarda o handshake de prontidão.

        Retorna True quando o listener XRecord está registrado e o
        worker está processando eventos. Em caso de falha (display
        indisponível, extensão XRecord ausente, erro de criação do
        contexto), registra o motivo em `failure` e retorna False —
        sem lançar exceção para a UI.
        """
        with self._lock:
            if self._state == "recording":
                return True
            if self._state not in ("idle", "stopped"):
                return False
            self._state = "starting"
            self._failure = None
            self._ready.clear()
            self._stop_event.clear()

        try:
            ctl = self._backend.open_display()
            data = self._backend.open_display()
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._state = "stopped"
                self._failure = f"display indisponível: {exc}"
            self._ready.set()
            return False

        try:
            ctx = self._backend.create_context(0, data, ctl, self._dispatch)
        except Exception as exc:  # noqa: BLE001
            for display in (data, ctl):
                try:
                    self._backend.close_display(display)
                except Exception:  # noqa: BLE001
                    pass
            with self._lock:
                self._state = "stopped"
                self._failure = f"XRecord indisponível: {exc}"
            self._ready.set()
            return False

        with self._lock:
            self._handles = XRecordHandles(ctl_display=ctl, data_display=data, ctx=ctx)
            self._start_mono = time.monotonic()
            self._last_at = 0.0
            self._count = 0

        self._worker = threading.Thread(
            target=self._run,
            name="mouse-hub-input-capture",
            daemon=True,
        )
        self._worker.start()

        # Handshake: aguarda o worker anunciar pronto ou falhar.
        self._ready.wait(timeout=5.0)
        with self._lock:
            ok = self._state == "recording"
        if not ok:
            # worker falhou ao habilitar/processar — motivo já em failure
            self._cleanup_handles()
        return ok

    def stop(self) -> int:
        """Encerra a captura de forma limpa: desabilita o contexto,
        aguarda o worker (que só sai quando o callback parar), fecha
        recursos exatamente uma vez, e retorna o número de eventos
        gravados. Após o return, o handler nunca mais recebe evento.
        """
        with self._lock:
            if self._state != "recording":
                return self._count
            self._state = "stopping"
            handles = self._handles
            self._handles = None

        if handles is not None:
            try:
                self._backend.disable_context(handles.ctx, handles.ctl_display)
            except Exception:  # noqa: BLE001 — display pode já ter caído
                pass

        self._stop_event.set()
        worker = self._worker
        if worker is not None:
            worker.join(timeout=2.0)

        # Snapshot final: o worker só saiu do enable_context (callback
        # parou de ser chamado), então o contador acumulado até aqui é
        # definitivo — nenhum evento da gravação é perdido entre a
        # parada e o retorno.
        with self._lock:
            count = self._count

        # Os handles foram zerados ANTES do disable (acima) — passamos
        # explicitamente para o cleanup, caso contrário free_context
        # nunca seria chamado (Idempotência do lifecycle).
        self._cleanup_handles(handles)

        with self._lock:
            self._state = "stopped"
            self._worker = None
        return count

    def cancel(self) -> None:
        """Aborta imediatamente e descarta tudo o que foi gravado."""
        with self._lock:
            was_recording = self._state == "recording"
        if not was_recording:
            return
        self.stop()
        with self._lock:
            self._count = 0

    def _cleanup_handles(self, handles: Optional[XRecordHandles] = None) -> None:
        """Fecha displays e contexto exatamente uma vez (idempotente).

        Quando `handles` é passado, eles são fechados diretamente
        (usado por `stop()`, que já zerou `self._handles`); caso
        contrário, busca e zera `self._handles` sob lock (usado por
        falhas de `start()` e chamadas diretas).
        """
        if handles is None:
            with self._lock:
                handles = self._handles
                self._handles = None
        if handles is None:
            return
        try:
            self._backend.free_context(handles.ctl_display, handles.ctx)
        except Exception:  # noqa: BLE001
            pass
        for display in (handles.data_display, handles.ctl_display):
            try:
                self._backend.close_display(display)
            except Exception:  # noqa: BLE001
                pass

    # ── Worker ─────────────────────────────────────────────────────

    def _run(self) -> None:
        handles = self._handles
        if handles is None:
            self._fail("contexto não criado")
            return
        try:
            # O handshake é declarado pronto IMEDIATAMENTE antes de
            # `enable_context`: mesma thread, instrução seguinte — não
            # existe janela em que a UI veja "recording" sem o listener
            # a caminho. (Sinalizar depois de a chamada retornar é
            # inviável: em produção `record_enable_context` bloqueia
            # até a parada, e sinalizar apenas no retorno tornaria
            # `start()` síncrono com toda a gravação.)
            with self._lock:
                if self._state == "starting":
                    self._state = "recording"
            self._ready.set()
            self._backend.enable_context(
                handles.ctx, handles.data_display, handles.ctl_display, self._dispatch
            )
        except Exception as exc:  # noqa: BLE001
            self._fail(f"erro ao habilitar contexto: {exc}")
            return

        # Aguarda a parada (contexto desabilitado). O enable_context
        # já voltou acima; a espera aqui cobre o intervalo entre
        # ready e o stop_event (e é o ponto onde o worker termina).
        self._stop_event.wait()

    # ── Dispatch / handler ─────────────────────────────────────────

    def _dispatch(self, data) -> None:
        """Callback do XRecord, chamado na thread do enable_context.

        A verificação de `recording` sob lock garante que nenhum evento
        é entregue ao handler depois de `stop()` (o disable_context
        para de chamar este callback, e o estado transita antes).
        """
        if not self.recording:
            return
        if getattr(data, "category", None) != xrecord.FromServer:
            return
        events = getattr(data, "data", None)
        if not events:
            return

        local_start = self._start_mono
        with self._lock:
            now_base = time.monotonic() - local_start
            if self._count == 0:
                last_at = 0.0
            else:
                last_at = self._last_at
            for event in events:
                payload = self._classify(event)
                if payload is None:
                    continue
                if self._count >= MAX_EVENTS:
                    break
                now = time.monotonic() - local_start
                delta_ms = 0.0 if self._count == 0 else (now - last_at) * 1000.0
                self._last_at = now
                self._count += 1
                last_at = now
                recorded = RecordedEvent(
                    kind=EventType(payload["kind"]),
                    button=int(payload.get("button", 0)),
                    keycode=int(payload.get("keycode", 0)),
                    delta_ms=max(0.0, delta_ms),
                )
                self._on_event(recorded)

    @staticmethod
    def _classify(event) -> Optional[dict]:
        kind = _EVENT_KIND.get(event.type)
        if kind is None:
            return None
        if kind in (EventType.KEY_PRESS, EventType.KEY_RELEASE):
            return {"kind": kind, "keycode": int(event.detail), "button": 0}
        if kind == EventType.MOUSE_MOVE:
            return {
                "kind": kind,
                "keycode": int(event.root_x),
                "button": int(event.root_y),
            }
        # botão 1/2/3 conforme protocolo X
        return {"kind": kind, "button": int(event.detail), "keycode": 0}

    def _fail(self, reason: str) -> None:
        """Registra falha enquanto ainda está no handshake.

        `starting`: falha antes do handshake (`start()` devolve False).
        `recording`: falha pós-handshake (ex.: `enable_context` bloqueia
        e estoura) — também vira stopped com `.failure` definido; o
        `_ready` já foi disparado e `start()` lê o estado final.
        """
        with self._lock:
            if self._state not in ("starting", "recording"):
                return
            self._state = "stopped"
            self._failure = reason
        self._ready.set()
