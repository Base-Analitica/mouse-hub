"""Fakes de hardware para a suíte de testes.

Permitem testar o core inteiro (descoberta, DPI, sensibilidade,
capabilities, controller) sem um G403 real, sem /dev/hidraw e sem
subprocess. Não há nenhum sucesso falso possível: cada fake registra
exatamente o que "aplicou" e sob quais condições falha.
"""

from __future__ import annotations

from typing import List, Optional

from mouse_hub.core.operation import OperationResult, OperationStatus
from mouse_hub.platform.protocol import HidAccess, MouseDevice, SystemInput


class FakeHidAccess(HidAccess):
    """HidAccess controlável em teste.

    write_succeeds determina se escritas são aceitas. opened_records
    guarda quais dispositivos foram abertos, permitindo verificar que
    o acessor só abriu o dispositivo confirmado pela descoberta.
    """

    def __init__(self) -> None:
        self.write_succeeds: bool = True
        self.device_required_for_write: bool = True
        self._opened: List[MouseDevice] = []
        self._device: Optional[MouseDevice] = None
        self.written_reports: List[bytes] = []

    def open(self, device: MouseDevice) -> OperationResult:
        self._opened.append(device)
        if device.hidraw_path is None:
            return OperationResult.device_not_found()
        if device.hidraw_path.startswith("/dev/permission_denied"):
            return OperationResult.permission_denied(device.hidraw_path)
        self._device = device
        return OperationResult.applied()

    def is_open(self) -> bool:
        return self._device is not None

    def read(self, length: int, timeout: float = 0.5) -> Optional[bytes]:
        return b"\x10\x00\x00\x00\x00\x00\x00" if self._device else None

    def write(self, report: bytes) -> OperationResult:
        if not self.is_open() and self.device_required_for_write:
            return OperationResult.failed("no open descriptor")
        self.written_reports.append(report)
        if self.write_succeeds:
            return OperationResult.applied()
        return OperationResult.failed("simulated hardware rejection")

    def close(self) -> None:
        self._device = None


class FakeSystemInput(SystemInput):
    """SystemInput controlável em teste.

    O apontador só é "encontrado" quando xinput_available é True e o
    nome procurado coincide com pointer_name. accel_state registra o
    último valor aplicado, e verify_after_write pode ser desligado para
    simular a falha de conferência pós-escrita.
    """

    def __init__(self) -> None:
        self.xinput_available: bool = True
        self.pointer_name: Optional[str] = "Logitech G403 HERO Gaming Mouse"
        self.accel_state: Optional[float] = None
        self.verify_after_write: bool = True
        self.set_succeeds: bool = True
        self.window_title: Optional[str] = None

    def is_available(self) -> bool:
        return self.xinput_available

    def find_pointer_id(self, mouse_name: str) -> Optional[int]:
        if not self.xinput_available:
            return None
        if self.pointer_name is None:
            return None
        if self.pointer_name.lower() not in mouse_name.lower():
            return None
        return 12

    def get_accel_speed(self, pointer_id: int) -> Optional[float]:
        if not self.xinput_available:
            return None
        if not self.verify_after_write:
            return None
        return self.accel_state if self.accel_state is not None else 0.0

    def set_accel_speed(self, pointer_id: int, accel: float) -> OperationResult:
        if not self.xinput_available:
            return OperationResult.unsupported()
        if not self.set_succeeds:
            return OperationResult.failed("xinput simulated failure")
        self.accel_state = accel
        if not self.verify_after_write:
            return OperationResult.failed("value could not be verified")
        return OperationResult.applied()

    def active_window_title(self) -> Optional[str]:
        return self.window_title


def fake_g403_device(hidraw: Optional[str] = "/dev/hidraw2") -> MouseDevice:
    from mouse_hub.core.constants import G403_PID, G403_VID

    return MouseDevice(
        hidraw_path=hidraw,
        vid=G403_VID,
        pid=G403_PID,
        name="Logitech G403 HERO Gaming Mouse",
    )
