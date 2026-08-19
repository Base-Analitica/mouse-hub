"""Testes de configuração XDG, migração legacy, JSON inválido e perfis."""

import json
from pathlib import Path

import pytest

from mouse_hub.core.config import (
    ConfigError,
    ConfigPaths,
    LoadKind,
    default_config,
    load_config,
    load_config_outcome,
    load_json_file,
    migrate_legacy_config,
    save_config,
    save_json_file,
)
from mouse_hub.core.constants import DPI_DEFAULT, SENSITIVITY_DEFAULT
from mouse_hub.core.profiles import ProfileStore

# Os presets oficiais do produto vivem no default de referência.
EXPECTED_PRESETS = {"minecraft", "csgo", "default", "fortnite"}


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
    assert set(config["profiles"]) >= EXPECTED_PRESETS
    assert "lighting" in config


def test_missing_config_returns_defaults(tmp_path):
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    config = load_config(paths)
    assert config["dpi"] == DPI_DEFAULT
    assert set(config["profiles"]) >= EXPECTED_PRESETS


def test_load_config_merges_missing_keys(tmp_path):
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    paths.config_dir.mkdir(parents=True)
    paths.config_file.write_text(json.dumps({"dpi": 400}))
    config = load_config(paths)
    assert config["dpi"] == 400
    # Chaves estruturais ausentes ganham o default sem destruir o valor
    # existente; perfis do usuário não ganham presets por cima.
    assert config["sensitivity"] == SENSITIVITY_DEFAULT
    assert config["profiles"] == {}


def test_load_config_preserves_unknown_keys(tmp_path):
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    paths.config_dir.mkdir(parents=True)
    paths.config_file.write_text(json.dumps({"dpi": 400, "custom_key": "preserve-me"}))
    config = load_config(paths)
    assert config["custom_key"] == "preserve-me"


def test_deleted_profile_stays_deleted_after_reload(tmp_path):
    """O bug anterior reinjetava perfis deletados a partir do default.
    A fonte única é o arquivo; perfis deletados não voltam."""
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    store = ProfileStore(paths)
    outcome = store.delete_profile("csgo")
    assert outcome.success
    assert store.get_profile("csgo") is None

    store2 = ProfileStore(paths)
    assert store2.get_profile("csgo") is None


# ── JSON inválido ─────────────────────────────────────────────────


def test_invalid_json_raises_config_error_with_backup(tmp_path):
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    paths.config_dir.mkdir(parents=True)
    paths.config_file.write_text("{this is not json!")
    outcome = load_config_outcome(paths)
    # Arquivo existente e ilegível nunca vira sucesso silencioso.
    assert outcome.kind == LoadKind.CORRUPTED
    assert any(".corrupted" in note for note in outcome.notes)
    backups = list(paths.config_dir.glob(".corrupted.*"))
    assert len(backups) == 1
    assert "this is not json!" in backups[0].read_text()
    with pytest.raises(ConfigError):
        load_config(paths, strict=True)


def test_default_config_applied_state_starts_unknown(tmp_path):
    """O estado aplicado começa desconhecido (None) — a janela só ganha
    applied_dpi/applied_sensitivity depois de confirmação real; o
    default nunca inventa valores aplicados."""
    config = default_config()
    assert config["applied_dpi"] is None
    assert config["applied_sensitivity"] is None


def test_load_config_migration_preserves_int_applied_state(tmp_path):
    """Config antiga com applied_dpi como int é preservada (migração
    compatível); int não é perdido nem reinterpretado como unknown."""
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    paths.config_dir.mkdir(parents=True)
    paths.config_file.write_text(json.dumps({"dpi": 1600, "applied_dpi": 800}))
    config = load_config(paths)
    assert config["applied_dpi"] == 800


def test_load_io_error_kind(tmp_path):
    """Arquivo existente mas ilegível por I/O: kind IO_ERROR (não
    CORRUPTED, não DEFAULT) — o caller distingue a causa."""
    import os
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    paths.config_dir.mkdir(parents=True)
    paths.config_file.write_text('{"dpi": 1200}')
    os.chmod(str(paths.config_file), 0o000)
    try:
        outcome = load_config_outcome(paths)
        assert outcome.kind == LoadKind.IO_ERROR
        with pytest.raises(ConfigError):
            load_config(paths, strict=True)
    finally:
        os.chmod(str(paths.config_file), 0o644)


