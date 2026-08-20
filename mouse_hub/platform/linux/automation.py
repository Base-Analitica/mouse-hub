"""Adapters de automação nativos para Linux — barreira definitiva contra
subprocessos no hot path.

Este módulo implementa os contratos definidos em
`mouse_hub.core.automation.io` usando diretamente `python-xlib` + XTest:

* `LinuxAutomationIO` — emite clique, press/release de tecla e mouse e
  movimento via `XTestFake*Event` na mesma conexão XDisplay reutilizada
  (nunca por clique/tecla/evento); cleanup idempotente;
* `X11TitleSource` — lê o título da janela ativa via
  `display.get_input_focus()` + `XGetAtomName`, sem xdotool, para o
  hot path de foco; mantém cache TTL compatível com `FocusChecker`;
* `focus_patterns()` — lista única e centralizada dos nomes/substrings
  de janela que a aplicação reconhece como "jogo permitido".

Nenhum destes componentes chama `subprocess.run/Popen`. Consultas
externas eventuais ficam em `LinuxSystemInput` (configuração esporádica
de DPI), fora dos hot paths de automação.

Thread safety:
* uma única instância é compartilhada entre consumidores (serviço
  central da UI);
* `XTestFake*Event` + `sync()` são chamados sob lock de conexão;
* a conexão é aberta sob demanda (lazy) e fechada em `cleanup()`.
"""

from __future__ import annotations

import contextlib
import threading
import time
from typing import Optional, Tuple

from Xlib import X
from Xlib.display import Display
from Xlib.ext import xtest
from Xlib import XK


def keycode_from_name(name: str, display: Optional[Display] = None) -> int:
    """Converte um nome de tecla legado (ex.: \"space\", \"a\") para o
    keycode X11. Tenta na ordem:

    1. nome numérico direto (\"38\" → keycode 38) — macros gravadas já
       gravam keycode numérico;
    2. keysym da biblioteca padrão (keysym_from_string), que cobre os
       nomes de tecla comuns do xdotool (\"space\", \"Return\", \"a\")
       com fallback maiúsculo;
    3. caractere único → keycode pelo primeiro matches do display
       (abre um Display sob demanda quando nenhum é fornecido).

    Retorna 0 quando não há correspondência — o IO trata keycode 0 como
    falha de emissão, nunca como evento vazio. O display é injetável
    para testes determinísticos (sem conexão X real)."""
    if not name:
        return 0
    name = str(name).strip()
    if not name:
        return 0
    # Nome numérico direto.
    if name.isdigit():
        code = int(name)
        return code if 0 < code < 256 else 0
    # Keysym por nome textual.
    keysym = 0
    # Xlib.XK.string_to_keysym cobre os nomes de tecla comuns do
    # xdotool ("space", "Return", "a") e retorna o keysym inteiro.
    try:
        XK.load_keysym_group("xf86")
    except Exception:  # noqa: BLE001
        pass
    try:
        keysym = int(XK.string_to_keysym(name))
        if keysym == 0:
            keysym = int(XK.string_to_keysym(name.title()))
    except Exception:  # noqa: BLE001
        keysym = 0
    if keysym != 0:
        # Keysym ASCII simples (letras minúsculas) mapeia direto para o
        # keycode XFree86 (offset 24) — sem consulta ao display.
        if 0x0020 <= keysym <= 0x007E:
            code = keysym - 0x0020 + 24
            if 0 < code < 256:
                return code
        dpy = display
        if dpy is None:
            try:
                dpy = Display()
            except Exception:  # noqa: BLE001
                return 0
        try:
            matches = dpy.keysym_to_keycodes(keysym)
            if matches:
                return int(matches[0][0])
        except Exception:  # noqa: BLE001
            pass
        finally:
            if display is None and dpy is not None:
                with contextlib.suppress(Exception):
                    dpy.close()
    # Caracter único: tentar o keysym direto.
    if len(name) == 1:
        code = ord(name) - 0x0020 + 24
        if 0 < code < 256:
            return code
    return 0

from mouse_hub.core.automation.io import AutomationIO, TitleSource
from mouse_hub.core.automation.types import MouseButton


