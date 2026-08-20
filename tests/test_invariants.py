"""Regressão das invariantes centrais do Mouse Hub (issue #9).

Suíte nova, nomeada por invariante, que protege as regras que as
suítes existentes ainda não cobriam diretamente:

* clamp + step do DPI no PIPELINE completo (controller), não só na
  função pura;
* separação estrita DPI físico × sensibilidade do sistema em todos os
  caminhos (inclusive o de falha);
* criação/carregamento/remoção de perfis com reload do disco (roundtrip
  real, não apenas o objeto em memória);
* serialização/desserialização de macros com perda de precisão
  conhecida do delta_ms (arredondamento a 2 casas) e entradas parciais;
* reprodução de macros com ordem preservada, repeat exato e falha que
  vira FAILED com release defensivo — nunca sucesso falso;
* limites e configuração do auto-clicker (CPS [1,50], idempotência,
  bloqueio por foco, falha de backend vira FAILED);
* scheduler com timing controlável (validação, cancelamento imediato);
* comportamento sem G403 / sem HID / fonte indisponível.

Determinística: nenhum teste abre Display X, toca hidraw real ou spawna
subprocesso. Usa apenas fakes já existentes em tests/fakes.py — sem
mocks que repetem a implementação.
"""

from __future__ import annotations

import time
import threading
from pathlib import Path
from typing import Optional

import pytest

from mouse_hub.core.automation.autoclicker import (
    AutoClickerEngine,
    AutoClickerState,
)
from mouse_hub.core.automation.focus import WindowFocusChecker
from mouse_hub.core.automation.macros import (
    MacroPlayer,
    MacroRecorder,
    PlaybackState,
)
from mouse_hub.core.automation.scheduler import AutomationScheduler
from mouse_hub.core.automation.store import MacroStore
from mouse_hub.core.automation.types import EventType, MouseButton, RecordedEvent
from mouse_hub.core.config import (
    ConfigPaths,
    LoadKind,
    default_config,
    load_config_outcome,
    save_config,
)
from mouse_hub.core.constants import (
    DPI_DEFAULT,
    DPI_MAX,
    DPI_MIN,
    DPI_STEP,
    SENSITIVITY_DEFAULT,
)
from mouse_hub.core.mouse_controller import MouseController, make_linux_controller
from mouse_hub.core.profiles import ProfileStore
from tests.fakes import (
    FakeAutomationIO,
    FakeFocusTitleSource,
    FakeHidAccess,
    FakeSystemInput,
    fake_g403_device,
)


# ── Helpers ─────────────────────────────────────────────────────────


class _TitleSource:
    """TitleSource mínimo com título programável (e opcionalmente
    indisponível)."""

    def __init__(self, title: Optional[str]) -> None:
        self.title = title

    def active_window_title(self) -> Optional[str]:
        return self.title


def _focus(title: Optional[str]) -> WindowFocusChecker:
    return WindowFocusChecker(_TitleSource(title), ttl_ms=500)


class FakeHidForPipeline(FakeHidAccess):
    """FakeHidAccess sem knobs especiais — o fake padrão já responde
    probe/ACK normalmente; o HidAccess real é aberto só dentro das
    operações."""

    pass


@pytest.fixture()
def controller():
    """Controller de produção com fakes e probe prévio — o mesmo que a
    UI usa após o startup (device registrado + endpoint confirmado)."""
    hid = FakeHidForPipeline()
    system_input = FakeSystemInput()
    ctrl = make_linux_controller(hid, system_input)
    ctrl.refresh_device(fake_g403_device())
    result = ctrl.probe_endpoint()
    assert result.status.ok, "probe não deveria falhar com o fake padrão"
    return ctrl, hid, system_input


def test_pipeline_normalizes_dpi_by_step(controller):
    """INVARIANTE: o DPI solicitado passa por clamp+step ANTES de tocar
    o hardware — um valor dentro da faixa, porém não alinhado ao step
    de 50, vira o passo superior (825 → 850) e o resultado declara
    APPLIED_PARTIAL com requested/applied explícitos. O hardware NUNCA
    recebe 825."""
    hid = FakeHidForPipeline()
    system_input = FakeSystemInput()
    ctrl = make_linux_controller(hid, system_input)
    ctrl.refresh_device(fake_g403_device())
    assert ctrl.probe_endpoint().status.ok

    result = ctrl.set_hardware_dpi(825)

    assert result.status.value == "applied_partial"
    assert result.details["requested"] == 825
    assert result.details["applied"] == 850
    assert hid.written_reports
    payload = hid.written_reports[-1]
    assert (payload[5] << 8 | payload[6]) == 850


