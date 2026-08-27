# -*- coding: utf-8 -*-
"""Suíte da issue #3 — [P0] Corrigir descoberta do G403 HERO e separar
DPI físico de sensibilidade.

Testes determinísticos sobre o core + UI reconfigurada, usando os fakes
existentes em tests/fakes.py. Cobrem os 14 cenários obrigatórios da
issue #3:

  1. UI/core com G403 ausente
  2. dispositivo com VID/PID errado
  3. G403 presente sem hidraw
  4. permission denied
  5. timeout HID++
  6. erro de protocolo
  7. sucesso confirmado de DPI
  8. falha de DPI não altera sensibilidade
  9. sucesso de DPI não altera sensibilidade
 10. valor solicitado != valor normalizado/aplicado
 11. persistência somente após confirmação
 12. nenhuma referência operacional a /dev/hidraw0 na UI
 13. nenhuma escrita em hardware antes da validação de identidade
 14. capabilities invalidadas após falha real

Mock não é prova de hardware real: os fakes emulam o contrato do
protocolo HID++ (headers ecoados, feature 0x2201, ACK de conferência).
"""
import ast
import pytest

from mouse_hub.core.constants import DPI_DEFAULT, G403_NAME, G403_PID, G403_VID
from mouse_hub.core.config import ConfigPaths
from mouse_hub.core.discovery import discover
from mouse_hub.core.mouse_controller import MouseController, make_linux_controller
from mouse_hub.core.operation import OperationStatus
from tests.fakes import (
    FakeHidAccess,
    FakeSystemInput,
    fake_g403_device,
)
from mouse_hub.core.dpi_persistence import NeverDpiPersister

# ---------------------------------------------------------------------------
# Fixtures de composição (mesma forma da factory de produção, com fakes).

def _make_controller(persister=None):
    """Controller com fakes + ConfigPaths em tempdir (não usa XDG real)."""
    import tempfile
    tmp = tempfile.mkdtemp()
    from pathlib import Path
    paths = ConfigPaths(Path(tmp), Path(tmp))
    return make_linux_controller(
        hid=FakeHidAccess(),
        system_input=FakeSystemInput(),
        config_paths=paths,
        dpi_persister=persister,
    ), paths


def _make_controller_with(hid=None, system_input=None, dpi_persister=None):
    import tempfile
    from pathlib import Path
    tmp = tempfile.mkdtemp()
    paths = ConfigPaths(Path(tmp), Path(tmp))
    return (
        MouseController(
            hid=hid if hid is not None else FakeHidAccess(),
            system_input=system_input if system_input is not None else FakeSystemInput(),
            dpi_persister=dpi_persister if dpi_persister is not None else NeverDpiPersister(),
        ),
        paths,
    )


def _discovered(hidraw="/dev/hidraw2"):
    return fake_g403_device(hidraw=hidraw)


# ---------------------------------------------------------------------------
# 1. G403 ausente — core e UI não assumem presença.

class TestIssue3DeviceAbsent:
    """Cenário obrigatório: UI/core com G403 ausente."""

    def test_discovery_returns_none_without_g403(self, tmp_path):
        """discover() devolve None quando não há mouse com a identidade
        esperada — nada é construído, nenhuma escrita acontece.

        Hermeticidade: sysfs falso vazio (o patch de os.scandir não
        cobre Path.iterdir em Python 3.12 — em máquina com o G403
        plugado o scan real devolveria o device e o teste mentiria)."""
        assert discover(sysfs_root=tmp_path) is None

    def test_controller_without_device_reports_no_dpi(self):
        core, _ = _make_controller_with()
        # Sem device registrado: capabilities negam tudo com causas reais.
        caps = core.capability_model().evaluate()
        assert not caps.is_available("mouse_detected")
        assert not caps.is_available("hid_available")
        assert not caps.is_available("hardware_dpi_available")
        assert core.applied_dpi is None  # estado físico real desconhecido
        assert core.applied_sensitivity is None

    def test_operation_on_absent_device_is_device_not_found(self):
        core, _ = _make_controller_with()
        result = core.set_hardware_dpi(800)
        assert result.status == OperationStatus.DEVICE_NOT_FOUND
        assert result.status.ok is False


