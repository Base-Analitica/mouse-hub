"""Suíte da camada de protocolo HID++ 2.0 (`mouse_hub.platform.hidpp`).

Cobre o contrato do wire format contra as fontes primárias:

* FAP long report 0x11 de 20 bytes;
* device index 0xFF para dispositivo conectado diretamente;
* erro FAP conforme `hidpp_match_error` do driver upstream
  (`hid-logitech-hidpp.c`): byte 3 = feature index do request
  REJEITADO, byte 4 = function+sw do request, byte 5 = error code;
* GetProtocolVersion exige major válido (0x04 ou 0x02) E o echo do
  ping (params[2] == 0x5A);
* request e response são correlacionados pelo header completo.

Nenhum hardware real é necessário: os reports são construídos pela
própria camada de protocolo e verificados bit a bit.
"""

from __future__ import annotations

import pytest

from mouse_hub.platform.hidpp import (
    DEVICE_INDEX_DIRECT,
    FAP_REPORT_LENGTH,
    LONG_REPORT_ID,
    PROTOCOL_ERROR_FEATURE_INDEX,
    RequestKey,
    RootFeature,
    SoftwareId,
    build_long_report,
    matches_ack,
    matches_protocol_error,
    parse_protocol_error,
)

DPI_FEATURE_INDEX = 0x01
SET_FN = 0x03
SW_ID = SoftwareId.MOUSE_HUB


def _request() -> bytes:
    return build_long_report(
        DPI_FEATURE_INDEX,
        SET_FN,
        params=bytes([0x00, 0x03, 0x20]),
        device_index=DEVICE_INDEX_DIRECT,
        software_id=SW_ID,
    )


# ── Formato dos packets ─────────────────────────────────────────────


def test_long_report_layout() -> None:
    """O report FAP é LONG (0x11, 20 bytes) com o header oficial:
    [report_id][device_index][feature_index][fn+sw][params...]."""
    report = _request()
    assert len(report) == FAP_REPORT_LENGTH
    assert report[0] == LONG_REPORT_ID
    assert report[1] == DEVICE_INDEX_DIRECT
    assert report[2] == DPI_FEATURE_INDEX
    assert (report[3] >> 4) & 0x0F == SET_FN
    assert report[3] & 0x0F == SW_ID
    assert (report[5] << 8) | report[6] == 0x0320


def test_out_of_range_is_value_error_not_bad_report() -> None:
    """Parâmetros fora de faixa NÃO geram report inválido — ValueError
    explícito: o caller nunca escreve garbage no bus."""
    with pytest.raises(ValueError):
        build_long_report(0x01, 0x20, device_index=DEVICE_INDEX_DIRECT)
    with pytest.raises(ValueError):
        build_long_report(0x100, 0x03, device_index=DEVICE_INDEX_DIRECT)
    with pytest.raises(ValueError):
        build_long_report(-1, 0x03, device_index=DEVICE_INDEX_DIRECT)


# ── ACK e correlação ────────────────────────────────────────────────


def test_ack_matches_request_header() -> None:
    key = RequestKey.from_long_request(
        DPI_FEATURE_INDEX, SET_FN,
        device_index=DEVICE_INDEX_DIRECT,
        software_id=SW_ID,
    )
    # ACK ecoa o header completo com params zerados (conferência).
    ack = (
        bytes([LONG_REPORT_ID, DEVICE_INDEX_DIRECT, DPI_FEATURE_INDEX,
               (SET_FN << 4) | SW_ID])
        + b"\x00" * (FAP_REPORT_LENGTH - 4)
    )
    assert matches_ack(ack, key)


def test_ack_with_other_feature_is_rejected() -> None:
    """Resposta da MESMA função em OUTRA feature não casa com o
    request — a correlação exige o feature index original."""
    key = RequestKey.from_long_request(
        DPI_FEATURE_INDEX, SET_FN,
        device_index=DEVICE_INDEX_DIRECT,
        software_id=SW_ID,
    )
    wrong_feature = (
        bytes([LONG_REPORT_ID, DEVICE_INDEX_DIRECT, 0x02,
               (SET_FN << 4) | SW_ID])
        + b"\x00" * (FAP_REPORT_LENGTH - 4)
    )
    assert not matches_ack(wrong_feature, key)


def test_ack_with_other_software_id_is_rejected() -> None:
    """Header ecoando sw_id de outro cliente não confirma o comando —
    é a resposta de outro software no mesmo bus."""
    key = RequestKey.from_long_request(
        DPI_FEATURE_INDEX, SET_FN,
        device_index=DEVICE_INDEX_DIRECT,
        software_id=SW_ID,
    )
    wrong_sw = (
        bytes([LONG_REPORT_ID, DEVICE_INDEX_DIRECT, DPI_FEATURE_INDEX,
               (SET_FN << 4) | 0x01])
        + b"\x00" * (FAP_REPORT_LENGTH - 4)
    )
    assert not matches_ack(wrong_sw, key)


def test_error_report_from_other_feature_is_rejected() -> None:
    """Regressão de `hidpp_match_error`: o erro FAP do kernel carrega o
    feature index do request rejeitado no byte 3 — o erro de OUTRA
    feature (mesma fn+sw) nunca casa com este request."""
    key = RequestKey.from_long_request(
        DPI_FEATURE_INDEX, SET_FN,
        device_index=DEVICE_INDEX_DIRECT,
        software_id=SW_ID,
    )
    error_other_feature = bytes([
        LONG_REPORT_ID,
        DEVICE_INDEX_DIRECT,
        PROTOCOL_ERROR_FEATURE_INDEX,
        0x02,  # feature index diferente do request
        (SET_FN << 4) | SW_ID,
        0x06,  # INVALID_FEATURE_INDEX
    ]) + b"\x00" * (FAP_REPORT_LENGTH - 6)
    assert not matches_protocol_error(error_other_feature, key)
    assert parse_protocol_error(error_other_feature, key) is None


