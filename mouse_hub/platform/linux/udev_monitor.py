"""Monitor de hotplug hidraw via netlink uevent (issue #67).

O app não pode depender de polling para saber se o G403 conectou ou
desconectou: o kernel publica um evento uevent (netlink) a cada add/
remove/change de dispositivo. Este módulo assina esses eventos em uma
thread dedicada e entrega apenas os de hidraw — orientado a evento,
custo zero quando nada acontece (recv bloqueante com timeout, sem giro
ocupado, sem varredura de /sys).

Sem dependências externas: socket AF_NETLINK cru (o mesmo mecanismo
que o libudev usa). Se o socket não estiver disponível (kernel sem
CONFIG_NETLINK? container?), o app segue funcionando sem hotplug —
fail soft, sem quebrar o resto.
"""

from __future__ import annotations

import queue
import socket
import threading
from typing import Optional, Tuple

# include/uapi/linux/netlink.h
NETLINK_KOBJECT_UEVENT = 15
# Grupo 1: uevents do kernel; grupo 2: eventos processados pelo udevd.
UDEV_GROUPS = 3

HidrawEvent = Tuple[str, str]
"""(ação, devpath) — ex.: ("add", "/devices/.../hidraw/hidraw2")."""

VALID_ACTIONS = frozenset({"add", "remove", "change", "bind", "unbind"})


def parse_uevent(payload: bytes) -> Optional[HidrawEvent]:
    """Extrai (ação, devpath) do cabeçalho de um datagrama uevent.

    Formato do kernel/libudev: b"add@/devices/...\\x00ACTION=add\\x00...".
    Retorna None para datagrama malformado (nunca levanta)."""
    if not payload:
        return None
    header = payload.split(b"\x00", 1)[0].decode("utf-8", "replace")
    action, sep, devpath = header.partition("@")
    if not sep or not action or not devpath:
        return None
    return (action, devpath)


def is_hidraw_event(event: Optional[HidrawEvent]) -> bool:
    """Filtra apenas add/remove/change/bind/unbind de nós hidraw.

    O devpath de um hidraw sempre contém ".../hidraw/hidrawN" — nem o
    HID_NAME nem eventos de outros subsystems passam aqui."""
    if event is None:
        return False
    action, devpath = event
    return action in VALID_ACTIONS and "/hidraw/" in devpath


def handle_datagram(data: bytes, out: "queue.Queue[HidrawEvent]") -> bool:
    """Processa um datagrama cru; enfileira se for evento de hidraw.

    Retorna True quando um evento foi enfileirado. Nunca levanta —
    datagrama podre é descartado, o monitor continua vivo."""
    try:
        event = parse_uevent(data)
        if not is_hidraw_event(event):
            return False
        out.put(event)
        return True
    except Exception:  # noqa: BLE001 — monitor nunca morre por payload
        return False


class UdevHidrawMonitor:
    """Assina uevents do kernel/udev e enfileira os de hidraw.

    * start(): cria o socket e a thread; idempotente;
    * stop(): sinaliza parada e fecha o socket; idempotente e
      seguro chamar sem start (closeEvent sempre chama);
    * a fila pertence a quem usa (desacoplado de Qt — a UI drena no
      timer dela, já na main thread)."""

    def __init__(
        self,
        out: "queue.Queue[HidrawEvent]",
        recv_timeout: float = 0.5,
        socket_factory=None,
    ) -> None:
        self._out = out
        self._recv_timeout = recv_timeout
        self._socket_factory = socket_factory or self._default_socket
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    @staticmethod
    def _default_socket() -> socket.socket:
        sock = socket.socket(
            socket.AF_NETLINK, socket.SOCK_DGRAM, NETLINK_KOBJECT_UEVENT
        )
        sock.bind((0, UDEV_GROUPS))
        return sock

    def start(self) -> bool:
        """Inicia o monitor. False quando o ambiente não suporta
        netlink (o app segue sem hotplug — degradação honesta)."""
        if self._thread is not None and self._thread.is_alive():
            return True
        try:
            self._sock = self._socket_factory()
            self._sock.settimeout(self._recv_timeout)
        except (OSError, AttributeError):
            self._sock = None
            return False
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="mouse-hub-udev-monitor", daemon=True
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            sock = self._sock
            if sock is None:
                break
            try:
                data = sock.recv(8192)
            except socket.timeout:
                continue
            except OSError:
                break  # socket fechado (stop) ou ambiente instável
            handle_datagram(data, self._out)


class HotplugDebouncer:
    """Converte rajadas de uevents em UM refresh.

    Plugar o mouse emite vários eventos em sequência (interfaces,
    change do udevd). Janela de silêncio: só dispara depois de
    `quiet_period` segundos SEM eventos novos (trailing edge). O relógio
    é injetado pelo caller (`now`), então o teste é determinístico."""

    def __init__(self, quiet_period: float = 0.4) -> None:
        self.quiet_period = quiet_period
        self._last_event_at: Optional[float] = None

    def event_received(self, now: float) -> None:
        """Registra chegada de evento; adia o disparo (burst)."""
        self._last_event_at = now

    def should_refresh(self, now: float) -> bool:
        """True uma única vez quando a janela de silêncio passou."""
        if self._last_event_at is None:
            return False
        if now - self._last_event_at < self.quiet_period:
            return False
        self._last_event_at = None  # consome: um burst = um refresh
        return True
