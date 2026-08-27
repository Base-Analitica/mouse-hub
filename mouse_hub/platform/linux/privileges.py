"""Concessão de acesso HID sem terminal (parte 2 do fluxo do usuário).

Para o usuário final, o aplicativo resolve a permissão sozinho: um
botão na página de Configurações dispara `pkexec` (polkit), que abre o
prompt GRÁFICO de senha de administrador e aplica a regra udev do G403
+ reload/trigger do udevadm. Nenhum terminal, nenhum instrução para o
usuário digitar.

Segurança:
* o conteúdo da regra é FIXO (mesma linha do pacote .deb e do
  docs/udev/); nada vindo de input do usuário entra no comando;
* `pkexec` roda os três comandos root mínimos: install do arquivo de
  regra, udevadm control --reload-rules e udevadm trigger (hidraw);
* cancelar o prompt de senha NÃO é erro do app — é recusa honesta do
  usuário (PERMISSION_DENIED), e a UI continua utilizável sem HID.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Callable, List, Optional

from mouse_hub.core.operation import OperationResult, OperationStatus

HID_RULE_PATH = "/etc/udev/rules.d/99-logitech-g403-hidraw.rules"

# Idêntica à linha efetiva de docs/udev/99-logitech-g403-hidraw.rules
# (o teste de paridade garante que não divergem). MODE 0660 + plugdev —
# sem 0666, sem chmod manual, como manda o projeto.
HID_RULE_CONTENT = (
    "# mouse-hub — regra udev específica para o Logitech G403 HERO\n"
    'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="046d", '
    'ATTRS{idProduct}=="c08f", GROUP="plugdev", MODE="0660"\n'
)

PKEXEC_TIMEOUT = 120.0  # prompt gráfico pode levar; 2 min é generoso

Runner = Callable[..., "subprocess.CompletedProcess"]


def _build_script(tmp_rule_path: str, rule_path: str = HID_RULE_PATH) -> str:
    """Script root mínimo executado pelo pkexec (sh -c)."""
    return (
        f"install -m 0644 '{tmp_rule_path}' '{rule_path}' && "
        "udevadm control --reload-rules && "
        "udevadm trigger --action=add --subsystem-match=hidraw"
    )


def fix_hid_permissions(
    rule_path: str = HID_RULE_PATH,
    runner: Optional[Runner] = None,
    pkexec_path: str = "pkexec",
) -> OperationResult:
    """Aplica a regra udev via prompt gráfico de senha (polkit).

    * APPLIED           → regra instalada + udev recarregado/triggerado;
    * PERMISSION_DENIED → usuário cancelou a autenticação (ou não tem
      direito administrativo);
    * FAILED            → pkexec ausente, timeout ou erro real.

    `runner` é injetável para testes (default: subprocess.run)."""
    run = runner if runner is not None else _default_runner

    fd, tmp_rule_path = tempfile.mkstemp(prefix="mouse-hub-rule-")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(HID_RULE_CONTENT)
        script = _build_script(tmp_rule_path, rule_path)
        cmd: List[str] = [pkexec_path, "/bin/sh", "-c", script]
        try:
            completed = run(cmd, capture_output=True, text=True,
                            timeout=PKEXEC_TIMEOUT)
        except subprocess.TimeoutExpired:
            return OperationResult.failed(
                "Prompt de administrador expirou sem resposta"
            )
        except FileNotFoundError:
            return OperationResult.failed(
                "pkexec não encontrado — ambiente sem polkit; instale a "
                "regra udev manualmente ou via pacote .deb"
            )

        if completed.returncode == 0:
            return OperationResult.applied(
                "Acesso HID concedido: regra udev aplicada e dispositivos "
                "recarregados"
            )
        # pkexec: 126 = descartado pela política, 127 = auth falhou/
        # cancelado pelo usuário (fingerprint/senha).
        if completed.returncode in (126, 127):
            return OperationResult.permission_denied(
                "Autenticação de administrador cancelada ou negada — "
                "o acesso HID continua indisponível"
            )
        stderr = (completed.stderr or "").strip()
        detail = f": {stderr[:200]}" if stderr else ""
        return OperationResult.failed(
            f"Falha ao aplicar a regra udev (exit {completed.returncode})"
            f"{detail}"
        )
    finally:
        try:
            os.unlink(tmp_rule_path)
        except OSError:
            pass


def _default_runner(cmd, **kwargs) -> "subprocess.CompletedProcess":
    return subprocess.run(cmd, **kwargs)


def is_hid_permission_issue(reason: str) -> bool:
    """True quando o reason da capability aponta para o problema que o
    botão resolve (sem regra udev / sem permissão) — e não para outra
    causa (device ausente, EPIPE, ambiguidade)."""
    if not reason:
        return False
    lowered = reason.lower()
    # Marcadores POSITIVOS — a mensagem genérica de falha ("...não
    # relacionada a permissão") contém a palavra como negação e NÃO
    # é um problema que a regra udev resolve.
    return (
        "regra udev" in lowered
        or "acesso negado" in lowered
        or "sem permissão" in lowered
    )
