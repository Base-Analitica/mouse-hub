"""Fakes de hardware para a suíte de testes.

Permitem testar o core inteiro (descoberta, DPI, sensibilidade,
capabilities, controller) sem um G403 real, sem /dev/hidraw e sem
subprocess. Não há nenhum sucesso falso possível: cada fake registra
exatamente o que "aplicou" e sob quais condições falha.

O FakeHidAccess implementa uma máquina de protocolo HID++ 2.0 mínima
porém correta, conforme o driver upstream do kernel:

* FAP SEMPRE em LONG report 0x11 de 20 bytes (o kernel não usa short
  para FAP);
* device index 0xFF para dispositivo conectado diretamente (G403
  cabeado);
* as respostas são COMPUTADAS a partir do request, espelhando o header
  (device_index, feature_index, function+software_id) — o core valida o
  eco do header como manda o protocolo;
* erros FAP saem conforme `hidpp_match_error` do kernel upstream:
  report longo com feature_index 0xFF no byte 2, o feature index do
  request rejeitado ECHOADO no byte 3, function+sw do request no
  byte 4 e o error code no byte 5 — o fake correlaciona o erro ao
  request como o dispositivo real faz.

Cenários configuráveis:

* open_permission_denied / open_raises → desfecho real de abertura;
* dpi_feature_index → feature index que IRoot.GetFeature(0x2201)
  devolve (0 = feature ausente; erro configurado → report FAP error);
* ifeatureset_index → o index real da IFeatureSet devolvido por
  GetFeature(0x0001) — NÃO é 0x01 hardcoded, como o core não deve
  assumir;
* sw_id_wrong / async_noise → reports de terceiros e eventos assíncronos
  que NÃO confirmam request (o core deve rejeitá-los);
* ack_timeout → o endpoint silencia na resposta;
* readback_mode → "echo" devolve o eco do SetSensorDPI com o valor
  aplicado, "none" devolve None (sem readback).
"""

from __future__ import annotations

from typing import List, Optional

from mouse_hub.core.operation import OperationResult, OperationStatus
from mouse_hub.platform.read_outcome import ReadOutcome, ReadOutcomeKind

# Knob write_failure_status → OperationStatus real: "device_not_found"
# (hot-unplug), "permission_denied", "failed" (genérico).
_WRITE_FAILURE_STATUS = {
    "device_not_found": OperationStatus.DEVICE_NOT_FOUND,
    "permission_denied": OperationStatus.PERMISSION_DENIED,
    "failed": OperationStatus.FAILED,
}
# Knob read_failure_status → ReadOutcome real: "device_not_found"
# (hot-unplug), "permission_denied", "failed" (genérico) — o core
# propaga a causa exata em vez de tratar como mudez.
_READ_FAILURE_OUTCOME = {
    "device_not_found": ReadOutcome.device_not_found(
        "simulated hot-unplug on read"
    ),
    "permission_denied": ReadOutcome.permission_denied(
        "simulated permission loss on read"
    ),
    "failed": ReadOutcome.failed("simulated transport failure on read"),
}
from mouse_hub.platform.hidpp import (
    FAP_REPORT_LENGTH,
    LONG_REPORT_ID,
    PROTOCOL_ERROR_FEATURE_INDEX,
    RootFeature,
    SoftwareId,
)
from mouse_hub.platform.protocol import HidAccess, MouseDevice, SystemInput

# Feature IDs — os indexes reais são descobertos via GetFeature, nunca
# deduzidos do Feature ID.
ROOT_FEATURE_INDEX = 0x00
ROOT_FN_GET_FEATURE = 0x00
ROOT_FN_GET_PROTOCOL_VERSION = 0x01
DPI_FN_SET = 0x03
GET_SENSOR_DPI_FN = 0x00
ADJUSTABLE_DPI_FEATURE_ID = 0x2201
FEATURE_SET_FEATURE_ID = 0x0001


