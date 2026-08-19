"""Persistência de configuração seguindo as práticas XDG do Linux.

Histórico do projeto: toda a configuração vivia em `~/mouse-hub/`,
caminho fixo e não padrão. Esta implementação:

* usa `XDG_CONFIG_HOME/mouse-hub/config.json` para configuração e
  `XDG_DATA_HOME/mouse-hub/` para dados (macros, perfis);
* migra a configuração antiga de `~/mouse-hub/` sem destruí-la: os
  arquivos originais permanecem intactos e é criada uma cópia no novo
  local;
* usa escrita segura (temporário + rename atômico dentro do mesmo
  diretório) para evitar corrupção por interrupção;
* trata JSON inválido de forma previsível: ignora o conteúdo corrompido,
  preserva-o em `.corrupted.<ts>` para diagnóstico e parte do default.

Nenhuma exceção de I/O escapa para a UI: operações devolvem o desfecho
real através de `ConfigError` quando a falha importa, e defaults quando
não importa.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from mouse_hub.core.constants import (
    DPI_DEFAULT,
    POLLING_RATES,
    SENSITIVITY_DEFAULT,
)

DEFAULT_LEGACY_DIR = Path.home() / "mouse-hub"

LIGHTING_DEFAULT = {
    "enabled": True,
    "color": "#FF0000",
    "brightness": 80,
    "mode": "static",
}

PROFILES_DEFAULT: Dict[str, Dict[str, int]] = {
    "minecraft": {"dpi": 1200, "sensitivity": 60},
    "csgo": {"dpi": 400, "sensitivity": 30},
    "default": {"dpi": DPI_DEFAULT, "sensitivity": SENSITIVITY_DEFAULT},
}


def default_config() -> Dict[str, Any]:
    return {
        "dpi": DPI_DEFAULT,
        "sensitivity": SENSITIVITY_DEFAULT,
        "applied_dpi": DPI_DEFAULT,
        "applied_sensitivity": SENSITIVITY_DEFAULT,
        "polling_rate": 1000,
        "lighting": dict(LIGHTING_DEFAULT),
        "profiles": {k: dict(v) for k, v in PROFILES_DEFAULT.items()},
    }


@dataclass(frozen=True)
class ConfigPaths:
    """Caminhos XDG resolvidos para o Mouse Hub."""

    config_dir: Path
    data_dir: Path

    @staticmethod
    def xdg() -> "ConfigPaths":
        config_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "mouse-hub"
        data_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "mouse-hub"
        return ConfigPaths(config_dir, data_dir)

    @property
    def config_file(self) -> Path:
        return self.config_dir / "config.json"

    @property
    def macros_file(self) -> Path:
        return self.data_dir / "macros.json"


class ConfigError(Exception):
    """Falha previsível de configuração (JSON inválido, I/O, etc.)."""


def _safe_write(path: Path, data: Dict[str, Any]) -> None:
    """Escreve `data` em `path` de forma atômica dentro do mesmo diretório."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".config-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _load_json_safe(path: Path) -> Optional[Dict[str, Any]]:
    """Carrega JSON de `path`; em caso de conteúdo inválido, preserva o
    arquivo original como `.corrupted.<ts>` e retorna None."""
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        corrupted = path.parent / f".corrupted.{int(time.time())}"
        try:
            shutil.copy2(path, corrupted)
        except OSError:
            pass
        raise ConfigError(f"JSON inválido em {path}; backup em {corrupted}")

    if not isinstance(data, dict):
        raise ConfigError(f"Conteúdo de {path} não é um objeto JSON")
    return data


def _merge_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """Completa chaves ausentes com os defaults do produto, preservando
    todo valor existente (compatível com versões antigas do arquivo)."""
    base = default_config()
    for key, default in base.items():
        if key not in config:
            config[key] = default if not isinstance(default, dict) else dict(default)
        elif isinstance(default, dict) and isinstance(config[key], dict):
            for sub_key, sub_default in default.items():
                config[key].setdefault(sub_key, sub_default)
    return config


def migrate_legacy_config(paths: ConfigPaths, legacy_dir: Path = DEFAULT_LEGACY_DIR) -> bool:
    """Migra configuração/macro de ~/mouse-hub para os diretórios XDG.

    A migração nunca destrói os arquivos antigos: apenas copia o que
    ainda não existe no destino e retorna True se algo foi migrado.
    """
    migrated = False

    legacy_config = legacy_dir / "config.json"
    if legacy_config.exists() and not paths.config_file.exists():
        try:
            data = _load_json_safe(legacy_config)
            if data is not None:
                _safe_write(paths.config_file, _merge_defaults(data))
                migrated = True
        except (ConfigError, OSError):
            # Config antiga corrompida: parte do default, sem propagar erro.
            _safe_write(paths.config_file, default_config())
            migrated = True

    legacy_macros = legacy_dir / "macros.json"
    if legacy_macros.exists() and not paths.macros_file.exists():
        try:
            shutil.copy2(legacy_macros, paths.macros_file)
            migrated = True
        except OSError:
            pass

    return migrated


def load_config(paths: Optional[ConfigPaths] = None) -> Dict[str, Any]:
    """Carrega (e, se necessário, migra) a configuração do produto."""
    paths = paths or ConfigPaths.xdg()

    data = _load_json_safe(paths.config_file)
    if data is None:
        migrate_legacy_config(paths)
        data = _load_json_safe(paths.config_file)

    if data is None:
        data = default_config()
    else:
        data = _merge_defaults(data)
    return data


def save_config(config: Dict[str, Any], paths: Optional[ConfigPaths] = None) -> None:
    """Persiste a configuração com escrita atômica."""
    paths = paths or ConfigPaths.xdg()
    _safe_write(paths.config_file, config)


def load_json_file(path: Path) -> Dict[str, Any]:
    """Carrega um arquivo de dados genérico (ex.: macros.json) com o
    mesmo tratamento previsível de JSON inválido."""
    data = _load_json_safe(path)
    if data is None:
        return {}
    return data


def save_json_file(path: Path, data: Dict[str, Any]) -> None:
    """Persiste um arquivo de dados genérico com escrita atômica."""
    _safe_write(path, data)