# ---------------------------------------------------------------------------
# 2. VID/PID errado — rejeição de identidade.

class TestIssue3WrongIdentity:
    """Cenário obrigatório: dispositivo com VID/PID errado."""

    def test_wrong_pid_is_rejected(self):
        from mouse_hub.core.discovery import MouseDevice
        core, _ = _make_controller_with()
        fake_device = MouseDevice(
            hidraw_path="/dev/hidraw2",
            vid=G403_VID,
            pid=G403_PID + 1,  # identidade divergente (device é frozen)
            name="dispositivo de teste",
        )
        result = core.refresh_device(fake_device)
        assert result.status == OperationStatus.DEVICE_NOT_FOUND
        assert core.device is None  # device rejeitado NUNCA é registrado
        assert core._dpi_feature_index is None

    def test_no_write_before_identity_check(self):
        """Cenário obrigatório: nenhuma escrita em hardware antes da
        validação de identidade. O fake conta writes observáveis."""
        from mouse_hub.core.discovery import MouseDevice
        hid = FakeHidAccess()
        core, _ = _make_controller_with(hid=hid)
        other_device = MouseDevice(
            hidraw_path="/dev/hidraw2",
            vid=G403_VID,
            pid=G403_PID + 3,  # identidade divergente (device é frozen)
            name="outro dispositivo",
        )
        core.refresh_device(other_device)
        core.probe_endpoint()
        try:
            core.set_hardware_dpi(800)
        except OSError:
            pass  # falha de transporte esperada — o ponto é o count
        assert hid._write_counter == 0
        assert hid.applied_dpi_history == []


# ---------------------------------------------------------------------------
# 3. G403 presente sem hidraw.

class TestIssue3NoHidraw:
    """Cenário obrigatório: G403 presente sem interface hidraw."""

    def test_device_without_hidraw_is_detected_but_not_controllable(self):
        core, _ = _make_controller_with()
        device = _discovered(hidraw=None)  # mouse presente, sem hidraw
        reg = core.refresh_device(device)
        assert reg.status == OperationStatus.UNSUPPORTED
        assert core.device is not None  # detectado

        caps = core.capability_model().evaluate()
        assert caps.is_available("mouse_detected")
        assert not caps.is_available("hid_available")
        assert not caps.is_available("hardware_dpi_available")

        result = core.probe_endpoint()
        assert result.status == OperationStatus.UNSUPPORTED
        dpi_result = core.set_hardware_dpi(800)
        assert dpi_result.status == OperationStatus.UNSUPPORTED
        assert dpi_result.status.ok is False


# ---------------------------------------------------------------------------
# 4. Permission denied.

class TestIssue3PermissionDenied:
    """Cenário obrigatório: permission denied permanece distinto."""

    def test_permission_denied_kept_distinct(self):
        hid = FakeHidAccess()
        hid.open_permission_denied = True
        core, _ = _make_controller_with(hid=hid)
        core.refresh_device(_discovered())
        probe = core.probe_endpoint()
        assert probe.status == OperationStatus.PERMISSION_DENIED
        assert probe.status.ok is False

        # E a capability reflete exatamente a causa (não genérico).
        caps = core.capability_model().evaluate()
        assert not caps.is_available("hid_available")


# ---------------------------------------------------------------------------
# 5. Timeout HID++.

