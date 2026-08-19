"""Modelo canônico e versionável de uma macro.

Esquema on-disk (v1):

    {
      "version": 1,
      "name": "exemplo",
      "created_at": "2026-08-19T14:32:01",
      "repeat": 1,
      "events": [
        {"t": 0.143, "type": "key_down", "key": "w"},
        {"t": 0.312, "type": "mouse_click", "button": 1}
      ]
    }

Tipos de evento canônicos: key_down, key_up, mouse_down, mouse_up,
mouse_move. O playback trata mouse_down/mouse_up como clique completo
(tolerância), e formatos antigos mapeiam para os canônicos sem perda
de capacidade.
"""

import json
import re
from datetime import datetime, timezone

# Tempo máximo entre eventos (1h) para proteger contra drift infinito
MAX_EVENT_GAP_S = 3600.0

# Timestamps negativos/absurdos são rejeitados
MAX_EVENT_T_S = 10 * 3600.0

CANONICAL_TYPES = {"key_down", "key_up", "mouse_down", "mouse_up", "mouse_move"}

# Mapas de compatibilidade: formatos antigos (web e app nativo v0) para o
# canônico. Mapeia type -> (tipo_canônico, kwargs_fixos).
# Tipos canônicos entram no mapa como identidade (sem mapeamento),
# garantindo roundtrip: evento canônico serializado -> desserializado.
_LEGACY_TYPE_MAP = {
    "key_down": ("key_down", {}),
    "key_up": ("key_up", {}),
    "key_press": ("key_down", {}),
    "key_release": ("key_up", {}),
    "key": ("key_down", {}),
    "mouse_click": ("mouse_down", {}),
    "mouse_down": ("mouse_down", {}),
    "mouse_up": ("mouse_up", {}),
    "click": ("mouse_down", {}),
    "mouse_move": ("mouse_move", {}),
    "move": ("mouse_move", {}),
}

# Nomes de campo antigos de timing
_LEGACY_TIME_KEYS = {"time", "timestamp", "elapsed"}

_NAME_RE = re.compile(r"^[A-Za-z0-9_.\- ]{1,64}$")


class MacroValidationError(ValueError):
    """Macro malformada (violou o schema)."""


class MacroEvent:
    """Um evento de macro em memória."""

    __slots__ = ("t", "type", "key", "button", "x", "y")

    def __init__(self, t, type_, key=None, button=None, x=None, y=None):
        self.t = float(t)
        if self.t < 0:
            raise MacroValidationError(f"timestamp negativo: {self.t}")
        self.type = type_
        self.key = key
        self.button = button
        self.x = x
        self.y = y

    def to_dict(self):
        d = {"t": round(self.t, 4), "type": self.type}
        if self.key is not None:
            d["key"] = self.key
        if self.button is not None:
            d["button"] = self.button
        if self.x is not None:
            d["x"] = self.x
        if self.y is not None:
            d["y"] = self.y
        return d

    @classmethod
    def from_dict(cls, raw):
        """Desserializa um evento cru, mapeando formatos antigos ao canônico."""
        if not isinstance(raw, dict):
            raise MacroValidationError(f"evento não é objeto: {raw!r}")

        # ─── timing ───
        t = None
        for k in ("t", "time", "timestamp", "elapsed"):
            if k in raw:
                t = raw[k]
                break
        if t is None:
            raise MacroValidationError(f"evento sem timestamp: {raw!r}")
        try:
            t = float(t)
        except (TypeError, ValueError):
            raise MacroValidationError(f"timestamp inválido: {t!r}")
        if t < 0 or t > MAX_EVENT_T_S:
            raise MacroValidationError(f"timestamp fora da faixa: {t}")

        # ─── tipo ───
        raw_type = raw.get("type")
        if not isinstance(raw_type, str) or raw_type not in _LEGACY_TYPE_MAP:
            raise MacroValidationError(f"tipo de evento desconhecido: {raw_type!r}")
        ctype, fixed = _LEGACY_TYPE_MAP[raw_type]

        # ─── payload por tipo ───
        if ctype.startswith("key"):
            key = raw.get("key")
            if key is None and not fixed.get("key"):
                raise MacroValidationError(f"evento {ctype} sem 'key': {raw!r}")
            key = str(key)
            if not key:
                raise MacroValidationError(f"evento {ctype} com key vazio: {raw!r}")
            ev = cls(t, ctype, key=key)

        elif ctype.startswith("mouse_"):
            if ctype == "mouse_move":
                x = raw.get("x", 0)
                y = raw.get("y", 0)
                try:
                    x, y = int(x), int(y)
                except (TypeError, ValueError):
                    raise MacroValidationError(f"move com coordenadas inválidas: {raw!r}")
                ev = cls(t, ctype, x=x, y=y)
            else:
                button = raw.get("button", 1)
                try:
                    button = int(button)
                except (TypeError, ValueError):
                    raise MacroValidationError(f"click com botão inválido: {button!r}")
                if button not in (1, 2, 3):
                    raise MacroValidationError(f"botão fora de 1..3: {button}")
                ev = cls(t, ctype, button=button)
        else:
            raise MacroValidationError(f"tipo canônico inesperado: {ctype}")

        return ev

    def __repr__(self):
        return (f"MacroEvent(t={self.t}, type={self.type!r}, key={self.key!r}, "
                f"button={self.button}, x={self.x}, y={self.y})")


