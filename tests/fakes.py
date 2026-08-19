"""Fakes de hardware para a suíte de testes.

Permitem testar o core inteiro (descoberta, DPI, sensibilidade,
capabilities, controller) sem um G403 real, sem /dev/hidraw e sem
subprocess. Não há nenhum sucesso falso possível: cada fake registra
exatamente o que "aplicou" e sob quais condições falha.

O FakeHidAccess implementa uma máquina de protocolo HID++ 2.0 mínima
porém correta: as respostas são COMPUTADAS a partir do request,
espelhando o header (device_index, feature_index, function+software_id)
e validando o software ID do próprio cliente, conforme a convenção
publicada (report curto 0x10 com device index 0x00 para conexão USB
direta). O fakes não dita o protocolo — a especificação dita, o fake só
a executa.

Cenários configuráveis:

* open_permission_denied / open_raises → desfecho real de abertura;
* dpi_feature_index → feature index que IRoot.GetFeature(0x2201)
  devolve (None/0 = feature ausente; índice dinâmico ≠ hardcoded);
* sw_id_wrong / async_noise → reports de terceiros e eventos assíncronos
  que NÃO confirmam request (o core deve rejeitá-los);
* probe_stage1_error / probe_stage2_error → o endpoint rejeita uma das
  etapas do probe (0x8F);
* ack_timeout → o endpoint silencia na resposta;
* readback_mode → "echo" devolve o eco do SetSensorDPI (fn 0x10) e o
  valor aplicado, "none" devolve None (sem readback).
"""

from __future__ import annotations

from typing import Callable, List, Optional

from mouse_hub.core.operation import OperationResult
from mouse_hub.platform.hidpp import (
    SHORT_REPORT_LENGTH,
    SoftwareId,
)
from mouse_hub.platform.protocol import HidAccess, MouseDevice, SystemInput

# IDs de referência — a máquina de protocolo usa o que o core escreve,
# não hardcoded de um lado só.
ROOT_FEATURE_INDEX = 0x00
FEATURE_SET_INDEX = 0x01
ROOT_FN_GET_FEATURE = 0x00
DPI_FN_SET = 0x03


