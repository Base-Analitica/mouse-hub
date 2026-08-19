"""Acesso real ao Logitech G403 HERO via dispositivo hidraw validado.

Este módulo implementa `HidAccess` abrindo a interface hidraw que
`device_discovery` confirmou pertencer ao G403 (VID/PID no uevent).
O `os.open` recebe a confirmação de identidade junto com o caminho, e a
identidade é re-verificada antes de aceitar o descritor.

Responsabilidades deste módulo:
* canal correto (identidade verificada antes de abrir e antes de
  aceitar o descritor);
* confirmação de protocolo por READBACK: o `verify_response` usa o
  `os.read` com timeout para esperar a resposta do dispositivo a um
  comando, sem interpretar bytes do protocolo (a construção dos reports
  e a interpretação do ACK são do domínio, em `core`).
* reportar falhas reais (permission_denied, device desconectado,
  timeout) em vez de sucesso fingido.

Nada aqui escreve um comando de efeito sem que o descritor tenha sido
verificado — mas a decisão de que o endpoint suporta a feature
específica pertence à seleção de protocolo em
`device_discovery.HydppEndpointSelection`, usada pelo serviço de
domínio antes de `set_hardware_dpi`.
"""

from __future__ import annotations

import errno
import os
import select
from pathlib import Path
from typing import Optional

from mouse_hub.core.operation import OperationResult
from mouse_hub.platform.protocol import HidAccess, MouseDevice
from mouse_hub.platform.read_outcome import ReadOutcome


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

    def read(self, length: int, timeout: float = 0.5) -> ReadOutcome:
        """Lê até `length` bytes, aguardando com timeout. O desfecho é
        SEMPRE tipado (ReadOutcome) — timeout não pode ser confundido
        com falha de transporte:

        * select sem dados até o fim → TIMEOUT (endpoint mudo, sem
          evidência de remoção);
        * BlockingIOError (EAGAIN) → TIMEOUT (o descritor é non-blocking:
          "nada disponível agora" não é evidência de remoção);
        * PermissionError → PERMISSION_DENIED (fd perdeu permissão);
        * OSError errno ENODEV/ENXIO/EIO → DEVICE_NOT_FOUND (device
          desconectado a quente);
        * outro OSError → FAILED (transporte genérico, fd corrompido).
        """
        if self._fd is None:
            return ReadOutcome.timeout("nenhum descritor aberto")
        try:
            ready, _, _ = select.select([self._fd], [], [], timeout)
            if not ready:
                return ReadOutcome.timeout()
            return ReadOutcome.from_data(os.read(self._fd, length))
        except PermissionError:
            return ReadOutcome.permission_denied("Permissão perdida na leitura")
        except BlockingIOError:
            # EAGAIN sem evidência de remoção: nada disponível agora
            # — timeout é a classificação conservadora correta.
            return ReadOutcome.timeout()
        except OSError as exc:
            if exc.errno in (errno.ENODEV, errno.ENXIO, errno.EIO):
                return ReadOutcome.device_not_found(
                    "Descritor desconectado na leitura (hot-unplug)"
                )
            return ReadOutcome.failed(f"OSError na leitura: {exc}", errno=exc.errno)

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

    def verify_response(self, timeout: float = 0.5, read_length: int = 20) -> ReadOutcome:
        """Aguarda a resposta do dispositivo a um comando já escrito.

        O desfecho é tipado (ReadOutcome): DATA com os bytes quando o
        device respondeu a tempo, ou a causa REAL (TIMEOUT = mudo, não
        é falha de transporte). O tempo de espera é limitado por
        `select` com timeout, nunca gira em loop ocupado.
        """
        return self.read(read_length, timeout=timeout)

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