FOCUS_PATTERN_TTL_MS = 500  # TTL do cache de título usado pelo foco


def focus_patterns() -> Tuple[str, ...]:
    """Lista centralizada e única dos padrões de janela de jogo.

    Todos os componentes (engine, UI, controller) consultam este ponto;
    nunca uma lista própria por tela. Inclui os padrões legados do
    produto, inclusive os que a base da PR #14 não carregava:
    Mina Launcher, Prismarine, Salwyrr e Vanilla.
    """
    return (
        "Minecraft",
        "Lunar Client",
        "Lunar",
        "Badlion",
        "Feather",
        "Hypixel",
        "Mina Launcher",
        "Prismarine",
        "Salwyrr",
        "Vanilla",
    )


class LinuxAutomationIO(AutomationIO):
    """Emissor direto de eventos via XTest — hot path sem subprocessos.

    Uma única conexão XDisplay é criada sob demanda e reutilizada por
    todas as emissões; `cleanup()` fecha exatamente uma vez, de forma
    idempotente. Retornar `False` em qualquer método indica falha
    detectável da emissão (display indisponível, extensão ausente,
    evento rejeitado) — o engine trata isso como FAILED.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._display: Optional[Display] = None
        self._error: Optional[str] = None

    # ── Conexão ────────────────────────────────────────────────────

    def _ensure_display(self) -> Optional[Display]:
        """Abre a conexão sob demanda.

        Toda a abertura do Display ocorre **dentro de self._lock** —
        a referência (`self._display`) e a criação da conexão são
        protegidas pelo mesmo lock, então dois threads que cheguem
        simultaneamente resultam em **exatamente um Display criado**.
        O thread perdedor reutiliza a conexão do vencedor; o excedente
        nunca é perdido (é fechado imediatamente).

        Retorna None (com self._error preenchido) quando o display não
        puder ser aberto ou a extensão XTest não estiver disponível —
        falha sinalizada ao caller em vez de exceção estourada.
        """
        with self._lock:
            if self._display is not None:
                return self._display
            display: Optional[Display] = None
            try:
                display = Display()
                if not display.has_extension("XTEST"):
                    display.close()
                    self._error = "extensão XTEST indisponível"
                    display = None
                    return None
                self._display = display
                return display
            except Exception as exc:  # noqa: BLE001 — Xlib lança bases variadas
                self._error = f"display indisponível: {exc}"
                display = None
                return None

    def cleanup(self) -> None:
        """Fecha a conexão exatamente uma vez, de forma idempotente."""
        self.close()

    def close(self) -> None:
        """Fecha a conexão exatamente uma vez, de forma idempotente —
        alias do `AutomationIO.close()` consumido pelo
        `AutomationService.cleanup()`."""
        with self._lock:
            display = self._display
            self._display = None
            self._error = None
        if display is not None:
            with contextlib.suppress(Exception):
                display.close()

    # ── Emissão ────────────────────────────────────────────────────

    def _emit(self, action) -> bool:  # pragma: no cover - requer X real
        display = self._ensure_display()
        if display is None:
            return False
        try:
            action(display)
            display.sync()
            return True
        except Exception:  # noqa: BLE001
            # Falha de emissão detectável — o engine vai para FAILED.
            return False

    def click(self, button: MouseButton) -> bool:
        def action(display: Display) -> None:
            btn = button.button_id
            xtest.fake_input(display, X.ButtonPress, btn)
            xtest.fake_input(display, X.ButtonRelease, btn)

        return self._emit(action)

    def press(self, button: MouseButton) -> bool:
        def action(display: Display) -> None:
            xtest.fake_input(display, X.ButtonPress, button.button_id)

        return self._emit(action)

    def release(self, button: MouseButton) -> bool:
        def action(display: Display) -> None:
            xtest.fake_input(display, X.ButtonRelease, button.button_id)

        return self._emit(action)

    def key_press(self, keycode: int) -> bool:
        if keycode == 0:
            return False

        def action(display: Display) -> None:
            xtest.fake_input(display, X.KeyPress, keycode)

        return self._emit(action)

    def key_release(self, keycode: int) -> bool:
        if keycode == 0:
            return False

        def action(display: Display) -> None:
            xtest.fake_input(display, X.KeyRelease, keycode)

        return self._emit(action)

    def move(self, x: int, y: int) -> bool:
        def action(display: Display) -> None:
            xtest.fake_input(display, X.MotionNotify, x=x, y=y)

        return self._emit(action)


class X11TitleSource(TitleSource):
    """Leitura do título da janela ativa diretamente via X11.

    Consulta `display.get_input_focus()` e o nome do top-level window
    via `_NET_WM_NAME`/`WM_NAME`. Resultado é cacheado por TTL
    (FOCUS_PATTERN_TTL_MS) — a frequência de consulta é independente do
    CPS. Quando o backend falha (display ausente, X indisponível), a
    UI pode distinguir capacidade indisponível de "jogo não focado":
    `active_window_title()` retorna None somente em falha, e
    `is_available()` expõe a capacidade.
    """

    def __init__(self, ttl_ms: int = FOCUS_PATTERN_TTL_MS) -> None:
        self._ttl_ms = ttl_ms
        self._lock = threading.Lock()
        self._display: Optional[Display] = None
        self._cached_title: Optional[str] = ""
        self._cached_until: float = 0.0
        self._unavailable: bool = False

    def is_available(self) -> bool:
        return not self._unavailable

    def close(self) -> None:
        """Fecha o display X owned exatamente uma vez, de forma
        idempotente — consumido pelo `AutomationService.cleanup()`
        para o TitleSource que ele mesmo criou (injetado = injetor).
        Chamadas após a primeira são no-ops; consultas posteriores
        reabrem sob demanda (o TTL zera junto)."""
        with self._lock:
            display = self._display
            self._display = None
            self._cached_title = ""
            self._cached_until = 0.0
        if display is not None:
            with contextlib.suppress(Exception):
                display.close()

    def _open(self) -> bool:
        if self._display is not None:
            return True
        try:
            self._display = Display()
            self._unavailable = False
            return True
        except Exception:  # noqa: BLE001
            self._unavailable = True
            self._display = None
            return False

    def _read_title(self) -> Optional[str]:
        display = self._ensure_display_local()
        if display is None:
            return None
        try:
            focus = display.get_input_focus()
            win = focus.focus
            while win is not None:
                props = win.get_full_property(display.intern_atom("_NET_WM_NAME"), 0)
                if props is None:
                    props = win.get_full_property(display.intern_atom("WM_NAME"), 0)
                if props is not None:
                    title = props.value.decode("utf-8", errors="replace").strip()
                    if title:
                        return title
                parent = win.query_tree().parent
                if parent is None or parent.id == display.screen().root.id:
                    break
                win = parent
            return ""
        except Exception:  # noqa: BLE001
            return None

    def _ensure_display_local(self) -> Optional[Display]:
        with self._lock:
            if self._display is None:
                self._open()
            return self._display

    def active_window_title(self) -> Optional[str]:
        """Título atual (cacheado por TTL). None = backend falhou."""
        with self._lock:
            now = time.monotonic()
            if now < self._cached_until:
                return self._cached_title
        title = self._read_title()
        if title is None:
            # Falha de backend: None distinto de título vazio.
            return None
        with self._lock:
            self._cached_title = title
            self._cached_until = time.monotonic() + self._ttl_ms / 1000.0
        return title


# A verificação de foco em si é o `WindowFocusChecker` do core da PR
# #14 (cache TTL, frequência independente do CPS). Este módulo fornece
# apenas a `TitleSource` nativa (`X11TitleSource`) que alimenta o
# checker — sem xdotool, com falha de backend sinalizada como None.
# Uso esperado:
#
#     from mouse_hub.platform.linux.automation import X11TitleSource
#     from mouse_hub.core.automation.focus import WindowFocusChecker
#     source = X11TitleSource()
#     checker = WindowFocusChecker(source, ttl_ms=500)
#     state = checker.is_focused(focus_patterns())
