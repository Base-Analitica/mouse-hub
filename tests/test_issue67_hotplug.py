"""Issue #67 — hotplug: plug/desplug reflete na UI em tempo real.

Antes: o app só re-avaliava hardware em startup/showEvent/operação —
desconectar mantinha "Online" mentiroso e conectar não acordava a UI.
Agora: monitor de uevents (netlink, orientado a evento, sem polling)
+ debounce de rajada + refresh de capacidades na main thread.

Todos os testes são determinísticos: datagramas sintéticos, relógio
injetado no debounce e socket falso no monitor. Nada toca /sys real."""

from __future__ import annotations

import queue
import socket

import pytest

from mouse_hub.platform.linux.udev_monitor import (
    HotplugDebouncer,
    UdevHidrawMonitor,
    handle_datagram,
    is_hidraw_event,
    parse_uevent,
)

ADD_G403 = (
    b"add@/devices/pci0000:00/0000:00:14.0/usb1/1-2/1-2:1.1/"
    b"0003:046D:C08F.0004/hidraw/hidraw2\x00ACTION=add\x00"
    b"SUBSYSTEM=hidraw\x00DEVNAME=hidraw2\x00SEQNUM=1234\x00"
)
REMOVE_G403 = (
    b"remove@/devices/pci0000:00/0000:00:14.0/usb1/1-2/1-2:1.1/"
    b"0003:046D:C08F.0004/hidraw/hidraw2\x00ACTION=remove\x00"
    b"SUBSYSTEM=hidraw\x00DEVNAME=hidraw2\x00"
)


# ── parse / filtro ───────────────────────────────────────────

def test_parse_uevent_extrai_acao_e_devpath():
    assert parse_uevent(ADD_G403) == (
        "add",
        "/devices/pci0000:00/0000:00:14.0/usb1/1-2/1-2:1.1/"
        "0003:046D:C08F.0004/hidraw/hidraw2",
    )


@pytest.mark.parametrize("payload", [b"", b"sem-arroba", b"\x00\x00", b"a@"],
                         ids=["vazio", "sem-arroba", "só-nulos", "devpath-vazio"])
def test_parse_uevent_malformado_retorna_none(payload):
    assert parse_uevent(payload) is None


def test_hidraw_add_e_remove_passam():
    assert is_hidraw_event(parse_uevent(ADD_G403))
    assert is_hidraw_event(parse_uevent(REMOVE_G403))


@pytest.mark.parametrize("payload", [
    b"change@/devices/.../block/sda\x00ACTION=change\x00",   # outro subsystem
    b"add@/devices/.../usb1/1-2\x00ACTION=add\x00",          # usb sem hidraw
    b"HID_NAME=Logitech G403 hidraw@/devices/x\x00",          # nome contém, path não
], ids=["block", "usb-puro", "nome-contem-hidraw"])
def test_eventos_que_nao_sao_hidraw_sao_filtrados(payload):
    assert not is_hidraw_event(parse_uevent(payload))


def test_handle_datagram_enfileira_hidraw_e_descarta_o_resto():
    q = queue.Queue()
    assert handle_datagram(ADD_G403, q) is True
    assert handle_datagram(b"lixo\x00", q) is False
    assert handle_datagram(b"change@/x/block/sdb\x00", q) is False
    assert q.get_nowait() == parse_uevent(ADD_G403)
    assert q.empty()


# ── debounce: rajada de plug vira UM refresh ─────────────────

def test_debounce_dispara_somente_apos_janela_de_silencio():
    d = HotplugDebouncer(quiet_period=0.4)
    assert not d.should_refresh(0.0)          # sem eventos
    d.event_received(0.0)
    assert not d.should_refresh(0.2)          # dentro da janela
    d.event_received(0.3)                     # evento novo adia (burst)
    assert not d.should_refresh(0.5)
    assert d.should_refresh(0.71)             # 0.3 + 0.4 passou
    assert not d.should_refresh(0.72)         # consome: um burst = um refresh
    d.event_received(1.0)                     # próximo evento dispara de novo
    assert d.should_refresh(1.5)


# ── thread do monitor com socket falso ───────────────────────

class FakeSocket:
    """Entrega datagramas pré-carregados e depois fica em timeout até
    ser fechado — mesma semântica do netlink real para o loop."""

    def __init__(self, datagrams):
        self._datagrams = list(datagrams)
        self.closed = False

    def settimeout(self, value):
        self._timeout = value

    def recv(self, size):
        if self.closed:
            raise OSError("closed")
        if self._datagrams:
            return self._datagrams.pop(0)
        raise socket.timeout

    def close(self):
        self.closed = True


