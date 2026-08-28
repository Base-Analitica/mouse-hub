"""Concessão de acesso HID sem terminal (polkit/pkexec).

O usuário final não deve precisar de terminal: o app aplica a regra
udev sozinho via prompt gráfico de senha. Testes determinísticos com
runner falso — nada invoca pkexec de verdade nem toca em /etc."""

from __future__ import annotations

import subprocess

import pytest

from mouse_hub.core.operation import OperationStatus
from mouse_hub.platform.linux.privileges import (
    HID_RULE_CONTENT,
    HID_RULE_PATH,
    _build_script,
    fix_hid_permissions,
    is_hid_permission_issue,
)

REPO = __import__("pathlib").Path(__file__).resolve().parents[1]


def _runner(returncode=0, stderr=""):
    calls = []

    def run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, returncode, "", stderr)

    run.calls = calls
    return run


# ── conteúdo da regra: paridade com o fonte do projeto ───────

def test_regra_embedida_confere_com_docs_udev():
    """A linha EFETIVA (não-comentário) da regra empacotada é a mesma
    que o app instala via pkexec — zero divergência possível."""
    source = (REPO / "docs" / "udev" / "99-logitech-g403-hidraw.rules"
              ).read_text()
    effective = [
        line.strip() for line in source.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    embedded = [
        line.strip() for line in HID_RULE_CONTENT.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert embedded == effective


# ── composição do comando ────────────────────────────────────

def test_script_root_minimo():
    script = _build_script("/tmp/regra", HID_RULE_PATH)
    assert "install -m 0644 '/tmp/regra'" in script
    assert f"'{HID_RULE_PATH}'" in script
    assert "udevadm control --reload-rules" in script
    assert "udevadm trigger --action=add --subsystem-match=hidraw" in script
    # proibições do projeto
    assert "chmod" not in script
    assert "0666" not in script
    assert "apt" not in script
    assert "pip" not in script


def test_pkexec_e_invocado_com_script_e_timeout():
    run = _runner(0)
    fix_hid_permissions(runner=run)
    (cmd, kwargs), = run.calls
    assert cmd[0] == "pkexec"
    assert cmd[1] == "/bin/sh" and cmd[2] == "-c"
    assert kwargs["timeout"] > 0


def test_sucesso_aplica_e_limpa_temp():
    run = _runner(0)
    result = fix_hid_permissions(runner=run)
    assert result.status == OperationStatus.APPLIED
    # o arquivo temporário de regra existiu e foi removido.
    # NÃO assumimos /tmp/: respeitamos o TMPDIR do ambiente.
    (cmd, _), = run.calls
    tmp_in_script = [
        p for p in cmd[3].split("'") if "mouse-hub-rule-" in p
    ]
    assert tmp_in_script, "script não referencia a regra temporária"
    import os
    assert not os.path.exists(tmp_in_script[0])


@pytest.mark.parametrize("code,expected", [
    (126, OperationStatus.PERMISSION_DENIED),
    (127, OperationStatus.PERMISSION_DENIED),
], ids=["politica", "auth-cancelada"])
def test_cancelamento_do_prompt_e_recusa_honesta(code, expected):
    result = fix_hid_permissions(runner=_runner(code))
    assert result.status == expected
    assert "cancelada" in result.message or "negada" in result.message


def test_erro_real_preserva_stderr():
    result = fix_hid_permissions(runner=_runner(1, stderr="boom udev"))
    assert result.status == OperationStatus.FAILED
    assert "boom udev" in result.message


def test_pkexec_ausente_e_falha_honesta():
    def run(cmd, **kwargs):
        raise FileNotFoundError()
    result = fix_hid_permissions(runner=run)
    assert result.status == OperationStatus.FAILED
    assert "pkexec" in result.message


def test_timeout_nao_trava():
    def run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=1)
    result = fix_hid_permissions(runner=run)
    assert result.status == OperationStatus.FAILED
    assert "expirou" in result.message


# ── classificação da causa ───────────────────────────────────

def test_causa_de_permissao_e_reconhecida():
    assert is_hid_permission_issue(
        "acesso negado ao descritor hidraw (regra udev ausente)")
    assert is_hid_permission_issue(
        "Descritor hidraw sem permissão de leitura/escrita")


def test_outras_causas_nao_sao_confundidas():
    assert not is_hid_permission_issue(
        "Endpoint rejeitou a escrita (EPIPE)")
    assert not is_hid_permission_issue("nenhum dispositivo registrado")
    assert not is_hid_permission_issue("")
    assert not is_hid_permission_issue(
        "endpoint desapareceu do sistema (hot-unplug)")


# ── UI: botão da SettingsPage (offscreen, runner falso) ──────

@pytest.fixture(scope="module")
def qapp():
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _make_page(qapp, monkeypatch, hid_available: bool, permission_issue: bool = True):
    """SettingsPage com state falso controlável + runner falso."""
    from app import mouse_hub_app as app_module
    from tests.fakes import FakeHidAccess, FakeSystemInput
    from mouse_hub.core.mouse_controller import MouseController
    from mouse_hub.core.dpi_persistence import NeverDpiPersister

    hid = FakeHidAccess()
    if not hid_available:
        hid.open_permission_denied = True
    core = MouseController(hid=hid, system_input=FakeSystemInput(),
                           dpi_persister=NeverDpiPersister())
    core.refresh_device(__import__("tests.fakes", fromlist=["fake_g403_device"]).fake_g403_device())
    core.probe_endpoint()
    state = app_module.MouseCoreState(core)

    # discovery fake: o refresh do app NUNCA varre o /sys real
    from tests.fakes import fake_g403_device
    monkeypatch.setattr(app_module, "discover_candidates",
                        lambda: [fake_g403_device()])

    calls = []

    def fake_fix(rule_path=HID_RULE_PATH, runner=None, pkexec_path="pkexec"):
        calls.append(rule_path)
        if hid.open_permission_denied:
            hid.open_permission_denied = False  # "usuário digitou a senha"
        from mouse_hub.core.operation import OperationResult
        return OperationResult.applied("Acesso HID concedido")

    monkeypatch.setattr(app_module, "fix_hid_permissions", fake_fix)
    page = app_module.SettingsPage(
        None, None, None, None, state=state)
    return page, state, calls


def test_botao_visivel_quando_permissao_e_o_problema(qapp, monkeypatch):
    page, state, calls = _make_page(qapp, monkeypatch, hid_available=False)
    assert page._permission_btn.isEnabled()
    assert "permiss" in page._permission_status.text().lower() or \
        "regra udev" in page._permission_status.text().lower()


def test_botao_inativo_quando_hid_ja_disponivel(qapp, monkeypatch):
    page, state, calls = _make_page(qapp, monkeypatch, hid_available=True)
    assert not page._permission_btn.isEnabled()
    assert "ativo" in page._permission_status.text().lower()


def test_botao_inativo_quando_causa_nao_e_permissao(qapp, monkeypatch):
    """EPIPE/ausência NÃO são resolvidos pela regra udev — o botão
    não pode prometer o que não entrega."""
    page, state, calls = _make_page(qapp, monkeypatch, hid_available=False)
    from mouse_hub.core.operation import OperationStatus
    page.state._core._invalidate_access_state(OperationStatus.FAILED)
    page.state._caps = page.state._evaluate()  # caps são cacheadas
    page._sync_permission_ui()
    assert not page._permission_btn.isEnabled()
    assert "outra causa" in page._permission_status.text().lower()


def test_clique_concede_e_reavalia_hardware(qapp, monkeypatch):
    from PyQt5.QtCore import QTimer
    page, state, calls = _make_page(qapp, monkeypatch, hid_available=False)
    assert not state.capability_state().is_available("hid_available")

    page._grant_hid_access()
    # espera o fluxo async terminar (thread + singleShot polls)
    import time as _t
    deadline = _t.monotonic() + 5.0
    while (_t.monotonic() < deadline
           and page._permission_thread is not None
           and page._permission_thread.is_alive()):
        qapp.processEvents()
        _t.sleep(0.02)
    for _ in range(50):
        qapp.processEvents()
        if "concedido" in page._permission_status.text().lower() or \
            "ativo" in page._permission_status.text().lower():
            break
        _t.sleep(0.02)
        qapp.processEvents()

    assert calls == [HID_RULE_PATH]
    assert state.capability_state().is_available("hid_available")
    assert "concedido" in page._permission_status.text().lower() or \
        "ativo" in page._permission_status.text().lower()
    assert not page._permission_btn.isEnabled()


def test_clique_duplo_nao_empilha_threads(qapp, monkeypatch):
    page, state, calls = _make_page(qapp, monkeypatch, hid_available=False)

    def slow_fix(**kwargs):
        import time as _t
        _t.sleep(0.3)
        from mouse_hub.core.operation import OperationResult
        return OperationResult.applied("ok")

    from app import mouse_hub_app as app_module
    monkeypatch.setattr(app_module, "fix_hid_permissions", slow_fix)
    page._grant_hid_access()
    t1 = page._permission_thread
    page._grant_hid_access()  # segundo clique durante execução
    assert page._permission_thread is t1
    t1.join(timeout=3.0)
