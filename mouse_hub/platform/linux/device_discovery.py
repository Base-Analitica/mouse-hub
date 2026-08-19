"""Descoberta do Logitech G403 HERO no Linux por identidade de hardware.

Nunca assumimos que o mouse será `/dev/hidraw0`. A descoberta percorre
`/sys/class/hidraw/*/device` em busca de interfaces HID cujo
`uevent` contenha o VID/PID do G403 HERO (046d:c08f). Quando a interface
for encontrada, associamos o `hidraw` correspondente (ex.: `/dev/hidraw2`).

Dispositivos que não batem com a identidade esperada são ignorados: a
escrita em hidraw só acontece com a confirmação da identidade.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from mouse_hub.core.constants import G403_PID, G403_VID
from mouse_hub.platform.protocol import MouseDevice

SYS_HIDRAW_ROOT = Path("/sys/class/hidraw")


def _parse_vid_pid(vid_str: str, pid_str: str) -> Optional[tuple[int, int]]:
    try:
        return int(vid_str, 16), int(pid_str, 16)
    except (ValueError, TypeError):
        return None


def find_g403_hidraw_devices(
    vid: int = G403_VID, pid: int = G403_PID, sysfs_root: Path = SYS_HIDRAW_ROOT
) -> List[MouseDevice]:
    """Varre o sysfs procurando hidraw cuja identidade seja (vid, pid).

    Funciona sem privilegiar nenhum caminho fixo: cada interface hidraw
    é validada individualmente pelo próprio uevent. Retorna todos os
    matches (útil quando há mais de um dispositivo do mesmo modelo),
    sendo o primeiro tipicamente o correto.
    """
    devices: List[MouseDevice] = []
    if not sysfs_root.is_dir():
        return devices

    for entry in sorted(sysfs_root.iterdir()):
        uevent = entry / "device" / "uevent"
        if not uevent.exists():
            continue

        found_vid: Optional[int] = None
        found_pid: Optional[int] = None
        found_name: str = ""
        try:
            text = uevent.read_text()
        except OSError:
            continue

        for line in text.splitlines():
            if line.startswith("HID_ID="):
                # HID_ID=<bus>:<vendor>:<product>
                parts = line.split("=", 1)[-1].split(":")
                if len(parts) >= 3:
                    found_vid, found_pid = int(parts[1], 16), int(parts[2], 16)
            elif line.startswith("HID_NAME="):
                found_name = line.split("=", 1)[-1].strip()

        if (found_vid is not None and found_pid is not None
                and (found_vid, found_pid) == (vid, pid)):
            name = found_name or ""
            devices.append(MouseDevice(
                hidraw_path=f"/dev/{entry.name}",
                vid=vid,
                pid=pid,
                name=name,
            ))

    return devices


def discover_g403(
    vid: int = G403_VID, pid: int = G403_PID, sysfs_root: Path = SYS_HIDRAW_ROOT
) -> Optional[MouseDevice]:
    """Retorna o primeiro G403 encontrado ou None."""
    devices = find_g403_hidraw_devices(vid, pid, sysfs_root)
    return devices[0] if devices else None


def read_uevent_identity(path: Path) -> Optional[tuple[int, int]]:
    """Expõe a leitura de identidade de um único uevent (para testes e
    ferramentas de diagnóstico)."""
    if not path.exists():
        return None
    try:
        text = path.read_text()
    except OSError:
        return None
    for line in text.splitlines():
        if line.startswith("HID_ID="):
            parts = line.split("=", 1)[-1].split(":")
            if len(parts) >= 3:
                return int(parts[1], 16), int(parts[2], 16)
    return None
