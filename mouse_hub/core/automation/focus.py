"""Detector de foco com frequência independente da frequência de clique.

O contrato funcional existente do produto permanece intacto: o
auto-clicker só gera cliques quando a janela ativa pertence ao
conjunto configurado (Minecraft, Lunar Client, Badlion, Feather,
Hypixel). O que muda é a eficiência — antes, cada consulta de foco
rodava `xdotool` por clique; agora a consulta ao sistema só ocorre
quando o cache expira.

Parâmetros padrão (tunáveis):

* `ttl_ms=500` — a 50 CPS, são no máximo 2 consultas ao sistema por
  segundo, contra 50 no modelo ingênuo;
* `unknown_is_not_focused=True` — sem título disponível, assume
  fora do jogo (comportamento conservador, igual ao original: clique
  só ocorre com janela confirmada).
"""

from __future__ import annotations

import time
from typing import Optional

from mouse_hub.core.automation.io import FocusChecker, TitleSource, FocusedState


class WindowFocusChecker(FocusChecker):
    """Implementação com cache de título e TTL configurável.

    `checker` é injetado: em produção, um adapter que lê
    `active_window_title` (xdotool) e expõe TTL; em teste, um fake
    com título programável. Isso mantém a frequência de clique (CPS)
    e a frequência de foco (TTL) totalmente desacopladas.
    """

    def __init__(
        self,
        checker: "TitleSource",
        ttl_ms: int = 500,
        unknown_is_not_focused: bool = True,
    ) -> None:
        if ttl_ms < 100:
            raise ValueError("TTL abaixo de 100 ms nega o propósito do cache")
        self._checker = checker
        self._ttl_ms = ttl_ms
        self._unknown_is_not_focused = unknown_is_not_focused
        self._cached: Optional[FocusedState] = None
        self._expiry = 0.0

    def is_focused(self, windows: tuple[str, ...]) -> FocusedState:
        """Consulta cache; só lê a janela ativa quando expirado.

        A tupla de substrings não afeta o custo: a comparação é
        `in` sobre strings em memória, case-insensitive (o X devolve
        títulos com capitalização variável — "minecraft" não casava
        com "Minecraft").

        Fail-closed: título indisponível (`None` do adapter ou "")
        nunca satisfaz o conjunto de jogos — clique sem janela
        confirmada é inaceitável.
        """
        now = time.monotonic()
        if self._cached is not None and now < self._expiry:
            cached = self._cached
            if not windows:
                return FocusedState(
                    focused=cached.focused, window_title=cached.window_title
                )
            return FocusedState(
                focused=cached.focused
                and any(w.lower() in cached.window_title.lower() for w in windows),
                window_title=cached.window_title,
            )

        title = self._checker.active_window_title()
        normalized = (title or "").lower()
        # Falha de leitura (None) e título vazio são tratados do mesmo
        # jeito pelo policy conservador — nenhum foco sem confirmação.
        focused = bool(normalized) if self._unknown_is_not_focused else True
        state = FocusedState(focused=focused, window_title=title or "")

        self._cached = state
        self._expiry = now + self._ttl_ms / 1000.0

        if not windows:
            return FocusedState(focused=state.focused, window_title=state.window_title)
        # Comparação case-insensitive sobre o título normalizado em
        # memória — o window_title exposto mantém a capitalização real.
        return FocusedState(
            focused=state.focused
            and any(w.lower() in normalized for w in windows),
            window_title=state.window_title,
        )

    def invalidate(self) -> None:
        """Força nova leitura do sistema na próxima consulta
        (útil após mudança de jogo/janela relevante)."""
        self._cached = None


