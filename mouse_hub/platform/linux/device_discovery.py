"""Descoberta do Logitech G403 HERO no Linux por identidade de hardware.

Nunca assumimos que o mouse será `/dev/hidraw0`. A descoberta
percorre `/sys/class/hidraw/*/device` em busca de interfaces HID cujo
`uevent` contenha o VID/PID do G403 HERO (046d:c08f).

A seleção de endpoint é feita em DUAS etapas, porque identidade por
VID/PID no uevent é condição necessária mas não suficiente:

1. Identidade: o parser de `HID_ID` é defensivo — entradas malformadas
   são ignoradas, jamais lançam exceção.
2. Protocolo: cada candidato é sondado de verdade via feature IRoot
   (0x0000) do HID++ 2.0 — GET_FEATURE_TABLE_COUNT de report curto
   (feature 0x00, fn 0) para confirmar IRoot (eco de 3 bytes de params,
   validando device index e software ID), e depois IRoot.GetFeature
   (fn 0) com o FEATURE ID 0x2201 (Adjustable DPI) para confirmar que o
   endpoint suporta a feature de DPI e descobrir o feature index que o
   dispositivo usará para endereçá-la. Só o endpoint que passa nas duas
   etapas é elegível para escritas de efeito.

Quando vários endpoints do mesmo G403 respondem ao protocolo, a
seleção é ambígua e o produto não decide por conta própria: nada é
escrito em endpoint incerto. A seleção também reporta a permissão do
acesso (device acessível vs inacessível) através de `Outcome` para que
quem usa distinga "device não confirmado" de "device existente mas sem
permissão (regra udev ausente)".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from mouse_hub.core.constants import G403_PID, G403_VID
from mouse_hub.platform.hidpp import (
    DIRECT_USB_DEVICE_INDEX,
    FeatureId,
    SHORT_REPORT_LENGTH,
    SoftwareId,
    RootFeature,
)
from mouse_hub.platform.protocol import HidAccess, MouseDevice

SYS_HIDRAW_ROOT = Path("/sys/class/hidraw")


def parse_hid_id(line: str) -> Optional[tuple[int, int]]:
    """Extrai (vid, pid) de uma linha de uevent `HID_ID=<bus>:<vendor>:<product>`.

    Parsing defensivo por design: conteúdo malformado (dígitos inválidos,
    campos faltantes, prefixo ausente, linhas truncadas) retorna None
    em vez de lançar exceção. Entradas inválidas são ignoradas, nunca
    contaminam o resultado.
    """
    if not isinstance(line, str) or not line.startswith("HID_ID="):
        return None
    raw = line.split("=", 1)[-1].strip()
    parts = raw.split(":")
    if len(parts) < 3:
        return None
    try:
        return int(parts[1], 16), int(parts[2], 16)
    except (ValueError, TypeError, OverflowError):
        return None


def read_uevent_identity(path: Path) -> Optional[tuple[int, int]]:
    """Lê a identidade (vid, pid) do uevent em `path`.

    Retorna None quando o arquivo não existe, não é legível ou seu
    conteúdo não é parseável — sem nunca lançar exceção.
    """
    if not path.exists():
        return None
    try:
        text = path.read_text()
    except OSError:
        return None
    for line in text.splitlines():
        parsed = parse_hid_id(line)
        if parsed is not None:
            return parsed
    return None


def find_g403_hidraw_devices(
    vid: int = G403_VID, pid: int = G403_PID, sysfs_root: Path = SYS_HIDRAW_ROOT
) -> List[MouseDevice]:
    """Varre o sysfs procurando hidraw cuja identidade seja (vid, pid).

    Funciona sem privilegiar nenhum caminho fixo: cada interface hidraw
    é validada individualmente pelo próprio uevent. Retorna TODOS os
    candidatos — a seleção final é responsabilidade da camada superior,
    que deve validar o protocolo antes de qualquer escrita (ver
    `HydppEndpointSelection`).
    """
    devices: List[MouseDevice] = []
    if not sysfs_root.is_dir():
        return devices

    for entry in sorted(sysfs_root.iterdir()):
        uevent = entry / "device" / "uevent"
        if not uevent.exists():
            continue

        identity = read_uevent_identity(uevent)
        if identity is None:
            continue
        if identity != (vid, pid):
            continue

        name = ""
        try:
            text = uevent.read_text()
            for line in text.splitlines():
                if line.startswith("HID_NAME="):
                    name = line.split("=", 1)[-1].strip()
                    break
        except OSError:
            pass

        devices.append(MouseDevice(
            hidraw_path=f"/dev/{entry.name}",
            vid=vid,
            pid=pid,
            name=name or "",
        ))

    return devices


def discover_g403(
    vid: int = G403_VID, pid: int = G403_PID, sysfs_root: Path = SYS_HIDRAW_ROOT
) -> Optional[MouseDevice]:
    """Retorna o primeiro G403 encontrado pela identidade, ou None.

    ATENÇÃO: esta função confirma apenas identidade por VID/PID. O
    endpoint retornado ainda precisa passar pela validação de protocolo
    (HydppEndpointSelection.select) antes de receber qualquer comando de
    efeito.
    """
    devices = find_g403_hidraw_devices(vid, pid, sysfs_root)
    return devices[0] if devices else None


@dataclass(frozen=True)
class ProbeOutcome:
    """Resultado do probe de protocolo de um candidato.

    * valid=True e feature_index != None → endpoint confirma IRoot e a
      feature Adjustable DPI (0x2201), com o feature index descoberto
      dinamicamente;
    * valid=True e feature_index == None → endpoint confirma IRoot mas
      NÃO suporta 0x2201 (dpi indisponível neste dispositivo);
    * valid=False → endpoint não validável ou rejeitado pelo protocolo.
    """

    valid: bool
    feature_index: Optional[int] = None

    # Permissão do acesso ao descritor durante o probe:
    # * None        → probe não precisou abrir (sem hidraw) ou falha
    #                 antes do open;
    # * True        → descritor acessível;
    # * False       → open recusado (permission denied, regra udev).
    accessible: Optional[bool] = None


class HydppEndpointSelection:
    """Segunda etapa da descoberta: confirma qual candidato realmente
    suporta o protocolo HID++ 2.0.

    Envolve o `HidAccess` (abre, sonda com GET_FEATURE_TABLE_COUNT via
    long packet e fecha) para decidir entre os candidatos. A seleção é
    fail closed: se nenhum candidato responder, se um responder com
    erro, ou se mais de um responder sem como decidir com segurança, a
    seleção falha e nenhum endpoint é retornado — nada é escrito em
    endpoint incerto.
    """

    def __init__(self, hid: HidAccess) -> None:
        self._hid = hid

    def _probe_one(self, device: MouseDevice) -> ProbeOutcome:
        """Probe de protocolo completo em duas etapas, conforme a
        especificação HID++ 2.0:

        1. GET_FEATURE_TABLE_COUNT via report curto (feature index 0 =
           IRoot, fn 0): confirma que o endpoint responde ao protocolo
           e que o report ecoa o device index usado.
        2. IRoot.GetFeature(0x2201 — Adjustable DPI): confirma a
           presença da feature e descobre o feature index real que o
           dispositivo usará para endereçar a feature.

        Abre o descritor temporariamente e o fecha em qualquer caminho
        (inclusive exceção). Nenhum estado fica para trás.
        """
        from mouse_hub.core.operation import OperationStatus

        opened = False
        try:
            open_result = self._hid.open(device)
            if not open_result.status.ok:
                accessible = (
                    open_result.status != OperationStatus.PERMISSION_DENIED
                    and open_result.status != OperationStatus.DEVICE_NOT_FOUND
                )
                # open rejeitado (permissão negada ou device ausente) =
                # endpoint não validável; preservamos a permissão para
                # quem usa distinguir o caso.
                return ProbeOutcome(valid=False, accessible=accessible)
            opened = True

            root = RootFeature(DIRECT_USB_DEVICE_INDEX, SoftwareId.MOUSE_HUB)

            # Etapa 1: GET_FEATURE_TABLE_COUNT (feature set 0x0001, fn 0).
            # O dispositivo ecoa o header completo no report de resposta,
            # então validamos device_index, feature_index (0x01) e
            # function+software_id antes de aceitar qualquer dado.
            request = root.get_feature_table_count_request()
            write_result = self._hid.write(request)
            if not write_result.status.ok:
                return ProbeOutcome(valid=False, accessible=True)
            response = self._hid.read(SHORT_REPORT_LENGTH, timeout=0.5)
            if response is None or len(response) < SHORT_REPORT_LENGTH:
                return ProbeOutcome(valid=False, accessible=True)
            # Header ecoado: device index e software ID do request.
            expected_fn_sw = (0x00 << 4) | SoftwareId.MOUSE_HUB
            if (
                response[1] != DIRECT_USB_DEVICE_INDEX
                or response[2] != 0x01
                or response[3] != expected_fn_sw
            ):
                return ProbeOutcome(valid=False, accessible=True)
            if root.parse_feature_table_count_response(response) is None:
                return ProbeOutcome(valid=False, accessible=True)

            # Etapa 2: IRoot.GetFeature(0x2201) — presença de DPI.
            request = root.get_feature_request(FeatureId.ADJUSTABLE_DPI)
            write_result = self._hid.write(request)
            if not write_result.status.ok:
                return ProbeOutcome(valid=False, accessible=True)
            response = self._hid.read(SHORT_REPORT_LENGTH, timeout=0.5)
            if response is None or len(response) < SHORT_REPORT_LENGTH:
                return ProbeOutcome(valid=False, accessible=True)
            expected_fn_sw = (root.FN_GET_FEATURE << 4) | SoftwareId.MOUSE_HUB
            if response[1] != DIRECT_USB_DEVICE_INDEX \
                    or response[3] != expected_fn_sw:
                # Header não espelha o request — pode ser report
                # assíncrono de outro software ou de outra feature.
                return ProbeOutcome(valid=False, accessible=True)
            if response[2] == 0x8F:
                # Erro RAP ecoado com o header correto: o dispositivo
                # rejeitou a consulta (HID++ válido, sem o que
                # consultamos) — endpoint válido, feature ausente.
                return ProbeOutcome(valid=True, feature_index=None,
                                    accessible=True)
            # Qualquer outro valor de byte2 que não seja o feature index
            # esperado nem 0x8F não cabe em uma resposta legítima do
            # GetFeature — endpoint não validável.
            if response[2] != root.FEATURE_INDEX:
                return ProbeOutcome(valid=False, accessible=True)
            feature_index = int(response[4])
            if feature_index == 0xFF:
                # Erro de protocolo HID++ 2.0: o dispositivo rejeitou o
                # GetFeature com INVALID_FEATURE_INDEX ou similar.
                return ProbeOutcome(valid=False, accessible=True)
            # GetFeature devolve (feature_index, flags, version); index
            # 0 significa que a feature NÃO é suportada — o endpoint
            # ainda é HID++ 2.0 válido, só sem Adjustable DPI.
            return ProbeOutcome(
                valid=True,
                feature_index=feature_index if feature_index != 0 else None,
                accessible=True,
            )
        except Exception:
            # Exceção de acesso (descritor sumiu, sysfs instável) é
            # "endpoint não validável" — nunca vira seleção nem vaza.
            return ProbeOutcome(valid=False, accessible=True)
        finally:
            if opened:
                self._hid.close()

    def probe(
        self, candidates: List[MouseDevice]
    ) -> List[ProbeOutcome]:
        """Probeia todos os candidatos e retorna o resultado de cada um
        (na mesma ordem). O probe sempre fecha o descritor: nada fica
        aberto."""
        return [self._probe_one(candidate) for candidate in candidates]

    def select(
        self, candidates: List[MouseDevice]
    ) -> Optional[MouseDevice]:
        """Seleciona o endpoint confirmado pelo protocolo.

        Regras (fail closed):
        * nenhum candidato valida → None;
        * exatamente um valida → esse;
        * mais de um valida sem critério seguro de desempate → None.
        """
        if not candidates:
            return None
        outcomes = self.probe(candidates)
        validated = [
            device
            for device, outcome in zip(candidates, outcomes)
            if outcome.valid and outcome.feature_index is not None
        ]
        if len(validated) == 1:
            return validated[0]
        # 0 validados ou ambiguidade: falhar fechado.
        return None


# Compatibilidade: quem usava os nomes antigos ainda resolve.
discover = discover_g403
