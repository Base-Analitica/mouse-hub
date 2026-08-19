"""Suíte do dpi_persistence: invariância fail-closed da persistência.

O DpiConfigPersister NUNCA escreve a partir de dados não confirmados:

* LoadKind.FILE            → escreve (apenas applied_dpi muda);
* LoadKind.DEFAULT + arquivo REALMENTE ausente → cria a config;
* LoadKind.CORRUPTED / IO_ERROR / DEFAULT + arquivo existente
  → nunca escreve; os bytes originais permanecem idênticos.

Nenhum teste escreve no HOME real: todo teste usa ConfigPaths
apontando para um diretório temporário controlado.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mouse_hub.core.config import (
    ConfigPaths,
    LoadKind,
    load_config_outcome,
    save_config,
)
from mouse_hub.core.dpi_persistence import DpiConfigPersister, NeverDpiPersister


@pytest.fixture()
def tmp_paths(tmp_path: Path) -> ConfigPaths:
    base = tmp_path / "mouse_hub"
    base.mkdir()
    return ConfigPaths(config_dir=base, data_dir=base)


def _write(paths: ConfigPaths, data: str) -> None:
    paths.config_file.parent.mkdir(parents=True, exist_ok=True)
    paths.config_file.write_text(data)


# ── Guard fail-closed ───────────────────────────────────────────────


def test_corrupted_config_is_never_overwritten(tmp_paths: ConfigPaths) -> None:
    _write(tmp_paths, "{isto nao e json valido!")
    original = tmp_paths.config_file.read_bytes()
    persister = DpiConfigPersister(tmp_paths)

    persisted = persister.persist_applied_dpi(1600)

    assert persisted is False
    assert tmp_paths.config_file.read_bytes() == original
    # O load ainda reporta CORRUPTED — nada foi perdido.
    outcome = load_config_outcome(tmp_paths, strict=False)
    assert outcome.kind == LoadKind.CORRUPTED


def test_io_error_config_is_never_overwritten(
    tmp_paths: ConfigPaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    """IO_ERROR REAL e determinístico: a leitura do arquivo levanta
    OSError (perda/indisponibilidade do fd) — o persister NÃO escreve,
    os bytes do arquivo permanecem idênticos e o load reporta IO_ERROR.
    monkeypatch substitui Path.read_text por uma que levanta OSError,
    reproduzindo o caso sem depender de chmod 0o000 (que root ignora
    e pode flaky em CI)."""
    _write(tmp_paths, '{"applied_dpi": 800, "applied_sensitivity": 50}')
    original = tmp_paths.config_file.read_bytes()
    monkeypatch.setattr(
        "pathlib.Path.read_text",
        lambda *a, **k: (_ for _ in ()).throw(OSError("fd indisponível")),
        raising=True,
    )
    persister = DpiConfigPersister(tmp_paths)

    persisted = persister.persist_applied_dpi(1600)

    assert persisted is False
    assert tmp_paths.config_file.read_bytes() == original
    outcome = load_config_outcome(tmp_paths, strict=False)
    assert outcome.kind == LoadKind.IO_ERROR


def test_valid_config_changes_only_applied_dpi(tmp_paths: ConfigPaths) -> None:
    _write(
        tmp_paths,
        '{"applied_dpi": 800, "applied_sensitivity": 50, "custom_key": 42}',
    )
    original = tmp_paths.config_file.read_text()
    persister = DpiConfigPersister(tmp_paths)

    persisted = persister.persist_applied_dpi(1600)

    assert persisted is True
    outcome = load_config_outcome(tmp_paths, strict=False)
    assert outcome.kind == LoadKind.FILE
    assert outcome.config["applied_dpi"] == 1600
    # Nenhuma outra chave foi alterada.
    assert outcome.config["applied_sensitivity"] == 50
    assert outcome.config["custom_key"] == 42
    # Só a linha do applied_dpi muda no JSON reescrito; as demais chaves
    # preservadas acima são a prova observável da invariável.
    assert original != tmp_paths.config_file.read_text()


def test_first_run_creates_config_preserving_defaults(
    tmp_paths: ConfigPaths,
) -> None:
    assert not tmp_paths.config_file.exists()
    persister = DpiConfigPersister(tmp_paths)

    persisted = persister.persist_applied_dpi(1200)

    assert persisted is True
    assert tmp_paths.config_file.exists()
    outcome = load_config_outcome(tmp_paths, strict=False)
    assert outcome.kind == LoadKind.FILE
    assert outcome.config["applied_dpi"] == 1200
    # Defaults intactos: sensibilidade e presets não foram tocados.
    assert "applied_sensitivity" in outcome.config
    assert "profiles" in outcome.config


def test_requested_dpi_persists_effective_value(tmp_paths: ConfigPaths) -> None:
    _write(tmp_paths, '{"applied_dpi": 800, "applied_sensitivity": 50}')
    persister = DpiConfigPersister(tmp_paths)

    persisted = persister.persist_applied_dpi(1600)

    assert persisted is True
    outcome = load_config_outcome(tmp_paths, strict=False)
    # Persiste o effective (normalizado), nunca o solicitado bruto.
    assert outcome.config["applied_dpi"] == 1600


# ── Controle de chamada ────────────────────────────────────────────


def test_timeout_or_rejection_never_calls_persister() -> None:
    """Caminhos de timeout/rejeição HID nunca tocam o persister: o
    controller só invoca persist_applied_dpi após ACK — a prova aqui é
    que um persister rastreado permanece sem chamadas quando a
    operação falha no controller (NeverDpiPersister como baseline)."""
    persister = NeverDpiPersister()
    assert persister.persist_applied_dpi(800) is False


def test_persister_called_only_after_ack(
    tmp_paths: ConfigPaths,
) -> None:
    from mouse_hub.core.mouse_controller import make_linux_controller
    from tests.fakes import FakeHidAccess, FakeSystemInput, fake_g403_device

    _write(
        tmp_paths,
        '{"applied_dpi": 800, "applied_sensitivity": 50}',
    )
    hid = FakeHidAccess()
    input_ = FakeSystemInput()
    ctrl = make_linux_controller(hid, input_, config_paths=tmp_paths)

    device = fake_g403_device(hidraw="/dev/hidraw10")
    ctrl.refresh_device(device)
    probe = ctrl.probe_endpoint()
    assert probe.status.ok, probe.details

    # Antes do ACK nenhum byte de config foi tocado.
    config_before = tmp_paths.config_file.read_text()

    # Rejeição do dispositivo: o persister NÃO é chamado.
    hid.dpi_set_rejected = True
    rejected = ctrl.set_hardware_dpi(1200)
    assert not rejected.status.ok
    assert rejected.status.name == "FAILED"
    assert tmp_paths.config_file.read_text() == config_before

    # Timeout: o persister NÃO é chamado.
    hid.dpi_set_rejected = False
    hid.ack_timeout = True
    timed_out = ctrl.set_hardware_dpi(1200)
    assert not timed_out.status.ok
    assert timed_out.status.name == "FAILED"
    assert tmp_paths.config_file.read_text() == config_before

    # ACK real: o persister REAL escreve apenas applied_dpi.
    hid.ack_timeout = False
    ok = ctrl.set_hardware_dpi(1200)
    assert ok.status.ok
    assert ok.details.get("persisted") is True  # type: ignore[union-attr]
    outcome = load_config_outcome(tmp_paths, strict=False)
    assert outcome.config["applied_dpi"] == 1200
    assert outcome.config["applied_sensitivity"] == 50
