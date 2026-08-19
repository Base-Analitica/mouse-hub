"""mouse_hub.automation — motor nativo de macros e auto-clicker.

Este pacote implementa a camada de automação compartilhada do Mouse Hub
(aplicativo nativo PyQt no Linux Mint):

- events:   modelo canônico e versionável de eventos de macro
- store:    persistência (load/save/list/delete) com validação e
            compatibilidade com macros gravadas por versões antigas
- capture:  capturador real de teclado e mouse (XRecord via python-xlib)
- playback: reprodutor com timing monotônico, repeat e término limpo
- focus:    interface pequena e injetável para detecção de janela ativa
- autoclicker: motor de auto-clicker com estado real e foco configurável
"""

from .events import Macro, MacroEvent
from .store import MacroStore, MacroStoreError
from .capture import InputCapture
from .playback import PlaybackController, PlaybackState
from .focus import FocusDetector, XdotoolFocusDetector
from .autoclicker import AutoClickerEngine, AutoClickerState

__all__ = [
    "Macro",
    "MacroEvent",
    "MacroStore",
    "MacroStoreError",
    "InputCapture",
    "PlaybackController",
    "PlaybackState",
    "FocusDetector",
    "XdotoolFocusDetector",
    "AutoClickerEngine",
    "AutoClickerState",
]