class Macro:
    """Macro em memória: metadados + eventos ordenados."""

    def __init__(self, name, events=None, repeat=1, created_at=None):
        if not isinstance(name, str) or not _NAME_RE.match(name.strip()):
            raise MacroValidationError(
                f"nome inválido (1-64 chars alfanuméricos/_- espaço): {name!r}")
        self.name = name.strip()
        self.events = list(events) if events else []
        self.repeat = max(1, int(repeat or 1))
        if created_at:
            self.created_at = created_at
        else:
            self.created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # ─── serialização ───

    def to_dict(self):
        return {
            "version": 1,
            "name": self.name,
            "created_at": self.created_at,
            "repeat": self.repeat,
            "events": [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_dict(cls, raw):
        """Desserializa macro, tolerando formato antigo (v0: dict de macros
        keyed por nome sem 'version') e validando rigorosamente."""
        if not isinstance(raw, dict):
            raise MacroValidationError(f"macro não é objeto: {raw!r}")

        version = raw.get("version", 0)
        if version not in (0, 1):
            raise MacroValidationError(f"versão de macro não suportada: {version}")

        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise MacroValidationError(f"macro sem nome válido: {name!r}")

        repeat = raw.get("repeat", 1)
        try:
            repeat = int(repeat)
        except (TypeError, ValueError):
            repeat = 1

        events_raw = raw.get("events")
        if not isinstance(events_raw, list):
            raise MacroValidationError(f"macro '{name}': 'events' ausente/inválido")

        events = [MacroEvent.from_dict(e) for e in events_raw]

        # Guard: intervalo monotônico com teto de gap (evita delay infinito
        # no playback por timestamp corrompido).
        prev = 0.0
        for ev in events:
            if ev.t < prev:
                raise MacroValidationError(
                    f"macro '{name}': eventos fora de ordem temporal")
            if ev.t - prev > MAX_EVENT_GAP_S:
                raise MacroValidationError(
                    f"macro '{name}': gap de {ev.t - prev:.0f}s entre eventos "
                    "(timestamp corrompido?)")
            prev = ev.t

        created_at = raw.get("created_at") or raw.get("created")
        if isinstance(created_at, str) and created_at.strip():
            try:
                datetime.fromisoformat(created_at)
            except ValueError:
                created_at = None

        return cls(name=name, events=events, repeat=repeat, created_at=created_at)

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, text):
        return cls.from_dict(json.loads(text))

    def __repr__(self):
        return f"Macro(name={self.name!r}, events={len(self.events)})"
