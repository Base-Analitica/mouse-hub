"""Contrato tipado para leitura em descritor hidraw.

MOTIVO — o contrato antigo (`Optional[bytes]`, None = timeout OU erro de
transporte) colapsava hot-unplug entre write e ACK com endpoint mudo:
o snapshot de capacidades podia permanecer True depois de o device ter
sumido do sistema. Com o `ReadOutcome`, quem consome distingue:

* DATA              → bytes recebidos (payload legível);
* TIMEOUT           → select esgotou o tempo SEM dados disponíveis
                      (endpoint mudo ou sem resposta — NÃO é falha de
                      transporte: nenhuma evidência de remoção);
* DEVICE_NOT_FOUND  → erro de leitura com evidência de remoção
                      (errno ENODEV/ENXIO/EIO) — o device sumiu a quente;
* PERMISSION_DENIED → PermissionError na leitura (fd perdeu permissão);
* FAILED            → qualquer outro OSError — falha de transporte
                      genérica (fd corrompido, I/O no OS).

TIMEOUT nunca vira DEVICE_NOT_FOUND: a ausência de resposta dentro da
janela é a definição de endpoint mudo e não pode ser falsamente
classificada como hot-unplug. O caller (controller/discovery) é quem
decide a semântica; o backend apenas classifica o que aconteceu no
descritor.

Backend real (LinuxHidAccess): a classificação usa o errno real do OS
(os.read) — nada é inventado;BlockingIOError (EAGAIN) sem evidência de
remoção é TIMEOUT (o descritor é non-blocking e o select só devolve
"pronto" quando há dados; EAGAIN significa "nada disponível agora",
sem evidência de remoção).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional


class ReadOutcomeKind(Enum):
    DATA = "data"
    TIMEOUT = "timeout"
    DEVICE_NOT_FOUND = "device_not_found"
    PERMISSION_DENIED = "permission_denied"
    FAILED = "failed"


class ReadOutcome:
    """Resultado de uma leitura em descritor hidraw.

    * kind            → classificação do desfecho (ReadOutcomeKind);
    * data            → bytes lidos quando kind == DATA, None caso
                        contrário;
    * message         → motivo legível para diagnóstico (vazio em DATA);
    * errno           → errno real do OSError quando aplicável (para
                        diagnóstico), None caso contrário.
    """

    __slots__ = ("kind", "_data", "message", "errno")

    @property
    def data(self) -> Optional[bytes]:
        """Bytes lidos quando kind == DATA, None caso contrário."""
        return self._data

    def __init__(
        self,
        kind: ReadOutcomeKind,
        data: Optional[bytes] = None,
        message: str = "",
        errno: Optional[int] = None,
    ) -> None:
        self.kind = kind
        # DATA sempre traz os bytes; os demais nunca.
        self._data = data if kind == ReadOutcomeKind.DATA else None
        self.message = message
        self.errno = errno

    @classmethod
    def from_data(cls, payload: bytes) -> "ReadOutcome":
        """Factory para desfecho com bytes (DATA). O nome é distinto
        do property `data` (que é o campo de leitura)."""
        return cls(ReadOutcomeKind.DATA, data=payload)

    @classmethod
    def timeout(cls, message: str = "timeout: nenhuma resposta dentro da janela") -> "ReadOutcome":
        return cls(ReadOutcomeKind.TIMEOUT, message=message)

    @classmethod
    def device_not_found(cls, message: str) -> "ReadOutcome":
        return cls(ReadOutcomeKind.DEVICE_NOT_FOUND, message=message)

    @classmethod
    def permission_denied(cls, message: str) -> "ReadOutcome":
        return cls(ReadOutcomeKind.PERMISSION_DENIED, message=message)

    @classmethod
    def failed(cls, message: str, errno: Optional[int] = None) -> "ReadOutcome":
        return cls(ReadOutcomeKind.FAILED, message=message, errno=errno)

    def is_data(self) -> bool:
        return self.kind == ReadOutcomeKind.DATA

    def is_timeout(self) -> bool:
        return self.kind == ReadOutcomeKind.TIMEOUT

    def is_transport_failure(self) -> bool:
        """True para qualquer causa REAL de acesso (removido/sem
        permissão/transporte) — NÃO inclui TIMEOUT (mudo), que não é
        evidência de falha do descritor."""
        return self.kind in (
            ReadOutcomeKind.DEVICE_NOT_FOUND,
            ReadOutcomeKind.PERMISSION_DENIED,
            ReadOutcomeKind.FAILED,
        )

    def __repr__(self) -> str:
        extra = f", data={len(self.data)}B" if self.data is not None else ""
        return f"ReadOutcome({self.kind.value}{extra})"
