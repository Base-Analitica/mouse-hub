"""Acesso real ao Logitech G403 HERO via dispositivo hidraw validado.

Este módulo implementa `HidAccess` abrindo a interface hidraw que
`device_discovery` confirmou pertencer ao G403 (pelo VID/PID no uevent).
O `os.open` recebe a confirmação de identidade junto com o caminho, e a
identidade é re-verificada antes de qualquer escrita.

Protocolo: os reports brutos do HID++ 2.0 (curto, ID 0x10) continuam
responsabilidade de quem constrói os bytes; este módulo garante apenas
que o canal é o dispositivo certo e reporta falhas reais em vez de
sucesso fingido.
"""

from __future__ import annotations

import errno
import os
import select
from typing import Optional

from mouse_hub.core.operation import OperationResult, OperationStatus
from mouse_hub.platform.protocol import HidAccess, MouseDevice


class LinuxHidAccess(HidAccess):
    def __init__(self) -> None:
        self._fd: Optional[int] = None
        self._device: Optional[MouseDevice] = None

    def open(self, device: MouseDevice) -> OperationResult:
        if self._fd is not None:
            self.close()

        if device.hidraw_path is None:
            return OperationResult.device_not_found(
                "Dispositivo sem interface hidraw acessível"
            )

        path = device.hidraw_path
        if not os.path.exists(path):
            return OperationResult.device_not_found(path)

        if not os.access(path, os.W_OK):
            return OperationResult.permission_denied(
                f"Sem permissão de escrita em {path}"
            )

        try:
            self._fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        except PermissionError:
            return OperationResult.permission_denied(path)
        except FileNotFoundError:
            self._fd = None
            return OperationResult.device_not_found(path)
        except OSError as exc:
            return OperationResult.failed(f"OSError ao abrir {path}: {exc}")

        # Revalidação de identidade antes de aceitar o descritor.
        verified = _verify_identity(self._fd, device.vid, device.pid)
        if not verified:
            os.close(self._fd)
            self._fd = None
            return OperationResult.failed(
                f"{path} não respondeu à identificação esperada "
                f"({device.vid:#06x}:{device.pid:#06x})"
            )

        self._device = device
        return OperationResult.applied(f"Descritor aberto em {path}")

    def is_open(self) -> bool:
        return self._fd is not None

    def read(self, length: int, timeout: float = 0.5) -> Optional[bytes]:
        if self._fd is None:
            return None
        try:
            ready, _, _ = select.select([self._fd], [], [], timeout)
            if not ready:
                return None
            return os.read(self._fd, length)
        except (BlockingIOError, OSError):
            return None

    def write(self, report: bytes) -> OperationResult:
        if self._fd is None or self._device is None:
            return OperationResult.failed("Nenhum descritor aberto")
        try:
            os.write(self._fd, bytes(report))
        except PermissionError:
            return OperationResult.permission_denied("Permissão perdida durante escrita")
        except OSError as exc:
            # ENODEV/ENXIO: dispositivo desconectado a quente
            if exc.errno in (errno.ENODEV, errno.ENXIO, errno.EIO):
                return OperationResult.device_not_found("Dispositivo desconectado")
            return OperationResult.failed(f"OSError durante escrita: {exc}")
        return OperationResult.applied()

    def close(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        self._device = None


def _verify_identity(fd: int, expected_vid: int, expected_pid: int) -> bool:
    """Confirma que o descritor aberto pertence ao dispositivo esperado.

    Lê o `uevent` do próprio caminho do descritor (via /sys) para
    confirmar VID/PID sem depender de qualquer resposta do hardware.
    Se o uevent não for legível, a validação falha (fail closed),
    evitando escrita em dispositivo incerto.
    """
    from mouse_hub.platform.linux.device_discovery import read_uevent_identity
    from pathlib import Path

    try:
        dev_link = Path(f"/proc/self/fd/{fd}").resolve()
    except OSError:
        return False

    # fd aponta para /dev/hidrawN; o uevent fica em
    # /sys/class/hidraw/hidrawN/device/uevent
    sys_uevent = Path(f"/sys/class/hidraw/{dev_link.name}/device/uevent")
    identity = read_uevent_identity(sys_uevent)
    if identity is None:
        return False
    return identity == (expected_vid, expected_pid)