class TestIssue3AckTimeout:
    """Cenário obrigatório: timeout HID++ (endpoint silencia)."""

    def test_hid_timeout_is_fail_closed(self):
        hid = FakeHidAccess()
        hid.ack_timeout = True
        core, _ = _make_controller_with(hid=hid)
        core.refresh_device(_discovered())
        probe = core.probe_endpoint()
        assert probe.status.ok is False
        assert probe.status in (OperationStatus.FAILED,
                                OperationStatus.DEVICE_NOT_FOUND)

        dpi = core.set_hardware_dpi(800)
        assert dpi.status.ok is False

    def test_timeout_on_set_kills_hardware_dpi_available(self):
        """Probe saudável, mas SetSensorDPI timeout: hardware_dpi_available
        deixa de ser True — hid_available permanece separado (transporte
        acessível). Re-probe recupera."""
        hid = FakeHidAccess()
        core, _ = _make_controller_with(hid=hid)
        core.refresh_device(_discovered())
        core.probe_endpoint()
        # Estado saudável após probe.
        caps = core.capability_model().evaluate()
        assert caps.is_available("hid_available")
        assert caps.is_available("hardware_dpi_available")

        # Timeout APENAS no SetSensorDPI (ack_timeout após probe).
        hid.ack_timeout = True
        result = core.set_hardware_dpi(800)
        assert result.status.ok is False
        assert core.applied_dpi is None  # nada aplicado
        assert "dpi_set_error" in result.details
        assert result.details["dpi_set_error"] == "timeout"

        # Capability: hardware_dpi_available morto, hid_available vivo.
        caps = core.capability_model().evaluate()
        assert not caps.is_available("hardware_dpi_available")
        reason = caps.reason_for("hardware_dpi_available")
        assert "timeout" in reason.lower()
        assert caps.is_available("hid_available")

        # Re-probe saudável recupera.
        hid.ack_timeout = False
        core.probe_endpoint()
        caps = core.capability_model().evaluate()
        assert caps.is_available("hardware_dpi_available")
        assert caps.is_available("hid_available")


# ---------------------------------------------------------------------------
# 6. Erro de protocolo.

class TestIssue3ProtocolError:
    """Cenário obrigatório: erro de protocolo não vira sucesso."""

    def test_protocol_error_reports_real_cause(self):
        hid = FakeHidAccess()
        hid.probe_stage2_error = True  # FAP error no GetFeature(0x2201)
        core, _ = _make_controller_with(hid=hid)
        core.refresh_device(_discovered())
        probe = core.probe_endpoint()
        assert probe.status.ok is False
        assert "fap_error_code" in probe.details
        assert probe.status == OperationStatus.FAILED

        # Falha de protocolo também mata a disponibilidade de DPI.
        caps = core.capability_model().evaluate()
        assert not caps.is_available("hardware_dpi_available")

    def test_rejected_dpi_set_is_not_success(self):
        hid = FakeHidAccess()
        hid.dpi_set_rejected = True  # FAP 0x02 no SetSensorDPI
        core, _ = _make_controller_with(hid=hid)
        core.refresh_device(_discovered())
        core.probe_endpoint()
        # Antes do set: capabilities saudáveis.
        caps = core.capability_model().evaluate()
        assert caps.is_available("hid_available")
        assert caps.is_available("hardware_dpi_available")

        result = core.set_hardware_dpi(800)
        assert result.status.ok is False
        # O dispositivo REJEITOU o comando (FAP 0x02) — o controller
        # trata como não aplicado: o DPI confirmado fica None e nada é
        # considerado efetivo, ainda que o request tenha saído no fio.
        assert core.applied_dpi is None
        assert core._applied_dpi is None

        # APÓS a falha: hardware_dpi_available deixa de ser True.
        # hid_available permanece True (transporte acessível).
        caps = core.capability_model().evaluate()
        assert not caps.is_available("hardware_dpi_available")
        assert caps.is_available("hid_available")

        # Re-probe saudável recupera a capability.
        hid.dpi_set_rejected = False
        core.probe_endpoint()
        caps = core.capability_model().evaluate()
        assert caps.is_available("hardware_dpi_available")
        assert caps.is_available("hid_available")


# ---------------------------------------------------------------------------
# 7. Sucesso confirmado de DPI.

