"""Serviço de controle do mouse sobre o core.

Ponto de entrada único para as operações de DPI e sensibilidade.
Orquestra descoberta, acesso HID e input do sistema pelos contratos de
`platform.protocol` e reporta o desfecho real de cada operação.

DPI físico é FAIL CLOSED com confirmação de resposta:

* o comando só é considerado aplicado quando o dispositivo DEVOLVE a
  resposta esperada dentro do timeout (ACK da feature, conforme o
  protocolo HID++ 2.0);
* escrita aceita mas sem resposta (TIMEOUT) ou erro de protocolo
  correlacionado (report longo conforme `hidpp_match_error` do kernel:
  feature_index 0xFF, feature index do request ecoado e function+sw
  originais) termina em FAILED com o error code real —
  `applied_dpi` nunca é atualizado e a sensibilidade nunca é tocada;

COMPOSIÇÃO DE PRODUÇÃO — o caminho padrão é montar o controller com
`make_linux_controller(hid, system_input)` (ou com ConfigPaths
próprias): o persister REAL (DpiConfigPersister ligado à ConfigStore)
é injetado automaticamente. Testes mantêm o hook `dpi_persister`
(NeverDpiPersister por default) sem acoplar a UI ao controller.
* todos os comandos FAP via o controller saem em LONG report 0x11 de
  20 bytes, conforme o driver upstream do kernel ("FAP only uses
  HIDPP_LONG messages") — nunca em short report;
* o device index 0xFF é o valor HID++ para o dispositivo conectado
  diretamente (G403 cabeado, sem receiver);
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
from mouse_hub.core.config import ConfigPaths
from mouse_hub.core.constants import G403_NAME, G403_PID, G403_VID
from mouse_hub.core.dpi import clamp_dpi, normalize_dpi
from mouse_hub.core.dpi_persistence import DpiConfigPersister, NeverDpiPersister
from mouse_hub.core.operation import OperationResult, OperationStatus
from mouse_hub.core.sensitivity import (
    accel_to_percent,
    clamp_sensitivity,
    percent_to_accel,
)
from mouse_hub.platform.hidpp import (
    AckResult,
    AckResultKind,
    DEVICE_INDEX_DIRECT,
    FAP_REPORT_LENGTH,
    FeatureId,
    matches_ack,
    matches_protocol_error,
    parse_protocol_error,
    RequestKey,
    RootFeature,
    SET_SENSOR_DPI_FUNCTION,
    SoftwareId,
    build_long_report,
)
from mouse_hub.platform.linux.device_discovery import (
    HydppEndpointSelection,
    ProbeOutcome,
)
from mouse_hub.platform.protocol import HidAccess, MouseDevice, SystemInput

# Comando SetSensorDPI (FAP, fn 0x03) — params: [sensor_idx] [dpi_hi]
# [dpi_lo]. O report FAP é sempre LONG (0x11, 20 bytes), conforme o
# driver upstream do kernel.
_DPI_SENSOR_INDEX = 0x00


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
        # Device index 0xFF: valor HID++ do dispositivo conectado
        # diretamente (kernel upstream __hidpp_send_report).
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
        # Persister do DPI: quem chama injeta (tests: NeverDpiPersister;
        # produção: DpiConfigPersister via make_linux_controller).
        self._dpi_persister = dpi_persister or NeverDpiPersister()

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
            f"index {outcome.feature_index:#04x} (device index "
            f"{DEVICE_INDEX_DIRECT:#04x})"
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

            request = build_long_report(
                self._dpi_feature_index,
                SET_SENSOR_DPI_FUNCTION,
                params=bytes([
                    _DPI_SENSOR_INDEX,
                    (effective >> 8) & 0xFF,
                    effective & 0xFF,
                ]),
            )
            request_key = RequestKey.from_long_request(
                self._dpi_feature_index,
                SET_SENSOR_DPI_FUNCTION,
                device_index=DEVICE_INDEX_DIRECT,
                software_id=SoftwareId.MOUSE_HUB,
            )
            try:
                write_result = self._hid.write(request)
                if not write_result.status.ok:
                    return write_result

                ack_result = _wait_for_ack(self._hid, request_key)
            except OSError:
                # Falha de transporte no descritor (fd sumiu, I/O no OS):
                # o comando NÃO pode ser considerado aplicado — fail closed.
                return OperationResult.failed(
                    "Falha de transporte no descritor hidraw ao aplicar DPI"
                )
            if ack_result.kind == AckResultKind.TIMEOUT:
                return OperationResult.failed(
                    "Comando de DPI enviado sem ACK do dispositivo "
                    "(nenhuma resposta dentro da janela de espera)"
                )
            if ack_result.kind == AckResultKind.PROTOCOL_ERROR:
                # Erro FAP correlacionado: report longo com feature_index
                # 0xFF e function do request ecoada — pertence a ESTE
                # request, não a evento assíncrono de outro cliente.
                return OperationResult.failed(
                    f"Comando de DPI rejeitado pelo dispositivo "
                    f"(erro HID++ 2.0 {ack_result.error_code:#04x})",
                    hidpp_error=ack_result.error_code,
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

def _wait_for_ack(hid: HidAccess, request_key: RequestKey) -> AckResult:
    """Classifica a resposta do request em resultado tipado: ACK, erro
    de protocolo correlacionado ou TIMEOUT.

    Reports que não casam com o request (event assíncrono de outro
    software, outra feature, outro report type) são descartados como
    noise. O erro FAP pertence ao request original quando o report
    longo tem feature_index 0xFF e ecoa o byte function+sw do request
    (params[0]) — sem isso, erro assíncrono de outro request nunca é
    aceito. Máximo de 3 janelas de leitura para não esperar
    indefinidamente em endpoint mudo."""
    import time

    deadline = time.monotonic() + 1.5
    for _ in range(3):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return AckResult(AckResultKind.TIMEOUT, timed_out=True)
        raw = hid.read(FAP_REPORT_LENGTH, timeout=min(0.5, remaining))
        if raw is None:
            continue
        if matches_ack(raw, request_key):
            return AckResult(AckResultKind.ACK, response=raw)
        if matches_protocol_error(raw, request_key):
            return AckResult(
                AckResultKind.PROTOCOL_ERROR,
                response=raw,
                error_code=parse_protocol_error(raw),
            )
        # Report que não pertence ao request = noise: descartar.
    return AckResult(AckResultKind.TIMEOUT, timed_out=True)


def _persist_applied_dpi(
    effective: int,
    device: Optional[MouseDevice],
    persister=None,
) -> Optional[bool]:
    """Persiste o DPI confirmado SOMENTE após ACK físico válido.

    O persister expõe `persist_applied_dpi(effective) -> bool`:
    * True  → persistido (applied_dpi salvo em config.json);
    * False → hardware confirmou mas persistência bloqueada/falhou
      (ex.: config corrompida/ilegível — guard fail-closed) — os dois
      estados ficam explícitos no resultado da operação.
    Timeout/rejeição nunca chega aqui — o chamador só invoca após ACK.
    O persister de produção (DpiConfigPersister) escreve apenas quando
    os dados carregados são confirmados (LoadKind.FILE ou DEFAULT com
    arquivo realmente ausente); config corrompida/ilegível nunca é
    sobrescrita."""
    if persister is None:
        return None
    try:
        return bool(persister.persist_applied_dpi(effective))
    except Exception:
        return False


def make_linux_controller(
    hid: HidAccess,
    system_input: SystemInput,
    config_paths: Optional[ConfigPaths] = None,
    mouse_name: str = G403_NAME,
    vid: int = G403_VID,
    pid: int = G403_PID,
) -> MouseController:
    """Composição de PRODUÇÃO do MouseController para o Linux.

    Monta o controller com o persister REAL ligado à ConfigStore XDG:
    o DPI confirmado físico é persistido automaticamente em
    config.json. Testes continuam injetando outro persister no
    constructor (o caminho de produção é esta factory, não mutação de
    atributo privado).

    Falha de persistência NUNCA apaga o efeito aplicado: o hardware
    mantém o DPI confirmado e o resultado da operação carrega
    `persisted=False` explícito."""
    return MouseController(
        hid,
        system_input,
        mouse_name=mouse_name,
        vid=vid,
        pid=pid,
        dpi_persister=DpiConfigPersister(config_paths),
    )
