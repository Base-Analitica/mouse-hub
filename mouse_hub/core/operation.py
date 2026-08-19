"""Resultado explícito de operações com efeitos externos.

O projeto historicamente retorna booleans soltos e, pior, sinaliza
sucesso quando apenas um fallback mudou (ex.: DPI físico falhou, mas a
sensibilidade do sistema foi alterada e o resultado foi `True`). Este
módulo torna o resultado de toda operação de hardware explícito e
enumera a causa real, de forma que nenhum "sucesso falso" seja possível
sem quebrar contratos de tipo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OperationStatus(Enum):
    """Desfecho real de uma operação com efeito externo.

    applied .............. o efeito solicitado foi realmente aplicado.
    applied_partial ...... o efeito foi aplicado, mas com adaptação
                           (ex.: DPI solicitado arredondado para o step).
    unsupported .......... a capacidade não está disponível no ambiente
                           (sem erro; o recurso simplesmente não existe).
    device_not_found ..... o dispositivo esperado não foi localizado.
    permission_denied .... o dispositivo existe, mas não há acesso
                           (típico: hidraw sem permissão de escrita).
    failed ............... tentativa realizada e rejeitada/falhada
                           pelo hardware ou pelo sistema.
    """

    APPLIED = "applied"
    APPLIED_PARTIAL = "applied_partial"
    UNSUPPORTED = "unsupported"
    DEVICE_NOT_FOUND = "device_not_found"
    PERMISSION_DENIED = "permission_denied"
    FAILED = "failed"

    @property
    def ok(self) -> bool:
        """True apenas quando o efeito solicitado foi de fato aplicado."""
        return self in (OperationStatus.APPLIED, OperationStatus.APPLIED_PARTIAL)


@dataclass(frozen=True)
class OperationResult:
    """Desfecho de uma operação, com o status real e contexto diagnóstico.

    Nunca retorne `OperationStatus.APPLIED` se o que aconteceu foi outra
    coisa. Operações compostas (ex.: DPI físico + sensibilidade pedida
    separadamente) devem informar o desfecho de cada parte em
    `details`, e o `status` deve refletir a intenção original.
    """

    status: OperationStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def applied(message: str = "", **details: Any) -> "OperationResult":
        return OperationResult(OperationStatus.APPLIED, message, dict(details))

    @staticmethod
    def applied_partial(message: str = "", **details: Any) -> "OperationResult":
        return OperationResult(OperationStatus.APPLIED_PARTIAL, message, dict(details))

    @staticmethod
    def unsupported(message: str = "", **details: Any) -> "OperationResult":
        return OperationResult(OperationStatus.UNSUPPORTED, message, dict(details))

    @staticmethod
    def device_not_found(message: str = "", **details: Any) -> "OperationResult":
        return OperationResult(OperationStatus.DEVICE_NOT_FOUND, message, dict(details))

    @staticmethod
    def permission_denied(message: str = "", **details: Any) -> "OperationResult":
        return OperationResult(OperationStatus.PERMISSION_DENIED, message, dict(details))

    @staticmethod
    def failed(message: str = "", **details: Any) -> "OperationResult":
        return OperationResult(OperationStatus.FAILED, message, dict(details))
