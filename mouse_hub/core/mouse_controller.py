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

from typing import List, Optional

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
from mouse_hub.platform.read_outcome import ReadOutcomeKind
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
        # Desfecho REAL do último acesso no probe (para capabilities e
        # para nunca colapsar permission_denied/device_not_found/falha
        # genérica em um único accessible=False).
        self._probe_access_status: Optional[OperationStatus] = None
        # Mensagem REAL da última falha de acesso no probe (ex.: EPIPE
        # da interface de input — issue #68); None quando não há falha
        # ou a causa é coberta pelo status.
        self._probe_access_message: Optional[str] = None
        # True quando MAIS DE UM candidato confirmou o protocolo no
        # select_endpoint sem critério seguro de desempate — nesse caso
        # nenhum endpoint é elegível a efeitos (fail closed), mesmo que
        # um probe isolado do primeiro candidato passe (issue #68).
        self._selection_ambiguous: bool = False
        # Causa da ÚLTIMA falha do próprio comando SetSensorDPI
        # (timeout/protocol_error). None = sem falha ou recuperado por
        # re-probe. Capability: hardware_dpi_available deixa de ser True
        # após falha real da operação de DPI mesmo com transporte
        # acessível (revisão PR #21) — hid_available permanece separado.
        self._dpi_set_error_reason: Optional[str] = None
        # Persister do DPI: quem chama injeta (tests: NeverDpiPersister;
        # produção: DpiConfigPersister via make_linux_controller).
        self._dpi_persister = dpi_persister or NeverDpiPersister()
        # Sensibilidade: leitura REAL do estado atual do sistema no
        # startup (issue #102). Sensibilidade do sistema é propriedade
        # do ponteiro, não do mouse: o valor inicial NÃO nasce desconhecido
        # nem depende de probe de hardware — quem responde é o
        # SystemInput (libinput/xinput). Falha de leitura permanece
        # None (desconhecido honesto), nunca default conveniente.
        self._applied_sensitivity = self.get_sensitivity()

    # ── Descoberta ────────────────────────────────────────────────

    @staticmethod
    def _matches_expected_device(
        device: Optional[MouseDevice],
        expected_vid: int,
        expected_pid: int,
    ) -> bool:
        """True se o dispositivo corresponde à identidade esperada (VID
        **e** PID). Usado em refresh_device ANTES de registrar e como
        defesa em profundidade antes de qualquer efeito HID — o caller
        pode ter usado discover_g403(), mas o controller NUNCA assume:
        outro mouse Logitech HID++ 2.0 com a feature 0x2201 passaria no
        protocolo sem esta checagem.

        Fonte da identidade: core/constants G403_VID/G403_PID (046d:c08f;
        issue #3 — validar que o dispositivo é realmente o G403 HERO
        antes de qualquer escrita)."""
        if device is None:
            return False
        return device.vid == expected_vid and device.pid == expected_pid

    def refresh_device(self, device: Optional[MouseDevice]) -> OperationResult:
        """Registra o dispositivo descoberto (por uma camada superior).

        Não abre nenhum descritor: a abertura acontece apenas quando uma
        operação a exige (probe ou comando), e o descritor é fechado logo
        depois. Este método é somente leitura quanto ao HID.

        A identidade do dispositivo (VID+PID) é validada ANTES de
        armazenar: um device que não corresponda ao G403 esperado NUNCA
        é registrado — self._device não pode continuar apontando para o
        device rejeitado e o estado de probe é descartado.
        """
        if not self._matches_expected_device(device, self._vid, self._pid):
            # Rejeição: self._device NÃO guarda o device inválido e o
            # estado de probe é resetado — nenhuma operação posterior
            # tem efeito sobre hardware errado.
            self._device = None
            self._dpi_feature_index = None
            self._probe_accessible = None
            self._probe_access_status = None
            self._dpi_set_error_reason = None
            if device is None:
                return OperationResult.device_not_found(
                    "Nenhum dispositivo registrado"
                )
            return OperationResult.device_not_found(
                f"Dispositivo rejeitado: identidade divergente "
                f"(esperado VID {self._vid:#06x} PID {self._pid:#06x}, "
                f"recebido VID {device.vid:#06x} PID {device.pid:#06x})"
            )
        self._device = device
        self._dpi_feature_index = None
        self._probe_accessible = None
        self._probe_access_status = None
        self._dpi_set_error_reason = None
        if device.hidraw_path is None:
            return OperationResult.unsupported(
                "Dispositivo sem interface hidraw acessível"
            )
        return OperationResult.applied("Dispositivo registrado")

    def _invalidate_access_state(self, status: OperationStatus) -> None:
        """Falha real de acesso (open ou write) invalida o snapshot de
        capacidades E o feature index confirmado — a causa é ambiente
        (device/transport), não protocolo. Quem quer efeito de novo
        precisa revalidar o ambiente (refresh_device + probe_endpoint).
        O snapshot nunca fica True depois de uma falha real: hot-unplug
        ou perda de permissão durante uma operação não deixam
        hid_available/hardware_dpi_available True."""
        self._probe_access_status = status
        self._probe_accessible = False
        self._probe_access_message = None
        self._dpi_feature_index = None
        self._dpi_set_error_reason = None

    def select_endpoint(
        self, candidates: List[MouseDevice]
    ) -> Optional[MouseDevice]:
        """Seleciona entre TODOS os hidraws do G403 o único que confirma
        o protocolo HID++ 2.0 (probe em dois estágios, fail closed).

        O G403 real expõe múltiplos /dev/hidrawN; apenas a interface
        vendor responde ao probe — as demais abrem mas rejeitam a
        escrita (EPIPE). Selecionar exige sondar todos (issue #68).

        Regras (HydppEndpointSelection.select):
        * nenhum candidato confirma → None;
        * exatamente um confirma → esse;
        * mais de um confirma sem desempate seguro → None, e o estado
          fica marcado como ambíguo: probe/DPI permanecem bloqueados
          até um novo select_endpoint limpar a marca.
        """
        if not candidates:
            self._selection_ambiguous = False
            return None
        selection = HydppEndpointSelection(self._hid)
        outcomes = selection.probe(candidates)
        validated = [
            device
            for device, outcome in zip(candidates, outcomes)
            if outcome.valid and outcome.feature_index is not None
        ]
        self._selection_ambiguous = len(validated) > 1
        if len(validated) == 1:
            return validated[0]
        return None

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
        if self._device is None:
            return OperationResult.device_not_found("Nenhum dispositivo registrado")
        # Defesa em profundidade: revalidar a identidade do device
        # registrado antes do probe — mesmo caminho via discover_g403().
        if not self._matches_expected_device(self._device, self._vid, self._pid):
            return OperationResult.failed(
                "Dispositivo registrado não corresponde à identidade "
                "esperada (VID/PID) — nenhum efeito HID aplicado"
            )
        if self._device.hidraw_path is None:
            # Mouse presente (mouse_detected=True) mas sem interface
            # hidraw controlável — não é "device ausente" (issue #3/#7).
            return OperationResult.unsupported(
                "Dispositivo presente, mas sem interface hidraw "
                "acessível — não é controlável via protocolo HID++"
            )

        # Re-probe é autoritativo: o conhecimento do endpoint parte do
        # zero e só sobrevive se ESTE probe terminar bem — um re-probe
        # falho NUNCA deixa o feature index do probe anterior vivo
        # (invalidação do snapshot anterior no início, não só em falha).
        # O DPI JÁ APLICADO (self._applied_dpi) é preservado: o hardware
        # mantém o estado; só o conhecimento do endpoint morre.
        self._dpi_feature_index = None
        self._probe_accessible = None
        self._probe_access_status = None
        self._dpi_set_error_reason = None

        if self._selection_ambiguous:
            # Seleção ambígua: nenhum endpoint é elegível — um probe
            # isolado NÃO pode confirmar feature index nem habilitar
            # escritas de efeito (fail closed, issue #68).
            ambiguous_reason = (
                "seleção de endpoint ambígua: mais de um candidato "
                "confirmou o protocolo — nada é escrito até um novo "
                "select_endpoint resolver"
            )
            self._probe_access_status = OperationStatus.FAILED
            self._probe_accessible = False
            self._probe_access_message = ambiguous_reason
            return OperationResult.failed(ambiguous_reason)

        selection = HydppEndpointSelection(self._hid)
        try:
            outcomes = selection.probe([self._device])
        except Exception as exc:
            self._probe_access_status = OperationStatus.FAILED
            return OperationResult.failed(
                f"Probe interrompido por falha de acesso: {exc}"
            )

        if not outcomes:
            self._probe_access_status = OperationStatus.FAILED
            return OperationResult.device_not_found("Candidato sem probe")

        outcome: ProbeOutcome = outcomes[0]
        self._probe_accessible = outcome.accessible
        self._probe_access_status = outcome.access_status
        self._probe_access_message = outcome.access_message

        if not outcome.valid:
            if outcome.access_status == OperationStatus.PERMISSION_DENIED:
                return OperationResult.permission_denied(
                    "Descritor hidraw sem permissão de leitura/escrita "
                    "(regra udev ausente ou usuário fora do grupo)"
                )
            if outcome.access_status == OperationStatus.DEVICE_NOT_FOUND:
                return OperationResult.device_not_found(
                    "Endpoint sumiu entre a descoberta e o probe "
                    "(hot-unplug ou device removido)"
                )
            details: dict = {}
            if outcome.error_code is not None:
                details["fap_error_code"] = outcome.error_code
            if outcome.access_status is not None:
                details["access"] = outcome.access_status.value
            if outcome.access_message is not None:
                # Causa real de acesso (ex.: EPIPE da interface de
                # input) — nunca colapsada em falha genérica (#68).
                return OperationResult.failed(
                    outcome.access_message, **details
                )
            return OperationResult.failed(
                "Endpoint não confirmou o protocolo HID++ "
                "(resposta ausente, header não ecoado, ping incorreto, "
                "erro FAP ou ambiguidade entre candidatos)",
                **details,
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
        # Defesa em profundidade: a identidade registrada é revalidada
        # ANTES de qualquer efeito HID — o caller pode ter usado
        # discover_g403(), mas o controller confirma de novo e nunca
        # escreve em device que não corresponda ao G403 esperado.
        if self._device is None:
            return OperationResult.device_not_found(
                f"DPI físico requer o {G403_NAME} registrado"
            )
        if not self._matches_expected_device(self._device, self._vid, self._pid):
            return OperationResult.failed(
                f"Dispositivo registrado não corresponde ao {G403_NAME} "
                f"(identidade VID/PID divergente) — nenhum efeito HID "
                "aplicado"
            )
        if self._device.hidraw_path is None:
            return OperationResult.unsupported(
                f"{G403_NAME} sem interface hidraw — não é controlável "
                "via protocolo HID++"
            )
        if self._dpi_feature_index is None:
            if self._probe_access_status == OperationStatus.PERMISSION_DENIED:
                return OperationResult.permission_denied(
                    "Descritor hidraw sem permissão de leitura/escrita "
                    "(regra udev ausente ou usuário fora do grupo)"
                )
            if self._probe_access_status == OperationStatus.DEVICE_NOT_FOUND:
                return OperationResult.device_not_found(
                    "Endpoint indisponível entre a descoberta e o uso"
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
                try:
                    open_result = self._hid.open(self._device)
                except OSError:
                    # Descritor indisponível na abertura (fd sumiu,
                    # I/O no OS) — a causa é ambiente: invalidar o
                    # snapshot e falhar fechado, nunca vaza exceção.
                    self._invalidate_access_state(OperationStatus.FAILED)
                    return OperationResult.failed(
                        "Descritor hidraw indisponível na abertura "
                        "(device sumiu ou falha de transporte no OS)"
                    )
                if not open_result.status.ok:
                    # Falha real de acesso invalida o snapshot de
                    # capacidades: open DEVICE_NOT_FOUND/PERMISSION_DENIED/
                    # FAILED são refletidos em hid_available e
                    # hardware_dpi_available imediatamente (não ficam
                    # com o snapshot do probe bem-sucedido anterior).
                    self._invalidate_access_state(open_result.status)
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
                    # ── Invalidation: falha real de acesso invalida o
                    # snapshot de capacidades ANTES de retornar o erro —
                    # o hot-unplug durante uma operação não deixa
                    # hid_available/DPI True.
                    self._invalidate_access_state(write_result.status)
                    return write_result

                ack_result = _wait_for_ack(self._hid, request_key)
            except OSError:
                # Falha de transporte no descritor (fd sumiu, I/O no OS):
                # o comando NÃO pode ser considerado aplicado — fail closed.
                self._invalidate_access_state(OperationStatus.FAILED)
                return OperationResult.failed(
                    "Falha de transporte no descritor hidraw ao aplicar DPI"
                )
            if ack_result.kind == AckResultKind.TRANSPORT_FAILURE:
                # Falha REAL de acesso durante a espera do ACK
                # (device desconectado entre o write e a leitura, fd
                # sem permissão, transporte quebrado): comando NÃO
                # considerado aplicado — fail closed com a causa
                # exata e invalidação do snapshot.
                transport = ack_result.read_outcome
                status = (
                    OperationStatus.DEVICE_NOT_FOUND
                    if transport is not None
                    and transport.kind == ReadOutcomeKind.DEVICE_NOT_FOUND
                    else OperationStatus.PERMISSION_DENIED
                    if transport is not None
                    and transport.kind == ReadOutcomeKind.PERMISSION_DENIED
                    else OperationStatus.FAILED
                )
                self._invalidate_access_state(status)
                if status == OperationStatus.DEVICE_NOT_FOUND:
                    return OperationResult.device_not_found(
                        "Dispositivo desconectado durante a espera do "
                        "ACK (hot-unplug entre o comando e a leitura)"
                    )
                if status == OperationStatus.PERMISSION_DENIED:
                    return OperationResult.permission_denied(
                        "Permissão perdida durante a espera do ACK "
                        "(descritor hidraw sem acesso de leitura)"
                    )
                return OperationResult.failed(
                    "Falha de transporte durante a espera do ACK "
                    "(descritor hidraw indisponível na leitura)"
                )
            if ack_result.kind == AckResultKind.TIMEOUT:
                # Falha real da PRÓPRIA operação de DPI (endpoint mudo):
                # a capability hardware_dpi_available deixa de ser True —
                # hid_available permanece separado (transporte acessível).
                # Recuperação: apenas nova evidência (re-probe confirmado).
                self._dpi_set_error_reason = "timeout"
                return OperationResult.failed(
                    "Comando de DPI enviado sem ACK do dispositivo "
                    "(nenhuma resposta dentro da janela de espera)",
                    dpi_set_error="timeout",
                )
            if ack_result.kind == AckResultKind.PROTOCOL_ERROR:
                # Erro FAP correlacionado: report longo com feature_index
                # 0xFF e function do request ecoada — pertence a ESTE
                # request, não a evento assíncrono de outro cliente.
                # Falha real da operação de DPI: hardware_dpi_available
                # deixa de ser True (hid_available permanece separado).
                self._dpi_set_error_reason = "protocol_error"
                return OperationResult.failed(
                    f"Comando de DPI rejeitado pelo dispositivo "
                    f"(erro HID++ 2.0 {ack_result.error_code:#04x})",
                    hidpp_error=ack_result.error_code,
                    dpi_set_error="protocol_error",
                )
        finally:
            if opened:
                self._hid.close()

        # Só agora o efeito é considerado confirmado — e a falha da
        # operação de DPI (se houve) é recuperada por evidência nova.
        self._dpi_set_error_reason = None
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
            if self._probe_access_status == OperationStatus.PERMISSION_DENIED:
                return False, "acesso negado ao descritor hidraw (regra udev ausente)"
            if self._probe_access_status == OperationStatus.DEVICE_NOT_FOUND:
                return False, "endpoint desapareceu entre a descoberta e o probe"
            if self._probe_access_status == OperationStatus.FAILED:
                return False, (
                    self._probe_access_message
                    or "falha de acesso ao descritor hidraw não "
                    "relacionada a permissão"
                )
            if self._probe_accessible is False:
                return False, "acesso negado ao descritor hidraw (regra udev ausente)"
            if self._probe_accessible is None:
                return False, "acesso ainda não avaliado (nenhum probe executado)"
            return True

        def _hardware_dpi_available() -> object:
            if device is None or device.hidraw_path is None:
                return False, "nenhum endpoint com interface hidraw"
            if self._probe_access_status == OperationStatus.DEVICE_NOT_FOUND:
                return (
                    False,
                    "endpoint desapareceu do sistema (hot-unplug) — "
                    "execute refresh_device + probe_endpoint após reconexão",
                )
            if self._probe_access_status == OperationStatus.PERMISSION_DENIED:
                return False, "acesso negado ao descritor hidraw (regra udev ausente)"
            if self._probe_access_status == OperationStatus.FAILED:
                return False, (
                    self._probe_access_message
                    or "falha de acesso ao endpoint (open/probe falhou)"
                )
            if self._probe_accessible is False:
                return False, "acesso negado ao descritor hidraw (regra udev ausente)"
            if not feature_known:
                return False, "endpoint nunca probeado; feature index desconhecido"
            if not feature_supported:
                return False, "feature Adjustable DPI (0x2201) ausente no dispositivo"
            if self._dpi_set_error_reason is not None:
                # Falha real da própria operação SetSensorDPI (timeout ou
                # erro de protocolo correlacionado): a capability NÃO
                # permanece afirmativa sem nova evidência (re-probe).
                # hid_available permanece separado — o transporte segue
                # comprovadamente acessível.
                if self._dpi_set_error_reason == "timeout":
                    return (
                        False,
                        "comando SetSensorDPI terminou em timeout — "
                        "execute refresh/re-probe para nova evidência",
                    )
                return (
                    False,
                    "comando SetSensorDPI rejeitado pelo dispositivo "
                    "(erro de protocolo HID++) — execute refresh/re-probe "
                    "para nova evidência",
                )
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
            # Polling rate do G403 HERO — issue #6. O padrão HID++ 2.0
            # especifica a feature Report Rate (0x8060,
            # "adjustableReportRate", documentada pelo OpenLogi em
            # https://openlogi.org/hidpp/features/x8060-report-rate), mas
            # o stack atual do Mouse Hub NÃO implementa a descoberta
            # dessa feature, não define suas funções nem suporta o
            # comando de alteração com confirmação. Sem hardware real
            # (G403 HERO físico) para validar feature index, taxas
            # suportadas e ACK, implementar seria inventar contrato —
            # proibido pela issue #6. A capacidade permanece
            # indisponível e a UI deve refletir isso sem simular valores.
            #
            # A causa técnica permanece no reason da capability para
            # diagnóstico; a camada de apresentação decide como traduzi-la.
            polling_rate_available=lambda: (
                False,
                "polling rate do G403 não é alterável/confirmável pelo "
                "stack HID++ atual: a feature Report Rate (0x8060) não "
                "está implementada na descoberta de features do projeto, "
                "e alteração segura exigiria validação em hardware real "
                "(G403 HERO físico) — vide issue #6",
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
    de protocolo correlacionado, causa REAL de transporte ou TIMEOUT.

    Reports que não casam com o request (event assíncrono de outro
    software, outra feature, outro report type) são descartados como
    noise. O erro FAP pertence ao request original quando o report
    longo tem feature_index 0xFF e ecoa o byte function+sw do request
    (params[0]) — sem isso, erro assíncrono de outro request nunca é
    aceito. Máximo de 3 janelas de leitura para não esperar
    indefinidamente em endpoint mudo.

    A leitura usa o contrato tipado ReadOutcome: timeout do select é
    mudez (endpoint sem resposta); a causa REAL de acesso (device
    desconectado, permissão perdida, transporte quebrado) NÃO vira
    timeout — volta imediatamente em AckResult(kind=TRANSPORT_FAILURE)
    com o ReadOutcome original em `read_outcome`, para que o caller
    propague a causa exata."""
    import time

    deadline = time.monotonic() + 1.5
    for _ in range(3):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return AckResult(AckResultKind.TIMEOUT, timed_out=True)
        outcome = hid.read(FAP_REPORT_LENGTH, timeout=min(0.5, remaining))
        if outcome.is_timeout():
            continue
        if outcome.is_transport_failure():
            # Falha REAL de acesso durante a espera do ACK — a causa
            # exata volta ao caller (device sumiu entre write e ACK,
            # fd sem permissão, transporte quebrado). Não confundir
            # com mudez: não há dados ≠ device ausente.
            return AckResult(
                AckResultKind.TRANSPORT_FAILURE,
                read_outcome=outcome,
            )
        if outcome.data is None:
            continue
        raw = outcome.data
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
