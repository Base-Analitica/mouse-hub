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
  preserva-o em `.corrupted.<ts>` para diagnóstico e parte do default;
* distingue os casos de ausência com precisão: arquivo inexistente
  (primeira execução, migra legacy ou parte do default) não é o mesmo
  que arquivo EXISTENTE mas ilegível (corrupção/I/O) — neste último caso
  nada é sobrescrito silenciosamente e o erro é propagável;
* valida o schema antes de usar dados existentes: perfis com campos
  não numéricos ou não-dicionários não são aceitos como estão; o
  problema é reportado (para diagnóstico) e o valor volta ao default,
  sem destruir o restante do arquivo.

Nenhuma exceção de I/O escapa para a UI por padrão: operações devolvem
o desfecho real através de `ConfigError` quando a falha importa, e
defaults quando não importa.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from mouse_hub.core.constants import (
    DPI_DEFAULT,
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
    # Presets oficiais do produto (mantidos em sincronia com a UI):
    "minecraft": {"dpi": 1200, "sensitivity": 60},
    "csgo": {"dpi": 400, "sensitivity": 30},
    "fortnite": {"dpi": 1600, "sensitivity": 70},
    "default": {"dpi": DPI_DEFAULT, "sensitivity": SENSITIVITY_DEFAULT},
}


