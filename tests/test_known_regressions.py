"""Testes de REGRESSÕES CONHECIDAS do Mouse Hub.

ESTES TESTES NÃO SÃO INVARIANTES PERMANENTES: reproduzem bugs reais da
implementação atual (documentados para correção em issues próprias —
#16 MacroStore reload, #17 MacroRecorder.load v1, #18 set_cps race,
GAP applied_dpi restore no startup). Quando cada bug for corrigido, o
assert correspondente DEVE mudar para o comportamento esperado descrito
na própria docstring — a docstring de cada teste descreve explicitamente
o comportamento esperado pós-correção.

NENHUM destes testes deve ser removido enquanto o bug existir: eles são
a única evidência determinística de que a correção aconteceu (o CI passa
a exigir o roundtrip/restore/hot-config completos).

Organização:
- test_macro_mouse_events_lost_on_reload   (bug #16 — MacroStore)
- test_recorder_load_handles_file_in_store_v1_format (bug #17 — Recorder)
- test_applied_dpi_lost_on_controller_reload (GAP — restore no startup)
- test_autoclicker_set_cps_during_run_stops_engine_silently (bug #18)

Determinística: sem hardware real, sem Display X, sem hidraw, sem
subprocesso — só fakes de tests/fakes.py.
"""

from __future__ import annotations

import time
from typing import Optional

import pytest

from mouse_hub.core.automation.autoclicker import (
    AutoClickerEngine,
    AutoClickerState,
)
from mouse_hub.core.automation.focus import WindowFocusChecker
from mouse_hub.core.automation.macros import MacroRecorder
from mouse_hub.core.automation.store import MacroStore
from mouse_hub.core.automation.types import EventType, MouseButton, RecordedEvent
from tests.fakes import (
    FakeAutomationIO,
    FakeSystemInput,
    fake_g403_device,
)
from tests.test_invariants import (
    FakeHidForPipeline,
    _TitleSource,
    _focus,
    controller,
)
from mouse_hub.core.config import (
    ConfigPaths,
    default_config,
    save_config,
)
from mouse_hub.core.mouse_controller import make_linux_controller


@pytest.fixture
def macro_store(tmp_path):
    return MacroStore(tmp_path / "macros.json")


def test_macro_mouse_events_lost_on_reload(macro_store):
    """REGRESSÃO CONHECIDA (registrada para correção em issue própria):
    o MacroStore grava o button do mouse como STRING ("left"), mas o
    _validate_event chama int() sobre ele — a macro inteira de mouse
    é descartada no reload (load==0) SEM qualquer aviso ou evidência:
    o get() volta None como se a macro nunca tivesse existido. Isto
    CONTRADIZ as invariantes 5 (falha nunca vira sucesso falso) e 7
    (persistência fail-closed com evidência): a gravação diz que
    persistiu, o reload diz que nada existia. Quando o bug for
    corrigido (serializar o id numérico do botão e/ou reportar
    entradas descartadas), este assert deve mudar para o roundtrip
    completo.
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

def test_recorder_load_handles_file_in_store_v1_format(macro_store):
    """REGRESSÃO CONHECIDA (registrada para correção em issue própria):
    o MacroStore grava macros no formato v1 (wrapper {schema_version,
    macros:{name: [...]}}), mas o MacroRecorder.load espera um dicionário
    raiz {nome: [eventos]} — o load do recorder retorna None para macros
    gravadas pelo store, sem aviso. Os dois consumidores NÃO compartilham
    a mesma fonte de verdade, o que contradiz a invariante "evidência":
    a gravação e a leitura reportam verdades diferentes sobre o mesmo
    arquivo. Quando o bug for corrigido, este assert deve mudar para o
    roundtrip completo."""
    events = [
        RecordedEvent(EventType.KEY_PRESS, button=0, keycode=38, delta_ms=0.0),
        RecordedEvent(EventType.KEY_RELEASE, button=0, keycode=38, delta_ms=33.33),
    ]
    macro_store.add("compartilhada", events)
    macro_store.flush()

    # Comportamento atual: o recorder não entende o formato v1 do store.
    assert MacroRecorder.load(macro_store._path, "compartilhada") is None

def test_applied_dpi_lost_on_controller_reload(tmp_path):
    """REGRESSÃO CONHECIDA (registrada para correção em issue própria):
    o DPI confirmado é persistido em config.json (persisted=True após
    o ACK do hardware), mas o constructor do MouseController SEMPRE
    parte de applied_dpi=None e NENHUM caminho (refresh_device/probe)
    restaura o valor confirmado do disco — o estado aplicado fica
    órfão no reinício, contradizendo a invariante "hardware real é
    autoridade": o controller declara não saber o DPI real mesmo após
    persistir a confirmação. requested/applied/persistido devem
    convergir no reload.
    Comportamento esperado após a correção: um controller recriado
    com o mesmo config (e o mesmo dispositivo registrado) deve
    restaurar applied_dpi == 1600 a partir do disco."""
    from mouse_hub.core.dpi_persistence import DpiConfigPersister

    paths = ConfigPaths(tmp_path / "cfg", tmp_path / "data")
    paths.config_dir.mkdir(parents=True)
    save_config(default_config(), paths)

    hid = FakeHidForPipeline()
    ctrl = make_linux_controller(hid, FakeSystemInput(), paths)
    ctrl.refresh_device(fake_g403_device())
    assert ctrl.probe_endpoint().status.ok

    result = ctrl.set_hardware_dpi(1600)
    assert result.status.value == "applied"
    assert result.details["persisted"] is True
    assert ctrl.applied_dpi == 1600

    # Reload: nova instância com o mesmo config e o mesmo dispositivo.
    ctrl2 = make_linux_controller(hid, FakeSystemInput(), paths)
    ctrl2.refresh_device(fake_g403_device())
    ctrl2.probe_endpoint()

    # Comportamento atual: o controller NÃO restaura o DPI confirmado
    # do disco — applied_dpi volta a None.
    assert ctrl2.applied_dpi is None


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
