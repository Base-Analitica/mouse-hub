"""Packets e mensagens do protocolo HID++ 2.0 (Logitech).

Modelo de protocolo conforme fontes primárias:

* kernel Linux `drivers/hid/hid-logitech-hidpp.c` (copyright
  Logitech/Google/Red Hat), que define a implementação upstream de
  referência para Linux:

    REPORT_ID_HIDPP_SHORT  = 0x10, 7 bytes;
    REPORT_ID_HIDPP_LONG   = 0x11, 20 bytes;
    REPORT_ID_HIDPP_VERY_LONG = 0x12, até 64 bytes.

    "The RAP protocol uses both report types, whereas the FAP only uses
    HIDPP_LONG messages." — `hidpp_send_fap_command_sync` envia FAP
    sempre em LONG (0x11) e VERY_LONG quando params > 16 bytes;
    nunca em SHORT.

    Antes de enviar, `__hidpp_send_report` preenche
    `device_index = 0xff` — 0xFF é o valor do HID++ 2.0 para o
    dispositivo conectado diretamente (ou o receiver); em receivers
    Unifying os pares ocupam 0x01..0x06.

    O kernel define o próprio software ID como 0x01
    (`LINUX_KERNEL_SW_ID`) no nibble alto de `funcindex_clientid`,
    para correlacionar requests com respostas.

    * especificação pública HID++ 2.0 (docs Logitech/OpenLogi):

    report longo: [report_id 0x11][device_index 0xFF][feature_index]
                  [function 4b + software_id 4b][16 bytes params]

    IRoot (Feature ID 0x0000, feature index 0):
      GetFeature(fn 0): params [id_hi, id_lo, 0x00]
        → response params [feature_index, flags, version]
          (index 0 = feature não suportada)
      GetProtocolVersion(fn 1): params [0x00, 0x00, ping_data]
        → response params [major, target_sw, ping_echo]
        A confirmação exige major in (0x02, 0x04) e ping_echo ==
        ping_data enviado (kernel rejeita ping mismatch com -EPROTO).

    Erro FAP — layout conforme `hidpp_match_error` do kernel:

      [0x11][device_index][0xFF][feature_index do REQUEST]
      [function+sw do REQUEST][error_code][zeros...]

    O byte 3 do erro é o feature index ORIGINAL do request rejeitado,
    não 0xFF; por isso um erro de OUTRA feature (mesma ou diferente
    function) nunca casa com este request.

A única garantia de feature index que a especificação dá sem consulta:
IRoot (Feature ID 0x0000) está sempre no feature index 0. Para qualquer
outro Feature ID o índice REAL precisa ser descoberto via
IRoot.GetFeature — Feature ID NÃO é feature index (0x0001 é IFeatureSet,
não o index 1).

Este módulo NÃO abre descritores nem executa nada no sistema: é apenas
a modelagem da camada de mensagens, testável deterministicamente.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

# ── Constantes de frame ─────────────────────────────────────────────

SHORT_REPORT_ID = 0x10
LONG_REPORT_ID = 0x11
VERY_LONG_REPORT_ID = 0x12

SHORT_REPORT_LENGTH = 7
LONG_REPORT_LENGTH = 20

# FAP (Feature Access Protocol, HID++ 2.0) usa exclusivamente o report
# longo: LONG (0x11, até 16 bytes de params) ou VERY_LONG (0x12, para
# params maiores — não usado pelo Mouse Hub, param max = 4).
# Fonte: `hidpp_send_fap_command_sync` do kernel upstream
# (drivers/hid/hid-logitech-hidpp.c).
FAP_REPORT_ID = LONG_REPORT_ID
FAP_REPORT_LENGTH = LONG_REPORT_LENGTH

# Device index 0xFF é o valor HID++ para o dispositivo conectado
# diretamente (ou o receiver Unifying). O kernel upstream preenche
# `hidpp_report->device_index = 0xff` para TODOS os envios
# (`__hidpp_send_report`); o transport reescreve o índice apenas em
# devices pareados num receiver DJ. O G403 HERO cabeado é conectado
# direto — index 0xFF.
# Fontes: kernel upstream citado; documentação pública HID++ 2.0
# (device index 0xFF = corded device / receiver).
DEVICE_INDEX_DIRECT = 0xFF

# Feature index 0xFF em report longo indica erro de protocolo FAP.
#
# Fonte: `hidpp_match_error` do kernel upstream (drivers/hid/
# hid-logitech-hidpp.c) correlaciona o erro com o request por:
#
#   answer->fap.feature_index == HIDPP20_ERROR   (0xFF)
#   answer->fap.funcindex_clientid == question->fap.feature_index
#   answer->fap.params[0] == question->fap.funcindex_clientid
#
# Ou seja: no report de erro, o byte 3 carrega o feature index do
# request rejeitado (ECHO), o byte 4 carrega o function+software_id
# originais do request e o byte 5 carrega o error code real.
PROTOCOL_ERROR_FEATURE_INDEX = 0xFF

# Major versions devolvidos por IRoot.GetProtocolVersion (params[0]).
# 0x04 = HID++ 2.0; 0x02 = 2.0 "legacy" (HID++ 2.0 pré-estabilizado,
# aceito como 2.0 pelo kernel); 0x8F = HID++ 1.0 (fora do escopo).
# Fonte: driver upstream `hidpp_root_get_protocol_version` + docs
# Logitech/OpenLogi (IRoot protocol major).
VALID_PROTOCOL_MAJORS = (0x04, 0x02)

# Erro RAP (HID++ 1.0) em report curto: sub_id.
RAP_ERROR_SUB_ID = 0x8F

# Códigos de erro HID++ 2.0 (params[1] do report de erro).
class ErrorCode:
    UNKNOWN = 0x01
    INVALID_ARGS = 0x02
    OUT_OF_RANGE = 0x03
    HW_ERROR = 0x04
    NOT_ALLOWED = 0x05
    INVALID_FEATURE_INDEX = 0x06
    INVALID_FUNCTION_ID = 0x07
    BUSY = 0x08
    UNSUPPORTED = 0x09


# ── Feature IDs de referência ───────────────────────────────────────

class FeatureId:
    IROOT = 0x0000
    FEATURE_SET = 0x0001
    ADJUSTABLE_DPI = 0x2201


# ── Software ID ─────────────────────────────────────────────────────
# 0x00 firmware / 0x01 receiver / 0x04 aplicação de PC (convenção
# Logitech). O kernel usa 0x01; o mouse_hub usa 0x04 para distinguir
# os próprios ACKs de reports de outros clientes (driver, firmware).
SOFTWARE_ID_MOUSE_HUB = 0x04


class SoftwareId:
    FIRMWARE = 0x00
    RECEIVER = 0x01
    MOUSE_HUB = 0x04


def encode_header(
    feature_index: int,
    function: int,
    device_index: int = DEVICE_INDEX_DIRECT,
    software_id: int = SOFTWARE_ID_MOUSE_HUB,
) -> bytes:
    """Bytes 1..3 do frame FAP: device_index, feature_index,
    function + software_id."""
    if not (0 <= feature_index <= 0xFF and 0 <= function <= 0x0F
            and 0 <= device_index <= 0xFF and 0 <= software_id <= 0x0F):
        raise ValueError("campo de header fora da faixa 0..255/0..15")
    return bytes([device_index, feature_index, (function << 4) | software_id])


def build_long_report(
    feature_index: int,
    function: int,
    params: bytes = b"",
    device_index: int = DEVICE_INDEX_DIRECT,
    software_id: int = SOFTWARE_ID_MOUSE_HUB,
) -> bytes:
    """Monta um FAP long report (0x11, 20 bytes) conforme o layout do
    kernel upstream e a especificação HID++ 2.0: FAP nunca usa short
    report. Params além de 16 bytes exigiriam VERY_LONG (0x12)."""
    if len(params) > FAP_REPORT_LENGTH - 4:
        raise ValueError(
            f"params longo demais para FAP long report ({len(params)} > 16); "
            "usar VERY_LONG para payloads maiores"
        )
    header = encode_header(feature_index, function, device_index, software_id)
    padded = params + b"\x00" * (FAP_REPORT_LENGTH - 4 - len(params))
    return bytes([LONG_REPORT_ID, *header, *padded])


# ── Interpretação de response ───────────────────────────────────────

@dataclass(frozen=True)
class ParsedResponseHeader:
    report_id: int
    device_index: int
    feature_index: int
    function: int
    software_id: int

    @staticmethod
    def parse(raw: bytes) -> Optional["ParsedResponseHeader"]:
        if len(raw) < 4:
            return None
        return ParsedResponseHeader(
            report_id=raw[0],
            device_index=raw[1],
            feature_index=raw[2],
            function=(raw[3] >> 4) & 0x0F,
            software_id=raw[3] & 0x0F,
        )


def parse_protocol_error(
    raw: bytes,
    request_key: Optional["RequestKey"] = None,
) -> Optional[int]:
    """Código de erro FAP se `raw` é um report de erro de protocolo
    (report longo com feature_index == 0xFF): retorna o error code
    (params[1] = raw[5]); otherwise None.

    Com `request_key`, o erro SÓ é reconhecido se pertencer AO MESMO
    request (feature index e fn+sw ecoados no erro, conforme
    `hidpp_match_error` do kernel) — erro assíncrono de OUTRA feature
    nunca é atribuído ao request corrente."""
    header = ParsedResponseHeader.parse(raw)
    if header is None or len(raw) < 6:
        return None
    if header.report_id != LONG_REPORT_ID:
        return None
    if header.feature_index != PROTOCOL_ERROR_FEATURE_INDEX:
        return None
    if request_key is not None:
        if raw[3] != request_key.feature_index:
            return None
        if raw[4] != (request_key.function << 4 | request_key.software_id):
            return None
        if raw[1] != request_key.device_index:
            return None
    return raw[5]


# ── Correlação request ↔ response ───────────────────────────────────

@dataclass(frozen=True)
class RequestKey:
    """Identidade completa de um request FAP, usada para validar ACK e
    erro. Um report recebido só confirma o request (ACK ou erro
    correlacionado) quando coincide nos campos que o protocolo fornece.

    ACK: (report_id, device_index, feature_index, function, software_id)
    iguais ao request. Erro: report longo com feature_index 0xFF,
    params[0] == function+software_id do request e params[1] = código
    de erro — sem isso, erro assíncrono de OUTRO request não é aceito.
    """

    report_id: int
    device_index: int
    feature_index: int
    function: int
    software_id: int

    @staticmethod
    def from_long_request(
        feature_index: int,
        function: int,
        device_index: int = DEVICE_INDEX_DIRECT,
        software_id: int = SOFTWARE_ID_MOUSE_HUB,
    ) -> "RequestKey":
        return RequestKey(
            report_id=LONG_REPORT_ID,
            device_index=device_index,
            feature_index=feature_index,
            function=function,
            software_id=software_id,
        )


def matches_ack(response: bytes, request_key: RequestKey) -> bool:
    """True quando `response` é o ACK exato do request descrito por
    `request_key`. Qualquer divergência (outra feature, outra função,
    outro software_id, outro device index, outro report type) = False.
    Reports de erro (feature_index 0xFF) nunca são ACK."""
    header = ParsedResponseHeader.parse(response)
    if header is None:
        return False
    if header.feature_index == PROTOCOL_ERROR_FEATURE_INDEX:
        # Erro de protocolo nunca confirma o request.
        return False
    return (
        header.report_id == request_key.report_id
        and header.device_index == request_key.device_index
        and header.feature_index == request_key.feature_index
        and header.function == request_key.function
        and header.software_id == request_key.software_id
    )


def matches_protocol_error(response: bytes, request_key: RequestKey) -> bool:
    """True quando `response` é o erro FAP que pertence AO MESMO
    request. Conforme `hidpp_match_error` do kernel upstream, o erro
    correlaciona com o request por TRÊS campos:

    * feature_index (byte 3) == feature index do request;
    * params[0] (byte 4) == function+software_id do request;
    * report type longo (0x11) no mesmo device index.

    Um erro de OUTRA feature com a mesma function/sw NÃO casa (byte 3
    diverge) — regressão obrigatória: feature A rejeitada não pode ser
    atribuída ao request da feature B. Erros de outro report type ou
    outro device também são rejeitados."""
    if not response or len(response) < 6:
        return False
    if response[0] != LONG_REPORT_ID:
        return False
    if response[1] != request_key.device_index:
        return False
    if response[2] != PROTOCOL_ERROR_FEATURE_INDEX:
        return False
    # Byte 3: feature index ORIGINAL do request rejeitado (eco).
    if response[3] != request_key.feature_index:
        return False
    # Byte 4: function+sw originais do request rejeitado (eco).
    return response[4] == (request_key.function << 4 | request_key.software_id)


# ── Resultado tipado de leitura ─────────────────────────────────────
from mouse_hub.platform.read_outcome import ReadOutcomeKind  # noqa: E402

class AckResultKind(Enum):
    """Desfecho de uma janela de leitura FAP:

    * ACK              → resposta que confirma o request;
    * PROTOCOL_ERROR   → erro HID++ 2.0 correlacionado com o request
                         (device rejeitou o comando com código real);
    * TIMEOUT          → nenhuma resposta na janela (device mudo ou
                         response ainda não chegou);
    * TRANSPORT_FAILURE → causa REAL de acesso durante a leitura
                         (device desconectado, permissão perdida ou
                         transporte quebrado) — NUNCA confunde com
                         TIMEOUT: não há dados ≠ device ausente.
    Reports que não casam com o request (event assíncrono de outro
    software, outra feature) são descartados como noise — não são
    nenhum destes.
    """

    ACK = "ack"
    PROTOCOL_ERROR = "protocol_error"
    TIMEOUT = "timeout"
    TRANSPORT_FAILURE = "transport_failure"


@dataclass(frozen=True)
class AckResult:
    kind: AckResultKind
    # ACK: resposta completa (long, 20 bytes).
    response: Optional[bytes] = None
    # PROTOCOL_ERROR: error code do params[1] (None se não parseável).
    error_code: Optional[int] = None
    # TIMEOUT: True.
    timed_out: bool = False
    # TRANSPORT_FAILURE: ReadOutcome real (None nos demais casos).
    read_outcome: Optional[object] = None


# ── IRoot: entry point do dispositivo ───────────────────────────────

class RootFeature:
    """Wrapper da feature 0x0000 (sempre no feature index 0):
    GetFeature e GetProtocolVersion (ping).

    Os builders emitem FAP em LONG (0x11) — nunca short, conforme o
    driver upstream. A única garantia de index da especificação é a de
    IRoot (index 0); para qualquer outro Feature ID use GetFeature e
    nunca deduza index a partir de Feature ID.
    """

    FEATURE_INDEX = 0
    FN_GET_FEATURE = 0x00
    FN_GET_PROTOCOL_VERSION = 0x01

    def __init__(
        self,
        device_index: int = DEVICE_INDEX_DIRECT,
        software_id: int = SOFTWARE_ID_MOUSE_HUB,
    ) -> None:
        self._device_index = device_index
        self._software_id = software_id

    # ── Builders de request ─────────────────────────────────────────

    def get_feature_request(self, feature_id: int) -> bytes:
        """IRoot.GetFeature(feature_id): params [id_hi, id_lo, 0x00].

        Response: params [feature_index, flags, version] — index 0
        significa feature não suportada; index 0xFF com error code em
        params[1] é erro de protocolo (parse com
        matches_protocol_error/parse_protocol_error)."""
        return build_long_report(
            self.FEATURE_INDEX,
            self.FN_GET_FEATURE,
            params=bytes([(feature_id >> 8) & 0xFF, feature_id & 0xFF, 0x00]),
            device_index=self._device_index,
            software_id=self._software_id,
        )

    def protocol_version_request(self, ping_data: int = 0x5A) -> bytes:
        """IRoot.GetProtocolVersion (fn 1): params [0x00, 0x00, ping].

        O kernel upstream usa ping 0x5A; qualquer valor de 1 byte
        serve — o dispositivo ecoa em params[2]."""
        return build_long_report(
            self.FEATURE_INDEX,
            self.FN_GET_PROTOCOL_VERSION,
            params=bytes([0x00, 0x00, ping_data & 0xFF]),
            device_index=self._device_index,
            software_id=self._software_id,
        )

    # ── Interpretação de response ───────────────────────────────────

    @staticmethod
    def parse_get_feature_response(raw: bytes) -> Optional[Tuple[int, int, int]]:
        """Response de GetFeature: (feature_index, flags, version).
        feature_index == 0 significa que o feature ID não é suportado.
        Chamar apenas após confirmar o header com matches_ack."""
        if len(raw) < FAP_REPORT_LENGTH:
            return None
        return raw[4], raw[5], raw[6]

    @staticmethod
    def parse_protocol_version_response(
        raw: bytes,
    ) -> Optional[Tuple[int, int, int]]:
        """Response de GetProtocolVersion: (major, target_sw,
        ping_echo)."""
        if len(raw) < FAP_REPORT_LENGTH:
            return None
        return raw[4], raw[5], raw[6]

    @staticmethod
    def is_protocol_version_confirmed(
        raw: bytes, ping_data: int = 0x5A
    ) -> bool:
        """True quando a resposta confirma HID++ 2.0 de verdade:

        * major in (0x02, 0x04) — 0x8F é HID++ 1.0 e não serve;
        * ping_echo (params[2]) == ping_data enviado.

        O kernel upstream valida exatamente o ping (ping mismatch →
        -EPROTO) e trata major 0x02 e 0x04 como 2.0.
        Fonte: `hidpp_root_get_protocol_version` upstream."""
        parsed = RootFeature.parse_protocol_version_response(raw)
        if parsed is None:
            return False
        major, _target_sw, ping_echo = parsed
        return major in VALID_PROTOCOL_MAJORS and ping_echo == (ping_data & 0xFF)

    def get_feature_request_key(self) -> RequestKey:
        return RequestKey.from_long_request(
            self.FEATURE_INDEX,
            self.FN_GET_FEATURE,
            device_index=self._device_index,
            software_id=self._software_id,
        )

    def protocol_version_request_key(self, ping_data: int = 0x5A) -> RequestKey:
        return RequestKey.from_long_request(
            self.FEATURE_INDEX,
            self.FN_GET_PROTOCOL_VERSION,
            device_index=self._device_index,
            software_id=self._software_id,
        )


# ── Adjustable DPI (0x2201) ─────────────────────────────────────────
# O feature INDEX usado em runtime é descoberto via IRoot.GetFeature
# (não é o Feature ID). SetSensorDPI usa function 3 (nibble) e o
# report FAP longo.

SET_SENSOR_DPI_FUNCTION = 0x03