def test_monitor_entrega_eventos_e_para_limpo():
    q = queue.Queue()
    sock = FakeSocket([ADD_G403, b"change@/x/block/sda\x00", REMOVE_G403])
    monitor = UdevHidrawMonitor(q, recv_timeout=0.05,
                                socket_factory=lambda: sock)
    assert monitor.start() is True
    events = []
    import time as _time
    deadline = _time.monotonic() + 2.0
    while len(events) < 2 and _time.monotonic() < deadline:
        try:
            events.append(q.get(timeout=0.1))
        except queue.Empty:
            pass
    monitor.stop()
    assert monitor._thread is None or not monitor._thread.is_alive()
    assert events == [
        ("add", parse_uevent(ADD_G403)[1]),
        ("remove", parse_uevent(REMOVE_G403)[1]),
    ]  # o change de block foi filtrado


def test_monitor_stop_sem_start_e_idempotente():
    q = queue.Queue()
    monitor = UdevHidrawMonitor(q)
    monitor.stop()  # nunca levanta
    monitor.stop()


def test_monitor_sem_netlink_degrada_sem_quebrar():
    def factory_fail():
        raise OSError("netlink indisponível")

    q = queue.Queue()
    monitor = UdevHidrawMonitor(q, socket_factory=factory_fail)
    assert monitor.start() is False  # app segue funcionando sem hotplug
    monitor.stop()


def test_monitor_start_duplo_nao_duplica_thread():
    q = queue.Queue()
    sock = FakeSocket([])
    monitor = UdevHidrawMonitor(q, recv_timeout=0.05,
                                socket_factory=lambda: sock)
    assert monitor.start() is True
    try:
        thread = monitor._thread
        assert monitor.start() is True
        assert monitor._thread is thread
    finally:
        monitor.stop()


# ── integração com a janela (offscreen, monitor falso) ───────

@pytest.fixture(scope="module")
def qapp():
    os_offscreen = __import__("os").environ
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_window_hotplug_plug_e_desplug_atualizam_sidebar(qapp, monkeypatch):
    """E2E determinístico da janela: evento na fila → refresh único →
    sidebar acorda (Offline → Detectado → Offline)."""
    from app import mouse_hub_app as app_module
    from tests.fakes import FakeHidAccess, FakeSystemInput
    from mouse_hub.core.mouse_controller import MouseController
    from mouse_hub.core.config import ConfigPaths
    from mouse_hub.core.dpi_persistence import NeverDpiPersister

    class DummyMonitor:
        started = False
        stopped = False

        def __init__(self, out):
            DummyMonitor.started = True

        def start(self):
            DummyMonitor.started = True
            return True

        def stop(self):
            DummyMonitor.stopped = True

    monkeypatch.setattr(app_module, "UdevHidrawMonitor", DummyMonitor)

    def make_state():
        core = MouseController(
            hid=FakeHidAccess(),
            system_input=FakeSystemInput(),
            dpi_persister=NeverDpiPersister(),
        )
        return app_module.MouseCoreState(core)

    monkeypatch.setattr(app_module, "build_mouse_state", make_state)

    w = app_module.MouseHubApp()
    try:
        assert DummyMonitor.started
        assert w._status_text.text() == "Offline"

        discoveries = iter(
            [[fake] for fake in (None,)]  # placeholder, substituído abaixo
        )
        from tests.fakes import fake_g403_device
        with_g403 = [fake_g403_device()]
        monkeypatch.setattr(app_module, "discover_candidates",
                            lambda: list(with_g403))

        w._hotplug_queue.put(("add", "/devices/x/hidraw/hidraw2"))
        w._poll_hotplug(now=0.0)
        w._poll_hotplug(now=0.5)
        # o FakeHidAccess responde ao probe completo → plug = Online
        # (com hardware real sem regra udev seria "Detectado")
        assert w._status_text.text() == "Online"

        monkeypatch.setattr(app_module, "discover_candidates", lambda: [])
        w._hotplug_queue.put(("remove", "/devices/x/hidraw/hidraw2"))
        w._poll_hotplug(now=10.0)
        w._poll_hotplug(now=10.5)
        assert w._status_text.text() == "Offline"

        # rajada: N eventos → UM refresh
        refreshes = {"n": 0}
        orig = w.mouse_state.refresh

        def counting():
            refreshes["n"] += 1
            orig()

        w.mouse_state.refresh = counting
        for i in range(5):
            w._hotplug_queue.put(("change", "/devices/x/hidraw/hidraw2"))
        w._poll_hotplug(now=20.0)   # drena a rajada
        w._poll_hotplug(now=20.2)   # dentro da janela de silêncio
        w._poll_hotplug(now=20.3)   # ainda dentro
        assert refreshes["n"] == 0
        w._poll_hotplug(now=20.5)   # silêncio completou → UM refresh
        assert refreshes["n"] == 1
        w._poll_hotplug(now=30.0)   # sem eventos novos → nada
        assert refreshes["n"] == 1
    finally:
        w.close()
    assert DummyMonitor.stopped
