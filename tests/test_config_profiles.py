"""Testes de configuração XDG, migração legacy, JSON inválido e perfis."""

import json
from pathlib import Path

import pytest

from mouse_hub.core.config import (
    ConfigError,
    ConfigPaths,
    default_config,
    load_config,
    load_json_file,
    migrate_legacy_config,
    save_config,
    save_json_file,
)
from mouse_hub.core.constants import DPI_DEFAULT, SENSITIVITY_DEFAULT
from mouse_hub.core.profiles import ProfileStore


# ── Persistência ──────────────────────────────────────────────────


def test_save_and_load_config_roundtrip(tmp_path):
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    config = default_config()
    config["dpi"] = 1200
    save_config(config, paths)
    loaded = load_config(paths)
    assert loaded["dpi"] == 1200
    assert loaded == config


def test_default_config_has_expected_shape():
    config = default_config()
    assert config["dpi"] == DPI_DEFAULT
    assert config["sensitivity"] == SENSITIVITY_DEFAULT
    assert config["polling_rate"] == 1000
    assert "profiles" in config
    assert "minecraft" in config["profiles"]
    assert "lighting" in config


def test_missing_config_returns_defaults(tmp_path):
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    config = load_config(paths)
    assert config["dpi"] == DPI_DEFAULT


def test_load_config_merges_missing_keys(tmp_path):
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    paths.config_dir.mkdir(parents=True)
    paths.config_file.write_text(json.dumps({"dpi": 400}))
    config = load_config(paths)
    assert config["dpi"] == 400
    # Chaves ausentes ganham o default sem destruir o valor existente.
    assert config["sensitivity"] == SENSITIVITY_DEFAULT
    assert "minecraft" in config["profiles"]


def test_load_config_preserves_unknown_keys(tmp_path):
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    paths.config_dir.mkdir(parents=True)
    paths.config_file.write_text(json.dumps({"dpi": 400, "custom_key": "preserve-me"}))
    config = load_config(paths)
    assert config["custom_key"] == "preserve-me"


# ── JSON inválido ─────────────────────────────────────────────────


def test_invalid_json_raises_config_error_with_backup(tmp_path):
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    paths.config_dir.mkdir(parents=True)
    paths.config_file.write_text("{this is not json!")
    with pytest.raises(ConfigError):
        load_config(paths)
    backups = list(paths.config_dir.glob(".corrupted.*"))
    assert len(backups) == 1
    assert "this is not json!" in backups[0].read_text()


def test_non_object_json_raises_config_error(tmp_path):
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    paths.config_dir.mkdir(parents=True)
    paths.config_file.write_text("[1, 2, 3]")
    with pytest.raises(ConfigError):
        load_config(paths)


def test_load_starts_from_defaults_after_invalid_json(tmp_path):
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    paths.config_dir.mkdir(parents=True)
    paths.config_file.write_text("{{{")
    try:
        load_config(paths)
    except ConfigError:
        pass
    config = load_config(paths)
    assert config["dpi"] == DPI_DEFAULT


# ── Migração legacy ───────────────────────────────────────────────


def test_migrate_legacy_config_copies_and_preserves_original(tmp_path):
    legacy = tmp_path / "mouse-hub"
    legacy.mkdir()
    legacy_config = legacy / "config.json"
    legacy_config.write_text(json.dumps({"dpi": 1600, "sensitivity": 70}))

    xdg_config = tmp_path / "xdg-config" / "mouse-hub"
    paths = ConfigPaths(xdg_config, tmp_path / "xdg-data" / "mouse-hub")
    migrated = migrate_legacy_config(paths, legacy)

    assert migrated is True
    assert json.loads(xdg_config.joinpath("config.json").read_text())["dpi"] == 1600
    # Original intacto.
    assert json.loads(legacy_config.read_text()) == {"dpi": 1600, "sensitivity": 70}


def test_migrate_legacy_does_not_overwrite_xdg(tmp_path):
    legacy = tmp_path / "mouse-hub"
    legacy.mkdir()
    (legacy / "config.json").write_text(json.dumps({"dpi": 1600}))

    xdg_config = tmp_path / "xdg-config" / "mouse-hub"
    xdg_config.mkdir(parents=True)
    (xdg_config / "config.json").write_text(json.dumps({"dpi": 400}))

    paths = ConfigPaths(xdg_config, tmp_path / "xdg-data" / "mouse-hub")
    assert migrate_legacy_config(paths, legacy) is False
    assert json.loads((xdg_config / "config.json").read_text())["dpi"] == 400


