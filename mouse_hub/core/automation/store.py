"""Persistência transacional de macros.

Requisitos que a escrita ingênua (PR #14 `save`/`load`) não cobria:

* **transação**: gravar no arquivo temporário do mesmo diretório e
  renomear atomicamente (mesmo filesystem — `os.replace`); o arquivo
  original nunca fica pela metade — interrupção no meio da escrita
  deixa o backup intacto;
* **rollback automático**: JSON corrompido é movido para
  `macros.json.bak.N` (backup de evidência) e a escrita recomeça de
  um estado vazio — o app nunca trava num arquivo morto;
* **nome duplicado**: `add()` rejeita nome já existente (com
  `overwrite=False`) — a UI decide com o usuário;
* **macro vazia**: gravações com zero eventos são rejeitadas
  explicitamente (com o motivo em `MacroStoreError.reason`) — o bug
  original da gravação fantasma (flags sem eventos) volta a ser
  impossível de persistir;
* **compatibilidade legado**: o carregador aceita o formato v0
  (`mouse_click`/`key_press` com timestamp absoluto `t`) e o formato
  web, mapeando para os tipos canônicos (v1) com delta relativo;
* **validação**: schema v1 com tipos/funções canônicos, teto de
  eventos por macro e validação de delta não-negativo.
"""

from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from mouse_hub.core.automation.types import EventType, MouseButton, RecordedEvent

# Conversão de nome textual de tecla ("w", "space", "Return") para
# keycode real — o main legado gravava key como nome xdotool/XK,
# nunca como int. Sem display X disponível (testes/sem servidor),
# a varredura keysym→keycode não é possível: retorna None.
_XK = None
_display_for_keycode = None

# Fallback determinístico sem display X: mapeamento keysym→keycode do
# layout US padrão (o layout de referência do X). Só é usado quando
# não há servidor para consultar — no runtime real, display
# #keysym_to_keycode resolve pelo servidor.
_FALLBACK_KEYCODES: Dict[int, int] = {
    # Latin-1 a-z (keysyms 0x61..0x7a) → keycodes 38..63
    **{0x61 + i: 38 + i for i in range(26)},
    # dígitos 0-9 (0x30..0x39) → keycodes 10..19 (linha numérica)
    **{0x30 + i: 10 + i for i in range(10)},
    0x020: 65,   # space
    0xff0d: 36,  # Return
    0xff09: 23,  # Tab
    0xff1b: 9,   # Escape
    0xff50: 110, # Home
    0xff51: 113, # Left
    0xff52: 98,  # Up
    0xff53: 114, # Right
    0xff54: 116, # Down
    0xffe1: 50,  # Shift_L
    0xffe2: 62,  # Shift_R
    0xffe3: 37,  # Control_L
    0xffe4: 105, # Control_R
    0xffe9: 64,  # Alt_L (0xffe9 resolve Meta_L/Alt_L pelo servidor)
    0xffea: 108, # Alt_R
    0xffe5: 66,  # Caps_Lock
    0xff55: 119, # Prior/PageUp
    0xff56: 121, # Next/PageDown
    0xff57: 115, # End
    0xffff: 119, # Delete
    0xff08: 22,  # BackSpace
    0xff13: 77,  # Num_Lock
    0xff14: 78,  # Scroll_Lock
    0xffbe: 95,  # F1
    **{0xffbe + i: 95 + i for i in range(12)},  # F1..F12 = 95..106
    0xffad: 106, # KP_Divide
    0xffaa: 63,  # KP_Multiply
    0xffaf: 82,  # KP_Subtract
    0xffab: 86,  # KP_Add
    0xff8d: 104, # KP_Enter
    0xff9e: 90,  # KP_0
    **{0xffb0 + i: 91 + i for i in range(9)},  # KP_1..KP_9 = 87..95
    0xffae: 83,  # KP_Decimal
    0xff95: 79,  # KP_7
    0xff96: 80,  # KP_8
    0xff97: 81,  # KP_9
    0xff98: 83,  # KP_4
    0xff99: 84,  # KP_5
    0xff9a: 85,  # KP_6
    0xff9b: 87,  # KP_1
    0xff9c: 88,  # KP_2
    0xff9d: 89,  # KP_3
}


