"""Implementação real de SystemInput para o Linux Mint.

Isola todas as chamadas a `xinput`, `xdotool` e friends. Cada operação
reporta o desfecho real via `OperationResult` em vez de engolir falhas
ou fingir sucesso, e `is_available` permite que a UI trate a ausência
das ferramentas como capacidade indisponível, sem declarar o mouse
inteiro como desconectado.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from typing import Optional

from mouse_hub.core.operation import OperationResult
from mouse_hub.platform.protocol import SystemInput


class LinuxSystemInput(SystemInput):
    def __init__(self) -> None:
        self._cache: dict[str, bool] = {}

    def is_available(self) -> bool:
        if "xinput" not in self._cache:
            self._cache["xinput"] = shutil.which("xinput") is not None
        return self._cache["xinput"]

    def find_pointer_id(self, mouse_name: str) -> Optional[int]:
        """Localiza o ID do apontador contendo `mouse_name` na saída de
        `xinput list`, restringindo a dispositivos do tipo pointer."""
        if not self.is_available():
            return None
        try:
            result = subprocess.run(
                ["xinput", "list"], capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return None
        except (OSError, subprocess.TimeoutExpired):
            return None

        for line in result.stdout.splitlines():
            if mouse_name.lower() in line.lower() and "pointer" in line.lower():
                match = re.search(r"id=(\d+)", line)
                if match:
                    return int(match.group(1))
        return None

    def get_accel_speed(self, pointer_id: int) -> Optional[float]:
        if not self.is_available():
            return None
        try:
            result = subprocess.run(
                ["xinput", "list-props", str(pointer_id)],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return None
        except (OSError, subprocess.TimeoutExpired):
            return None

        for line in result.stdout.splitlines():
            if "libinput Accel Speed (" in line or "libinput Accel Speed:" in line:
                value = line.split(":")[-1].strip()
                try:
                    return float(value)
                except ValueError:
                    continue
        return None

    def set_accel_speed(self, pointer_id: int, accel: float) -> OperationResult:
        if not self.is_available():
            return OperationResult.unsupported("xinput não disponível")
        try:
            result = subprocess.run(
                [
                    "xinput", "set-prop", str(pointer_id),
                    "libinput Accel Speed", f"{accel:.3f}",
                ],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return OperationResult.failed(
                    f"xinput rejeitou a alteração: {result.stderr.strip()}"
                )
        except subprocess.TimeoutExpired:
            return OperationResult.failed("Tempo esgotado ao chamar xinput")
        except OSError as exc:
            return OperationResult.failed(f"Erro ao executar xinput: {exc}")

        # Confirmação pós-escrita: lê de volta o valor aplicado.
        current = self.get_accel_speed(pointer_id)
        if current is None or abs(current - accel) > 0.01:
            return OperationResult.failed(
                "Valor aplicado não confere com o solicitado"
            )
        return OperationResult.applied(f"Aceleração definida para {accel:.3f}")

    def active_window_title(self) -> Optional[str]:
        """Título da janela ativa via xdotool, ou None se indisponível."""
        if shutil.which("xdotool") is None:
            return None
        try:
            wid = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True, text=True, timeout=2,
            )
            if wid.returncode != 0:
                return None
            name = subprocess.run(
                ["xdotool", "getwindowname", wid.stdout.strip()],
                capture_output=True, text=True, timeout=2,
            )
            if name.returncode != 0:
                return None
            return name.stdout.strip() or None
        except (OSError, subprocess.TimeoutExpired):
            return None
