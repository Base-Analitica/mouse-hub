"""Serviço de controle do mouse sobre o core.

Ponto de entrada único para as operações de DPI e sensibilidade.
Orquestra descoberta, acesso HID e input do sistema pelos contratos de
`platform.protocol` e reporta o desfecho real de cada operação.

DPI físico é FAIL CLOSED com confirmação de resposta:

* o comando só é considerado aplicado quando o dispositivo DEVOLVE a
  resposta esperada dentro do timeout (ACK da feature, conforme o
  protocolo HID++ 2.0);
* escrita aceita mas sem resposta (timeout) ou resposta de erro
  (sub-report 0x8F / erro de protocolo 0xFF) termina em FAILED —
  `applied_dpi` nunca é atualizado e a sensibilidade nunca é tocada;
* o endpoint só participa de comandos de efeito depois de confirmado no
  protocolo (HydppEndpointSelection), com o feature index da feature
  Adjustable DPI (0x2201) descoberto dinamicamente via IRoot.GetFeature;
* requests e responses são correlacionados pelo header completo
  (report_id, device_index, feature_index, function, software_id); um
  report de outra feature, outro software ID ou evento assíncrono NÃO
  confirma o comando.

LIFECYCLE PÚBLICO — quem usa nunca manipula o HidAccess diretamente:

    ctrl.refresh_device(device)   # registra (não abre)
    ctrl.probe_endpoint()         # abre temporariamente, probeia, fecha
    ctrl.set_hardware_dpi(800)    # abre de novo sob demanda, fecha

O descritor só fica aberto durante a operação que o exige; o estado
confirmado (feature index, capacidades, último desfecho de acesso)
permanece no controller entre operações.

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
from mouse_hub.platform.hidpp import (
    DIRECT_USB_DEVICE_INDEX,
    FeatureId,
    SHORT_REPORT_LENGTH,
    SoftwareId,
    RootFeature,
    matches_ack,
    build_short_report,
)
from mouse_hub.platform.linux.device_discovery import (
    HydppEndpointSelection,
    ProbeOutcome,
)
from mouse_hub.platform.protocol import HidAccess, MouseDevice, SystemInput

# Report de comando SetSensorDPI (relatório curto 0x10):
#   [report_id] [device_index] [feature_index descoberto] [fn+sw_id]
#   [sensor_idx] [dpi_hi] [dpi_lo]
_DPI_SET_FUNCTION = 0x03  # nibble da fn SetSensorDPI (spec oficial)
_DPI_SENSOR_INDEX = 0x00
_DPI_COMMAND_REPORT_LENGTH = 7
_DEFAULT_PERSISTENCE = None  # injetável em teste


class MouseController:
    """Controlador de DPI e sensibilidade sobre o core compartilhado."""

    def __init__(
        self,
        hid: HidAccess,
        system_input: SystemInput,
        mouse_name: str = G403_NAME,
        vid: int = G403_VID,
        pid: int = G403_PID,
        dpi_persister=None,
    ) -> None:
        self._hid = hid
        self._input = system_input
        self._mouse_name = mouse_name
        self._vid = vid
        self._pid = pid
        self._device: Optional[MouseDevice] = None
        # Estado físico REAL não é conhecido até leitura/probe confirmados.
        self._applied_dpi: Optional[int] = None
        self._applied_sensitivity: Optional[int] = None
        # Feature index da Adjustable DPI descoberto dinamicamente via
        # IRoot.GetFeature(0x2201). None = nunca descoberto; -1 = feature
        # ausente no dispositivo.
        self._dpi_feature_index: Optional[int] = None
        # Estado do acesso durante o probe (para capabilities e para
        # distinguir permission_denied sem probe prévio).
        self._probe_accessible: Optional[bool] = None
        self._dpi_persister = dpi_persister

    # ── Descoberta ────────────────────────────────────────────────

    def refresh_device(self, device: Optional[MouseDevice]) -> OperationResult:
        """Registra o dispositivo descoberto (por uma camada superior).

        Não abre nenhum descritor: a abertura acontece apenas quando uma
        operação a exige (probe ou comando), e o descritor é fechado logo
        depois. Este método é somente leitura quanto ao HID.
        """
        self._device = device
        self._dpi_feature_index = None
        self._probe_accessible = None
        if device is None:
            return OperationResult.device_not_found("Nenhum dispositivo registrado")
        if device.hidraw_path is None:
            return OperationResult.unsupported(
                "Dispositivo sem interface hidraw acessível"
            )
        return OperationResult.applied("Dispositivo registrado")

    def probe_endpoint(self) -> OperationResult:
        """Valida o dispositivo registrado no protocolo HID++ 2.0.

        Fluxo interno completo (quem usa nunca toca no HidAccess):
        1. abre o descritor temporariamente;
        2. probe em duas etapas (HydppEndpointSelection): IRoot
           confirmado + IRoot.GetFeature(0x2201);
        3. se válido, guarda o feature index descoberto;
        4. FECHA o descritor em qualquer caminho (incluindo exceção).

        Resultado:
        * APPLIED            → endpoint confirmado, DPI disponível;
        * UNSUPPORTED        → endpoint HID++ 2.0 válido, mas a feature
          Adjustable DPI (0x2201) não existe no dispositivo;
        * PERMISSION_DENIED  → dispositivo presente mas sem regra udev;
        * FAILED/DEVICE_NOT  → endpoint não confirmou o protocolo.
        """
        if self._device is None or self._device.hidraw_path is None:
            return OperationResult.device_not_found("Nenhum endpoint para validar")

        selection = HydppEndpointSelection(self._hid)
        try:
            outcomes = selection.probe([self._device])
        except Exception as exc:
            return OperationResult.failed(
                f"Probe interrompido por falha de acesso: {exc}"
            )

        if not outcomes:
            return OperationResult.device_not_found("Candidato sem probe")

        outcome: ProbeOutcome = outcomes[0]
        self._probe_accessible = outcome.accessible

        if not outcome.valid:
            if outcome.accessible is False:
                return OperationResult.permission_denied(
                    "Descritor hidraw sem permissão de leitura/escrita "
                    "(regra udev ausente ou usuário fora do grupo)"
                )
            return OperationResult.failed(
                "Endpoint não confirmou o protocolo HID++ "
                "(resposta ausente, header não ecoado, erro 0x8F ou "
                "ambiguidade entre candidatos)"
            )

        if outcome.feature_index is None:
            # IRoot presente, mas 0x2201 não existe no dispositivo.
            self._dpi_feature_index = -1
            return OperationResult.unsupported(
                "Dispositivo HID++ 2.0 confirmado, mas a feature "
                "Adjustable DPI (0x2201) não está disponível"
            )

        self._dpi_feature_index = outcome.feature_index
        return OperationResult.applied(
            f"Endpoint confirmado: Adjustable DPI (0x2201) no feature "
            f"index {outcome.feature_index:#04x}"
        )

    @property
    def device(self) -> Optional[MouseDevice]:
        return self._device

    # ── DPI físico ────────────────────────────────────────────────

    def set_hardware_dpi(self, value: int) -> OperationResult:
        """Aplica DPI físico no sensor do G403, falhando fechado.

        Regras:
        * o valor é normalizado (clamp + step) e a diferença é reportada
          como APPLIED_PARTIAL quando houver arredondamento;
        * o feature index da Adjustable DPI precisa ter sido descoberto
          dinamicamente no probe (nunca é hardcoded);
        * o descritor é aberto apenas para esta operação e fechado ao
          final, em qualquer caminho;
        * a resposta do dispositivo é OBRIGATÓRIA e CORRELACIONADA ao
          request: mesmo (report_id, device_index, feature_index,
          function, software_id);
        * NUNCA toca na sensibilidade do sistema.
        """
        effective, was_rounded = normalize_dpi(value)
        if self._device is None:
            return OperationResult.device_not_found(
                f"DPI físico requer o {G403_NAME} registrado"
            )
        if self._device.hidraw_path is None:
            return OperationResult.unsupported(
                f"{G403_NAME} sem interface hidraw — não é controlável "
                "via protocolo HID++"
            )
        if self._dpi_feature_index is None:
            if self._probe_accessible is False:
                return OperationResult.permission_denied(
                    "Descritor hidraw sem permissão de leitura/escrita "
                    "(regra udev ausente ou usuário fora do grupo)"
                )
            return OperationResult.failed(
                "Endpoint não confirmado no protocolo HID++ "
                "(execute probe_endpoint antes)"
            )
        if self._dpi_feature_index < 0:
            return OperationResult.unsupported(
                "Feature Adjustable DPI (0x2201) ausente neste dispositivo"
            )

        opened = False
        try:
            if not self._hid.is_open():
                open_result = self._hid.open(self._device)
                if not open_result.status.ok:
                    if open_result.status == OperationStatus.PERMISSION_DENIED:
                        return OperationResult.permission_denied(
                            "Descritor hidraw sem permissão de leitura/escrita "
                            "(regra udev ausente ou usuário fora do grupo)"
                        )
                    return open_result
                opened = True

            request = build_short_report(
                self._dpi_feature_index,
                _DPI_SET_FUNCTION,
                params=bytes([
                    _DPI_SENSOR_INDEX,
                    (effective >> 8) & 0xFF,
                    effective & 0xFF,
                ]),
            )
            try:
                write_result = self._hid.write(request)
                if not write_result.status.ok:
                    return write_result

                response = _wait_for_ack(
                    self._hid,
                    RequestKeyFrom(self._dpi_feature_index, _DPI_SET_FUNCTION),
                )
            except OSError:
                # Falha de transporte no descritor (fd sumiu, I/O no OS):
                # o comando NÃO pode ser considerado aplicado — fail closed.
                return OperationResult.failed(
                    "Falha de transporte no descritor hidraw ao aplicar DPI"
                )
            if response is None:
                return OperationResult.failed(
                    "Comando de DPI enviado sem ACK do dispositivo "
                    "(nenhuma resposta dentro da janela de espera)"
                )
            error_code = _protocol_error(response)

            if error_code is not None:
                return OperationResult.failed(
                    f"Comando de DPI rejeitado pelo dispositivo "
                    f"(erro HID++ 2.0 {error_code:#04x})"
                )
        finally:
            if opened:
                self._hid.close()

        # Só agora o efeito é considerado confirmado.
        self._applied_dpi = effective
        persist_result = _persist_applied_dpi(
            effective, self._device, self._dpi_persister
        )
        if was_rounded:
            if persist_result is None:
                return OperationResult.applied_partial(
                    f"DPI aplicado no hardware: {effective} (solicitado "
                    f"{value}); persistência indisponível",
                    requested=value,
                    applied=effective,
                    confirmation=True,
                    persisted=False,
                )
            return OperationResult.applied_partial(
                f"DPI aplicado no hardware: {effective} (solicitado {value})",
                requested=value,
                applied=effective,
                confirmation=True,
                persisted=persist_result,
            )
        if persist_result is None:
            return OperationResult.applied(
                f"DPI físico aplicado: {effective}; persistência "
                "indisponível",
                applied=effective,
                confirmation=True,
                persisted=False,
            )
        return OperationResult.applied(
            f"DPI físico aplicado: {effective}",
            applied=effective,
            confirmation=True,
            persisted=persist_result,
        )

    @property
    def applied_dpi(self) -> Optional[int]:
        """Último DPI efetivamente confirmado (aplicado no hardware E
        readback validado). None = desconhecido (nunca confirmado)."""
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

        Capabilidades NÃO dependem do descritor estar aberto: a
        arquitetura é lazy (o descritor só fica aberto durante uma
        operação). `hid_endpoint_known` reflete o conhecimento obtido no
        probe; `hid_access_available` reflete o último resultado real de
        acesso.
        """
        device = self._device
        feature_known = self._dpi_feature_index is not None
        feature_supported = self._dpi_feature_index is not None and self._dpi_feature_index > 0

        def _mouse_detected() -> object:
            if device is None:
                return False, "nenhum dispositivo registrado"
            return True

        def _hid_endpoint_known() -> object:
            if device is None:
                return False, "nenhum dispositivo registrado"
            if device.hidraw_path is None:
                return False, "dispositivo sem interface hidraw"
            if not feature_known:
                return False, "endpoint nunca probeado no protocolo HID++"
            return True

        def _hid_access_available() -> object:
            if device is None or device.hidraw_path is None:
                return False, "nenhum endpoint para acessar"
            if self._probe_accessible is False:
                return False, "acesso negado ao descritor hidraw (regra udev ausente)"
            if self._probe_accessible is None:
                return False, "acesso ainda não avaliado (nenhum probe executado)"
            return True

        def _hardware_dpi_available() -> object:
            if device is None or device.hidraw_path is None:
                return False, "nenhum endpoint com interface hidraw"
            if self._probe_accessible is False:
                return False, "acesso negado ao descritor hidraw (regra udev ausente)"
            if not feature_known:
                return False, "endpoint nunca probeado; feature index desconhecido"
            if not feature_supported:
                return False, "feature Adjustable DPI (0x2201) ausente no dispositivo"
            return True

        def _sensitivity_available() -> object:
            if not self._input.is_available():
                return False, "ferramenta de input (xinput) ausente"
            return True

        def _window_available() -> object:
            if not self._input.window_title_backend_available():
                return False, "leitor de janela (xdotool) ausente"
            return True

        return CapabilityModel(
            mouse_detected=_mouse_detected,
            hid_endpoint_known=_hid_endpoint_known,
            hid_available=_hid_access_available,
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


# ── Helpers de correlação e persistência ────────────────────────────

def _wait_for_ack(
    hid: HidAccess, request_key: RequestKey
) -> Optional[bytes]:
    """Aguarda o ACK correlacionado do request, descartando reports que
    não o confirmam (events assíncronos de outros clientes).

    O HID pode entregar events de outro software (report de report
    rate, eventos de botões, notifications) entre o request e a
    resposta — todos são descartados até chegar o ACK exato ou o
    tempo acabar. Máximo de 3 janelas de leitura para não esperar
    indefinidamente em endpoint mudo."""
    for _ in range(3):
        response = hid.read(SHORT_REPORT_LENGTH, timeout=0.5)
        if response is None:
            return None
        if matches_ack(response, request_key):
            return response
    return None

def RequestKeyFrom(feature_index: int, function: int):
    """Chave de correlação para o ACK de um comando de efeito:
    short report, device index USB direto, software ID próprio."""
    from mouse_hub.platform.hidpp import RequestKey

    return RequestKey.from_short_request(
        feature_index,
        function,
        device_index=DIRECT_USB_DEVICE_INDEX,
        software_id=SoftwareId.MOUSE_HUB,
    )


def _protocol_error(raw: bytes) -> Optional[int]:
    """Código de erro de protocolo HID++ 2.0 (feature_index 0xFF em
    report longo) ou None se o report não é um erro."""
    from mouse_hub.platform.hidpp import is_protocol_error

    return is_protocol_error(raw)


def _persist_applied_dpi(
    effective: int,
    device: Optional[MouseDevice],
    persister=None,
) -> Optional[bool]:
    """Persiste o DPI confirmado. `persister(effective) -> bool | None`:
    True = persistido, False = falha (o hardware confirmou, mas a
    persistência não — os dois estados ficam explícitos), None = sem
    persister configurado. Retornamos None para "não aplicável" e
    booleano para "aplicado/falhou"."""
    if persister is None:
        return None
    try:
        return bool(persister(effective))
    except Exception:
        return False
