"""Descoberta do G403 HERO de alto nível, testável por injeção.

Combina a varredura de sysfs (implementação real) com um hook de
injeção para testes: qualquer chamador pode substituir o scanner sem
mudar o contrato. A decisão de qual `hidraw` usar só é tomada depois
que a identidade VID/PID é confirmada pelo próprio uevent do nó.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

from mouse_hub.core.constants import G403_PID, G403_VID
from mouse_hub.platform.linux.device_discovery import find_g403_hidraw_devices
from mouse_hub.platform.protocol import MouseDevice

SysfsScanner = Callable[[int, int, Path], List[MouseDevice]]

DEFAULT_SCANNER: SysfsScanner = find_g403_hidraw_devices


def discover(
    vid: int = G403_VID,
    pid: int = G403_PID,
    sysfs_root: Path = Path("/sys/class/hidraw"),
    scanner: SysfsScanner = DEFAULT_SCANNER,
) -> Optional[MouseDevice]:
    """Localiza o G403 HERO pelo VID/PID. Retorna None se ausente."""
    devices = scanner(vid, pid, sysfs_root)
    return devices[0] if devices else None


def discover_candidates(
    vid: int = G403_VID,
    pid: int = G403_PID,
    sysfs_root: Path = Path("/sys/class/hidraw"),
    scanner: SysfsScanner = DEFAULT_SCANNER,
) -> List[MouseDevice]:
    """Retorna TODOS os hidraws com a identidade do G403 (VID/PID).

    O G403 real expõe mais de um /dev/hidrawN (interface de input do
    mouse, interface vendor HID++). Identidade por VID/PID não diz qual
    fala o protocolo — a escolha do endpoint é feita depois, por
    HydppEndpointSelection (issue #68: pegar o primeiro candidato é um
    bug de hardware real, a interface de input rejeita a escrita)."""
    return scanner(vid, pid, sysfs_root)
