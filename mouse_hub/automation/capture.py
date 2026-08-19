"""Captura real de eventos de teclado e mouse durante a gravação de macros.

Lifecycle explícito:

    cap = InputCapture(sink=callback)
    cap.start()     # abre conexão X, cria contexto XRecord, thread rodando
    # ... eventos chegam via sink(MacroEvent) com relógio monotônico ...
    cap.stop()      # sinaliza parada, desabilita contexto
    cap.cleanup()   # aguarda thread, fecha conexão — nada fica preso

O capturador usa XRecord com AllClients, então teclas e cliques são
capturados independentemente da janela ativa — comportamento esperado de
um gravador de macros.

Nomes de tecla são resolvidos via `Xlib.XK.string_to_keysym` (grupos
latin1/miscellany), produzindo nomes compatíveis com `xdotool key`
(ex.: "KP_Add", "Return", "F5", "space").

Dependência: python-xlib (já listada no README do projeto). Nenhuma
dependência nova.
"""

import enum
import threading
import time

from Xlib import XK, X

from .events import MacroEvent


class CaptureState(enum.Enum):
    IDLE = "idle"
    ACTIVE = "active"
    STOPPED = "stopped"
    FAILED = "failed"


def _init_keysym_cache():
    XK.load_keysym_group("latin1")
    XK.load_keysym_group("miscellany")


_init_keysym_cache()


def _keysym_to_name(keysym):
    """Keysym -> nome de tecla compatível com xdotool key."""
    name = XK.keysym_to_string(keysym)
    if name and name.isprintable() and len(name) == 1:
        # caractere simples: gravar o caractere em si (xdotool key aceita)
        return name
    if name:
        return name
    return f"keysym_0x{keysym:x}"


class InputCapture:
    """Capturador de input via XRecord (python-xlib)."""

    def __init__(self, sink, display_name=None):
        """
        sink(event): chamado na thread de captura para cada evento capturado.
            event = MacroEvent com t em segundos monotônicos desde start().
        display_name: display X (None = $DISPLAY padrão).
        """
        self._sink = sink
        self._display_name = display_name
        self._state = CaptureState.IDLE
        self._lock = threading.Lock()
        self._thread = None
        self._stop_event = threading.Event()
        self._dpy_ctl = None
        self._dpy_data = None
        self._t0 = 0.0
        self._failed_reason = None

    @property
    def state(self):
        return self._state

    @property
    def failed_reason(self):
        return self._failed_reason

    def start(self):
        """Inicia captura. Idiopetente (nada faz se já ativo)."""
        with self._lock:
            if self._state in (CaptureState.ACTIVE, CaptureState.STOPPED):
                return
            self._state = CaptureState.ACTIVE
            self._failed_reason = None
            self._stop_event.clear()
            self._t0 = time.monotonic()
            self._thread = threading.Thread(
                target=self._run, name="input-capture", daemon=True)
            self._thread.start()

    def stop(self):
        """Sinaliza parada do capturador. Não bloqueia."""
        with self._lock:
            if self._state != CaptureState.ACTIVE:
                return
            self._state = CaptureState.STOPPED
        self._stop_event.set()
        # Desabilitar o contexto força EndOfData na data connection e
        # destrava o record_enable_context.
        try:
            if self._dpy_ctl is not None:
                try:
                    self._dpy_ctl.record_disable_context(self._ctx_id)
                except Exception:
                    pass
                try:
                    self._dpy_ctl.record_free_context(self._ctx_id)
                except Exception:
                    pass
                try:
                    self._dpy_ctl.close()
                except Exception:
                    pass
        finally:
            self._dpy_ctl = None
            self._dpy_data = None

    def cleanup(self):
        """Aguarda a thread morrer e libera recursos. Chamar sempre ao fim.
        Idiempotente."""
        self.stop()
        if self._thread is not None:
            self._thread.join(timeout=3)
        self._thread = None
        with self._lock:
            if self._state == CaptureState.ACTIVE:
                self._state = CaptureState.IDLE

    def _run(self):
        """Thread de captura XRecord. Qualquer exceção vira FAILED."""
        try:
            from Xlib import display as xdisplay
            from Xlib.ext import record as xrecord

            self._dpy_ctl = xdisplay.Display(self._display_name)
            self._dpy_data = xdisplay.Display(self._display_name)

            if not self._dpy_ctl.has_extension(xrecord):
                raise RuntimeError(
                    "extensão XRecord não disponível neste servidor X")

            ctx = self._dpy_ctl.record_create_context(
                0,
                [xrecord.AllClients],
                [{
                    "core_requests": (0, 0),
                    "core_replies": (0, 0),
                    "ext_requests": (0, 0, 0, 0),
                    "ext_replies": (0, 0, 0, 0),
                    "delivered_events": (0, 0),
                    "device_events": (X.KeyPress, X.ButtonRelease),
                    "errors": (0, 0),
                    "client_started": False,
                    "client_died": False,
                }])
            self._ctx_id = ctx

            self._dpy_data.record_enable_context(ctx, self._handle_event)
            # bloqueia até EndOfData (nossa chamada de stop)
            self._dpy_data.record_free_context(ctx)
        except Exception as exc:
            with self._lock:
                self._failed_reason = str(exc)
                self._state = CaptureState.FAILED
            self._stop_event.set()

    def _handle_event(self, reply):
        """Callback do XRecord, executado na thread da data connection."""
        if reply.category != xrecord.FromServer:
            return
        if reply.client_swapped:
            return
        if not len(reply.data):
            return

        data = reply.data
        while data:
            event, data = xdisplay.Display.parse_event(data)
            kind = getattr(event, "type", None)

            t = time.monotonic() - self._t0
            if kind == X.KeyPress:
                name = _keysym_to_name(event.detail)
                self._sink(MacroEvent(t, "key_down", key=name))
            elif kind == X.KeyRelease:
                name = _keysym_to_name(event.detail)
                self._sink(MacroEvent(t, "key_up", key=name))
            elif kind == X.ButtonPress:
                self._sink(MacroEvent(t, "mouse_down", button=event.detail))
            elif kind == X.ButtonRelease:
                self._sink(MacroEvent(t, "mouse_up", button=event.detail))
            # Movimento do ponteiro não é gravado: posição absoluta gravada
            # por amostra não reproduz de forma confiável e o README prometido
            # cobre "teclas e cliques com timing preciso". O modelo continua
            # suportando mouse_move caso um capturador futuro o envie.
