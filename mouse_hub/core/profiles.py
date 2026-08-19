"""Perfis do usuário, com fonte de verdade única.

Hoje os perfis aparecem hardcoded em duas UIs diferentes (web e PyQt),
com listas divergentes (Fortnite existe só no app, por exemplo). Este
módulo trata o `config.json` como única fonte de verdade: a UI apenas
consulta e pede aplicações; nunca mantém sua própria lista.

Perfis não são um recurso novo nem alteram a tela de perfis: apenas
consolidam onde os dados vivem. O conjunto default inclui os presets
oficiais do produto (Minecraft PvP, CS:GO, Fortnite e Default), que a
UI pode consultar sem recriar hardcoded.

Robustez por design:
* leitura de arquivo EXISTENTE que falha (I/O ou schema) NÃO retorna
  defaults — retorna raise, para que ninguém sobrescreva dados reais
  com o default;
* a primeira execução (arquivo inexistente) parte do default, incluindo
  os presets;
* operações de mutação devolvem `ProfileOutcome`: se a escrita falhar,
  nada se considera salvo e o erro é reportado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from mouse_hub.core.config import (
    ConfigError,
    ConfigPaths,
    default_config,
    load_config_outcome,
    save_config,
)
from mouse_hub.core.dpi import clamp_dpi
from mouse_hub.core.sensitivity import clamp_sensitivity


@dataclass(frozen=True)
class Profile:
    name: str
    dpi: int
    sensitivity: int


@dataclass(frozen=True)
class ProfileOutcome:
    """Desfecho de uma operação de perfil, com dados lidos e eventuais
    notas de diagnóstico (valores corrigidos, schema, migração)."""

    success: bool
    message: str = ""
    profiles: List[Profile] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


class ProfileStore:
    """Acesso transacional aos perfis armazenados na configuração."""

    def __init__(self, paths: Optional[ConfigPaths] = None) -> None:
        self._paths = paths or ConfigPaths.xdg()

    def _read(self) -> Dict[str, Any]:
        """Relê sempre do arquivo: o arquivo é a fonte única de verdade,
        nunca uma cópia em memória entre instâncias.

        Arquivo inexistente → default conhecido (primeira execução).
        Arquivo existente mas ilegível/inválido → ConfigError, nunca
        defaults: retornar default aqui apagaria silenciosamente os
        dados reais numa mutação posterior.
        """
        outcome = load_config_outcome(self._paths)
        return outcome.config

    def _write(self, config: Dict[str, Any]) -> None:
        self._paths.config_dir.mkdir(parents=True, exist_ok=True)
        save_config(config, self._paths)

    # ── Leitura (safe): nunca falha em cascata ─────────────────────

    def list_profiles(self) -> List[Profile]:
        """Perfis atuais, ou presets de default se o arquivo não existir.

        I/O falho mantém o último estado conhecido? NÃO — relê sempre do
        arquivo e deixa a falha subir como ConfigError, para que a UI
        saiba que está lendo dados não confirmados.
        """
        config = self._read()
        return _parse_profiles(config)

    def get_profile(self, name: str) -> Optional[Profile]:
        for profile in self.list_profiles():
            if profile.name == name:
                return profile
        return None

    # ── Mutação (transacional): ou tudo confirmado, ou nada ────────

    def save_profile(self, name: str, dpi: int, sensitivity: int) -> ProfileOutcome:
        """Cria ou atualiza um perfil com valores normalizados.

        Só persiste se a leitura confirmou dados reais e a escrita
        terminou sem erro; qualquer falha devolve success=False com a
        causa, e o arquivo permanece como estava.
        """
        try:
            config = self._read()
        except ConfigError as exc:
            return ProfileOutcome(
                success=False,
                message=f"Não foi possível ler a configuração: {exc}",
            )
        config["profiles"][name] = {
            "dpi": clamp_dpi(dpi),
            "sensitivity": clamp_sensitivity(sensitivity),
        }
        try:
            self._write(config)
        except OSError as exc:
            return ProfileOutcome(
                success=False,
                message=f"Falha ao persistir o perfil '{name}': {exc}",
            )
        return ProfileOutcome(success=True, profiles=[Profile(
            name=name, dpi=clamp_dpi(dpi), sensitivity=clamp_sensitivity(sensitivity),
        )])

    def delete_profile(self, name: str) -> ProfileOutcome:
        """Remove um perfil; falha se não existir ou se a persistência
        falhar. Exclusão é definitiva no arquivo — não há undelete
        automático, o backup `.corrupted` continua existindo para os
        casos de corrupção."""
        try:
            config = self._read()
        except ConfigError as exc:
            return ProfileOutcome(
                success=False,
                message=f"Não foi possível ler a configuração: {exc}",
            )
        profiles = config.get("profiles", {})
        if name not in profiles:
            return ProfileOutcome(success=False, message=f"Perfil '{name}' não existe")
        del profiles[name]
        config["profiles"] = profiles
        try:
            self._write(config)
        except OSError as exc:
            return ProfileOutcome(
                success=False,
                message=f"Falha ao persistir a exclusão de '{name}': {exc}",
            )
        return ProfileOutcome(success=True, profiles=list(self._profiles_from(config)))

    def rename_profile(self, old_name: str, new_name: str) -> ProfileOutcome:
        """Renomeia preservando os valores; falha se o destino já existe,
        se a origem não existe, ou se a persistência falhar."""
        try:
            config = self._read()
        except ConfigError as exc:
            return ProfileOutcome(
                success=False,
                message=f"Não foi possível ler a configuração: {exc}",
            )
        profiles = config.get("profiles", {})
        if old_name not in profiles:
            return ProfileOutcome(success=False, message=f"Perfil '{old_name}' não existe")
        if new_name in profiles:
            return ProfileOutcome(success=False, message=f"Perfil '{new_name}' já existe")
        profiles[new_name] = profiles.pop(old_name)
        config["profiles"] = profiles
        try:
            self._write(config)
        except OSError as exc:
            return ProfileOutcome(
                success=False,
                message=f"Falha ao persistir a renomeação: {exc}",
            )
        return ProfileOutcome(success=True, profiles=list(self._profiles_from(config)))

    # ── Internos ───────────────────────────────────────────────────

    @staticmethod
    def _profiles_from(config: Dict[str, Any]) -> List[Profile]:
        return _parse_profiles(config)


def _parse_profiles(config: Dict[str, Any]) -> List[Profile]:
    """Transforma o mapa de perfis da configuração em objetos Profile."""
    base = default_config()
    defaults = base["profiles"]["default"]
    profiles: Dict[str, Any] = config.get("profiles", {})
    result: List[Profile] = []
    for name, data in profiles.items():
        if not isinstance(data, dict):
            continue
        result.append(Profile(
            name=name,
            dpi=int(data.get("dpi", defaults["dpi"])),
            sensitivity=int(data.get("sensitivity", defaults["sensitivity"])),
        ))
    return result
