"""Persistência de macros.

O arquivo continua sendo `~/mouse-hub/macros.json` (mesmo path usado pelas
versões atuais), mas com schema v1 por macro, validação rigorosa e erros
explícitos — falhas de persistência não são mais engolidas silenciosamente.

Formato on-disk v1:

    {
      "version": 1,
      "macros": { "<name>": { "version": 1, "name": ..., ... }, ... }
    }

O loader também aceita o formato antigo (dict puro keyed por nome), pois as
versões atuais gravam exatamente assim. Macros antigas inválidas são
reportadas individualmente em `load_warnings` e nunca sobrescrevem/destroem
as válidas; o arquivo corrompido de JSON é preservado como backup
(`macros.json.bak`) para não destruir dados do usuário.
"""

import json
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from .events import Macro, MacroValidationError

DEFAULT_MACROS_PATH = Path.home() / "mouse-hub" / "macros.json"


class MacroStoreError(Exception):
    """Erro de persistência de macros (visível ao chamador)."""


class MacroStore:
    """Coleção de macros persistida em JSON."""

    def __init__(self, path=None):
        self.path = Path(path) if path else DEFAULT_MACROS_PATH
        self._lock = threading.Lock()
        self._macros = {}
        self.load_warnings = []
        self.load()

    # ─── acesso básico ───

    def get(self, name):
        """Retorna Macro ou None se inexistente."""
        with self._lock:
            return self._macros.get(name)

    def list_all(self):
        with self._lock:
            return {
                name: {
                    "name": m.name,
                    "count": len(m.events),
                    "created": m.created_at,
                    "repeat": m.repeat,
                }
                for name, m in self._macros.items()
            }

    def names(self):
        with self._lock:
            return list(self._macros.keys())

    def __contains__(self, name):
        with self._lock:
            return name in self._macros

    # ─── mutações ───

    def add(self, macro):
        """Adiciona/substitui macro. Lança MacroValidationError se inválida.
        Nomes duplicados sobrescrevem (comportamento atual da feature);
        macro vazia é permitida mas listada com count=0."""
        if not isinstance(macro, Macro):
            raise MacroValidationError(f"não é uma Macro: {macro!r}")
        with self._lock:
            self._macros[macro.name] = macro
        self._flush()

    def delete(self, name):
        """Remove macro. Retorna True se existia."""
        with self._lock:
            if name not in self._macros:
                return False
            del self._macros[name]
        self._flush()
        return True

    def upsert_events(self, name, events, repeat=1):
        """Usado pelo capturador: monta uma Macro e grava.
        Nome vazio/inválido e eventos vazios são tratados sem quebrar o app:
        nome vazio vira timestamp-generated; retorna (ok, mensagem)."""
        if not name or not name.strip():
            name = f"macro_{int(datetime.now(timezone.utc).timestamp())}"
        try:
            macro = Macro(name=name, events=list(events), repeat=repeat)
        except MacroValidationError as exc:
            return False, str(exc)
        self.add(macro)
        return True, name

    # ─── I/O ───

    def load(self):
        """Carrega do disco. Erros de JSON viram backup + aviso, nunca crash."""
        self.load_warnings = []
        with self._lock:
            self._macros = {}

        if not self.path.exists():
            return

        try:
            text = self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise MacroStoreError(f"falha ao ler {self.path}: {exc}")

        try:
            raw = json.loads(text)
        except (json.JSONDecodeError, ValueError) as exc:
            self._backup_corrupt()
            self.load_warnings.append(f"JSON inválido no arquivo; backup criado: {exc}")
            return

        if not isinstance(raw, dict):
            self.load_warnings.append("arquivo não é um objeto JSON; ignorado")
            return

        if raw.get("version") == 1:
            container = raw.get("macros", {})
        else:
            # Formato antigo: dict puro keyed por nome de macro
            container = raw

        if not isinstance(container, dict):
            self.load_warnings.append("container de macros inválido; ignorado")
            return

        with self._lock:
            for name, item in container.items():
                if not isinstance(item, dict):
                    self.load_warnings.append(f"macro '{name}': entrada inválida, ignorada")
                    continue
                try:
                    macro = Macro.from_dict(item)
                except MacroValidationError as exc:
                    self.load_warnings.append(f"macro '{name}': inválida, ignorada ({exc})")
                    continue
                # Normaliza para v1 on-disk na próxima gravação
                self._macros[macro.name] = macro

    def save(self):
        """Grava tudo (idempotente; re-levanta falhas de I/O)."""
        self._flush()

    def _flush(self):
        with self._lock:
            payload = {
                "version": 1,
                "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "macros": {name: m.to_dict() for name, m in self._macros.items()},
            }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            raise MacroStoreError(f"falha ao gravar {self.path}: {exc}")

    def _backup_corrupt(self):
        try:
            shutil.copy(self.path, self.path.with_suffix(self.path.suffix + ".bak"))
        except OSError:
            pass
