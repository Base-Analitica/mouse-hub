"""Serviço de controle do mouse sobre o core.

Este módulo é o ponto de entrada único para as operações de DPI e
sensibilidade do produto. Ele orquestra descoberta, acesso HID e input
do sistema através dos contratos de `platform.protocol`, e reporta o
desfecho real de cada operação:

* DPI físico e sensibilidade são operações INDEPENDENTES: aplicar DPI
  físico com sucesso nunca altera a sensibilidade, e a sensibilidade
  nunca é apresentada como se fosse DPI.
* Se o hardware DPI falhar, o resultado NUNCA retorna sucesso dizendo
  que o DPI foi alterado — nem por ter modificado libinput.
* Ausência do mouse e ausência de permissão são desfechos distintos.

Macros e auto-clicker NÃO pertencem a este módulo: ficam com a outra
instância responsável pelas automações. A fronteira é mantida de
propósito.
"""

from __future__ import annotations

from typing import Optional

from mouse_hub.core.capabilities import CapabilityModel
from mouse_hub.core.constants import G403_NAME, G403_PID, G403_VID
from mouse_hub.core.dpi import clamp_dpi, normalize_dpi
from mouse_hub.core.operation import OperationResult, OperationStatus
from mouse_hub.core.sensitivity import (
    accel_to_percent,
    clamp_sensitivity,
    percent_to_accel,
)
from mouse_hub.platform.protocol import HidAccess, MouseDevice, SystemInput