def _xk_module():
    global _XK
    if _XK is None:
        try:
            from Xlib import XK as _m
            # Carrega os grupos de keysyms usados pelos jogos
            # (latin1 cobre a-z, dígitos, space, Return etc.).
            for _g in ("latin1", "xf86"):
                try:
                    _m.load_keysym_group(_g)
                except Exception:
                    pass
            _XK = _m
        except ImportError:
            _XK = False
    return _XK if _XK else None


def textual_key_to_keycode(key: str, display=None) -> int:
    """Nome textual ("w", "space", "Return") → keycode real via keysym.

    `int("w")` é rejeitado explicitamente — nome que não é decimal
    nunca vira keycode inteiro; quando um display real está disponível
    (runtime), o keysym é traduzido pelo servidor; sem display,
    retorna 0 (evento de tecla inválido — o player ignora keycode 0)."""
    if not isinstance(key, str) or not key:
        return 0
    # Nome decimal? Rejeitado — o main grava nome textual.
    try:
        int(key)
    except ValueError:
        pass
    else:
        return 0
    xk = _xk_module()
    if xk is None:
        return 0
    keysym = xk.string_to_keysym(key)
    if keysym == 0:
        return 0
    if display is not None and hasattr(display, "keysym_to_keycode"):
        code = display.keysym_to_keycode(keysym)
        if code:
            return code
    # Sem display (testes headless): consulta o mapa determinístico do
    # layout US — nunca inventa keycode a partir de string.
    return _FALLBACK_KEYCODES.get(keysym, 0)

SCHEMA_VERSION = 1
MAX_EVENTS_PER_MACRO = 100_000
MAX_MACROS = 500  # teto defensivo para o container

# Mapeamento de tipos legados (v0 do app nativo e da UI web) para os
# tipos canônicos do schema v1. Usado exclusivamente no carregador.
LEGACY_TYPE_MAP = {
    # Formato web (PRs anteriores): eventos separados em lists.
    # "mouse_click" NÃO está aqui — é tratado em separado pelo
    # _convert_legacy (vira press+release, pois era clique completo).
    "key_press": EventType.KEY_PRESS,
    "key_release": EventType.KEY_RELEASE,
    "mouse_down": EventType.MOUSE_PRESS,
    "mouse_up": EventType.MOUSE_RELEASE,
    # Formato canônico v1
    "mouse_press": EventType.MOUSE_PRESS,
    "mouse_release": EventType.MOUSE_RELEASE,
    "mouse_move": EventType.MOUSE_MOVE,
    "key_press_v1": EventType.KEY_PRESS,
    "key_release_v1": EventType.KEY_RELEASE,
    # Formato web compacto do main: type="key" com `key` textual,
    # type="click" com `button`, type="move" com `x`/`y`.
    "key": EventType.KEY_PRESS,
    "click": EventType.MOUSE_PRESS,
    "move": EventType.MOUSE_MOVE,
}