class TestIssue3ConfirmedSuccess:
    """Cenário obrigatório: sucesso SÓ quando o hardware confirmou."""

    def test_applied_dpi_only_after_ack(self):
        hid = FakeHidAccess()
        core, _ = _make_controller_with(hid=hid)
        core.refresh_device(_discovered())
        core.probe_endpoint()

        result = core.set_hardware_dpi(800)
        assert result.status.ok is True
        # O fake ecoa o SetSensorDPI só quando o ACK confirma — e o
        # controller aplica no history observável.
        assert hid.applied_dpi_history == [(hid.dpi_feature_index, 800)]
        assert core.applied_dpi == 800

    def test_success_still_reports_real_status(self):
        hid = FakeHidAccess()
        core, _ = _make_controller_with(hid=hid)
        core.refresh_device(_discovered())
        core.probe_endpoint()
        result = core.set_hardware_dpi(1200)
        assert result.status == OperationStatus.APPLIED
        assert result.details.get("applied") == 1200


# ---------------------------------------------------------------------------
# 8. Falha de DPI não altera sensibilidade.

class TestIssue3DpiFailureKeepsSensitivity:
    """Cenário obrigatório: falha de DPI NÃO altera sensibilidade —
    nem antes, nem como consequência."""

    def test_dpi_failure_never_touches_sensitivity(self):
        hid = FakeHidAccess()
        system_input = FakeSystemInput()
        hid.dpi_set_rejected = True
        core, _ = _make_controller_with(hid=hid, system_input=system_input)
        core.refresh_device(_discovered())
        core.probe_endpoint()

        core.set_sensitivity(50)
        # 50% -> accel 0.0 (percent_to_accel = v/100*2 - 1)
        assert system_input.accel_state == pytest.approx(0.0, abs=1e-9)
        before_sensitivity = core.applied_sensitivity

        result = core.set_hardware_dpi(800)  # falha
        assert result.status.ok is False
        # Sensibilidade inalterada — o core.set_hardware_dpi não toca no
        # SystemInput, e nenhuma correção automática ocorre.
        assert core.applied_sensitivity == before_sensitivity
        assert system_input.accel_state == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# 9. Sucesso de DPI não altera sensibilidade.

class TestIssue3DpiSuccessKeepsSensitivity:
    """Cenário obrigatório: mesmo no sucesso, DPI físico e sensibilidade
    são ações separadas — sucesso de DPI não toca no ponteiro."""

    def test_dpi_success_never_touches_sensitivity(self):
        hid = FakeHidAccess()
        system_input = FakeSystemInput()
        core, _ = _make_controller_with(hid=hid, system_input=system_input)
        core.refresh_device(_discovered())
        core.probe_endpoint()

        core.set_sensitivity(70)
        # 70% -> accel 0.4
        assert system_input.accel_state == pytest.approx(0.4, abs=1e-9)
        before = core.applied_sensitivity

        result = core.set_hardware_dpi(1600)
        assert result.status.ok is True
        assert core.applied_dpi == 1600
        assert core.applied_sensitivity == before
        assert system_input.accel_state == pytest.approx(0.4, abs=1e-9)


# ---------------------------------------------------------------------------
# 10. Valor solicitado != valor normalizado/aplicado.

class TestIssue3NormalizedApplied:
    """Cenário obrigatório: a UI exibe o que o hardware confirmou, não o
    que foi pedido. Valores fora da faixa normal do sensor são
    arredondados/normalizados e o details.loaded carregam o par."""

    def test_applied_differs_from_requested_when_normalized(self):
        hid = FakeHidAccess()
        # Sensor real normaliza 750 -> 750? O controller normaliza ao
        # step (50): 751 -> 750, 799 -> 800.
        core, _ = _make_controller_with(hid=hid)
        core.refresh_device(_discovered())
        core.probe_endpoint()

        result = core.set_hardware_dpi(799)
        assert result.status.ok is True
        requested = result.details.get("requested")
        applied = result.details.get("applied")
        assert requested == 799
        assert applied != requested
        assert applied == 800
        assert core.applied_dpi == 800

    def test_clamped_value_persists_clamped(self):
        hid = FakeHidAccess()
        core, _ = _make_controller_with(hid=hid)
        core.refresh_device(_discovered())
        core.probe_endpoint()
        result = core.set_hardware_dpi(999999)
        assert result.status.ok is True
        assert 100 <= result.details.get("applied") <= 25600
        assert result.details.get("applied") == core.applied_dpi


