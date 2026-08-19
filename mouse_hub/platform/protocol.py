"""Contratos puros entre o core e as camadas de sistema.

Estas interfaces permitem que o core seja testado sem hardware real e
sem depender de `subprocess`, `udevadm` ou `/dev/hidraw*`. Em produção,
`mouse_hub.platform.linux` fornece as implementações reais; em teste,
fakes/mocks implementam os mesmos contratos.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from mouse_hub.core.operation import OperationResult
from mouse_hub.platform.read_outcome import ReadOutcome


@dataclass(frozen=True)
class MouseDevice:
    """Identidade de um dispositivo HID encontrado no sistema.

    `hidraw_path` pode estar ausente quando o dispositivo só aparece
    como apontador (xinput) sem interface hidraw acessível.
    """

    hidraw_path: Optional[str]
    vid: int
    pid: int
    name: str = ""


class HidAccess(ABC):
    """Acesso ao dispositivo HID do G403 HERO (leitura/escrita raw).

    A implementação real valida VID/PID antes de abrir o descritor, de
    modo que jamais se escreve em um `/dev/hidrawN` que não pertença ao
    mouse esperado. A validação em si é responsabilidade da
    implementação, não de quem chama.
    """

    @abstractmethod
    def open(self, device: MouseDevice) -> OperationResult:
        """Abre o descritor do dispositivo. Retorna o desfecho real,
        diferenciando device_not_found, permission_denied e failed."""

    @abstractmethod
    def is_open(self) -> bool:
        """True se há um descritor aberto."""

    @abstractmethod
    def read(self, length: int, timeout: float = 0.5) -> ReadOutcome:
        """Lê até `length` bytes do descritor.

        O desfecho é SEMPRE tipado (ReadOutcome): DATA quando há bytes,
        TIMEOUT quando o select esgota sem dados (endpoint mudo — não é
        falha de transporte), ou a causa REAL do erro de leitura
        (DEVICE_NOT_FOUND/PERMISSION_DENIED/FAILED). Nada colapsa em
        None: timeout não pode ser confundido com hot-unplug."""

    @abstractmethod
    def write(self, report: bytes) -> OperationResult:
        """Envia um report bruto ao dispositivo. Retorna o desfecho real."""

    @abstractmethod
    def close(self) -> None:
        """Fecha o descritor, se aberto."""


class SystemInput(ABC):
    """Operações de input do sistema operacional (xinput, xdotool, foco).

    Isola todas as chamadas externas para que possam ser substituídas em
    teste e para que falhas do sistema sejam reportadas como capacidade
    indisponível, e não como exceções silenciosas.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """True se as ferramentas de input estão presentes e utilizáveis."""

    @abstractmethod
    def find_pointer_id(self, mouse_name: str) -> Optional[int]:
        """Localiza o ID do apontador no xinput pelo nome do dispositivo."""

    @abstractmethod
    def get_accel_speed(self, pointer_id: int) -> Optional[float]:
        """Lê a propriedade 'libinput Accel Speed' do apontador."""

    @abstractmethod
    def set_accel_speed(self, pointer_id: int, accel: float) -> OperationResult:
        """Define a aceleração do apontador. Retorna o desfecho real."""

    @abstractmethod
    def active_window_title(self) -> Optional[str]:
        """Título da janela ativa, ou None se indisponível."""

    @abstractmethod
    def window_title_backend_available(self) -> bool:
        """True se o mecanismo de leitura de título da janela existe no
        sistema (ex.: xdotool instalado). SEM efeito colateral: não
        lê nenhum título, não abre nada — é o critério correto para a
        capacidade active_window_detection_available, que existe ou não
        independentemente de alguma janela ter título agora."""