def default_config() -> Dict[str, Any]:
    return {
        "dpi": DPI_DEFAULT,
        "sensitivity": SENSITIVITY_DEFAULT,
        # Estado físico REAL só é conhecido após probe/leitura confirma
        # dos: nunca assumimos DPI aplicado de fábrica (pode ser 400, 800
        # ou qualquer valor deixado pelo firmware/usuário). None =
        # desconhecido; o campo só ganha valor quando o hardware confirma.
        "applied_dpi": None,
        "applied_sensitivity": None,
        "polling_rate": 1000,
        "lighting": dict(LIGHTING_DEFAULT),
        "profiles": {k: dict(v) for k, v in PROFILES_DEFAULT.items()},
        # Preferências do auto-clicker (issue #5): CPS e botão
        # persistem entre sessões; a validação de range fica nos
        # leitores abaixo (1..50, botões left/middle/right).
        "autoclicker": {"cps": 10, "button": "left"},
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


class LoadKind(Enum):
    """De onde veio a configuração carregada."""

    FILE = "file"              # arquivo existente, válido e validado
    DEFAULT = "default"        # arquivo inexistente: primeira execução/migração
    CORRUPTED = "corrupted"    # arquivo existia mas o conteúdo é inválido
    IO_ERROR = "io_error"      # arquivo existia mas o I/O falhou (ilegível)


@dataclass(frozen=True)
class LoadOutcome:
    """Resultado completo de um carregamento de configuração."""

    config: Dict[str, Any]
    kind: LoadKind
    notes: List[str] = field(default_factory=list)


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


def _read_file(path: Path) -> Optional[str]:
    """Lê o texto do arquivo; None = não existe; OSError propagado —
    o chamador decide o tratamento (nunca silenciar I/O aqui)."""
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _validate_config(data: Any, notes: List[str]) -> Dict[str, Any]:
    """Valida o schema da configuração, devolvendo uma cópia limpa.

    * raiz não-dicionário é rejeitada (raise ConfigError);
    * perfis que não são dicionários ou com dpi/sensitivity não
      numéricos são substituídos pelos defaults do produto (nota);
    * campos desconhecidos na raiz e valores de iluminação são
      preservados — nunca destruímos dados que não entendemos;
    * perfis deletados pelo usuário NÃO voltam do default: o mapa de
      perfis do usuário tem precedência sobre os presets.
    """
    if not isinstance(data, dict):
        raise ConfigError("Conteúdo do arquivo não é um objeto JSON")

    config: Dict[str, Any] = {}
    for key, value in data.items():
        if key == "profiles":
            continue
        config[key] = value

    profiles_in: Any = data.get("profiles")
    if not isinstance(profiles_in, dict):
        if profiles_in is not None:
            notes.append(
                f"'profiles' não é um objeto ({type(profiles_in).__name__}); "
                "reconstruído a partir dos defaults"
            )
        profiles_in = {}

    profiles: Dict[str, Any] = {}
    for name, profile in profiles_in.items():
        if not isinstance(profile, dict):
            notes.append(
                f"perfil '{name}' ignorado (não é um objeto); "
                "valores de default aplicados"
            )
            profiles[name] = dict(PROFILES_DEFAULT.get("default", {}))
            continue
        dpi = profile.get("dpi")
        sens = profile.get("sensitivity")
        fixed: Dict[str, Any] = {}
        if isinstance(dpi, int):
            fixed["dpi"] = dpi
        elif isinstance(dpi, float) and float(int(dpi)) == dpi:
            fixed["dpi"] = int(dpi)
        else:
            notes.append(
                f"perfil '{name}': dpi inválido ({dpi!r}); valor de default aplicado"
            )
        if isinstance(sens, int):
            fixed["sensitivity"] = sens
        elif isinstance(sens, float) and float(int(sens)) == sens:
            fixed["sensitivity"] = int(sens)
        else:
            notes.append(
                f"perfil '{name}': sensitivity inválida ({sens!r}); valor de default aplicado"
            )
        default_profile = PROFILES_DEFAULT.get(name, PROFILES_DEFAULT["default"])
        fixed.setdefault("dpi", default_profile.get("dpi", DPI_DEFAULT))
        fixed.setdefault("sensitivity", default_profile.get("sensitivity", SENSITIVITY_DEFAULT))
        profiles[name] = fixed
    config["profiles"] = profiles
    return config


def _merge_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """Completa chaves estruturais ausentes com os defaults do produto,
    preservando todo valor existente (compatível com versões antigas do
    arquivo).

    O dicionário `profiles` é tratado separadamente: ele é um mapa
    definido pelo usuário, e perfis deletados não devem voltar do
    default. Apenas a estrutura de cada perfil existente é garantida.
    """
    base = default_config()
    for key, default in base.items():
        if key == "profiles":
            continue
        if key not in config:
            config[key] = default if not isinstance(default, dict) else dict(default)
        elif isinstance(default, dict) and isinstance(config[key], dict):
            for sub_key, sub_default in default.items():
                config[key].setdefault(sub_key, sub_default)
    if "profiles" not in config or not isinstance(config["profiles"], dict):
        config["profiles"] = {k: dict(v) for k, v in base["profiles"].items()}
    else:
        default_profiles = base["profiles"]
        for name, profile in config["profiles"].items():
            if isinstance(profile, dict):
                default_profile = default_profiles.get(name, default_profiles["default"])
                if isinstance(default_profile, dict):
                    for sub_key, sub_default in default_profile.items():
                        profile.setdefault(sub_key, sub_default)
    return config


AUTOCICKER_BUTTONS = ("left", "middle", "right")


def load_autoclicker_settings(
    paths: Optional[ConfigPaths] = None,
) -> tuple[int, str]:
    """Lê as preferências do auto-clicker do config XDG.

    Valores fora do contrato (CPS fora de 1..50, botão desconhecido)
    caem para o default — config não pode quebrar o motor. Retorna
    (cps, button_name)."""
    config = load_config(paths)
    raw = config.get("autoclicker")
    raw = raw if isinstance(raw, dict) else {}
    try:
        cps = int(raw.get("cps", 10))
    except (TypeError, ValueError):
        cps = 10
    if not 1 <= cps <= 50:
        cps = 10
    button = raw.get("button", "left")
    if button not in AUTOCICKER_BUTTONS:
        button = "left"
    return cps, button


def save_autoclicker_settings(
    cps: int,
    button: str,
    paths: Optional[ConfigPaths] = None,
) -> None:
    """Persiste CPS/botão do auto-clicker preservando o restante do
    config (read-modify-write atômico via _safe_write)."""
    if not 1 <= int(cps) <= 50:
        raise ValueError(f"CPS deve estar entre 1 e 50: {cps}")
    if button not in AUTOCICKER_BUTTONS:
        raise ValueError(f"botão inválido: {button}")
    paths = paths or ConfigPaths.xdg()
    config = load_config(paths)
    config["autoclicker"] = {"cps": int(cps), "button": button}
    _safe_write(paths.config_file, config)


def migrate_legacy_config(paths: ConfigPaths, legacy_dir: Path = DEFAULT_LEGACY_DIR) -> bool:
    """Migra configuração/macro de ~/mouse-hub para os diretórios XDG.

    A migração nunca destrói os arquivos antigos: apenas copia o que
    ainda não existe no destino e retorna True se algo foi migrado.
    """
    migrated = False

    legacy_config = legacy_dir / "config.json"
    if legacy_config.exists() and not paths.config_file.exists():
        try:
            text = _read_file(legacy_config)
            if text is not None:
                try:
                    data = json.loads(text)
                except (json.JSONDecodeError, ValueError):
                    data = None
                if isinstance(data, dict):
                    _safe_write(paths.config_file, _merge_defaults(data))
                    migrated = True
                else:
                    # Legacy corrompido: parte do default no novo local,
                    # sem tocar no arquivo antigo (ele fica legível lá).
                    _safe_write(paths.config_file, default_config())
                    migrated = True
        except (OSError, ConfigError):
            # Falha de I/O no legacy: nada é forçado; o usuário migra
            # manualmente se precisar.
            pass

    legacy_macros = legacy_dir / "macros.json"
    if legacy_macros.exists() and not paths.macros_file.exists():
        try:
            paths.macros_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy_macros, paths.macros_file)
            migrated = True
        except OSError:
            pass

    return migrated


