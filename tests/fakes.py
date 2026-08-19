"""Fakes de hardware para a suíte de testes.

Permitem testar o core inteiro (descoberta, DPI, sensibilidade,
capabilities, controller) sem um G403 real, sem /dev/hidraw e sem
subprocess. Não há nenhum sucesso falso possível: cada fake registra
exatamente o que "aplicou" e sob quais condições falha.

O FakeHidAccess modela o protocolo HID++ 2.0 na extensão mínima que o
core exige: feature tables, set de DPI e respostas (ACK, erro 0x8F,
readback). As constantes de report ID seguem a convenção do HID++ 2.0
(curto 0x10, longo 0x11; device index 0xFF).
"""

from __future__ import annotations

from typing import List, Optional

from mouse_hub.core.operation import OperationResult
from mouse_hub.platform.protocol import HidAccess, MouseDevice, SystemInput


def _parse_hidpp_header(report: bytes) -> Optional[tuple[int, int]]:
    """Retorna (report_id, feature_index) de um report HID++ 2.0."""
    if len(report) < 3:
        return None
    report_id = report[0]
    # Report curto (0x10): [report_id][feature_index][fn][params...]
    # Report longo (0x11): [report_id][sw_id][feature_index][fn][params...]
    if report_id == 0x10:
        return report_id, report[1]
    if report_id == 0x11:
        return report_id, report[2]
    return None


class FakeHidAccess(HidAccess):
    """HidAccess controlável em teste, com modelo de protocolo HID++ 2.0.

    Permite simular os modos de confirmação que o core exige:
    * probe_responses: respostas que o endpoint devolve ao probe
      GET_FEATURE_TABLE_COUNT (report longo, feature 0x00, fn 0x00) —
      vazio = endpoint mudo, não validável;
    * probe_error_response: probe devolve erro HID++ 0x8F;
    * dpi_set_ack: se True, um set de DPI produce ACK; se False, a
      escrita "falha" no dispositivo;
    * ack_timeout: se True, o endpoint silencia (o read não devolve ACK);
    * hidpp_error: se True, respostas usam o sub-report de erro 0x8F;
    * readback_dpi: valor que o readback do DPI devolve (None = ausente).

    A combinação desses campos modela os cenários do review: endpoint
    que não responde ao protocolo, write aceito mas rejeitado, e
    timeout de confirmação — todos devem terminar em FAILED, nunca
    APPLIED.
    """

    FEATURE_DPI = 0x01  # índice simulado da feature AdjustableDPI (0x2201)

    def __init__(self) -> None:
        self.write_succeeds: bool = True
        self.device_required_for_write: bool = True
        self.probe_responses: List[bytes] = [b"\x11\xff\x00\x04" + b"\x00" * 14]
        self.probe_error_response: bool = False
        self.dpi_set_ack: bool = True
        self.ack_timeout: bool = False
        self.hidpp_error: bool = False
        self.open_permission_denied: bool = False
        self.open_raises: Optional[BaseException] = None
        self.readback_dpi: Optional[int] = None
        self.feature_count: int = 4
        self.read_calls: int = 0
        self._opened: List[MouseDevice] = []
        self._device: Optional[MouseDevice] = None
        self.written_reports: List[bytes] = []
        self._last_set_dpi: Optional[int] = None
        self._last_write_was_probe: bool = False

    def open(self, device: MouseDevice) -> OperationResult:
        self._opened.append(device)
        if device.hidraw_path is None:
            return OperationResult.device_not_found()
        if device.hidraw_path.startswith("/dev/permission_denied") or self.open_permission_denied:
            return OperationResult.permission_denied(device.hidraw_path)
        if self.open_raises is not None:
            raise self.open_raises
        self._device = device
        return OperationResult.applied()

    def is_open(self) -> bool:
        return self._device is not None

    def read(self, length: int, timeout: float = 0.5) -> Optional[bytes]:
        self.read_calls += 1
        if self._device is None:
            return None
        if self.ack_timeout:
            return None
        # Resposta de readback: eco do último set-DPI (feature index
        # 0x01), com o valor que o fake recebeu, para que o controller
        # valide a confirmação byte a byte.
        if self.hidpp_error:
            return b"\x11\xff\x8f\x00\x00\x00" + b"\x00" * (length - 6)
        if self.probe_error_response:
            return b"\x11\xff\x8f\x00\x00\x00" + b"\x00\x00" * (length - 6)
        if self._last_write_was_probe:
            self._last_write_was_probe = False
            if self.probe_responses:
                return self.probe_responses.pop(0)
            # Probe sem resposta configurada: endpoint mudo, não validado.
            return None
        if self.ack_timeout:
            return None
        # Resposta de eco do último set-DPI (feature index 0x01), se
        # houver; caso contrário o endpoint é mudo.
        if self.readback_value is not None:
            return self.readback_value
        return None

    def write(self, report: bytes) -> OperationResult:
        if not self.is_open() and self.device_required_for_write:
            return OperationResult.failed("no open descriptor")
        self.written_reports.append(report)
        if not self.write_succeeds:
            return OperationResult.failed("simulated hardware rejection")
        header = _parse_hidpp_header(report)
        if header is None:
            return OperationResult.failed("report sem cabeçalho HID++")
        report_id, feature_index = header
        if report_id == 0x11 and feature_index == 0x00:
            # Get feature table: devolve a contagem configurada (fn 0).
            self._last_write_was_probe = True
            return OperationResult.applied()
        if report_id in (0x10, 0x11) and feature_index == self.FEATURE_DPI:
            if not self.dpi_set_ack:
                return OperationResult.failed("device rejected dpi set")
            if self.hidpp_error:
                return OperationResult.failed("HID++ error 0x8F")
            # Guarda o DPI solicitado do payload (bytes 3-4) para
            # o fake de readback saber o que devolver.
            if len(report) >= 5:
                self._last_set_dpi = (report[3] << 8) | report[4]
            return OperationResult.applied()
        return OperationResult.applied()

    @property
    def readback_value(self) -> Optional[bytes]:
        """Resposta que um readback do DPI devolve."""
        if self.readback_dpi is None and self._last_set_dpi is None:
            return None
        value = self.readback_dpi if self.readback_dpi is not None else self._last_set_dpi
        if value is None:
            return None
        return b"\x11\xff\x01" + value.to_bytes(2, "big") + b"\x00" * 4

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
        self.query_count: int = 0
        self.title_provider_fails: bool = False
        self.window_title_available: bool = True

    def is_available(self) -> bool:
        return self.xinput_available

    def find_pointer_id(self, mouse_name: str) -> Optional[int]:
        self.query_count += 1
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
        self.query_count += 1
        if not self.window_title_available:
            return None
        if self.title_provider_fails:
            raise RuntimeError("xdotool falhou ao ler título da janela")
        return self.window_title

    def window_title_backend_available(self) -> bool:
        return self.window_title_available


def fake_g403_device(hidraw: Optional[str] = "/dev/hidraw2") -> MouseDevice:
    from mouse_hub.core.constants import G403_PID, G403_VID

    return MouseDevice(
        hidraw_path=hidraw,
        vid=G403_VID,
        pid=G403_PID,
        name="Logitech G403 HERO Gaming Mouse",
    )