class MouseController:
    """Controlador de DPI e sensibilidade sobre o core compartilhado."""

    def __init__(
        self,
        hid: HidAccess,
        system_input: SystemInput,
        mouse_name: str = G403_NAME,
        vid: int = G403_VID,
        pid: int = G403_PID,
    ) -> None:
        self._hid = hid
        self._input = system_input
        self._mouse_name = mouse_name
        self._vid = vid
        self._pid = pid
        self._device: Optional[MouseDevice] = None
        self._applied_dpi: Optional[int] = None
        self._applied_sensitivity: Optional[int] = None

    # ── Descoberta ────────────────────────────────────────────────

    def refresh_device(self, device: Optional[MouseDevice]) -> OperationResult:
        """Registra o dispositivo descoberto (por uma camada superior) e
        tenta abrir o acesso HID se houver interface hidraw.

        A descoberta em si (sysfs/VID-PID) é responsabilidade de quem
        usa este serviço, para que o ambiente de teste possa injetar
        dispositivos falsos diretamente.
        """
        self._device = device
        if device is None:
            self._hid.close()
            return OperationResult.device_not_found("Nenhum dispositivo registrado")
        if device.hidraw_path is None:
            # Mouse utilizável como apontador, mas sem acesso direto ao
            # sensor: DPI físico indisponível, sensibilidade ok.
            self._hid.close()
            return OperationResult.unsupported(
                "Dispositivo sem interface hidraw acessível"
            )
        open_result = self._hid.open(device)
        if not open_result.status.ok:
            # Falha ao abrir o novo dispositivo não pode deixar o antigo
            # descritor aberto apontando para outro nó — fail closed.
            self._hid.close()
        return open_result

    @property
    def device(self) -> Optional[MouseDevice]:
        return self._device

    # ── DPI físico ────────────────────────────────────────────────

    def set_hardware_dpi(self, value: int) -> OperationResult:
        """Aplica DPI físico no sensor do G403.

        Regras:
        * o valor é normalizado (clamp + step) e a diferença é
          reportada como APPLIED_PARTIAL quando houver arredondamento;
        * se o hardware não estiver acessível, retorna device_not_found
          ou permission_denied conforme o caso — nunca sucesso;
        * NUNCA toca na sensibilidade do sistema.
        """
        effective, was_rounded = normalize_dpi(value)

        if self._device is None or self._device.hidraw_path is None:
            return OperationResult.device_not_found(
                f"DPI físico requer o {G403_NAME} com interface hidraw"
            )

        if not self._hid.is_open():
            open_result = self._hid.open(self._device)
            if not open_result.status.ok:
                return open_result

        # Report HID++ 2.0 curto para SetSensorDPI (index 0x10 da feature
        # AdjustDPI é aproximado do firmware atual; o report real usado
        # pelo projeto existente: ID 0x10, function 0x10, index 0x00).
        report = bytearray(7)
        report[0] = 0x10
        report[1] = 0x10
        report[2] = 0x00
        report[3] = (effective >> 8) & 0xFF
        report[4] = effective & 0xFF

        write_result = self._hid.write(bytes(report))
        if not write_result.status.ok:
            # Falha de hardware não vira sucesso silencioso.
            return write_result

        self._applied_dpi = effective
        if was_rounded:
            return OperationResult.applied_partial(
                f"DPI aplicado no hardware: {effective} (solicitado {value})",
                requested=value,
                applied=effective,
            )
        return OperationResult.applied(
            f"DPI físico aplicado: {effective}",
            applied=effective,
        )

    @property
    def applied_dpi(self) -> Optional[int]:
        """Último DPI efetivamente aplicado ao hardware (pode diferir do
        solicitado)."""
        return self._applied_dpi

    # ── Sensibilidade do ponteiro ─────────────────────────────────

    def set_sensitivity(self, value: int) -> OperationResult:
        """Aplica sensibilidade do ponteiro via libinput.

        Operação independente: não consulta nem altera o DPI físico.
        """
        effective, was_clamped = (
            (clamp_sensitivity(value), value != clamp_sensitivity(value))
        )

        if self._device is None:
            return OperationResult.device_not_found(
                "Nenhum dispositivo registrado; sensibilidade requer o mouse"
            )

        pointer_id = self._input.find_pointer_id(self._mouse_name)
        if pointer_id is None:
            return OperationResult.device_not_found(
                "Apontador não localizado no xinput"
            )

        accel = percent_to_accel(effective)
        result = self._input.set_accel_speed(pointer_id, accel)
        if not result.status.ok:
            return result

        self._applied_sensitivity = effective
        if was_clamped:
            return OperationResult.applied_partial(
                f"Sensibilidade aplicada: {effective}% (solicitada {value}%)",
                requested=value,
                applied=effective,
            )
        return OperationResult.applied(
            f"Sensibilidade aplicada: {effective}%",
            applied=effective,
        )

    def get_sensitivity(self) -> Optional[int]:
        """Lê a sensibilidade efetiva do sistema, ou None se indisponível."""
        pointer_id = self._input.find_pointer_id(self._mouse_name)
        if pointer_id is None:
            return None
        accel = self._input.get_accel_speed(pointer_id)
        if accel is None:
            return None
        return accel_to_percent(accel)

    @property
    def applied_sensitivity(self) -> Optional[int]:
        return self._applied_sensitivity

    # ── Modelo de capacidades ─────────────────────────────────────

    def capability_model(self) -> CapabilityModel:
        """Monta o modelo de capacidades do ambiente atual.

        Usado pela UI para exibir estado real por feature.
        """
        mouse_detected = self._device is not None
        hid_available = self._device is not None and bool(self._device.hidraw_path)
        hardware_dpi_available = hid_available

        sensitivity_available = (
            self._input.is_available()
            and self._input.find_pointer_id(self._mouse_name) is not None
        )
        window_available = self._input.active_window_title() is not None

        return CapabilityModel(
            mouse_detected=lambda: mouse_detected,
            hid_available=lambda: hid_available,
            hardware_dpi_available=lambda: hardware_dpi_available,
            sensitivity_available=lambda: sensitivity_available,
            polling_rate_available=lambda: False,  # requer feature HID específica
            macro_capture_available=lambda: False,  # fronteira: automações
            autoclick_available=lambda: False,      # fronteira: automações
            active_window_detection_available=lambda: window_available,
        )