def load_config(
    paths: Optional[ConfigPaths] = None,
    *,
    strict: bool = False,
) -> Dict[str, Any]:
    """Carrega (e, se necessário, migra) a configuração do produto.

    Com `strict=False` (default), qualquer problema no arquivo de
    configuração é tratado de forma previsível: JSON inválido é
    preservado como backup `.corrupted.<ts>` e a configuração parte do
    default. Com `strict=True`, `ConfigError` é propagado para quem
    precisa diagnosticar o conteúdo corrompido.
    """
    outcome = load_config_outcome(paths, strict=strict)
    return outcome.config


def load_config_outcome(
    paths: Optional[ConfigPaths] = None,
    *,
    strict: bool = False,
) -> LoadOutcome:
    """Carrega a configuração com status explícito de origem.

    Casos:
    * arquivo inexistente → LoadKind.DEFAULT (após migração legacy, se
      houver); primeira execução sempre parte de defaults conhecidos;
    * arquivo existente e válido → LoadKind.FILE;
    * arquivo existente mas inválido → backup `.corrupted.<ts>` e
      LoadKind.CORRUPTED (strict=True propaga ConfigError).
    """
    paths = paths or ConfigPaths.xdg()
    notes: List[str] = []

    try:
        raw = _read_file(paths.config_file)
    except OSError as exc:
        if strict:
            raise ConfigError(f"Erro de leitura em {paths.config_file}: {exc}") from exc
        return LoadOutcome(
            default_config(),
            LoadKind.IO_ERROR,
            [f"arquivo ilegível: {exc}"],
        )

    if raw is None:
        migrate_legacy_config(paths)
        # A migração (ou outra instância) pode ter criado o arquivo.
        try:
            raw = _read_file(paths.config_file)
        except OSError as exc:
            if strict:
                raise ConfigError(f"Erro de leitura em {paths.config_file}: {exc}") from exc
            return LoadOutcome(
                default_config(),
                LoadKind.IO_ERROR,
                [f"arquivo ilegível: {exc}"],
            )

    if raw is None:
        return LoadOutcome(default_config(), LoadKind.DEFAULT, notes)

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        corrupted = paths.config_file.parent / f".corrupted.{int(time.time())}"
        try:
            shutil.copy2(paths.config_file, corrupted)
        except OSError:
            pass
        if strict:
            raise ConfigError(f"JSON inválido em {paths.config_file}; backup em {corrupted}")
        notes.append(f"JSON inválido; conteúdo preservado em {corrupted.name}")
        return LoadOutcome(default_config(), LoadKind.CORRUPTED, notes)

    try:
        validated = _validate_config(data, notes)
    except ConfigError:
        if strict:
            raise
        notes.append("Schema inválido; partindo do default")
        return LoadOutcome(default_config(), LoadKind.CORRUPTED, notes)

    return LoadOutcome(_merge_defaults(validated), LoadKind.FILE, notes)


def save_config(config: Dict[str, Any], paths: Optional[ConfigPaths] = None) -> None:
    """Persiste a configuração com escrita atômica.

    SOMENTE persiste dados confirmados: quem chama é responsável por
    gravar applied_dpi/applied_sensitivity apenas após a operação
    correspondente retornar APPLIED/APPLIED_PARTIAL confirmado.
    """
    paths = paths or ConfigPaths.xdg()
    _safe_write(paths.config_file, config)


def load_json_file(path: Path) -> Dict[str, Any]:
    """Carrega um arquivo de dados genérico (ex.: macros.json) com o
    mesmo tratamento previsível de JSON inválido."""
    try:
        raw = _read_file(path)
    except OSError:
        return {}
    if raw is None:
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def save_json_file(path: Path, data: Dict[str, Any]) -> None:
    """Persiste um arquivo de dados genérico com escrita atômica."""
    _safe_write(path, data)
