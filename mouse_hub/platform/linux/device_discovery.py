"""Descoberta do Logitech G403 HERO no Linux por identidade de hardware.

Nunca assumimos que o mouse será `/dev/hidraw0`. A descoberta
percorre `/sys/class/hidraw/*/device` em busca de interfaces HID cujo
`uevent` contenha o VID/PID do G403 HERO (046d:c08f).

A seleção de endpoint é feita em DUAS etapas, porque identidade por
VID/PID no uevent é condição necessária mas não suficiente:

1. Identidade: o parser de `HID_ID` é defensivo — entradas malformadas
   são ignoradas, jamais lançam exceção.
2. Protocolo: cada candidato é sondado com um report HID++ 2.0 válido
   (GET_FEATURE_TABLE_COUNT, long packet) através do mesmo `HidAccess`
   que fará as escritas. Só o endpoint que responde ao protocolo é
   elegível para escritas de efeito; candidatos que não respondem são
   descarte, e se nenhum responder a decisão segura é falhar fechado
   (device não usável para DPI), em vez de escrever no primeiro match.

Quando vários endpoints do mesmo G403 respondem ao protocolo, a
seleção é ambígua e o produto não decide por conta própria: nada é
escrito em endpoint incerto.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from mouse_hub.core.constants import G403_PID, G403_VID
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

    def _probe_feature_table(self, device: MouseDevice) -> Optional[int]:
        """Sonda o endpoint com um GET_FEATURE_TABLE_COUNT (feature 0,
        function 0, long packet). Retorna a contagem de features se o
        dispositivo respondeu ao protocolo, ou None se não respondeu.

        Qualquer exceção ou falha de open/read/write é tratada como
        "endpoint não validável" — nunca como sucesso.
        """
        from mouse_hub.core.operation import OperationResult

        opened = False
        try:
            open_result = self._hid.open(device)
            if not open_result.status.ok:
                return None
            opened = True
            write_result = self._hid.write(b"\x11\xff\x00\x00" + b"\x00" * 16)
            if not write_result.status.ok:
                return None
            response = self._hid.read(20, timeout=0.5)
            if response is None or len(response) < 3:
                return None
            if response[0] != 0x11:
                return None
            if response[2] == 0x8F:
                # Resposta de erro HID++: o endpoint responde, mas rejeita.
                return None
            return int(response[3])
        except Exception:
            # Exceção de acesso (descritor sumiu, sysfs instável) é
            # "endpoint não validável" — nunca vira seleção nem vaza.
            return None
        finally:
            if opened:
                self._hid.close()

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
        validated: List[MouseDevice] = []
        for candidate in candidates:
            count = self._probe_feature_table(candidate)
            if count is not None:
                validated.append(candidate)
        if len(validated) == 1:
            return validated[0]
        # 0 validados ou ambiguidade: falhar fechado.
        return None


# Compatibilidade: quem usava os nomes antigos ainda resolve.
discover = discover_g403