def test_migrate_legacy_handles_corrupted_legacy(tmp_path):
    legacy = tmp_path / "mouse-hub"
    legacy.mkdir()
    (legacy / "config.json").write_text("{{invalid")

    paths = ConfigPaths(tmp_path / "xc", tmp_path / "xd")
    migrated = migrate_legacy_config(paths, legacy)
    assert migrated is True
    # Parte do default sem destruir o legacy (que permanece legível lá).
    assert load_config(paths)["dpi"] == DPI_DEFAULT
    assert (legacy / "config.json").read_text() == "{{invalid"


def test_migrate_legacy_macros_file(tmp_path):
    legacy = tmp_path / "mouse-hub"
    legacy.mkdir()
    (legacy / "macros.json").write_text(json.dumps({"combo": {"events": []}}))

    paths = ConfigPaths(tmp_path / "xc", tmp_path / "xd" / "mouse-hub")
    assert migrate_legacy_config(paths, legacy) is True
    assert json.loads(paths.macros_file.read_text())["combo"]["events"] == []


# ── Escrita segura ────────────────────────────────────────────────


def test_atomic_write_leaves_no_tmp_on_success(tmp_path):
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    save_config(default_config(), paths)
    leftovers = list(paths.config_dir.glob(".config-*.tmp"))
    assert leftovers == []
    assert paths.config_file.exists()


def test_generic_json_file_persistence(tmp_path):
    path = tmp_path / "file.json"
    save_json_file(path, {"macros": {"a": 1}})
    assert load_json_file(path) == {"macros": {"a": 1}}


def test_load_generic_json_missing_returns_empty(tmp_path):
    assert load_json_file(tmp_path / "absent.json") == {}


# ── Perfis (fonte única) ──────────────────────────────────────────


def test_profile_store_default_profiles(tmp_path):
    store = ProfileStore(ConfigPaths(tmp_path / "c", tmp_path / "d"))
    names = {p.name for p in store.list_profiles()}
    assert {"minecraft", "csgo", "default"} <= names


def test_save_and_get_profile(tmp_path):
    store = ProfileStore(ConfigPaths(tmp_path / "c", tmp_path / "d"))
    profile = store.save_profile("custom", 1500, 65)
    assert profile.dpi == 1500
    assert profile.sensitivity == 65
    assert store.get_profile("custom") == profile


def test_profile_values_are_clamped(tmp_path):
    store = ProfileStore(ConfigPaths(tmp_path / "c", tmp_path / "d"))
    profile = store.save_profile("custom", 99999, -10)
    assert profile.dpi == 25600
    assert profile.sensitivity == 0


def test_delete_profile(tmp_path):
    store = ProfileStore(ConfigPaths(tmp_path / "c", tmp_path / "d"))
    assert store.delete_profile("csgo") is True
    assert store.get_profile("csgo") is None
    assert store.delete_profile("csgo") is False


def test_rename_profile(tmp_path):
    store = ProfileStore(ConfigPaths(tmp_path / "c", tmp_path / "d"))
    assert store.rename_profile("csgo", "valorant") is True
    assert store.get_profile("valorant") is not None
    assert store.get_profile("csgo") is None
    assert store.get_profile("valorant").dpi == 400


def test_rename_profile_fails_when_target_exists(tmp_path):
    store = ProfileStore(ConfigPaths(tmp_path / "c", tmp_path / "d"))
    assert store.rename_profile("csgo", "minecraft") is False
    assert store.get_profile("csgo") is not None


def test_profiles_are_single_source_of_truth(tmp_path):
    """Os perfis lidos são sempre os do arquivo de configuração."""
    paths = ConfigPaths(tmp_path / "c", tmp_path / "d")
    store = ProfileStore(paths)
    store.save_profile("custom", 900, 40)

    store2 = ProfileStore(paths)
    assert store2.get_profile("custom").dpi == 900
