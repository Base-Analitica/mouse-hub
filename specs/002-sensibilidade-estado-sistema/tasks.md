# Tasks: Sensibilidade como estado do sistema (issue #102)

**Input**: `specs/002-sensibilidade-estado-sistema/spec.md` + `plan.md`

## Phase 1: Setup

- [x] T001 Branch `fix/sensitivity-system-state-hero` a partir da `main`
      atualizada; spec/plan/tasks commitados na PR.

## Phase 2: User Story 1 — Hero = estado do sistema (P1) 🎯 MVP

**Goal**: Hero exibe a sensibilidade lida do sistema; zero menção a
"leitura do hardware" na página.

**Independent Test**: pytest offscreen em `tests/test_issue102_sens_state.py`.

### Tests for User Story 1 ⚠️ (escrever primeiro, ver FALHAR)

- [x] T002 [US1] `tests/test_issue102_sens_state.py`: (a) com
      `accel_state=0.5`, hero exibe `75%`; (b) com xinput indisponível,
      hero exibe `—` + `valor atual do sistema indisponível`; (c) nenhum
      QLabel da página contém "aguardando leitura do hardware" (falhou
      antes da mudança: exibia `—`/`aguardando leitura do hardware…`).

### Implementation for User Story 1

- [x] T003 [US1] Core: `MouseController.__init__` executa
      `self._applied_sensitivity = self.get_sensitivity()` (leitura real
      do sistema no startup; falha → None).
- [x] T004 [US1] UI: constantes `_SENS_STATE_TEXT` ("VELOCIDADE DO
      PONTEIRO NO SISTEMA") e `_SENS_UNKNOWN_TEXT` ("valor atual do
      sistema indisponível"); `SensitivityPage` usa as constantes em
      build/preview/commit/showEvent.

## Phase 3: User Story 2 — Sem regressão de domínios (P1)

**Goal**: Separ DPI (físico, unknown até ACK) de sensibilidade (sistema,
lida); suíte existente verde.

### Tests & fixes for User Story 2

- [x] T005 [US2] Atualizar `test_applied_values_are_none_before_confirmation`
      e `test_sensitivity_page_renders_unknown`
      (`tests/test_issue3_ui_integration.py`): DPI continua unknown;
      sensibilidade exibe o valor lido do sistema (50% no fake default).
- [x] T006 [US2] Atualizar `test_dashboard_renders_unknown` (card de
      sensibilidade exibe o valor lido do sistema).
- [x] T007 [US2] Atualizar
      `test_controller_without_device_reports_no_dpi`
      (`tests/test_issue3_ui_core.py`): sensibilidade lida do sistema
      mesmo sem device (o device é do mouse, não do ponteiro).
- [x] T008 [US2] `test_partial_state_dpi_ok_sens_fail`
      (`tests/test_issue6_profiles_polling.py`): fake com
      `verify_after_write=False` para que a leitura pós-falha seja
      honestamente None (falha de set → unknown, não default).

## Phase 4: Screenshots & Finalização

- [x] T009 Regenerar `2_sens.png`, `small_sens.png`, `preview.png`.
- [x] T010 Suíte completa (`pytest tests/`) + compileall verdes.
