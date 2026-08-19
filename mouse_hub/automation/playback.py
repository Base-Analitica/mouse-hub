"""Reprodução de macros.

Características:

- Timing com relógio monotônico (nunca depende de horário civil)
- Respeita o `repeat` da macro
- Término limpo: stop() faz a thread corrente encerrar na próxima
  barreira de evento, sem matar a thread bruscamente
- Não bloqueia a thread principal da UI (roda em worker próprio)
- Não cria threads órfãs: cada PlaybackController mantém no máximo uma
  thread de execução, com join em stop/cleanup
- Estado real retornável: stopped | running | failed

O backend de execução de eventos é injetável (ClickKeyBackend). O default
usa subprocess xdotool (stack atual do projeto); testes usam um fake.
"""

import enum
import subprocess
import threading
import time

from .events import Macro


class PlaybackState(enum.Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    BLOCKED = "blocked"
    FAILED = "failed"


class PlaybackError(RuntimeError):
    """Playback não pôde iniciar ou falhou durante execução."""


class ClickKeyBackend:
    """Backend default: xdotool (mesmo stack do projeto hoje)."""

    def send_event(self, ev):
        if ev.type == "key_down":
            subprocess.run(["xdotool", "key", ev.key],
                           capture_output=True, timeout=2, check=True)
        elif ev.type == "key_up":
            pass  # xdotool key já faz press+release
        elif ev.type == "mouse_down":
            subprocess.run(["xdotool", "click", str(ev.button)],
                           capture_output=True, timeout=2, check=True)
        elif ev.type == "mouse_up":
            pass
        elif ev.type == "mouse_move":
            subprocess.run(["xdotool", "mousemove", str(ev.x), str(ev.y)],
                           capture_output=True, timeout=2, check=True)
        else:
            raise PlaybackError(f"tipo de evento não suportado: {ev.type}")


class PlaybackController:
    """Controla a execução de uma macro.

    Uso:
        ctl = PlaybackController(store)
        ok = ctl.start(name, repeat=3)      # valida e inicia worker
        state = ctl.state                   # stopped|running|blocked|failed
        ctl.stop()                          # término limpo
        ctl.cleanup()                       # aguarda worker morrer
    """

    def __init__(self, store, backend=None):
        self._store = store
        self._backend = backend or ClickKeyBackend()
        self._lock = threading.Lock()
        self._thread = None
        self._state = PlaybackState.STOPPED
        self._stop_event = threading.Event()
        self._error = None
        self._macro = None

    @property
    def state(self):
        return self._state

    @property
    def error(self):
        return self._error

    def start(self, name, repeat=None):
        """Inicia reprodução. Valida a macro antes de prometer sucesso.
        Retorna True se o worker foi iniciado."""
        macro = self._store.get(name)
        if macro is None:
            self._state = PlaybackState.STOPPED
            self._error = f"macro inexistente: {name}"
            return False
        if not macro.events:
            self._state = PlaybackState.STOPPED
            self._error = f"macro vazia: {name}"
            return False

        with self._lock:
            if self._state == PlaybackState.RUNNING:
                # playback já em andamento: iniciar de novo é no-op bloqueado
                return False
            self._macro = macro
            self._stop_event.clear()
            self._error = None
            self._state = PlaybackState.RUNNING
            self._thread = threading.Thread(
                target=self._run, args=(macro, repeat),
                name=f"macro-playback:{name}", daemon=True)
            self._thread.start()
        return True

    def stop(self):
        """Término limpo: sinaliza e aguarda a thread corrente."""
        self._stop_event.set()
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout=3)

    def cleanup(self):
        """Garante que o worker morreu. Idiempotente."""
        self.stop()
        with self._lock:
            self._thread = None
            if self._state == PlaybackState.RUNNING:
                self._state = PlaybackState.STOPPED

    def _run(self, macro, repeat_override):
        """Worker de reprodução com timing monotônico."""
        try:
            repeat = repeat_override if repeat_override is not None else macro.repeat
            for _ in range(max(1, repeat)):
                if self._stop_event.is_set():
                    break
                t_prev = 0.0
                t0 = time.monotonic()  # origem do tempo deste passe
                interrupted = False
                for ev in macro.events:
                    if self._stop_event.is_set():
                        interrupted = True
                        break
                    target = ev.t  # tempo alvo desde o início do passe
                    deadline = t0 + target
                    while time.monotonic() < deadline:
                        if self._stop_event.wait(
                                min(0.05, max(0.0, deadline - time.monotonic()))):
                            interrupted = True
                            break
                        if time.monotonic() >= deadline:
                            break
                    if interrupted:
                        break
                    t_prev = ev.t
                    self._backend.send_event(ev)
                if interrupted:
                    break
        except PlaybackError as exc:
            self._error = str(exc)
            with self._lock:
                self._state = PlaybackState.FAILED
            return
        except Exception as exc:
            self._error = str(exc)
            with self._lock:
                self._state = PlaybackState.FAILED
            return
        # parada solicitada por stop() ou repetições concluídas — sempre
        # deixa o estado consistente (o worker nunca sai sem marcar)
        with self._lock:
            if self._state == PlaybackState.RUNNING:
                self._state = PlaybackState.STOPPED
