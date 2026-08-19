"""Perfis do usuário, com fonte de verdade única.

Hoje os perfis aparecem hardcoded em duas UIs diferentes (web e PyQt),
com listas divergentes (Fortnite existe só no app, por exemplo). Este
módulo trata o `config.json` como única fonte de verdade: a UI apenas
consulta e pede aplicações; nunca mantém sua própria lista.

Perfis não são um recurso novo nem alteram a tela de perfis: apenas
consolidam onde os dados vivem.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from mouse_hub.core.config import (
    ConfigError,
    ConfigPaths,
    default_config,
    load_config,
    save_config,
)
from mouse_hub.core.dpi import clamp_dpi
from mouse_hub.core.sensitivity import clamp_sensitivity


@dataclass(frozen=True)
class Profile:
    name: str
    dpi: int
    sensitivity: int


class ProfileStore:
    """Acesso transacional aos perfis armazenados na configuração."""

    def __init__(self, paths: Optional[ConfigPaths] = None) -> None:
        self._paths = paths or ConfigPaths.xdg()

    def _read(self) -> Dict[str, Any]:
        """Relê sempre do arquivo: o arquivo é a fonte única de verdade,
        nunca uma cópia em memória entre instâncias."""
        try:
            return load_config(self._paths)
        except (ConfigError, OSError):
            return default_config()

    def _write(self, config: Dict[str, Any]) -> None:
        self._paths.config_dir.mkdir(parents=True, exist_ok=True)
        save_config(config, self._paths)

    def list_profiles(self) -> List[Profile]:
        config = self._read()
        profiles: Dict[str, Any] = config.get("profiles", {})
        result: List[Profile] = []
        for name, data in profiles.items():
            if not isinstance(data, dict):
                continue
            result.append(Profile(
                name=name,
                dpi=int(data.get("dpi", default_config()["dpi"])),
                sensitivity=int(data.get("sensitivity", default_config()["sensitivity"])),
            ))
        return result

    def get_profile(self, name: str) -> Optional[Profile]:
        for profile in self.list_profiles():
            if profile.name == name:
                return profile
        return None

    def save_profile(self, name: str, dpi: int, sensitivity: int) -> Profile:
        """Cria ou atualiza um perfil com valores normalizados."""
        config = self._read()
        config["profiles"][name] = {
            "dpi": clamp_dpi(dpi),
            "sensitivity": clamp_sensitivity(sensitivity),
        }
        self._write(config)
        return Profile(name=name, dpi=clamp_dpi(dpi), sensitivity=clamp_sensitivity(sensitivity))

    def delete_profile(self, name: str) -> bool:
        config = self._read()
        profiles = config.get("profiles", {})
        if name not in profiles:
            return False
        del profiles[name]
        config["profiles"] = profiles
        self._write(config)
        return True

    def rename_profile(self, old_name: str, new_name: str) -> bool:
        """Renomeia preservando os valores; falha se o destino já existe."""
        config = self._read()
        profiles = config.get("profiles", {})
        if old_name not in profiles or new_name in profiles:
            return False
        profiles[new_name] = profiles.pop(old_name)
        config["profiles"] = profiles
        self._write(config)
        return True
