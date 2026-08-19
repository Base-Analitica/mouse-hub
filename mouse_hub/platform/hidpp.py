"""Packets e mensagens do protocolo HID++ 2.0 (Logitech).

Modelo de protocolo conforme especificação pública:

* layout do kernel Linux (`drivers/hid/hid-logitech-hidpp.c`, copyright
  Logitech/Google/Red Hat):

    short report (7 bytes):
      byte 0 = report_id  (0x10 curto, 0x11 longo 20 bytes, 0x12 muito longo)
      byte 1 = device_index
      byte 2 = feature_index (FAP) ou sub_id (RAP)
      byte 3 = function (4 bits altos) + software_id (4 bits baixos)
      byte 4.. = parâmetros

* IRoot (feature 0x0000, sempre no feature index 0):
      GetFeature(fn 0): params [id_hi, id_lo, 0x00]
        → response [feature_index, flags, version]  (index 0 = não suportado)
      GetProtocolVersion/ping(fn 1): params [0x00, 0x00, ping_data]
        → response [major, target_sw, ping_data]

* Software ID: valor não-zero transportado no mesmo byte da função para
  correlacionar request e response e distinguir os próprios reports de
  eventos assíncronos de outros clientes (convenção Logitech: 0x00
  firmware, 0x01 receiver, 0x04 aplicação PC).

* Respostas espelham o request: mesmo (report_id, device_index,
  feature_index); erro de protocolo vem em report longo com
  feature_index == 0xFF (params [function, error_code]).

Este módulo NÃO abre descritores nem executa nada no sistema: é apenas
a modelagem da camada de mensagens, testável deterministicamente.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

# ── Constantes de frame ─────────────────────────────────────────────

SHORT_REPORT_ID = 0x10
LONG_REPORT_ID = 0x11

SHORT_REPORT_LENGTH = 7
LONG_REPORT_LENGTH = 20

# Erro de protocolo (feature_index) em report longo: params[0]=function,
# params[1]=código de erro HID++ 2.0 (INVALID_FEATURE_INDEX 0x06,
# INVALID_FUNCTION_ID 0x07, NOT_ALLOWED 0x05, UNSUPPORTED 0x09...).
PROTOCOL_ERROR_FEATURE_INDEX = 0xFF

# Erro RAP (HID++ 1.0) em report curto: sub_id.
RAP_ERROR_SUB_ID = 0x8F


# ── Feature IDs de referência ───────────────────────────────────────

class FeatureId:
    IROOT = 0x0000
    ADJUSTABLE_DPI = 0x2201


# ── Software ID ─────────────────────────────────────────────────────
# 0x00 firmware / 0x01 receiver / 0x04 aplicação de PC (convenção
# Logitech). O mouse_hub usa um ID próprio não-zero para poder
# distinguir os próprios ACKs de reports assíncronos de terceiros.
SOFTWARE_ID_MOUSE_HUB = 0x04


class SoftwareId:
    FIRMWARE = 0x00
    RECEIVER = 0x01
    MOUSE_HUB = 0x04


# ── Device index ────────────────────────────────────────────────────
# USB direto (dispositivo cabeado): device index 0x00, conforme a
# documentação pública Logitech do HID++ (conexão direta) e o emprego
# no kernel para dispositivos sem receiver. Pares em receiver Unifying
# usam 0x01..0x06 e o próprio receiver 0xFF.
DIRECT_USB_DEVICE_INDEX = 0x00


def encode_header(
    feature_index: int,
    function: int,
    device_index: int = DIRECT_USB_DEVICE_INDEX,
    software_id: int = SOFTWARE_ID_MOUSE_HUB,
) -> bytes:
    """Bytes 1..3 do frame FAP: device_index, feature_index,
    function + software_id."""
    if not (0 <= feature_index <= 0xFF and 0 <= function <= 0x0F
            and 0 <= device_index <= 0xFF and 0 <= software_id <= 0x0F):
        raise ValueError("campo de header fora da faixa 0..255/0..15")
    return bytes([device_index, feature_index, (function << 4) | software_id])


def build_short_report(
    feature_index: int,
    function: int,
    params: bytes = b"",
    device_index: int = DIRECT_USB_DEVICE_INDEX,
    software_id: int = SOFTWARE_ID_MOUSE_HUB,
) -> bytes:
    """Monta um short report (7 bytes) conforme o layout oficial."""
    if len(params) > SHORT_REPORT_LENGTH - 4:
        raise ValueError(
            f"params longo demais para short report ({len(params)} > 3)"
        )
    header = encode_header(feature_index, function, device_index, software_id)
    padded = (params + b"\x00" * 3)[:3]
    return bytes([SHORT_REPORT_ID, *header, *padded])


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


def is_protocol_error(raw: bytes) -> Optional[int]:
    """Código de erro HID++ 2.0 se o report é um erro de protocolo
    (feature_index == 0xFF em report longo), ou None."""
    header = ParsedResponseHeader.parse(raw)
    if header is None or len(raw) < 5:
        return None
    if header.feature_index != PROTOCOL_ERROR_FEATURE_INDEX:
        return None
    # report longo: params[0]=function, params[1]=error code
    return raw[5]


# ── Correlação request ↔ response ───────────────────────────────────

@dataclass(frozen=True)
class RequestKey:
    """Identidade completa de um request FAP, usada para validar o ACK.

    Um report recebido só confirma o request se coincidir em todos os
    campos: report_id, device_index, feature_index, function e
    software_id. Reports de outra feature, de outro software (outro
    aplicativo Logitech, firmware) ou eventos assíncronos são ignorados.
    """

    report_id: int
    device_index: int
    feature_index: int
    function: int
    software_id: int

    @staticmethod
    def from_short_request(
        feature_index: int,
        function: int,
        device_index: int = DIRECT_USB_DEVICE_INDEX,
        software_id: int = SOFTWARE_ID_MOUSE_HUB,
    ) -> "RequestKey":
        return RequestKey(
            report_id=SHORT_REPORT_ID,
            device_index=device_index,
            feature_index=feature_index,
            function=function,
            software_id=software_id,
        )


def matches_ack(response: bytes, request_key: RequestKey) -> bool:
    """True quando `response` é o ACK exato do request descrito por
    `request_key`. Qualquer divergência (outra feature, outra função,
    outro software_id, outro device index) = False."""
    header = ParsedResponseHeader.parse(response)
    if header is None:
        return False
    return (
        header.report_id == request_key.report_id
        and header.device_index == request_key.device_index
        and header.feature_index == request_key.feature_index
        and header.function == request_key.function
        and header.software_id == request_key.software_id
    )


# ── IRoot: entry point do dispositivo ───────────────────────────────

class RootFeature:
    """Wrapper da feature 0x0000 (sempre no feature index 0):
    GetFeature, GetProtocolVersion (ping) e validações."""

    FEATURE_INDEX = 0
    FN_GET_FEATURE = 0x00
    FN_GET_PROTOCOL_VERSION = 0x01

    def __init__(
        self,
        device_index: int = DIRECT_USB_DEVICE_INDEX,
        software_id: int = SOFTWARE_ID_MOUSE_HUB,
    ) -> None:
        self._device_index = device_index
        self._software_id = software_id

    # ── Builders de request ─────────────────────────────────────────

    def get_feature_request(self, feature_id: int) -> bytes:
        """IRoot.GetFeature(feature_id): params [id_hi, id_lo, 0x00].

        Response: byte 0 = feature_index (0 = feature não suportada,
        0xFF = erro de protocolo), byte 1 = flags, byte 2 = version.
        """
        return build_short_report(
            self.FEATURE_INDEX,
            self.FN_GET_FEATURE,
            params=bytes([(feature_id >> 8) & 0xFF, feature_id & 0xFF, 0x00]),
            device_index=self._device_index,
            software_id=self._software_id,
        )

    def get_feature_table_count_request(self) -> bytes:
        """Feature set 0x0001, fn 0 (GET_FEATURE_TABLE_COUNT): retorna
        o número de features da feature table do dispositivo.

        É um report curto comum (7 bytes) com feature_index=1 e fn=0 —
        não confundir com IRoot (index 0)."""
        return build_short_report(
            0x01,
            0x00,
            params=b"",
            device_index=self._device_index,
            software_id=self._software_id,
        )

    @staticmethod
    def parse_feature_table_count_response(raw: bytes) -> Optional[int]:
        """Response do GET_FEATURE_TABLE_COUNT: byte 4 = contagem de
        features."""
        if len(raw) < SHORT_REPORT_LENGTH:
            return None
        return int(raw[4])

    def protocol_version_request(self, ping_data: int = 0x55) -> bytes:
        return build_short_report(
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
        feature_index == 0 significa que o feature ID não é suportado."""
        if len(raw) < 7:
            return None
        return raw[4], raw[5], raw[6]

    @staticmethod
    def parse_protocol_version_response(raw: bytes) -> Optional[Tuple[int, int, int]]:
        """Response de GetProtocolVersion: (major, target_sw, ping_echo)."""
        if len(raw) < 7:
            return None
        return raw[4], raw[5], raw[6]

    def feature_request_key(self, feature_id: int) -> RequestKey:
        return RequestKey.from_short_request(
            self.FEATURE_INDEX,
            self.FN_GET_FEATURE,
            device_index=self._device_index,
            software_id=self._software_id,
        )

    def protocol_version_request_key(self, ping_data: int = 0x55) -> RequestKey:
        return RequestKey.from_short_request(
            self.FEATURE_INDEX,
            self.FN_GET_PROTOCOL_VERSION,
            device_index=self._device_index,
            software_id=self._software_id,
        )
