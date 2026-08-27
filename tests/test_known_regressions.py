"""Testes de REGRESSÕES CONHECIDAS do Mouse Hub.

ESTES TESTES NÃO SÃO INVARIANTES PERMANENTES: reproduzem bugs reais da
implementação atual (documentados para correção em issues próprias —
#16 MacroStore reload, #17 MacroRecorder.load v1, #18 set_cps race,
GAP applied_dpi restore no startup). Quando cada bug for corrigido, o
teste DEVE ser convertido para o comportamento esperado descrito na
própria docstring (o CI passa a exigir o roundtrip/restore/hot-config
completos — é isso que garante que a correção permaneça corrigida).
Bugs corrigidos na PR #20 (asserts convertidos para o comportamento
esperado, mantendo o teste como reguarda de regressão):
- #16 → test_macro_mouse_events_roundtrip_after_fix
- #17 → test_recorder_load_reads_store_v1_after_fix
- #18 → test_autoclicker_set_cps_during_run_keeps_running_after_fix
Correção pendente (bug ainda existente):
- GAP applied_dpi restore no startup → test_applied_dpi_lost_on_controller_reload

Organização:
- test_macro_mouse_events_roundtrip_after_fix (bug #16 corrigido — MacroStore)
- test_recorder_load_reads_store_v1_after_fix (bug #17 corrigido — Recorder)
- test_applied_dpi_lost_on_controller_reload (GAP pendente — restore no startup)
- test_autoclicker_set_cps_during_run_keeps_running_after_fix (bug #18 corrigido)

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


def test_macro_mouse_events_roundtrip_after_fix(macro_store):
    """INVARIANTE (correção #16, anteriormente regressão conhecida):
    eventos de mouse fazem roundtrip completo pelo MacroStore — o flush
    grava o button como ID NUMÉRICO e o reload o aceita nos dois
    formatos (numérico e textual legado "left"), com as entradas
    descartadas visíveis em `discarded_entries` em vez de perda
    silenciosa. Este era o teste
    `test_macro_mouse_events_lost_on_reload` (reload descartava a macro
    inteira), convertido para o comportamento esperado pós-correção."""
    events = [
        RecordedEvent(EventType.MOUSE_PRESS, button=MouseButton.LEFT.value, keycode=0, delta_ms=0.0),
        RecordedEvent(EventType.MOUSE_RELEASE, button=MouseButton.LEFT.value, keycode=0, delta_ms=10.0),
    ]
    macro_store.add("mouse", events)
    macro_store.flush()

    # Comportamento esperado pós-correção (#16): roundtrip completo,
    # sem descartes — o roundtrip vazio era o bug.
    assert macro_store.load() == 1
    loaded = macro_store.get("mouse")
    assert loaded is not None
    assert len(loaded) == 2
    assert loaded[0].kind == EventType.MOUSE_PRESS and loaded[0].button == 1
    assert macro_store.discarded_entries.get("mouse", 0) == 0

def test_store_flush_reload_preserves_recorded_macro(macro_store):
    """INVARIANTE (contrato #17 sob persistência única, issue #2):
    gravação e reprodução compartilham o MESMO contrato de armazenamento
    — uma instância do MacroStore relê do disco exatamente o que outra
    gravou (o MacroRecorder.save/load duplicado foi removido; o store
    transacional é a única implementação)."""
    events = [
        RecordedEvent(EventType.KEY_PRESS, button=0, keycode=38, delta_ms=0.0),
        RecordedEvent(EventType.KEY_RELEASE, button=0, keycode=38, delta_ms=33.33),
    ]
    macro_store.add("compartilhada", events)
    macro_store.flush()

    # Nova instância (simula reinício do app): lê o que a anterior gravou.
    reread = MacroStore(macro_store._path)
    assert reread.load() == 1
    loaded = reread.get("compartilhada")
    assert loaded is not None
    assert len(loaded) == 2
    assert loaded[0].kind == EventType.KEY_PRESS
    assert loaded[1].delta_ms == pytest.approx(33.33, abs=0.005)

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
    engine.set_cps(50)  # interval cai para 20 ms — o engine segue vivo
    time.sleep(0.4)
    # Comportamento esperado pós-correção (#18): o engine continua
    # RUNNING após o set_cps e os cliques continuam somando — parar
    # sozinho era o bug (race do Event de parada no setter de interval).
    assert engine.state == AutoClickerState.RUNNING
    assert engine.running
    assert engine.stats.clicks > clicks_before
    extra = engine.stats.clicks - clicks_before
    assert extra >= 10  # ~20 cliques esperados a 50 CPS em 0.4 s
    engine.stop()
    assert engine.state == AutoClickerState.STOPPED