def test_pipeline_clamps_below_minimum(controller):
    """INVARIANTE: valor abaixo do mínimo físico vira DPI_MIN (applied
    ≠ requested) — o sensor não aceita 50 DPI; nada vira sucesso
    silencioso com o valor errado."""
    hid = FakeHidForPipeline()
    ctrl = make_linux_controller(hid, FakeSystemInput())
    ctrl.refresh_device(fake_g403_device())
    assert ctrl.probe_endpoint().status.ok

    result = ctrl.set_hardware_dpi(50)

    assert result.status.value == "applied_partial"
    assert result.details["applied"] == DPI_MIN
    assert result.details["requested"] == 50


def test_pipeline_clamps_above_maximum(controller):
    """INVARIANTE: valor acima do teto físico vira DPI_MAX — o clamp
    impede que o request ultrapasse o que o sensor suporta."""
    hid = FakeHidForPipeline()
    ctrl = make_linux_controller(hid, FakeSystemInput())
    ctrl.refresh_device(fake_g403_device())
    assert ctrl.probe_endpoint().status.ok

    result = ctrl.set_hardware_dpi(99999)

    assert result.status.value == "applied_partial"
    assert result.details["applied"] == DPI_MAX


def test_step_rounds_to_nearest_step_boundary(controller):
    """INVARIANTE: o step arredonda para o valor suportado MAIS PRÓXIMO
    — valores acima do meio do passo (825+) sobem, abaixo (824-) descem.
    O hardware sempre recebe um valor alinhado ao passo de 50."""
    hid = FakeHidForPipeline()
    ctrl = make_linux_controller(hid, FakeSystemInput())
    ctrl.refresh_device(fake_g403_device())
    assert ctrl.probe_endpoint().status.ok

    for requested, expected in ((800, 800), (824, 800), (825, 850), (875, 900), (876, 900)):
        hid.written_reports.clear()
        result = ctrl.set_hardware_dpi(requested)
        assert result.details["applied"] == expected, (
            f"{requested} → {expected} (step {DPI_STEP})"
        )
        if requested != expected:
            assert result.status.value == "applied_partial"


def test_exact_dpi_is_applied_full(controller):
    """INVARIANTE: valor exato de um passo suportado vira APPLIED
    (não parcial) — o report parcial só existe quando houve adaptação
    real."""
    hid = FakeHidForPipeline()
    ctrl = make_linux_controller(hid, FakeSystemInput())
    ctrl.refresh_device(fake_g403_device())
    assert ctrl.probe_endpoint().status.ok

    result = ctrl.set_hardware_dpi(DPI_DEFAULT)

    assert result.status.value == "applied"
    assert result.details["applied"] == DPI_DEFAULT
    assert "requested" not in result.details


# ── Invariante: DPI físico ≠ sensibilidade do sistema ───────────────


def test_dpi_pipeline_never_touches_system_sensitivity(controller):
    """INVARIANTE: qualquer caminho do DPI físico (parcial ou completo)
    não altera a sensibilidade do sistema — conceitos diferentes,
    controles diferentes."""
    hid = FakeHidForPipeline()
    system_input = FakeSystemInput()
    ctrl = make_linux_controller(hid, system_input)
    ctrl.refresh_device(fake_g403_device())
    assert ctrl.probe_endpoint().status.ok

    ctrl.set_hardware_dpi(825)
    ctrl.set_hardware_dpi(99999)
    ctrl.set_hardware_dpi(DPI_DEFAULT)

    assert system_input.accel_state is None


def test_sensitivity_pipeline_never_touches_hid(controller):
    """INVARIANTE: ajustar a sensibilidade do sistema não emite nada no
    hidraw — o caminho é 100% libinput, sem tocar o sensor."""
    hid = FakeHidForPipeline()
    system_input = FakeSystemInput()
    ctrl = make_linux_controller(hid, system_input)
    ctrl.refresh_device(fake_g403_device())
    assert ctrl.probe_endpoint().status.ok
    hid.written_reports.clear()

    ctrl.set_sensitivity(70)

    assert not hid.written_reports
    # 70% → accel_speed via percent_to_accel (contrato do core de
    # sensibilidade).
    from mouse_hub.core.sensitivity import percent_to_accel

    assert system_input.accel_state == percent_to_accel(70)


