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
}


class MacroStoreError(Exception):
    """Falha de persistência com motivo reportável à UI."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


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
    try:
        button = int(entry.get("button", 0))
        keycode = int(entry.get("keycode", 0))
        delta = float(entry.get("delta_ms", 0))
    except (TypeError, ValueError):
        return None
    if delta < 0:
        return None
    return RecordedEvent(kind=kind, button=button, keycode=keycode, delta_ms=delta)


def _convert_legacy(entries: List[Any]) -> List[RecordedEvent]:
    """Converte o formato legado v0/web para eventos canônicos.

    O formato legado usava timestamp absoluto `t` (ms desde o início)
    e nomes de tipo distintos. O delta relativo é reconstruído pela
    diferença de `t` — o resultado é indistinguível do v1 para o
    player.
    """
    events: List[RecordedEvent] = []
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
            # O formato REAL do main legado usa `time` (ms), `key`
            # (keycode), `click` (botão) e `move` ([x, y]) — o v0/web
            # usava `t`/`keycode`/`button`. Ambos coexistem aqui.
            t_raw = entry.get("t")
            t = float(t_raw if t_raw is not None else entry.get("time", 0))
            key_raw = entry.get("keycode")
            keycode = int(key_raw if key_raw is not None else entry.get("key", 0))
            button = int(entry.get("button", entry.get("click", 0)))
            move_xy = entry.get("move")
        except (TypeError, ValueError):
            continue
        delta_ms = max(0.0, t - prev_t) if events else 0.0
        prev_t = t
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
            self._macros = {}
            self._dirty = False
            return 0

        raw: str
        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError as exc:
            # Arquivo ilegível e sem chance de backup: estado vazio,
            # original intacto — o app nunca deve travar no load.
            self._macros = {}
            self._dirty = False
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
            self._macros = {}
            self._dirty = False
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
            self._macros = {}
            self._dirty = False
            return 0

        macros: Dict[str, List[RecordedEvent]] = {}
        for name, entries in container.items():
            if not isinstance(name, str) or not name:
                continue
            if len(macros) >= MAX_MACROS:
                break
            events = self._parse_entries(entries)
            if events is not None and events:
                macros[name] = events
        self._macros = macros
        self._published = {name: list(events) for name, events in macros.items()}
        self._dirty = False
        return len(macros)

    def _parse_entries(self, entries: Any) -> Optional[List[RecordedEvent]]:
        # Formato REAL do main legado: cada macro é um wrapper
        # {name, events, created, count} — a lista de eventos fica
        # em "events"; created/count são metadados descartáveis para
        # a reprodução. O container raiz nunca traz schema_version.
        if isinstance(entries, dict) and "events" in entries:
            macro_events = entries["events"]
            if not isinstance(macro_events, list):
                return None
            entries = macro_events
        if not isinstance(entries, list):
            return None
        # Schema v1: cada entrada tem "kind"
        if entries and isinstance(entries[0], dict) and "kind" in entries[0]:
            events = [e for e in (_validate_event(x) for x in entries) if e is not None]
            return events[:MAX_EVENTS_PER_MACRO] if events else None
        # Formato legado (v0/web): "type" + "t"
        return _convert_legacy(entries) or None

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
                        "button": event.button,
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
