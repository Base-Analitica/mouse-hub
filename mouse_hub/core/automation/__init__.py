"""Automações de baixo overhead.

Módulos:
* types       — RecordedEvent, MouseButton, EventType, FocusedState
* io          — AutomationIO (emissor direto, hot path sem subprocesso)
                e FocusChecker (cache TTL, frequência própria)
* focus       — WindowFocusChecker com TTL configurável
* scheduler   — AutomationScheduler (Event.wait, cancelável, 0 busy-wait)
* autoclicker — AutoClickerEngine (1 thread, CPS/botão sem recriar worker)
* macros      — MacroRecorder (callback, lifecycle curto) e MacroPlayer
                (scheduler eficiente, cancelável)

Nenhum componente aqui cria subprocesso, spin-loop ou thread por
evento. A adoção pelos engines da UI continua sendo responsabilidade
de outra instância; este pacote apenas entrega a implementação
eficiente e os contratos de injeção.
"""

from mouse_hub.core.automation.autoclicker import AutoClickerEngine, EngineStats
from mouse_hub.core.automation.focus import WindowFocusChecker
from mouse_hub.core.automation.io import AutomationIO, FocusChecker, FocusedState
from mouse_hub.core.automation.macros import MacroPlayer, MacroRecorder
from mouse_hub.core.automation.scheduler import AutomationScheduler
from mouse_hub.core.automation.types import (
    EventType,
    MouseButton,
    RecordedEvent,
)

__all__ = [
    "AutoClickerEngine",
    "AutomationIO",
    "AutomationScheduler",
    "EngineStats",
    "EventType",
    "FocusChecker",
    "FocusedState",
    "MacroPlayer",
    "MacroRecorder",
    "MouseButton",
    "RecordedEvent",
    "WindowFocusChecker",
]