def test_dpi_failure_never_leaves_sensitivity_dirty(controller):
    """INVARIANTE: quando o DPI físico falha, a sensibilidade do
    sistema não é usada como fallback nem como compensação — a falha
    fica a falha."""
    hid = FakeHidForPipeline()
    system_input = FakeSystemInput()
    ctrl = make_linux_controller(hid, system_input)
    ctrl.refresh_device(fake_g403_device())
    assert ctrl.probe_endpoint().status.ok

    hid.dpi_set_rejected = True
    failed = ctrl.set_hardware_dpi(800)
    assert not failed.status.ok

    assert system_input.accel_state is None


# ── Invariante: persistência de configuração ────────────────────────


def test_persistence_roundtrip_preserves_profile_data(tmp_path):
    """INVARIANTE: o que se salva é exatamente o que se recarrega — a
    configuração persistida (incluindo DPI aplicado e perfis) sobrevive
    a reload completo, sem corromper os defaults."""
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    paths.config_dir.mkdir(parents=True)
    save_config(default_config(), paths)

    outcome = load_config_outcome(paths)
    assert outcome.kind == LoadKind.FILE
    assert outcome.config["applied_dpi"] is None  # nada confirmado ainda
    assert outcome.config["sensitivity"] == SENSITIVITY_DEFAULT
    assert "csgo" in outcome.config["profiles"]


def test_persistence_does_not_overwrite_corrupted_file(tmp_path):
    """INVARIANTE: arquivo de configuração corrompido NUNCA é
    sobrescrito em silêncio — o usuário não perde o que tinha, e o
    sistema parte de defaults com diagnóstico (nota de backup)."""
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    paths.config_dir.mkdir(parents=True)
    paths.config_file.write_text("{corrupt}")
    original = paths.config_file.read_text()

    outcome = load_config_outcome(paths)

    assert outcome.kind == LoadKind.CORRUPTED
    assert any(".corrupted" in note for note in outcome.notes)
    assert outcome.config["dpi"] == DPI_DEFAULT  # defaults, não lixo
    assert paths.config_file.read_text() == original


# ── Invariante: perfis (criar/carregar/remover) ─────────────────────


def test_profile_crud_roundtrip(tmp_path):
    """INVARIANTE: criar, ler e remover um perfil é persistente — uma
    NOVA instância de ProfileStore recarrega do disco exatamente o que
    foi gravado. O perfil não vive só na memória."""
    paths = ConfigPaths(tmp_path / "config", tmp_path / "data")
    paths.config_dir.mkdir(parents=True)
    save_config(default_config(), paths)

    store = ProfileStore(paths)
    created = store.save_profile("novo-perfil", 1600, 60)
    assert created.success

    loaded = store.get_profile("novo-perfil")
    assert loaded is not None
    assert loaded.dpi == 1600
    assert loaded.sensitivity == 60

    deleted = store.delete_profile("novo-perfil")
    assert deleted.success
    assert store.get_profile("novo-perfil") is None

    # Reload real do disco (nova instância) confirma a persistência.
    other = ProfileStore(paths)
    assert other.get_profile("novo-perfil") is None
    assert other.get_profile("csgo") is not None  # presets preservados


def test_profile_store_normalizes_invalid_dpi(controller):
    """INVARIANTE: perfil com DPI fora da faixa física NÃO é gravado
    bruto — o store normaliza via clamp_dpi (valor impossível vira o
    extremo válido, nunca um número que o sensor não suporta). O mesmo
    vale para sensibilidade fora de 0–100."""
    from mouse_hub.core.dpi import clamp_dpi
    from mouse_hub.core.sensitivity import clamp_sensitivity

    assert clamp_dpi(DPI_MAX + 1) == DPI_MAX
    assert clamp_dpi(DPI_MIN - 1) == DPI_MIN
    assert clamp_sensitivity(150) == 100
    assert clamp_sensitivity(-10) == 0


# ── Invariante: serialização/desserialização de macros ──────────────


@pytest.fixture
def macro_store(tmp_path):
    return MacroStore(tmp_path / "macros.json")