# ---------------------------------------------------------------------------
# 11. Persistência somente após confirmação.

class TestIssue3PersistenceAfterConfirmation:
    """Cenário obrigatório: o config.json só muda depois de ACK real."""

    def test_persistence_only_after_ack(self, tmp_path):
        from pathlib import Path
        hid = FakeHidAccess()
        paths = ConfigPaths(Path(tmp_path), Path(tmp_path))
        # make_linux_controller injeta o persister REAL (DpiConfigPersister)
        # — a própria factory é o que valida a rota de produção.
        core = make_linux_controller(
            hid=hid,
            system_input=FakeSystemInput(),
            config_paths=paths,
        )
        core.refresh_device(_discovered())
        core.probe_endpoint()

        result = core.set_hardware_dpi(1000)
        assert result.status.ok is True

        # Config de produção gravou SOMENTE o DPI confirmado (applied),
        # e o valor default restante permanece.
        loaded = __import__("mouse_hub.core.config", fromlist=["load_config_outcome", "default_config"])
        outcome = loaded.load_config_outcome(paths)
        cfg = outcome.config
        assert cfg["applied_dpi"] == 1000
        assert cfg["dpi"] == loaded.default_config()["dpi"]

    def test_rejected_set_persists_nothing(self, tmp_path):
        from pathlib import Path
        hid = FakeHidAccess()
        hid.dpi_set_rejected = True
        paths = ConfigPaths(Path(tmp_path), Path(tmp_path))
        core = make_linux_controller(
            hid=hid,
            system_input=FakeSystemInput(),
            config_paths=paths,
        )
        core.refresh_device(_discovered())
        core.probe_endpoint()

        result = core.set_hardware_dpi(1000)
        assert result.status.ok is False

        # O ACK nunca veio (FAP 0x02): nenhum arquivo de config foi
        # criado/alterado — a primeira execução sem confirmação parte
        # dos defaults.
        loaded = __import__("mouse_hub.core.config", fromlist=["load_config_outcome", "default_config"])
        cfg = loaded.load_config_outcome(paths).config
        assert cfg.get("applied_dpi") is None
        assert cfg["dpi"] == loaded.default_config()["dpi"]


# ---------------------------------------------------------------------------
# 12. Nenhuma referência operacional a /dev/hidraw0 na UI.

class TestIssue3NoHidraw0InUI:
    """Cenário obrigatório: a UI nativa nunca referencia /dev/hidraw0."""

    def test_app_source_has_no_operational_hidraw0(self):
        """Cenário obrigatório: a UI nativa nunca referencia /dev/hidraw0
        em caminho OPERACIONAL (strings literais de código/execução).
        Comentários/documentação histórica são permitidos — o teste
        analisa apenas o AST (nós de string em expressões e atribuições
        executáveis), ignorando docstrings.
        """
        import app.mouse_hub_app as app_module
        import inspect
        source = inspect.getsource(app_module)
        tree = ast.parse(source)
        # Marcar pais de cada nó (docstrings são Constant dentro de
        # Expr como PRIMEIRO statement de um bloco class/func/module).
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                child._parent = node

        def _is_docstring(node):
            parent = getattr(node, "_parent", None)
            if not isinstance(parent, ast.Expr):
                return False
            grand = getattr(parent, "_parent", None)
            if not isinstance(
                grand,
                (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                 ast.ClassDef),
            ):
                return False
            return (
                getattr(grand, "body", [None])[0] is parent
                or getattr(grand, "body", [None])[0] == parent
            )

        offending: list = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and "/dev/hidraw0" in node.value
                and not _is_docstring(node)
            ):
                offending.append(node)
        assert not offending, "/dev/hidraw0 aparece em código operacional da UI"

    def test_app_source_parses_cleanly(self):
        import app.mouse_hub_app as app_module
        source = __import__("inspect").getsource(app_module)
        ast.parse(source)  # sem SyntaxError — método `is` renomeado


