"""Serviço de controle do mouse sobre o core.

Ponto de entrada único para as operações de DPI e sensibilidade.
Orquestra descoberta, acesso HID e input do sistema pelos contratos de
`platform.protocol` e reporta o desfecho real de cada operação.

DPI físico é FAIL CLOSED com confirmação de resposta:

* o comando só é considerado aplicado quando o dispositivo DEVOLVE a
  resposta esperada dentro do timeout (ACK da feature, conforme o
  protocolo HID++ 2.0);
* escrita aceita mas sem resposta (timeout) ou resposta de erro
  (sub-report 0x8F) termina em FAILED — `applied_dpi` nunca é atualizado
  e a sensibilidade nunca é tocada;
* o endpoint só participa de comandos de efeito depois de confirmado no
  protocolo (HydppEndpointSelection), evitando escrever em interface
  que "parece" o G403 pelo VID/PID mas não responde ao protocolo.

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
from mouse_hub.platform.linux.device_discovery import HydppEndpointSelection
from mouse_hub.platform.protocol import HidAccess, MouseDevice, SystemInput

# Feature index da AdjustDPI para o G403 HERO no report SetSensorDPI
# usado por este produto (relatório curto 0x10, função 0x10, index 0x01).
_DPI_FEATURE_INDEX = 0x01
_DPI_COMMAND_REPORT_LENGTH = 7


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
        # O endpoint só é considerado confirmado após passar por
        # HydppEndpointSelection. Sem isso, hardware_dpi_available é
        # False e set_hardware_dpi recusa comandos de efeito.
        self._endpoint_confirmed: bool = False

    # ── Descoberta ────────────────────────────────────────────────

    def refresh_device(self, device: Optional[MouseDevice]) -> OperationResult:
        """Registra o dispositivo descoberto (por uma camada superior) e
        tenta abrir o acesso HID se houver interface hidraw.

        A descoberta em si (sysfs/VID-PID) é responsabilidade de quem
        usa este serviço, para que o ambiente de teste possa injetar
        dispositivos falsos diretamente. Um dispositivo registrado sem
        endpoint confirmado exige `probe_endpoint` antes de qualquer
        comando de DPI.
        """
        self._device = device
        self._endpoint_confirmed = False
        self._last_access_status: Optional[OperationStatus] = None
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
            # Registrar o desfecho real da abertura: o set de DPI pode
            # chegar sem endpoint confirmado (probe nunca ocorreu) e
            # ainda assim precisa distinguir permissão negada de falha
            # genérica.
            self._last_access_status = open_result.status
        else:
            self._last_access_status = None
        return open_result

    def probe_endpoint(self) -> OperationResult:
        """Valida que o dispositivo registrado responde ao protocolo
        HID++ 2.0 (feature table count), confirmando o endpoint para
        comandos de DPI.

        O probe abre e fecha o descritor sem efeito colateral permanente:
        a avaliação de capacidades pode chamá-lo sem mudar o estado do
        HID, que permanece como estava.
        """
        if self._device is None or self._device.hidraw_path is None:
            return OperationResult.device_not_found("Nenhum endpoint para validar")

        if self._hid.is_open():
            # O acesso está em uso; reabrir/fechar aqui conflitaria.
            # A validação exige posse exclusiva do descritor.
            return OperationResult.unsupported(
                "Endpoint já aberto por outra operação; valide antes de usar"
            )

        selection = HydppEndpointSelection(self._hid)
        selected = selection.select([self._device])
        if selected is None:
            self._endpoint_confirmed = False
            return OperationResult.failed(
                "Endpoint não confirmou o protocolo HID++ "
                "(resposta ausente, erro 0x8F ou ambiguidade)"
            )
        self._endpoint_confirmed = True
        return OperationResult.applied("Endpoint confirmado no protocolo HID++")

    @property
    def device(self) -> Optional[MouseDevice]:
        return self._device

    # ── DPI físico ────────────────────────────────────────────────

    def set_hardware_dpi(self, value: int) -> OperationResult:
        """Aplica DPI físico no sensor do G403, falhando fechado.

        Regras:
        * o valor é normalizado (clamp + step) e a diferença é
          reportada como APPLIED_PARTIAL quando houver arredondamento;
        * o endpoint precisa estar confirmado no protocolo (probe);
        * a resposta do dispositivo é OBRIGATÓRIA: sem confirmação de
          readback o resultado é FAILED e `applied_dpi` não muda;
        * NUNCA toca na sensibilidade do sistema.
        """
        # normalize_dpi já clampia e alinha ao step; nada fora da faixa
        # do sensor chega ao report.
        effective, was_rounded = normalize_dpi(value)

        if self._device is None or self._device.hidraw_path is None:
            return OperationResult.device_not_found(
                f"DPI físico requer o {G403_NAME} com interface hidraw"
            )

        if not self._endpoint_confirmed:
            # Endpoint sem confirmação: se a abertura do descritor já
            # havia falhado com permissão negada (regra udev ausente), o
            # desfecho real é permission_denied, não uma falha genérica.
            if self._last_access_status == OperationStatus.PERMISSION_DENIED:
                return OperationResult.permission_denied(
                    "Descritor hidraw sem permissão de leitura/escrita "
                    "(regra udev ausente ou usuário fora do grupo)"
                )
            return OperationResult.failed(
                "Endpoint não confirmado no protocolo HID++ "
                "(execute probe_endpoint antes)"
            )

        if not self._hid.is_open():
            open_result = self._hid.open(self._device)
            if not open_result.status.ok:
                # Permissão negada no descritor: o dispositivo existe,
                # mas sem regra udev não há acesso (desfecho distinto
                # de falha genérica).
                if open_result.status == OperationStatus.PERMISSION_DENIED:
                    return OperationResult.permission_denied(
                        "Descritor hidraw sem permissão de leitura/escrita "
                        "(regra udev ausente ou usuário fora do grupo)"
                    )
                return open_result

        # Report HID++ 2.0 curto: [report id 0x10] [feature index
        # 0x01 — AdjustDPI] [fn 0x10 — SetSensorDPI] [DPI hi] [DPI lo].
        report = bytearray(_DPI_COMMAND_REPORT_LENGTH)
        report[0] = 0x10
        report[1] = _DPI_FEATURE_INDEX
        report[2] = 0x10
        report[3] = (effective >> 8) & 0xFF
        report[4] = effective & 0xFF

        write_result = self._hid.write(bytes(report))
        if not write_result.status.ok:
            # Falha de escrita não vira sucesso silencioso.
            return write_result

        # Confirmação obrigatória: o dispositivo deve devolver o
        # reporte da mesma feature. Timeout ou erro 0x8F = falha.
        response = self._hid.read(20, timeout=0.5)
        if response is None or len(response) < 3:
            return OperationResult.failed(
                "Comando de DPI enviado sem resposta do dispositivo "
                "(timeout de confirmação)"
            )
        if response[2] == 0x8F:
            return OperationResult.failed(
                "Comando de DPI rejeitado pelo dispositivo (erro HID++ 0x8F)"
            )
        if response[2] != _DPI_FEATURE_INDEX:
            return OperationResult.failed(
                f"Resposta inesperada do dispositivo "
                f"(feature {response[2]:#04x}; esperado {_DPI_FEATURE_INDEX:#04x})"
            )

        # Só agora o efeito é considerado aplicado.
        self._applied_dpi = effective
        if was_rounded:
            return OperationResult.applied_partial(
                f"DPI aplicado no hardware: {effective} (solicitado {value})",
                requested=value,
                applied=effective,
                confirmation=True,
            )
        return OperationResult.applied(
            f"DPI físico aplicado: {effective}",
            applied=effective,
            confirmation=True,
        )

    @property
    def applied_dpi(self) -> Optional[int]:
        """Último DPI efetivamente confirmado no hardware (pode diferir
        do solicitado)."""
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
        """Monta o modelo de capacidades do ambiente atual, refletindo o
        estado real de cada recurso — com a causa quando indisponível.

        A avaliação é de somente leitura: nenhum detector abre o
        dispositivo, lê janelas ou executa subprocesso.
        """
        device = self._device

        def _mouse_detected() -> object:
            if device is None:
                return False, "nenhum dispositivo registrado"
            return True

        def _hid_available() -> object:
            if device is None:
                return False, "nenhum dispositivo registrado"
            if device.hidraw_path is None:
                return False, "dispositivo sem interface hidraw"
            if not self._hid.is_open():
                return False, "descritor hidraw fechado (não inicializado)"
            return True

        def _hardware_dpi_available() -> object:
            if not self._hid.is_open():
                return False, "hidraw fechado; sem canal de comandos"
            if not self._endpoint_confirmed:
                return False, "endpoint não confirmado no protocolo HID++"
            return True

        def _sensitivity_available() -> object:
            if not self._input.is_available():
                return False, "ferramenta de input (xinput) ausente"
            # A detecção do apontador envolve consulta real ao sistema;
            # a avaliação de capacidades é só leitura e não a executa.
            return True

        def _window_available() -> object:
            if not self._input.window_title_backend_available():
                return False, "leitor de janela (xdotool) ausente"
            return True

        return CapabilityModel(
            mouse_detected=_mouse_detected,
            hid_available=_hid_available,
            hardware_dpi_available=_hardware_dpi_available,
            sensitivity_available=_sensitivity_available,
            polling_rate_available=lambda: (
                False, "feature de polling rate não implementada"
            ),
            macro_capture_available=lambda: (
                False, "fronteira: automações são de outra instância"
            ),
            autoclick_available=lambda: (
                False, "fronteira: automações são de outra instância"
            ),
            active_window_detection_available=_window_available,
        )