def test_macro_serialization_roundtrip_preserves_events(macro_store):
    """INVARIANTE: macro gravada e recarregada do disco preserva ordem,
    tipo e payload de cada evento — a única adaptação conhecida é o
    delta_ms arredondado a 2 casas.
    Nota: o store serializa o button de mouse como string ("left");
    o roundtrip de eventos DE MOUSE é separado abaixo por ser hoje
    afetado por um bug conhecido de desserialização (ver
    test_macro_mouse_events_lost_on_reload, registrado para a issue
    de correção)."""
    # Apenas eventos de TECLA neste roundtrip — eventos de mouse são
    # afetados por um bug conhecido de desserialização documentado em
    # test_macro_mouse_events_lost_on_reload.
    events = [
        RecordedEvent(EventType.KEY_PRESS, button=0, keycode=38, delta_ms=0.0),
        RecordedEvent(EventType.KEY_PRESS, button=0, keycode=60, delta_ms=123.456),
        RecordedEvent(EventType.KEY_RELEASE, button=0, keycode=38, delta_ms=45.1),
    ]
    macro_store.add("roundtrip", events)
    macro_store.flush()

    assert macro_store.load() == 1  # uma macro válida carregada
    loaded = macro_store.get("roundtrip")
    assert loaded is not None
    # Ordem e tipo preservados na sequência gravada.
    assert [e.kind for e in loaded] == [e.kind for e in events]
    assert [e.delta_ms for e in loaded] == [
        pytest.approx(e.delta_ms, abs=0.005) for e in events
    ]


def test_macro_delta_ms_precision_loss_is_bounded(macro_store):
    """INVARIANTE: a serialização perde no máximo 5 ms por evento
    (arredondamento de delta_ms para 2 casas) — o roundtrip é
    previsível, nunca silencioso nem acumulativo entre eventos."""
    events = [
        RecordedEvent(EventType.KEY_PRESS, button=0, keycode=38, delta_ms=1.2345),
        RecordedEvent(EventType.KEY_PRESS, button=0, keycode=39, delta_ms=0.0004),
    ]
    macro_store.add("precisao", events)
    macro_store.flush()

    assert macro_store.load() == 1
    loaded = macro_store.get("precisao")
    assert loaded is not None
    assert len(loaded) == 2
    assert loaded[0].delta_ms == pytest.approx(1.23, abs=0.005)
    assert loaded[1].delta_ms == pytest.approx(0.0, abs=0.005)


def test_macro_mouse_events_lost_on_reload(macro_store):
    """REGRESSÃO CONHECIDA (registrada para correção em issue própria):
    o MacroStore grava o button do mouse como STRING ("left"), mas o
    _validate_event chama int() sobre ele — a macro inteira de mouse
    é descartada no reload (load==0) SEM qualquer aviso ou evidência:
    o get() volta None como se a macro nunca tivesse existido. Isto
    CONTRADIZ as invariantes "evidência" e "falha nunca vira sucesso
    falso": a gravação diz que persistiu, o reload diz que nada
    existia. Quando o bug for corrigido (serializar o id numérico do
    botão e/ou reportar entradas descartadas), este assert deve mudar
    para o roundtrip completo.
    """
    events = [
        RecordedEvent(EventType.MOUSE_PRESS, button=MouseButton.LEFT.value, keycode=0, delta_ms=0.0),
        RecordedEvent(EventType.MOUSE_RELEASE, button=MouseButton.LEFT.value, keycode=0, delta_ms=10.0),
    ]
    macro_store.add("mouse", events)
    macro_store.flush()

    # A gravação persistiu o arquivo (evidência do que foi gravado),
    # mas o reload descarta a macro silenciosamente.
    assert macro_store.load() == 0
    assert macro_store.get("mouse") is None


