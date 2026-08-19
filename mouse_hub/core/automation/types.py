"""Tipos de eventos e contratos das automações.

Este módulo define o vocabulário compartilhado entre o gravador, o
player, o auto-clicker e o detector de foco. Nenhum evento real é
produzido aqui: tudo é injetado via interfaces (ver
`mouse_hub.platform.protocol.AutomationIO`), o que permite testar o
motor inteiro sem xdotool, xinput ou display real.

Conceito central: os hot paths (clique a 50 CPS, captura de evento)
NÃO criam subprocessos. A produção de evento é uma chamada direta
(`AutomationIO.click` / `emit_event`); a verificação de foco é um
componente separado com frequência própria.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MouseButton(Enum):
    """Botões suportados pelo auto-clicker e graváveis em macros.

    Equivalente aos botões do protocolo X: 1 = esquerdo, 2 = meio,
    3 = direito. Os nomes do app (esquerdo/meio/direito) mapeiam
    1:1 para estes valores.
    """

    LEFT = "left"
    MIDDLE = "middle"
    RIGHT = "right"

    @property
    def button_id(self) -> int:
        return {"left": 1, "middle": 2, "right": 3}[self.value]

    @classmethod
    def from_id(cls, button_id: int) -> "MouseButton":
        return {1: cls.LEFT, 2: cls.MIDDLE, 3: cls.RIGHT}[button_id]


class EventType(Enum):
    """Tipos de evento capturáveis em uma macro."""

    MOUSE_PRESS = "mouse_press"
    MOUSE_RELEASE = "mouse_release"
    MOUSE_MOVE = "mouse_move"
    KEY_PRESS = "key_press"
    KEY_RELEASE = "key_release"


@dataclass(frozen=True)
class RecordedEvent:
    """Um evento gravado na linha do tempo da macro.

    `delta_ms` é o intervalo desde o evento anterior (timing relativo,
    como no formato de persistência existente), permitindo a reprodução
    independente do momento da gravação.
    """

    kind: EventType
    button: int  # botão do mouse (0 quando não aplicável)
    keycode: int  # código da tecla (0 quando não aplicável)
    delta_ms: float


@dataclass(frozen=True)
class FocusedState:
    """Resultado da checagem de foco da janela ativa."""

    focused: bool
    window_title: str  # título observado ("" quando indisponível)
