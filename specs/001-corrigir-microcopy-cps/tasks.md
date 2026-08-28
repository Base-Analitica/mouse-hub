# Tasks: Microcopy consistente do heading CPS

**Input**: Design documents from `/specs/001-corrigir-microcopy-cps/`

**Prerequisites**: plan.md (required), spec.md (required), quickstart.md

**Tests**: Incluídos conforme FR-005 da spec (regressão com teste, Princípio IV).

**Status final**: CONVERGED — 544/544 testes, CI da PR #119 verde.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Feature branch `001-corrigir-microcopy-cps` ativa e spec/plan
      commitados (spec-kit scaffolding na `chore/spec-kit-setup`)

## Phase 2: User Story 1 — Heading sem mistura de idiomas (P1) 🎯 MVP

**Goal**: Heading do controle CPS exibe `CPS (Cliques por segundo)`.

**Independent Test**: pytest offscreen `-k cps_heading`.

### Tests for User Story 1 ⚠️ (escrever primeiro, ver FALHAR)

- [x] T002 [US1] Teste `test_clicker_cps_heading_copy` em
      `tests/test_issue66_ui_craft.py`: construir página do clicker offscreen e
      assegurar que o texto do heading é exatamente `CPS (Cliques por segundo)`
      (falhou com o texto antigo, conforme esperado)

### Implementation for User Story 1

- [x] T003 [US1] Trocar literal em `app/mouse_hub_app.py` (~linha 1591):
      `"CPS (Clicks Por Segundo)"` → `"CPS (Cliques por segundo)"`

**Checkpoint**: US1 completa — heading corrigido, teste verde, comportamento
do auto-clicker inalterado (suíte existente passa).

## Phase 3: User Story 2 — Screenshots públicas atualizadas (P2)

**Goal**: Screenshots do clicker refletem o novo texto.

**Independent Test**: `python3 scripts/capture_screenshots.py` + inspeção dos PNGs.

### Implementation for User Story 2

- [x] T004 [US2] Regenerar screenshots com
      `python3 scripts/capture_screenshots.py` e commitar
      `docs/screenshots/3_clicker.png`, `small_clicker.png` e `preview.png`
      (pixel diff confirma mudança localizada só na linha do heading)

**Checkpoint**: US2 completa — material público consistente com o produto.

## Phase 4: Polish & Cross-Cutting

- [x] T005 Convergência: suíte completa **544 passed** (543 anteriores + 1
      teste novo); checkboxes da spec marcados; CI da PR #119 verde
- [x] T006 PR: atualizada na branch `chore/spec-kit-setup` (PR #119) com
      `Closes #117` no commit do fix (merge é do mantenedor)

## Dependencies & Execution Order

- T002 → T003 (teste primeiro, ver falhar, depois o fix)
- T003 → T004 (screenshots só depois do texto novo)
- T004 → T005 → T006

## Notes

- Mudança de produto: 1 linha. Teste: 1 função. Sem dependência nova.
- Commit após cada tarefa ou grupo lógico (regra do projeto).