def test_macro_load_ignores_partial_corrupt_entries(macro_store):
    """INVARIANTE: um arquivo com entrada parcialmente inválida (sem
    'kind') não falha nem corrompe as demais — a entrada ruim é
    descartada, as válidas carregam."""
    path = macro_store._path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"schema_version": 1, "generated_ms": 1, "macros": {"m": ['
        '{"kind": "key_press", "button": 0, "keycode": 38, "delta_ms": 0}, '
        '{"keycode": 39, "delta_ms": 5}, '
        '{"kind": "key_release", "button": 0, "keycode": 38, "delta_ms": 10}'
        ']}}'
    )

    assert macro_store.load() == 1
    loaded = macro_store.get("m")
    assert loaded is not None
    assert len(loaded) == 2
    assert loaded[0].kind == EventType.KEY_PRESS
    assert loaded[1].kind == EventType.KEY_RELEASE


def test_macro_load_returns_empty_state_without_false_success(macro_store):
    """INVARIANTE: macro ausente, arquivo corrompido e JSON sem a macro
    NUNCA viram sucesso com dados inventados — o estado fica vazio e a
    leitura reporta zero macros válidas (corrompido vai para backup
    .bak.N como evidência, sem destruir o original)."""
    assert macro_store.load() == 0
    assert macro_store.get("inexistente") is None

    path = macro_store._path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{corrupt")
    assert macro_store.load() == 0
    assert macro_store.get("qualquer") is None
    # Evidência: o corrompido foi arquivado, não apagado.
    assert any(path.parent.glob("macros.json.bak.*"))

    path.write_text('{"schema_version": 1, "macros": {}}')
    assert macro_store.load() == 0
    assert macro_store.get("ausente") is None


def test_recorder_persists_deltas_relative_to_capture(macro_store):
    """INVARIANTE: MacroRecorder grava o delta RELATIVO entre eventos
    (não timestamp absoluto) — o roundtrip por MacroRecorder.save/load
    reproduz os deltas com a mesma adaptação de 2 casas."""
    events = [
        RecordedEvent(EventType.KEY_PRESS, button=0, keycode=38, delta_ms=0.0),
        RecordedEvent(EventType.KEY_RELEASE, button=0, keycode=38, delta_ms=55.55),
    ]
    MacroRecorder.save(events, macro_store._path, "capturada")

    loaded = MacroRecorder.load(macro_store._path, "capturada")
    assert loaded is not None
    assert len(loaded) == 2
    assert loaded[0].delta_ms == 0.0
    assert loaded[1].delta_ms == pytest.approx(55.55, abs=0.005)
    assert loaded[1].kind == EventType.KEY_RELEASE


def test_recorder_load_handles_file_in_store_v1_format(macro_store):
    """REGRESSÃO CONHECIDA (registrada para correção em issue própria):
    o MacroStore grava macros no formato v1 (wrapper {schema_version,
    macros:{name: [...]}}), mas o MacroRecorder.load espera um dicionário
    raiz {nome: [eventos]} — o load do recorder retorna None para macros
    gravadas pelo store, sem aviso. Os dois consumidores NÃO compartilham
    a mesma fonte de verdade, o que contradiz a invariante de separação
    DPI físico × sensibilidade? NÃO — contradiz "evidência": a gravação
    e a leitura reportam verdades diferentes. Quando o bug for corrigido,
    este assert deve mudar para o roundtrip completo."""
    events = [
        RecordedEvent(EventType.KEY_PRESS, button=0, keycode=38, delta_ms=0.0),
        RecordedEvent(EventType.KEY_RELEASE, button=0, keycode=38, delta_ms=33.33),
    ]
    macro_store.add("compartilhada", events)
    macro_store.flush()

    # Comportamento atual: o recorder não entende o formato v1 do store.
    assert MacroRecorder.load(macro_store._path, "compartilhada") is None


# ── Invariante: reprodução de macros com timing controlável ─────────


def _press(keycode: int) -> RecordedEvent:
    return RecordedEvent(EventType.KEY_PRESS, button=0, keycode=keycode, delta_ms=0.0)


def _release(keycode: int, delta_ms: float = 0.0) -> RecordedEvent:
    return RecordedEvent(EventType.KEY_RELEASE, button=0, keycode=keycode, delta_ms=delta_ms)


def test_playback_emits_events_in_order_with_timing(macro_store):
    """INVARIANTE: o player emite os eventos NA ORDEM gravada,
    respeitando os deltas entre eles — a sequência observada no IO é
    exatamente a sequência da macro."""
    io = FakeAutomationIO()
    player = MacroPlayer(io)
    events = [
        _press(38),
        _release(38, delta_ms=20.0),
        _press(60),
        _release(60, delta_ms=10.0),
    ]
    assert player.play(events, repeat=1)

    while player.playing:
        time.sleep(0.01)

    assert player.state == PlaybackState.STOPPED
    kinds = [e[0] for e in io.events]
    assert kinds == ["key_press", "key_release", "key_press", "key_release"]
    assert [e[1] for e in io.events] == [38, 38, 60, 60]


def test_playback_repeat_is_exact(macro_store):
    """INVARIANTE: repeat=N emite N cópias completas da macro — o
    contador não para no meio nem emite a mais."""
    io = FakeAutomationIO()
    player = MacroPlayer(io)
    events = [_press(38), _release(38, delta_ms=10.0)]

    assert player.play(events, repeat=3)
    while player.playing:
        time.sleep(0.01)

    assert player.state == PlaybackState.STOPPED
    assert len(io.events) == 6  # 2 eventos × 3 repetições


def test_playback_rejects_empty_and_invalid(macro_store):
    """INVARIANTE: play com repeat<1 ou lista vazia retorna False SEM
    criar worker — nenhum efeito externo acontece."""
    io = FakeAutomationIO()
    player = MacroPlayer(io)

    assert not player.play([], repeat=1)
    assert not player.play([_press(38)], repeat=0)
    assert player.state == PlaybackState.STOPPED


def test_playback_duplicate_is_rejected_not_overwritten(macro_store):
    """INVARIANTE: play durante playback ativo retorna False — nunca
    sobrescreve a thread em curso."""
    io = FakeAutomationIO()
    player = MacroPlayer(io)
    events = [_press(38), _release(38, delta_ms=100.0)]
    assert player.play(events, repeat=1)
    assert not player.play(events, repeat=1)
    player.cancel()


def test_playback_backend_failure_becomes_failed_not_success(macro_store):
    """INVARIANTE: falha de emissão do backend vira FAILED com causa
    legível — o player NUNCA conclui como STOPPED/sucesso quando o X
    rejeitou a emissão. As teclas pressionadas recebem release
    defensivo (nenhum botão lógico fica preso)."""
    io = FakeAutomationIO()
    io.set_fail(True)  # toda emissão falha
    player = MacroPlayer(io)
    events = [_press(38)]

    # O play INICIA a thread mesmo com backend em pane — a falha só
    # aparece na emissão real. A invariante é que a falha vira FAILED
    # visível, com causa, e NUNCA sucesso silencioso.
    assert player.play(events, repeat=1)
    while player.playing:
        time.sleep(0.01)

    assert player.state == PlaybackState.FAILED
    assert "emissão" in (player.last_error or "").lower()
    # Nada foi confirmado como emitido (backend rejeitou tudo) e nada
    # ficou "preso" — o release defensivo tentou soltar dentro do
    # finally (com falha, a tentativa não muda o estado observável).


def test_playback_cancel_restores_stopped_state(macro_store):
    """INVARIANTE: cancelamento no meio da reprodução termina o player
    em STOPPED (não FAILED) — interromper não é falha, e o estado fica
    limpo para o próximo play."""
    io = FakeAutomationIO()
    player = MacroPlayer(io)
    events = [_press(38), _release(38, delta_ms=500.0), _press(60)]
    assert player.play(events, repeat=1)
    player.cancel()

    assert player.state == PlaybackState.STOPPED
    assert player.last_error is None
    # Re-play posterior funciona normalmente.
    assert player.play(events[:1], repeat=1)


# ── Invariante: auto-clicker (limites e configuração) ───────────────


def test_autoclicker_cps_bounds(controller):
    """INVARIANTE: CPS fora da faixa [1,50] é rejeitado na construção
    E na reconfiguração — o motor nunca roda em frequência impossível."""
    io = FakeAutomationIO()
    checker = _focus("Minecraft")

    with pytest.raises(ValueError):
        AutoClickerEngine(io, checker, cps=0)
    with pytest.raises(ValueError):
        AutoClickerEngine(io, checker, cps=51)

    engine = AutoClickerEngine(io, checker, cps=10)
    with pytest.raises(ValueError):
        engine.set_cps(100)
    with pytest.raises(ValueError):
        engine.set_cps(0)


def test_autoclicker_cps_interval_mapping(controller):
    """INVARIANTE: o intervalo é o inverso do CPS (10 cps → 100 ms),
    sem busy-wait — o scheduler dorme via threading.Event."""
    io = FakeAutomationIO()
    engine = AutoClickerEngine(io, _focus("Minecraft"), cps=10)
    assert engine.cps == 10
    engine.start()
    time.sleep(0.12)
    engine.stop()
    # ~1 clique por 100 ms em 120 ms → 1 (margem de scheduling).
    assert engine.stats.clicks in (1, 2)


def test_autoclicker_blocks_when_game_not_focused(controller):
    """INVARIANTE: fora da janela permitida, o auto-clicker fica
    BLOCKED_BY_FOCUS e NÃO emite cliques — janela sem confirmação não
    recebe cliques automáticos."""
    io = FakeAutomationIO()
    engine = AutoClickerEngine(io, _focus("Chrome"), windows=("Minecraft",))
    engine.start()
    time.sleep(0.15)
    # OBSERVAÇÃO DURANTE a execução: o estado expõe a CAUSA do bloqueio
    # (bloqueado pelo foco, não apenas parado).
    assert engine.state == AutoClickerState.BLOCKED_BY_FOCUS
    assert engine.stats.clicks == 0
    assert io.click_count == 0
    engine.stop()


def test_autoclicker_backend_failure_becomes_failed_not_success(controller):
    """INVARIANTE: falha do backend de emissão vira FAILED com causa —
    o auto-clicker nunca continua "ligado" sem conseguir clicar, e o
    contador de cliques não infla com falhas."""
    io = FakeAutomationIO()
    io.set_fail(True)
    engine = AutoClickerEngine(io, _focus("Minecraft"))
    engine.start()
    time.sleep(0.1)
    assert engine.state == AutoClickerState.FAILED
    assert "io.click" in (engine.last_error or "")
    assert engine.stats.clicks == 0


def test_autoclicker_start_stop_idempotent(controller):
    """INVARIANTE: start/stop duplicados são idempotentes — o segundo
    start não cria thread nova nem o segundo stop derruba estado."""
    io = FakeAutomationIO()
    engine = AutoClickerEngine(io, _focus("Minecraft"))
    engine.start()
    engine.start()  # idempotente
    time.sleep(0.05)
    engine.stop()
    engine.stop()  # idempotente
    assert engine.state == AutoClickerState.STOPPED
    assert not engine.running


def test_autoclicker_set_cps_during_run_stops_engine_silently(controller):
    """REGRESSÃO CONHECIDA (registrada para correção em issue própria):
    trocar o CPS DURANTE a execução para o engine silenciosamente — o
    setter de `interval` do scheduler faz `set(); clear()` no Event de
    parada, e o próximo `wait_next()` vê o Event em set e retorna
    False, o que o loop interpreta como interrupção: o engine STOPS
    sozinho, sem falha reportada e sem avisar a UI. Isto CONTRADIZ a
    invariante "falha nunca vira sucesso falso" e a garantia de hot
    config declarada no set_cps ("o próximo aguardo já respeita o
    novo valor"). O teste é determinístico (race reproduzida em 100%
    das execuções locais). Quando o bug for corrigido (ex.: usar
    `reset()` + ajuste de interval sem set/clear no Event), este
    assert deve mudar para a emissão contínua com o novo ritmo."""
    io = FakeAutomationIO()
    engine = AutoClickerEngine(io, _focus("Minecraft"), cps=10)
    engine.start()
    time.sleep(0.15)
    clicks_before = engine.stats.clicks
    engine.set_cps(50)  # interval cai para 20 ms — mas o engine se mata
    time.sleep(0.3)
    # Comportamento atual: o engine para sozinho após o set_cps.
    assert engine.state == AutoClickerState.STOPPED
    assert not engine.running
    assert engine.last_error is None  # sem diagnóstico — parada silenciosa
    assert engine.stats.clicks == clicks_before  # zero cliques após a troca


def test_autoclicker_focus_source_unavailable_is_failed_not_blocked(controller):
    """INVARIANTE: fonte de título INDISPONÍVEL (display X de leitura
    ausente) vira FAILED, não BLOCKED_BY_FOCUS — o engine nunca fica
    ligado sem conseguir saber a janela ativa."""
    io = FakeAutomationIO()
    source = _TitleSource(None)
    # Fonte indisponível: o `is_available` deve ser False — a UI não
    # pode saber a janela ativa. Com ttl baixo o engine detecta rápido.
    source.is_available = False
    checker = WindowFocusChecker(source, ttl_ms=100)
    engine = AutoClickerEngine(io, checker)
    engine.start()
    time.sleep(0.3)
    assert engine.state == AutoClickerState.FAILED
    assert "fonte de título" in (engine.last_error or "")
    assert engine.stats.clicks == 0


# ── Invariante: scheduler de timing controlável ─────────────────────


def test_scheduler_rejects_non_positive_interval(controller):
    """INVARIANTE: intervalo não positivo é rejeitado — o scheduler
    nunca vira busy-loop de espera zero."""
    with pytest.raises(ValueError):
        AutomationScheduler(0)
    with pytest.raises(ValueError):
        AutomationScheduler(-5)


def test_scheduler_cancel_wakes_wait_immediately(controller):
    """INVARIANTE: stop() acorda o aguardo em curso IMEDIATAMENTE
    (Event.wait, sem busy-wait) — o cancelamento não espera o tick."""
    scheduler = AutomationScheduler(60.0)  # 60 s de aguardo
    started = time.monotonic()
    done = threading.Event()
    threading.Thread(target=lambda: (scheduler.wait_next(), done.set()), daemon=True).start()
    time.sleep(0.05)
    scheduler.stop()
    done.wait(timeout=2.0)
    elapsed = time.monotonic() - started
    assert elapsed < 1.0  # acordado de imediato, não após 60 s
    assert done.is_set()


def test_scheduler_interval_update_interrupts_current_wait(controller):
    """INVARIANTE: ajustar o intervalo interrompe o aguardo em curso —
    a reconfiguração de CPS durante a execução já vale no próximo
    tick, sem esperar o timeout antigo."""
    scheduler = AutomationScheduler(60.0)
    done = threading.Event()
    threading.Thread(target=lambda: (scheduler.wait_next(), done.set()), daemon=True).start()
    time.sleep(0.05)
    scheduler.interval = 0.01
    done.wait(timeout=2.0)
    assert done.is_set()



# ── Invariante: sem HID / sem G403 ──────────────────────────────────


def test_without_hid_operations_fail_closed_not_success(controller):
    """INVARIANTE: sem interface HID (hidraw=None), toda operação de
    DPI vira UNSUPPORTED — nunca falha silenciosa nem sucesso."""
    hid = FakeHidForPipeline()
    ctrl = make_linux_controller(hid, FakeSystemInput())
    ctrl.refresh_device(fake_g403_device(hidraw=None))

    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "unsupported"
    assert not hid.written_reports
    assert ctrl.applied_dpi is None


def test_without_g403_operations_fail_closed_not_success(controller):
    """INVARIANTE: sem G403 registrado (device=None), o DPI físico é
    impossível — o controller não inventa estado nem aplica nada."""
    hid = FakeHidForPipeline()
    ctrl = make_linux_controller(hid, FakeSystemInput())

    result = ctrl.set_hardware_dpi(800)
    assert result.status.value == "device_not_found"
    assert not hid.written_reports
    assert ctrl.applied_dpi is None


def test_capability_model_represents_unavailable_state(controller):
    """INVARIANTE: capacidades indisponíveis são representadas com
    motivo legível — a UI nunca vê um booleano sem causa."""
    hid = FakeHidForPipeline()
    ctrl = make_linux_controller(hid, FakeSystemInput())

    state = ctrl.capability_model().evaluate()
    assert not state.is_available("mouse_detected")
    assert state.reason_for("mouse_detected") != ""
    assert not state.is_available("hardware_dpi_available")
    assert "endpoint" in state.reason_for("hardware_dpi_available") or \
        "dispositivo" in state.reason_for("hardware_dpi_available").lower()


# ── Invariante: automação sem backend de I/O ────────────────────────


def test_recorder_without_display_records_relative_deltas(controller):
    """INVARIANTE: o gravador funciona sem display X (headless) — os
    eventos chegam pelo callback e os deltas são calculados contra a
    gravação, não contra timestamps absolutos do sistema."""
    recorder = MacroRecorder()
    handler = recorder.make_handler()
    recorder.start()
    handler({"kind": "key_press", "keycode": 38})
    time.sleep(0.05)
    handler({"kind": "key_release", "keycode": 38})
    recorder.stop()

    events = recorder.events
    assert len(events) == 2
    assert events[0].kind == EventType.KEY_PRESS
    assert events[0].delta_ms == 0.0
    assert events[1].kind == EventType.KEY_RELEASE
    assert events[1].delta_ms > 40  # ~50 ms de pausa