class FakeHidAccess(HidAccess):
    """HidAccess controlável em teste, com máquina de protocolo HID++ 2.0.

    Requests e responses usam report CURTO (0x10) com device index 0x00
    (USB direto) — o fake responde a qualquer report_id, preservando
    nas respostas o que o request trouxe, para que o core valide o eco
    do header como manda o protocolo.
    """

    def __init__(self) -> None:
        # Abertura
        self.open_permission_denied: bool = False
        self.open_raises: Optional[BaseException] = None
        # Feature Adjustable DPI: feature index devolvido por
        # IRoot.GetFeature(0x2201). 0 (ou None) = feature ausente;
        # -1 = erro de protocolo (index 0xFF, FAP error).
        self.dpi_feature_index: Optional[int] = 1
        # Rejeição das etapas do probe com sub-report de erro 0x8F:
        # stage1 = feature set count; stage2 = GetFeature(0x2201).
        self.probe_stage1_error: bool = False
        self.probe_stage2_error: bool = False
        # Software ID errado nas respostas: o header ecoa um sw_id de
        # outro cliente — o core deve tratar como não-ACK.
        self.sw_id_wrong: bool = False
        self.wrong_sw_id: int = 0x01
        # Eventos assíncronos de outro software injetados na fila de
        # respostas (ex.: event de report de outro aplicativo Logitech)
        # antes de qualquer resposta esperada.
        self.async_noise: List[bytes] = []
        # Confirmação
        self.ack_timeout: bool = False
        # Falha de transporte na escrita (fd sumiu, write falhou no OS):
        # o controller deve tratar como FAILED antes de assumir sucesso.
        self.write_succeeds: bool = True
        # DPI aplicado
        self.dpi_set_rejected: bool = False
        self.dpi_fn_error: bool = False  # GetSensorDPI fn 0x20 com erro 0x8F
        # Readback: "echo" devolve o eco do último SetSensorDPI (fn 0x10)
        # com o valor aplicado; "none" devolve None.
        self.readback_mode: str = "echo"
        self.query_count: int = 0
        self._opened: List[MouseDevice] = []
        self._device: Optional[MouseDevice] = None
        self.written_reports: List[bytes] = []
        self._last_set_dpi: Optional[int] = None
        # Fila FIFO de responses pré-programadas (para cenários que a
        # computação não cobre). Cada read consome uma entrada.
        self.probe_responses: List[bytes] = []
        # Últimos requests por par (report_id, feature_index) para o
        # eco de header — não usa fila, preserva contexto.
        self._last_request_header: Optional[bytes] = None

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
        # Abertura nova = contexto novo: descartar o request pendente do
        # contexto anterior (o read do novo contexto não pode responder
        # a um request de um handle que já fechou).
        self._last_request_header = None
        self._last_set_dpi = None

    # ── Protocolo ─────────────────────────────────────────────────

    def _parse_request(self, report: bytes) -> Optional[dict]:
        """Header de request: [report_id][device_index][feature_index]
        [fn+sw_id][params...]. Retorna os campos decodificados."""
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
        function+software_id (o próprio ID ou sw_id de outro cliente,
        se configurado)."""
        if self.sw_id_wrong:
            fn_sw = (req["function"] << 4) | self.wrong_sw_id
        else:
            fn_sw = (req["function"] << 4) | req["software_id"]
        payload = (
            bytes([req["report_id"]])
            + bytes([req["device_index"]])
            + bytes([req["feature_index"]])
            + bytes([fn_sw])
            + params
        )
        # Report curto = 7 bytes total; preenche com zeros.
        return (payload + b"\x00" * (SHORT_REPORT_LENGTH - len(payload)))[:SHORT_REPORT_LENGTH]

    def _error_response(self, req: dict) -> bytes:
        """Sub-report de erro HID++ (RAP 0x8F): report curto com
        sub_id 0x8F, device index do request, function, error code
        (INVALID_ARGS 0x02)."""
        fn_sw = (req["function"] << 4) | req["software_id"]
        return bytes([
            req["report_id"],
            req["device_index"],
            0x8F,
            fn_sw,
            req["function"],
            0x02,
            0x00,
        ])

    def write(self, report: bytes) -> OperationResult:
        if not self.is_open():
            return OperationResult.failed("no open descriptor")
        if not self.write_succeeds:
            raise OSError("simulated write failure on hidraw")
        self.written_reports.append(report)
        req = self._parse_request(report)
        if req is None:
            return OperationResult.failed("report sem cabeçalho HID++")
        self._last_request_header = report
        return OperationResult.applied("request aceito pelo endpoint")

    def read(self, length: int, timeout: float = 0.5) -> Optional[bytes]:
        self.query_count += 1
        if self._device is None:
            return None
        if self.ack_timeout:
            return None

        # Noise assíncrono primeiro: events de outro software que a
        # função consumidora deve ignorar (não são ACK).
        if self.async_noise:
            return self.async_noise.pop(0)

        # Responses pré-programadas têm precedência explícita.
        if self.probe_responses:
            return self.probe_responses.pop(0)

        # Sem header de request válido: endpoint mudo.
        if self._last_request_header is None:
            return None
        req = self._parse_request(self._last_request_header)
        if req is None:
            return None

        # Erro RAP 0x8F (rejeição pelo dispositivo).
        if self.probe_stage1_error and req["feature_index"] == FEATURE_SET_INDEX:
            return self._error_response(req)
        if self.probe_stage2_error and req["feature_index"] == ROOT_FEATURE_INDEX:
            return self._error_response(req)

        # IRoot.GetFeature(id_hi, id_lo, 0) → (feature_index, flags,
        # version). Feature index 0 = não suportada; configurável.
        if req["feature_index"] == ROOT_FEATURE_INDEX:
            if req["function"] == ROOT_FN_GET_FEATURE:
                feature_id = (req["params"][0] << 8) | req["params"][1]
                if feature_id == 0x2201:
                    index = self.dpi_feature_index
                    if index is None:
                        index = 0  # feature ausente
                    return self._echo_response(req, bytes([index, 0x00, 0x03]))
                # Feature inexistente de teste → não suportada.
                return self._echo_response(req, bytes([0x00, 0x00, 0x00]))
            return self._echo_response(req, bytes([0x00, 0x00, 0x00]))

        # Feature set GET_FEATURE_TABLE_COUNT (feature 0x01, fn 0).
        if req["feature_index"] == FEATURE_SET_INDEX and req["function"] == 0x00:
            return self._echo_response(req, bytes([0x08, 0x00, 0x00]))

        # SetSensorDPI (fn 0x10, no feature index configurado):
        # params [sensor_idx, dpi_hi, dpi_lo].
        if (
            req["feature_index"] == self.dpi_feature_index
            and req["function"] == DPI_FN_SET
            and self.dpi_feature_index not in (None, 0)
        ):
            if self.dpi_set_rejected:
                return self._error_response(req)
            dpi = (req["params"][1] << 8) | req["params"][2]
            self._last_set_dpi = dpi
            # ACK ecoa o request sem params alterados (conferência).
            return self._echo_response(req, b"")

        # Qualquer outro request: eco simples (funcionalidade extra).
        return self._echo_response(req, req["params"][:3])

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
