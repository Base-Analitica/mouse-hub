"""Contrato de I/O das automações — a barreira anti-subprocess.

O requisito crítico desta PR: em nenhum hot path (clique do
auto-clicker, emissão de evento de macro, checagem de foco) se cria
um subprocesso. `xdotool click` a cada ciclo, em 20-50 CPS, é
proibido — cada `Popen` custa ordens de magnitude mais que o clique
em si e transforma o engine num multiplicador de processos.

A alternativa adequada no stack Linux do projeto (que já usa
`python-xlib`) é gerar eventos diretamente via `XTestFake*` na
mesma conexão XDisplay:

* `XTestFakeButtonEvent` — clique (hot path do auto-clicker);
* `XTestFakeKeyEvent` — tecla (emissão de macro);
* `XTestFakeMotionEvent` — movimento (emissão de macro).

Estas chamadas são uma função C da própria libXtst chamada pelo
Python, sem fork/exec. Para macros de teclado também serve
`Xlib.ext.xtest.fake_input`.

`AutomationIO` é o ponto de injeção: em produção, `LinuxAutomationIO`
usa `python-xlib`; em teste, um fake acumula eventos. O motor nunca
sabe (nem precisa saber) como o evento chegou ao X.

O foco é lido por `FocusChecker` — interface separada justamente para
que a frequência de checagem de foco seja independente da frequência
de clique (ver `focus.py`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Tuple

from mouse_hub.core.automation.types import FocusedState, MouseButton


class AutomationIO(ABC):
    """Emissor direto de eventos de input. Hot path sem subprocessos.

    Implementações devem ser thread-safe: o auto-clicker chama
    `click` de uma thread dedicada, e o player de macro também é
    dedicado. Uma única instância é compartilhada entre consumidores
    (reuso de serviço, nunca um emissor por clique).
    """

    @abstractmethod
    def click(self, button: MouseButton) -> bool:
        """Gera pressionamento+soltura do botão. Retorna False apenas
        se a emissão falhar de forma detectável."""

    @abstractmethod
    def press(self, button: MouseButton) -> bool:
        """Pressiona e segura o botão (usada por macros com press/release)."""

    @abstractmethod
    def release(self, button: MouseButton) -> bool:
        """Solta o botão mantido."""

    @abstractmethod
    def key_press(self, keycode: int) -> bool:
        """Pressiona uma tecla por código X (0 = inválido)."""

    @abstractmethod
    def key_release(self, keycode: int) -> bool:
        """Solta uma tecla."""

    @abstractmethod
    def move(self, x: int, y: int) -> bool:
        """Move o ponteiro para coordenadas absolutas."""

    def close(self) -> None:
        """Libera recursos mantidos (display X, workers) — chamado
        pelo `AutomationService.cleanup()`. Default no-op para fakes."""


class TitleSource:
    """Abstração mínima da leitura do título da janela ativa.

    Em produção: adapter sobre `SystemInput.active_window_title`
    (xdotool). Existe separadamente de `FocusChecker` para que o
    mesmo reader seja compartilhado por engine, UI e outras
    ferramentas — nunca uma nova consulta por consumidor.
    """

    def active_window_title(self) -> Optional[str]:
        raise NotImplementedError


class FocusChecker(ABC):
    """Verifica a janela ativa com frequência independente do clicker.

    A interface é deliberadamente genérica: o motor pergunta "está
    focado?" na frequência decidida por quem o configura, e a
    implementação decide se consulta o X (xdotool getactivewindow,
    ou XLib.display.get_input_focus quando disponível) e quando
    caches expiram.

    Implementação padrão (`mouse_hub.platform.linux`): mantém um
    cache de título com TTL; a consulta ao sistema só acontece quando
    o cache expirar — a 50 CPS com TTL de 500 ms, o custo de foco é
    no máximo 2 consultas por segundo, não 50.
    """

    @abstractmethod
    def is_focused(self, windows: Tuple[str, ...]) -> FocusedState:
        """True se a janela ativa contém algum dos substrings."""
        raise NotImplementedError