def test_io_error_blocks_mutations(tmp_path):
    """Arquivo existente mas ilegível: nenhuma mutação pode prosseguir
    — salvar/renomear/deletar perfis falha explicitamente sem tocar no
    arquivo."""
    import os
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    paths.config_dir.mkdir(parents=True)
    paths.config_file.write_text('{"dpi": 1200, "profiles": {"csgo": {"dpi": 800, "sensitivity": 50}}}')
    os.chmod(str(paths.config_file), 0o000)
    try:
        store = ProfileStore(paths)
        assert not store.save_profile("new", 1600, 60).success
        assert not store.delete_profile("csgo").success
        assert not store.rename_profile("csgo", "other").success
    finally:
        os.chmod(str(paths.config_file), 0o644)
    # As mutações bloquearam sem tocar no arquivo: o conteúdo original
    # segue byte a byte no disco.
    assert paths.config_file.read_text() == (
        '{"dpi": 1200, "profiles": {"csgo": {"dpi": 800, '
        '"sensitivity": 50}}}'
    )


def test_non_object_json_raises_config_error(tmp_path):
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    paths.config_dir.mkdir(parents=True)
    paths.config_file.write_text("[1, 2, 3]")
    with pytest.raises(ConfigError):
        load_config(paths, strict=True)


def test_load_starts_from_defaults_after_invalid_json(tmp_path):
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    paths.config_dir.mkdir(parents=True)
    paths.config_file.write_text("{{{")
    config = load_config(paths)
    assert config["dpi"] == DPI_DEFAULT
    assert set(config["profiles"]) >= EXPECTED_PRESETS
    # O conteúdo corrompido foi preservado para diagnóstico.
    assert any(paths.config_dir.glob(".corrupted.*"))


def test_invalid_json_does_not_destroy_existing_data(tmp_path):
    """Leitura de arquivo EXISTENTE que falha NUNCA retorna defaults em
    modo estrito, nem sobrescreve o arquivo — o dado real permanece."""
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    paths.config_dir.mkdir(parents=True)
    paths.config_file.write_text("{corrupt}")
    with pytest.raises(ConfigError):
        load_config(paths, strict=True)
    assert paths.config_file.read_text() == "{corrupt}"


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
    assert names >= EXPECTED_PRESETS


def test_save_and_get_profile(tmp_path):
    store = ProfileStore(ConfigPaths(tmp_path / "c", tmp_path / "d"))
    outcome = store.save_profile("custom", 1500, 65)
    assert outcome.success, outcome.message
    assert outcome.profiles[0].dpi == 1500
    assert outcome.profiles[0].sensitivity == 65
    assert store.get_profile("custom") == outcome.profiles[0]


def test_profile_values_are_clamped(tmp_path):
    store = ProfileStore(ConfigPaths(tmp_path / "c", tmp_path / "d"))
    outcome = store.save_profile("custom", 99999, -10)
    assert outcome.success, outcome.message
    assert outcome.profiles[0].dpi == 25600
    assert outcome.profiles[0].sensitivity == 0


def test_delete_profile(tmp_path):
    store = ProfileStore(ConfigPaths(tmp_path / "c", tmp_path / "d"))
    assert store.delete_profile("csgo").success
    assert store.get_profile("csgo") is None
    # Excluir de novo não é idempotente silencioso: não existe mais.
    assert not store.delete_profile("csgo").success


def test_rename_profile(tmp_path):
    store = ProfileStore(ConfigPaths(tmp_path / "c", tmp_path / "d"))
    outcome = store.rename_profile("csgo", "valorant")
    assert outcome.success, outcome.message
    assert store.get_profile("valorant") is not None
    assert store.get_profile("csgo") is None
    assert store.get_profile("valorant").dpi == 400


def test_rename_profile_fails_when_target_exists(tmp_path):
    store = ProfileStore(ConfigPaths(tmp_path / "c", tmp_path / "d"))
    outcome = store.rename_profile("csgo", "minecraft")
    assert not outcome.success
    assert "já existe" in outcome.message
    assert store.get_profile("csgo") is not None


def test_profiles_are_single_source_of_truth(tmp_path):
    """Os perfis lidos são sempre os do arquivo de configuração."""
    paths = ConfigPaths(tmp_path / "c", tmp_path / "d")
    store = ProfileStore(paths)
    store.save_profile("custom", 900, 40)

    store2 = ProfileStore(paths)
    assert store2.get_profile("custom").dpi == 900


def test_presets_preserved_across_updates(tmp_path):
    """Atualizar um perfil existente não apaga os presets oficiais, e
    criar um perfil não remove os demais."""
    store = ProfileStore(ConfigPaths(tmp_path / "c", tmp_path / "d"))
    store.save_profile("fortnite", 2400, 40)
    names = {p.name for p in store.list_profiles()}
    assert names >= EXPECTED_PRESETS
    assert store.get_profile("fortnite").dpi == 2400