# ---------------------------------------------------------------------------
# 13. Nenhuma escrita em hardware antes da validação de identidade.

class TestIssue3IdentityBeforeWrites:
    """Cenário obrigatório (complemento): o probe valida a identidade
    ANTES de qualquer efeito HID — nenhum write chega ao fake antes do
    registro aprovado (VID+PID)."""

    def test_probe_writes_only_after_register(self):
        hid = FakeHidAccess()
        core, _ = _make_controller_with(hid=hid)
        device = _discovered()

        # Antes de refresh_device: nada escrito.
        core.probe_endpoint()
        assert hid._write_counter == 0

        core.refresh_device(device)
        writes_before_probe = hid._write_counter
        core.probe_endpoint()
        # Após registro aprovado o probe pode escrever (descoberta de
        # feature); antes do registro, zero.
        assert hid.applied_dpi_history == []  # DPI só depois de set

    def test_unregistered_device_cannot_write_dpi(self):
        hid = FakeHidAccess()
        core, _ = _make_controller_with(hid=hid)
        try:
            core.set_hardware_dpi(800)
        except OSError:
            pass
        assert hid._write_counter == 0
        assert hid.applied_dpi_history == []


# ---------------------------------------------------------------------------
# 14. Capabilities invalidadas após falha real.

class TestIssue3CapabilityInvalidation:
    """Cenário obrigatório: após falha real de acesso, hid_available /
    hardware_dpi_available NUNCA permanecem True."""

    def test_capabilities_dead_after_real_access_failure(self):
        hid = FakeHidAccess()
        core, _ = _make_controller_with(hid=hid)
        core.refresh_device(_discovered())
        core.probe_endpoint()
        # Estado saudável:
        caps = core.capability_model().evaluate()
        assert caps.is_available("hid_available")
        assert caps.is_available("hardware_dpi_available")

        # Falha real (hot-unplug simulado no fake).
        hid.open_permission_denied = True
        core.probe_endpoint()  # falha agora invalida o snapshot
        caps = core.capability_model().evaluate()
        assert not caps.is_available("hid_available")
        assert not caps.is_available("hardware_dpi_available")
        # O feature index confirmado também morre (ambiente invalidado).
        assert core._dpi_feature_index is None

    def test_invalidation_survives_re_probe(self):
        hid = FakeHidAccess()
        core, _ = _make_controller_with(hid=hid)
        core.refresh_device(_discovered())
        # Timeout HID++ no probe é falha de PROTOCOLO (o acesso real ao
        # descritor funcionou) — hid_available continua refletindo o
        # acesso real. A invalidação de acesso vem de falha REAL de
        # transporte (open/write/read), não de protocolo.
        core.probe_endpoint()
        hid.open_permission_denied = True
        probe = core.probe_endpoint()  # falha REAL de acesso — invalida
        caps = core.capability_model().evaluate()
        assert not caps.is_available("hid_available")
        # Re-probe recupera quando o ambiente volta a ser saudável.
        hid.open_permission_denied = False
        core.probe_endpoint()
        caps = core.capability_model().evaluate()
        assert caps.is_available("hid_available")
        # E se falhar DE NOVO, invalida de novo — nunca fica True
        # espontaneamente depois de falha real.
        hid.open_permission_denied = True
        core.probe_endpoint()
        caps = core.capability_model().evaluate()
        assert not caps.is_available("hid_available")