class FakeHidAccess(HidAccess):
    """HidAccess controlável em teste, com máquina de protocolo HID++ 2.0.

    Requests e responses usam FAP em LONG report 0x11 (20 bytes) com
    device index 0xFF (USB direto), conforme o driver upstream — o fake
    responde ao que o core escreve, preservando nas respostas o que o
    request trouxe (eco de header), para que o core valide o eco como
    manda o protocolo.
    """

    def __init__(self) -> None:
        # Abertura
        self.open_permission_denied: bool = False
        self.open_raises: Optional[BaseException] = None
        # Feature Adjustable DPI: feature index devolvido por
        # IRoot.GetFeature(0x2201). 0 = feature ausente; -1 = o
        # dispositivo rejeita o GetFeature com erro de protocolo.
        self.dpi_feature_index: int = 1
        # O index real da IFeatureSet (GetFeature 0x0001) — o core não
        # pode assumir 0x01; o fake expõe qualquer valor.
        self.ifeatureset_index: int = 0x05
        # IFeatureSet.GetFeatureCount (fn 1): quantas features o device
        # anuncia. -1 = não implementado (device devolve erro NOT_ALLOWED).
        self.ifeatureset_count: int = 6
        # Rejeição do probe em GetFeature(0x2201) com erro FAP
        # correlacionado. probe_stage2_error_code especifica o código
        # real (ex.: 0x06 INVALID_FEATURE_INDEX; 0x08 BUSY; 0x09
        # UNSUPPORTED — tratado como feature ausente pelo core).
        self.probe_stage2_error: bool = False
        self.probe_stage2_error_code: int = 0x06
        # GetProtocolVersion: major devolvido (params[0]). 0x04 =
        # HID++ 2.0; 0x02 = 2.0 legacy; 0x8F = HID++ 1.0; valores
        # desconhecidos não confirmam o protocolo.
        self.protocol_major: int = 0x04
        # GetProtocolVersion: ping_echo (params[2]) diverge do ping
        # enviado — o kernel trata como ping mismatch (-EPROTO).
        self.wrong_ping_echo: bool = False
        self.ping_echo: Optional[int] = None
        # Software ID errado nas respostas: o header ecoa um sw_id de
        # outro cliente — o core deve tratar como não-ACK.
        self.sw_id_wrong: bool = False
        self.wrong_sw_id: int = 0x01
        # Eventos assíncronos de outro software injetados na fila de
        # respostas (ex.: event de report rate de outro aplicativo)
        # antes de qualquer resposta esperada.
        self.async_noise: List[bytes] = []
        # Confirmação: endpoint mudo até o fim da janela.
        self.ack_timeout: bool = False
        # Falha de transporte na escrita (fd sumiu, write falhou no OS):
        # o controller deve tratar como FAILED antes de assumir sucesso.
        self.write_succeeds: bool = True
        # Hot-unplug SIMULADO após open OK: write retorna uma causa REAL
        # específica em vez de sucesso — DEVICE_NOT_FOUND (device sumiu
        # entre open e write), PERMISSION_DENIED (fd perdeu permissão)
        # ou FAILED (genérico). É o desfecho determinístico do
        # hot-unplug pós-open: o controller deve propagar a causa exata.
        self.write_failure_status: Optional[str] = None
        # Knob pontual: writeFailureStatus é GLOBAL (afeta TODOS os
        # writes). write_failure_at limita o efeito a UMA operação
        # (N-ésimo write == 1): para testar o SEGUNDO write do probe
        # (GetFeature) sem afetar o primeiro (GetProtocolVersion).
        self.write_failure_at: Optional[int] = None
        self._write_counter: int = 0
        # Leitura com causa REAL de transporte (fake do contrato
        # ReadOutcome): read_failure_status ativa a falha; read_failure_at
        # a limita ao N-ésimo read (determinístico). Hot-unplug entre o
        # write do SetSensorDPI e o read do ACK é o caso típico.
        self.read_failure_status: Optional[str] = None
        self.read_failure_at: Optional[int] = None
        self._read_counter: int = 0
        # DPI aplicado
        self.dpi_set_rejected: bool = False
        # Rejeita o SetSensorDPI com erro FAP 0x09 (UNSUPPORTED) em
        # vez de erro RAP curto — para cobrir a correlação de erros FAP.
        self.dpi_set_fap_error: bool = False
        # Readback: "echo" devolve o eco do último SetSensorDPI com o
        # valor aplicado; "none" devolve None.
        self.readback_mode: str = "echo"
        self.query_count: int = 0
        self._opened: List[MouseDevice] = []
        self._device: Optional[MouseDevice] = None
        self.written_reports: List[bytes] = []
        self._last_set_dpi: Optional[int] = None
        # Fila FIFO de responses pré-programadas (para cenários que a
        # computação não cobre). Cada read consome uma entrada.
        self.probe_responses: List[bytes] = []
        # Contexto do último request do handle aberto (eco de header):
        # descartado no close — read de outro handle não responde a
        # request antigo.
        self._last_request: Optional[dict] = None

    # ── Lifecycle ─────────────────────────────────────────────────

    def open(self, device: MouseDevice) -> OperationResult:
        self._opened.append(device)
        if device.hidraw_path is None:
            return OperationResult.device_not_found(device.hidraw_path)
        if (
            device.hidraw_path.startswith("/dev/permission_denied")
            or self.open_permission_denied
        ):
            return OperationResult.permission_denied(device.hidraw_path)
        if self.open_raises is not None:
            raise self.open_raises
        self._device = device
        return OperationResult.applied(device.hidraw_path)

    def is_open(self) -> bool:
        return self._device is not None

    def close(self) -> None:
        self._device = None
        # Contexto novo: descartar o request pendente do handle que
        # fechou — o read do novo handle não pode responder a request
        # de um descritor que já fechou.
        self._last_request = None
        self._last_set_dpi = None

    # ── Protocolo ─────────────────────────────────────────────────

    def _parse_request(self, report: bytes) -> Optional[dict]:
        """Header de request FAP: [report_id][device_index]
        [feature_index][fn+sw_id][params...]. Retorna os campos."""
        if len(report) < 4:
            return None
        return {
            "report_id": report[0],
            "device_index": report[1],
            "feature_index": report[2],
            "function": (report[3] >> 4) & 0x0F,
            "software_id": report[3] & 0x0F,
            "params": report[4:],
        }

    def _echo_response(self, req: dict, params: bytes) -> bytes:
        """Resposta espelhando o header do request, conforme o
        protocolo: mesmos report_id, device_index, feature_index e
        function+software_id (o próprio sw_id ou o de outro cliente,
        se configurado). Report LONG de 20 bytes."""
        if self.sw_id_wrong:
            fn_sw = (req["function"] << 4) | self.wrong_sw_id
        else:
            fn_sw = (req["function"] << 4) | req["software_id"]
        payload = (
            bytes([req["report_id"], req["device_index"],
                   req["feature_index"], fn_sw])
            + params
        )
        return (payload + b"\x00" * (FAP_REPORT_LENGTH - len(payload)))[:FAP_REPORT_LENGTH]

    def _fap_error(self, req: dict, error_code: int) -> bytes:
        """Erro FAP 2.0 conforme `hidpp_match_error` do kernel
        upstream: report LONG com

        [0x11][device_index][0xFF][feature_index DO REQUEST]
        [function+sw DO REQUEST][error_code][zeros...]

        O byte 3 ecoa o feature index do request rejeitado — por isso
        o erro de OUTRA feature nunca casa com este request
        (matches_protocol_error exige os três campos)."""
        fn_sw = (req["function"] << 4) | req["software_id"]
        payload = bytes([
            req["report_id"],
            req["device_index"],
            PROTOCOL_ERROR_FEATURE_INDEX,
            req["feature_index"],  # feature index do request (eco)
            fn_sw,                  # function+sw do request (eco)
            error_code,             # error code real
        ])
        return (payload + b"\x00" * (FAP_REPORT_LENGTH - len(payload)))[:FAP_REPORT_LENGTH]

    def write(self, report: bytes) -> OperationResult:
        self._write_counter += 1
        if not self.is_open():
            return OperationResult.failed("no open descriptor")
        # write_failure_at: falha pontual (N-ésimo write); caso geral
        # (todos os writes) permanece em write_failure_status.
        if (
            self.write_failure_status is not None
            and (self.write_failure_at is None
                 or self._write_counter == self.write_failure_at)
        ):
            # Hot-unplug/transport failure tipado: DEVICE_NOT_FOUND
            # (device sumiu), PERMISSION_DENIED (fd sem permissão) ou
            # FAILED (genérico) — o caller PRESERVA a causa real.
            return OperationResult(
                _WRITE_FAILURE_STATUS[self.write_failure_status],
                "simulated write failure: " + self.write_failure_status,
            )
        if not self.write_succeeds:
            raise OSError("simulated write failure on hidraw")
        self.written_reports.append(report)
        req = self._parse_request(report)
        if req is None:
            return OperationResult.failed("report sem cabeçalho HID++")
        if req["report_id"] != LONG_REPORT_ID:
            # FAP só usa long report; o fake não responde a short
            # report (mudo, como o device real faria).
            return OperationResult.applied("request aceito pelo endpoint")
        self._last_request = req
        return OperationResult.applied("request aceito pelo endpoint")

    def read(self, length: int, timeout: float = 0.5) -> ReadOutcome:
        self.query_count += 1
        self._read_counter += 1
        # Falha REAL de transporte na leitura (hot-unplug entre o
        # write e o read, permissão perdida, transporte quebrado):
        # read_failure_status define a causa; read_failure_at a
        # limita ao N-ésimo read.
        if (
            self.read_failure_status is not None
            and (self.read_failure_at is None
                 or self._read_counter == self.read_failure_at)
        ):
            return _READ_FAILURE_OUTCOME[self.read_failure_status]
        if not self.is_open():
            return ReadOutcome.timeout("handle fechado no fake")
        if self.ack_timeout:
            return ReadOutcome.timeout()

        # Noise assíncrono primeiro: events de outro software que a
        # função consumidora deve ignorar (não são ACK).
        if self.async_noise:
            return ReadOutcome.from_data(self.async_noise.pop(0))

        # Responses pré-programadas têm precedência explícita.
        if self.probe_responses:
            return ReadOutcome.from_data(self.probe_responses.pop(0))

        # Sem header de request válido: endpoint mudo.
        if self._last_request is None:
            return ReadOutcome.timeout()
        req = dict(self._last_request)

        # ── IRoot (feature index 0x00) ──────────────────────────────
        if req["feature_index"] == ROOT_FEATURE_INDEX:
            if req["function"] == ROOT_FN_GET_PROTOCOL_VERSION:
                # [major, target_sw, ping_echo] — configurable por
                # teste para cobrir major 0x02/0x04/0x8F/desconhecido,
                # ping mismatch e ping correto (default = eco).
                if self.wrong_ping_echo and self.ping_echo is None:
                    ping_echo = (req["params"][2] + 1) % 256 \
                        if len(req["params"]) >= 3 else 0x00
                elif self.ping_echo is not None:
                    ping_echo = self.ping_echo
                else:
                    ping_echo = req["params"][2] \
                        if len(req["params"]) >= 3 else 0x5A
                return ReadOutcome.from_data(self._echo_response(
                    req, bytes([self.protocol_major, 0x02, ping_echo])
                ))
            if req["function"] == ROOT_FN_GET_FEATURE:
                if len(req["params"]) < 3:
                    return ReadOutcome.timeout()
                feature_id = (req["params"][0] << 8) | req["params"][1]
                # GetFeature(ADJUSTABLE_DPI) rejeitado pelo device?
                if (
                    feature_id == ADJUSTABLE_DPI_FEATURE_ID
                    and self.probe_stage2_error
                ):
                    # Erro FAP correlacionado com o código configurado
                    # (0x06 INVALID_FEATURE_INDEX, 0x08 BUSY etc.) — o
                    # layout ecoa feature index e fn+sw do request.
                    return ReadOutcome.from_data(self._fap_error(
                        req, self.probe_stage2_error_code
                    ))
                if feature_id == ADJUSTABLE_DPI_FEATURE_ID:
                    return ReadOutcome.from_data(self._echo_response(
                        req, bytes([self.dpi_feature_index, 0x00, 0x03]),
                    ))
                if feature_id == FEATURE_SET_FEATURE_ID:
                    # Index real da IFeatureSet: o core NUNCA assume 0x01.
                    return ReadOutcome.from_data(self._echo_response(
                        req, bytes([self.ifeatureset_index, 0x00, 0x03]),
                    ))
                # Feature ID desconhecida → não suportada (index 0).
                return ReadOutcome.from_data(self._echo_response(
                    req, bytes([0x00, 0x00, 0x00])
                ))
            return ReadOutcome.from_data(self._echo_response(
                req, bytes([0x00, 0x00, 0x00])
            ))

        # ── IFeatureSet ─────────────────────────────────────────────
        if req["feature_index"] == self.ifeatureset_index \
                and self.ifeatureset_count >= 0:
            if req["function"] == 0x01:  # GetFeatureCount
                return ReadOutcome.from_data(self._echo_response(
                    req, bytes([self.ifeatureset_count, 0x00, 0x00])
                ))
            if req["function"] == 0x00:  # GetFeatureId(index)
                idx = req["params"][0] if req["params"] else 0
                ids = {0: ROOT_FEATURE_INDEX, self.ifeatureset_count - 1: 0x2201}
                fid = ids.get(idx, 0x0000)
                return ReadOutcome.from_data(self._echo_response(
                    req, bytes([(fid >> 8) & 0xFF, fid & 0xFF, 0x03])
                ))

        # ── Adjustable DPI (feature index descoberto) ───────────────
        if (
            req["feature_index"] == self.dpi_feature_index
            and self.dpi_feature_index not in (None, 0)
        ):
            if req["function"] == GET_SENSOR_DPI_FN:  # GetSensorDPI
                return ReadOutcome.from_data(self._echo_response(
                    req, bytes([
                        0x00,  # sensor index
                        ((self._last_set_dpi or 0) >> 8) & 0xFF,
                        (self._last_set_dpi or 0) & 0xFF,
                        0x00,  # reserved
                    ]),
                ))
            if req["function"] == DPI_FN_SET:  # SetSensorDPI
                if self.dpi_set_fap_error:
                    return ReadOutcome.from_data(self._fap_error(req, 0x09))
                if self.dpi_set_rejected:
                    return ReadOutcome.from_data(self._fap_error(req, 0x02))
                dpi = (req["params"][1] << 8) | req["params"][2]
                self._last_set_dpi = dpi
                # ACK ecoa o header com params zerados (conferência).
                return ReadOutcome.from_data(self._echo_response(req, b""))

        # Qualquer outro request: eco simples (funcionalidade extra).
        return ReadOutcome.from_data(self._echo_response(
            req, req["params"][:3]
        ))

    @property
    def applied_dpi(self) -> Optional[int]:
        """Último DPI confirmado que o fake "aplicou" (eco do SetSensorDPI)."""
        return self._last_set_dpi


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
