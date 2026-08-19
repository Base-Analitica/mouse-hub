"""Detecção de janela ativa — interface pequena e injetável.

O auto-clicker só clica quando a janela ativa corresponde a um padrão
permitido (regra atual do produto: Minecraft/Lunar Client). A obtenção do
foco é separada em uma interface mínima para permitir testes com fake e
eventual troca de implementação (xdotool -> query X11 nativa) sem tocar o
motor.

Implementação atual: xdotool (mesmo stack do projeto). A versão nativa
via Display.get_input_focus + _NET_WM_NAME fica como ponto de integração
futuro — documentado na PR, fora de escopo desta branch (a instância que
cuida de core/plataforma assume depois).
"""

import abc
import re
import subprocess

# Padrões permitidos (mantém a regra atual do produto: Minecraft only)
DEFAULT_ALLOWED_PATTERNS = [
    "Minecraft",
    "Lunar Client",
    "Lunar",
    "Badlion",
    "Feather",
    "Hypixel",
]


class FocusDetector(abc.ABC):
    """Interface injetável de detecção de janela ativa."""

    @abc.abstractmethod
    def active_window_name(self):
        """Retorna o título da janela ativa ou None."""

    def is_allowed(self, allowed_patterns=DEFAULT_ALLOWED_PATTERNS):
        name = self.active_window_name()
        if not name:
            return False
        lower = name.lower()
        return any(p.lower() in lower for p in allowed_patterns)


class XdotoolFocusDetector(FocusDetector):
    """Detecção via `xdotool getactivewindow` + `getwindowname`.

    Um único subprocesso por consulta (comportamento atual do produto).
    Evitamos iniciar subprocessos em alta frequência: o motor de
    auto-clicker só consulta a cada 200ms quando não está clicando.
    """

    def active_window_name(self):
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True, text=True, timeout=2)
            if result.returncode != 0:
                return None
            wid = result.stdout.strip()
            result = subprocess.run(
                ["xdotool", "getwindowname", wid],
                capture_output=True, text=True, timeout=2)
            if result.returncode != 0:
                return None
            return result.stdout.strip() or None
        except Exception:
            return None