def test_error_report_matches_own_request() -> None:
    """Erro FAP do próprio request: bytes 3-4 ecoam feature index e
    fn+sw originais, byte 5 carrega o error code real."""
    key = RequestKey.from_long_request(
        DPI_FEATURE_INDEX, SET_FN,
        device_index=DEVICE_INDEX_DIRECT,
        software_id=SW_ID,
    )
    error = bytes([
        LONG_REPORT_ID,
        DEVICE_INDEX_DIRECT,
        PROTOCOL_ERROR_FEATURE_INDEX,
        DPI_FEATURE_INDEX,  # eco do feature index do request
        (SET_FN << 4) | SW_ID,  # eco de fn+sw
        0x02,  # INVALID_ARGS
    ]) + b"\x00" * (FAP_REPORT_LENGTH - 6)
    assert matches_protocol_error(error, key)
    assert parse_protocol_error(error, key) == 0x02


def test_error_report_with_wrong_header_is_rejected() -> None:
    """Erro com header não-ecoado (outro device index) é noise — o
    kernel também exige device_index igual."""
    key = RequestKey.from_long_request(
        DPI_FEATURE_INDEX, SET_FN,
        device_index=DEVICE_INDEX_DIRECT,
        software_id=SW_ID,
    )
    error = bytes([
        LONG_REPORT_ID,
        0x01,  # device index diferente
        PROTOCOL_ERROR_FEATURE_INDEX,
        DPI_FEATURE_INDEX,
        (SET_FN << 4) | SW_ID,
        0x02,
    ]) + b"\x00" * (FAP_REPORT_LENGTH - 6)
    assert not matches_protocol_error(error, key)


def test_error_report_wrong_report_type_is_rejected() -> None:
    """Erro em report 0x10 (short) não casa — FAP só usa long."""
    key = RequestKey.from_long_request(
        DPI_FEATURE_INDEX, SET_FN,
        device_index=DEVICE_INDEX_DIRECT,
        software_id=SW_ID,
    )
    error = bytes([
        0x10,  # short report: não é erro FAP válido
        DEVICE_INDEX_DIRECT,
        PROTOCOL_ERROR_FEATURE_INDEX,
        DPI_FEATURE_INDEX,
        (SET_FN << 4) | SW_ID,
        0x02,
    ]) + b"\x00" * (FAP_REPORT_LENGTH - 6)
    assert not matches_protocol_error(error, key)


# ── GetProtocolVersion ──────────────────────────────────────────────


def test_protocol_version_request_layout() -> None:
    """O ping IRoot desta camada usa long report 0x11 com os params
    [0x00, 0x00, ping] — o header ecoa IRoot/fn1, e o ping é validado
    no echo. O wire format completo é idêntico ao de qualquer outro
    request IRoot (o kernel também valida eco do ping)."""
    root = RootFeature()
    req = root.protocol_version_request()
    assert len(req) == FAP_REPORT_LENGTH
    assert req[0] == LONG_REPORT_ID
    assert req[1] == DEVICE_INDEX_DIRECT
    assert req[2] == 0x00  # IRoot
    assert (req[3] >> 4) & 0x0F == 0x01  # fn GetProtocolVersion
    assert req[6] == 0x5A  # ping


def test_protocol_version_confirmed_hidpp2() -> None:
    """Major 0x04/0x02 = HID++ 2.0 confirmado; qualquer outro major
    (0x8F = HID++ 1.0, 0x00, inválido) não confirma — o device não é
    controlável pelo FAP."""
    for major, ok in ((0x04, True), (0x02, True), (0x01, False),
                      (0x8F, False), (0x00, False), (0x03, False)):
        response = bytes([LONG_REPORT_ID, DEVICE_INDEX_DIRECT, 0x00, 0x01,
                          major, 0x02, 0x5A]) + b"\x00" * 13
        assert RootFeature.is_protocol_version_confirmed(response) is ok, \
            f"major {major:#04x}"


def test_protocol_version_ping_mismatch_is_rejected() -> None:
    """Ping echo divergente = o response não pertence ao nosso request
    (kernel: -EPROTO). Mesmo com major correto."""
    response = bytes([LONG_REPORT_ID, DEVICE_INDEX_DIRECT, 0x00, 0x01,
                      0x04, 0x02, 0x01]) + b"\x00" * 13
    assert not RootFeature.is_protocol_version_confirmed(response)


def test_get_feature_response_parsed_dynamically() -> None:
    """GetFeature(0x2201) devolve o feature index real — o core nunca
    assume index; a camada apenas decodifica."""
    response = bytes([LONG_REPORT_ID, DEVICE_INDEX_DIRECT, 0x00,
                      0x00, 0x07, 0x00, 0x03]) + b"\x00" * 13
    parsed = RootFeature.parse_get_feature_response(response)
    assert parsed is not None
    assert parsed[0] == 0x07  # index descoberto, não hardcoded
    assert parsed[1] == 0x00  # feature flags
    assert parsed[2] == 3     # version