class MacroStoreError(Exception):
    """Falha de persistência com motivo reportável à UI."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _button_id(raw: Any) -> Optional[int]:
    """Normaliza o button gravado para o ID numérico X (1/2/3).

    O store CANÔNICO grava o ID numérico (`MouseButton.button_id`);
    arquivos antigos podem trazer o nome textual ("left", "middle",
    "right") — ambos são aceitos aqui. Valores inconvertíveis
    retornam None e a entrada é descartada explicitamente (com
    evidência registrada no `discarded_entries`), nunca silenciosamente."""
    if isinstance(raw, int):
        if raw in (0, 1, 2, 3):
            return raw
        return None
    if isinstance(raw, float) and raw.is_integer() and int(raw) in (0, 1, 2, 3):
        return int(raw)
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if normalized in ("left", "middle", "right"):
            return MouseButton(normalized).button_id
        if normalized == "":
            return 0
        return None
    return None


def _validate_event(entry: Dict[str, Any]) -> Optional[RecordedEvent]:
    if not isinstance(entry, dict):
        return None
    kind_raw = entry.get("kind")
    if not isinstance(kind_raw, str):
        return None
    try:
        kind = EventType(kind_raw)
    except ValueError:
        return None
    # MOUSE_MOVE usa o campo `button` como coordenada X da tela
    # (o player emite `io.move(x=event.button, y=event.keycode)` —
    # são coordenadas, não ID de botão — aceita qualquer não-negativo).
    button = (
        _move_coordinate(entry.get("button", 0))
        if kind == EventType.MOUSE_MOVE
        else _button_id(entry.get("button", 0))
    )
    if button is None:
        return None
    try:
        keycode = int(entry.get("keycode", 0))
        delta = float(entry.get("delta_ms", 0))
    except (TypeError, ValueError):
        return None
    if delta < 0:
        return None
    return RecordedEvent(kind=kind, button=button, keycode=keycode, delta_ms=delta)


def _move_coordinate(raw: Any) -> Optional[int]:
    """Coordenada de movimento (X/Y) como inteiro não-negativo.

    Diferente do ID de botão: não há teto pequeno — um movimento
    legítimo pode apontar qualquer pixel da tela."""
    if isinstance(raw, int):
        return raw if raw >= 0 else None
    if isinstance(raw, float) and raw.is_integer():
        i = int(raw)
        return i if i >= 0 else None
    return None


def _convert_legacy(entries: List[Any]) -> List[RecordedEvent]:
    """Converte o formato legado v0/web para eventos canônicos.

    O formato legado usava timestamp absoluto `t` (ms desde o início)
    e nomes de tipo distintos. O delta relativo é reconstruído pela
    diferença de `t` — o resultado é indistinguível do v1 para o
    player.
    """
    events: List[RecordedEvent] = []
    # prev_t em SEGUNDOS: o main real grava time=time.time()-start,
    # ou seja, float de segundos — converter para ms na hora do delta
    # evita perda de resolução e erros de ordem de grandeza.
    prev_t = 0.0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        kind_raw = entry.get("type") or entry.get("kind")
        if not isinstance(kind_raw, str):
            continue
        # "mouse_click" legado é tratado à parte (clique completo vira
        # press+release) — o tipo canônico é irrelevante para ele, e
        # a resolução genérica abaixo o descartaria como desconhecido.
        if kind_raw == "mouse_click":
            kind = EventType.MOUSE_PRESS
        else:
            kind = LEGACY_TYPE_MAP.get(kind_raw)
            if kind is None:
                try:
                    kind = EventType(kind_raw)
                except ValueError:
                    continue
        try:
            # O formato REAL do main legado: `time` em SEGUNDOS
            # (time.time() - record_start), `key` textual ("w",
            # "space", "Return"), `button` no mouse_click, `x`/`y`
            # no mouse_move. O v0/web usava `t`/`keycode`/`button`.
            # Ambos coexistem aqui — segundos viram ms no delta.
            t_raw = entry.get("t")
            if t_raw is not None:
                t_sec = float(t_raw) / 1000.0  # v0/web era ms
            else:
                t_sec = float(entry.get("time", 0))  # main real: segundos
            key_raw = entry.get("keycode")
            key_textual = entry.get("key")
            if isinstance(key_raw, int):
                keycode = int(key_raw)
            elif isinstance(key_textual, str):
                keycode = textual_key_to_keycode(key_textual)
            else:
                keycode = 0
            button = int(entry.get("button", entry.get("click", 0)))
            move_xy = entry.get("move")
        except (TypeError, ValueError):
            continue
        delta_ms = max(0.0, (t_sec - prev_t) * 1000.0) if events else 0.0
        prev_t = t_sec
        # Formato web compacto: `type="move"` guarda as coordenadas em
        # `x`/`y` (não no array `move`) — normalizar para o array que o
        # branch de MOUSE_MOVE espera.
        if kind_raw in ("move", "mouse_move") and move_xy is None:
            # Tanto o formato web (`type="move"`) quanto o main puro
            # (`type="mouse_move"`) guardam as coordenadas em `x`/`y`.
            mx_raw, my_raw = entry.get("x"), entry.get("y")
            if mx_raw is not None and my_raw is not None:
                move_xy = [mx_raw, my_raw]
        if kind_raw == "mouse_click":
            # Formato legado: mouse_click era um clique COMPLETO
            # (xdotool click, press+release atômico). Na reprodução
            # nativa vira press imediatamente seguido de release com o
            # mesmo delta para não alterar o timing geral.
            events.append(
                RecordedEvent(kind=EventType.MOUSE_PRESS, button=button, keycode=keycode, delta_ms=delta_ms)
            )
            events.append(
                RecordedEvent(kind=EventType.MOUSE_RELEASE, button=button, keycode=keycode, delta_ms=0.0)
            )
        elif kind == EventType.MOUSE_MOVE:
            # `move` do main real guarda as coordenadas em [x, y]; o
            # player lê io.move(x=event.button, y=event.keycode), então
            # x→button e y→keycode — o formato fica equivalente ao v1.
            if isinstance(move_xy, (list, tuple)) and len(move_xy) >= 2:
                mx, my = int(move_xy[0]), int(move_xy[1])
            else:
                mx, my = keycode, button
            # O player emite io.move(x=event.button, y=event.keycode)
            # — x vai em button, y vai em keycode para fechar o ciclo
            # do formato canônico (v1).
            events.append(
                RecordedEvent(kind=EventType.MOUSE_MOVE, button=mx, keycode=my, delta_ms=delta_ms)
            )
        elif kind_raw in ("key", "click") and kind_raw == "key":
            # Formato web compacto: type="key" é um pressionamento
            # completo (press + release), como xdotool key — press
            # carrega o delta real; release fecha com delta 0.
            events.append(
                RecordedEvent(kind=EventType.KEY_PRESS, button=button, keycode=keycode, delta_ms=delta_ms)
            )
            events.append(
                RecordedEvent(kind=EventType.KEY_RELEASE, button=button, keycode=keycode, delta_ms=0.0)
            )
        elif kind_raw == "click":
            # type="click" = clique completo (xdotool click): press +
            # release imediato com delta 0 — mesmo tratamento do
            # mouse_click do formato main puro.
            events.append(
                RecordedEvent(kind=EventType.MOUSE_PRESS, button=button, keycode=keycode, delta_ms=delta_ms)
            )
            events.append(
                RecordedEvent(kind=EventType.MOUSE_RELEASE, button=button, keycode=keycode, delta_ms=0.0)
            )
        else:
            events.append(
                RecordedEvent(kind=kind, button=button, keycode=keycode, delta_ms=delta_ms)
            )
    return events


class MacroStore:
    """Container transacional de macros.

    Uso:

        store = MacroStore(Path.home() / ".mouse-hub" / "macros.json")
        store.load()                         # valida, converte legado
        store.add("macro-1", events)         # transacional
        store.list()                         # nomes
        store.get("macro-1")                 # eventos canônicos
        store.delete("macro-1")              # transacional
        store.flush()                        # persiste de volta ao disco
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._macros: Dict[str, List[RecordedEvent]] = {}
        self._dirty = False
        # Estado publicado — último commit que sobreviveu a um flush
        # bem-sucedido (ou ao load). Usado como ponto de retorno real
        # quando a escrita falha: add/delete que não foram persistidos
        # são desfazidos contra esse snapshot.
        self._published: Dict[str, List[RecordedEvent]] = {}
        # Evidência de entradas descartadas no último reload (issue #16):
        # o reload nunca silencia perda — o caller consulta
        # `discarded_entries` para reportar à UI.
        self._discarded_entries: Dict[str, int] = {}

    @property
    def path(self) -> Path:
        return self._path

    @property
    def dirty(self) -> bool:
        return self._dirty

    # ── Leitura ────────────────────────────────────────────────────

    def load(self) -> int:
        """Carrega (e valida/converte) o container. Retorna o número
        de macros válidas carregadas; arquivos ausentes/corrompidos
        viram estado vazio (corrompido é arquivado como .bak.N)."""
        if not self._path.exists():
            self._reset()
            return 0

        raw: str
        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError as exc:
            # Arquivo ilegível e sem chance de backup: estado vazio,
            # original intacto — o app nunca deve travar no load.
            self._reset()
            self._read_error = str(exc)
            return 0
        try:
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            try:
                self._archive_corrupt(exc)
            except MacroStoreError:
                # Backup impossível: original preservado, estado vazio.
                self._read_error = str(exc)
            else:
                self._read_error = None
            self._reset()
            return 0
        if not isinstance(data, dict):
            try:
                self._archive_corrupt("container não é um objeto JSON")
            except MacroStoreError:
                self._read_error = "container não é um objeto JSON"
            else:
                self._read_error = None
            self._macros = {}
            self._dirty = False
            return 0

        # O container v1 é empacotado (schema_version + macros) —
        # iterar o objeto raiz direto carregaria os metadados como
        # macros. O legado v0/web era o dicionário raiz.
        container = data.get("macros") if "schema_version" in data else data
        if not isinstance(container, dict):
            self._archive_corrupt("container não é um objeto JSON")
            self._reset()
            return 0

        macros: Dict[str, List[RecordedEvent]] = {}
        discarded: Dict[str, int] = {}
        for name, entries in container.items():
            if not isinstance(name, str) or not name:
                continue
            if len(macros) >= MAX_MACROS:
                break
            events, dropped = self._parse_entries(entries)
            if events is not None and events:
                macros[name] = events
            if dropped:
                discarded[name] = dropped
        # Evidência do que o reload descartou: macros com entradas
        # parcialmente inválidas entram, mas o caller (e a UI) pode
        # consultar `discarded_entries` — nada é perdido em silêncio.
        self._discarded_entries = discarded
        self._macros = macros
        self._published = {name: list(events) for name, events in macros.items()}
        self._dirty = False
        return len(macros)

    def _parse_entries(
        self, entries: Any
    ) -> tuple[Optional[List[RecordedEvent]], int]:
        """Parseia a lista de entradas de uma macro.

        Retorna (eventos, descartados): `descartados` é a contagem de
        entradas inválidas que o carregador pulou — a UI usa esse
        número para reportar perda de dados em vez de silenciar.
        O formato REAL do main legado é um wrapper {name, events,
        created, count} — a lista de eventos fica em "events";
        created/count são metadados descartáveis para a reprodução.
        O container raiz nunca traz schema_version."""
        if isinstance(entries, dict) and "events" in entries:
            macro_events = entries["events"]
            if not isinstance(macro_events, list):
                return None, 0
            entries = macro_events
        if not isinstance(entries, list):
            return None, 0
        # Schema v1: cada entrada tem "kind"
        if entries and isinstance(entries[0], dict) and "kind" in entries[0]:
            parsed: List[RecordedEvent] = []
            dropped = 0
            for raw in entries:
                event = _validate_event(raw)
                if event is None:
                    dropped += 1
                    continue
                parsed.append(event)
            return parsed[:MAX_EVENTS_PER_MACRO] if parsed else None, dropped
        # Formato legado (v0/web): "type" + "t" — entradas ilegíveis
        # também contam como descartadas (evidência), mesmo que o
        # conversor ignore a linha com `continue`.
        total = len(entries) if isinstance(entries, list) else 0
        legacy = _convert_legacy(entries)
        dropped = total - len(legacy)
        return legacy if legacy else None, dropped

    @property
    def discarded_entries(self) -> Dict[str, int]:
        """Contagem de entradas descartadas por macro no último reload.

        Um reload que carregou macros com menos eventos do que o
        arquivo continha fica visível aqui — a UI pode reportar a
        perda em vez de fingir que tudo voltou inteiro."""
        return dict(self._discarded_entries)

    # ── Inicialização ──────────────────────────────────────────────

    def _reset(self) -> None:
        """Estado vazio consistente — usado após falha de leitura."""
        self._macros = {}
        self._published = {}
        self._discarded_entries = {}
        self._dirty = False

    def _archive_corrupt(self, exc) -> None:
        """Move o arquivo corrompido para .bak.N como evidência.

        A perda deliberada do original é inaceitável — se o backup não
        puder ser criado (permissões, disco cheio), o arquivo original
        fica intacto e a exceção é levantada para o caller decidir,
        em vez de deletar silenciosamente a única cópia dos dados."""
        suffix = int(time.time())
        backup = self._path.with_name(f"{self._path.name}.bak.{suffix}")
        try:
            os.replace(self._path, backup)
        except OSError:
            # NÃO deletar o original: sem backup válido, a evidência
            # corrompida é a única cópia. O caller (load) sabe que a
            # leitura falhou e pode reportar à UI.
            raise MacroStoreError(
                f"backup do arquivo corrompido impossível ({exc}); "
                "o original foi preservado"
            )

    # ── Escrita ────────────────────────────────────────────────────

    def list(self) -> List[str]:
        return list(self._macros.keys())

    def get(self, name: str) -> Optional[List[RecordedEvent]]:
        events = self._macros.get(name)
        return list(events) if events is not None else None

    def has(self, name: str) -> bool:
        return name in self._macros

    def add(
        self, name: str, events: List[RecordedEvent], overwrite: bool = False
    ) -> None:
        """Adiciona uma macro de forma transacional.

        Levanta `MacroStoreError` quando: o nome já existe (e
        `overwrite=False`), a lista de eventos é vazia, o nome é
        inválido, ou o tamanho excede o teto defensivo. A gravação
        fantasma (macro sem eventos) é rejeitada aqui.
        """
        if not isinstance(name, str) or not name.strip():
            raise MacroStoreError("nome inválido")
        name = name.strip()
        if not events:
            raise MacroStoreError("macro vazia: gravação sem eventos")
        if len(events) > MAX_EVENTS_PER_MACRO:
            raise MacroStoreError(
                f"macro excede o teto de {MAX_EVENTS_PER_MACRO} eventos"
            )
        if name in self._macros and not overwrite:
            raise MacroStoreError(f"macro '{name}' já existe")

        self._macros[name] = list(events)
        self._dirty = True

    @property
    def _live(self) -> Dict[str, List[RecordedEvent]]:
        """Acesso único ao dicionário vivo (memória) para leitura."""
        return self._macros

    def delete(self, name: str) -> bool:
        if name not in self._macros:
            return False
        del self._macros[name]
        self._dirty = True
        return True

    def flush(self) -> None:
        """Persiste o container de forma transacional com rollback real.

        1. snapshot do estado atual (_macros) — o ponto de retorno;
        2. serializa no arquivo temporário do MESMO diretório (mesmo
           filesystem) — se falhar, o original não foi tocado;
        3. renomeia atomicamente com `os.replace` — se falhar, o tmp é
           descartado e o original continua íntegro;
        4. só então o snapshot vira o estado publicado.

        Em qualquer falha de escrita, o estado em memória retorna ao
        snapshot e a exceção é levantada — a próxima flush reescreve
        o conteúdo garantidamente completo (nada fica pela metade)."""
        if not self._dirty:
            return
        # Snapshot do estado publicado (último commit) é o ponto de
        # retorno real: adições/deleções não persistidas são desfazidas
        # contra ele — nada fica publicado no meio de uma transação.
        snapshot = {name: list(events) for name, events in self._published.items()}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "generated_ms": int(time.time() * 1000),
            "macros": {
                name: [
                    {
                        "kind": event.kind.value,
                        "button": event.button,  # ID numérico X (1/2/3)
                        "keycode": event.keycode,
                        "delta_ms": round(event.delta_ms, 2),
                    }
                    for event in events
                ]
                for name, events in self._macros.items()
            },
        }
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        try:
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            try:
                tmp.unlink()
            except OSError:
                pass
            self._macros = snapshot
            self._dirty = True  # estado restaurado ainda precisa de flush
            raise MacroStoreError(f"falha ao escrever o arquivo temporário: {exc}")
        try:
            os.replace(tmp, self._path)
        except OSError:
            try:
                tmp.unlink()
            except OSError:
                pass
            self._macros = snapshot
            self._dirty = True  # estado restaurado ainda precisa de flush
            raise MacroStoreError("falha ao persistir o container de macros")
        # Escrita concluída: o estado atual vira o novo estado publicado
        # e o snapshot avança junto — a próxima falha desfará apenas as
        # mudanças posteriores.
        self._published = {name: list(events) for name, events in self._macros.items()}
        self._dirty = False
