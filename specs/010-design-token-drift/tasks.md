# Tasks: Design system sem drift de tokens (issue #96)

**Input**: Design documents from `/specs/010-design-token-drift/`

**Status**: Convergido localmente; aguardando CI do PR

## Phase 1 — Spec e teste (TDD)

- [x] T001 Criar spec, plano, tabela de princípios e checklist.
- [x] T002 Escrever `tests/test_issue96_design_tokens.py` para cores e
  medidas excepcionais.
- [x] T003 Executar o teste antes do fix: RED confirmado nos três invariantes.

## Phase 2 — User Story 1: tokens centralizados

- [x] T004 [US1] Adicionar tokens nomeados `RADIUS.card`, `SPACE.card` e
  `SPACE.empty_state`, preservando 16/20/30 px.
- [x] T005 [US1] Migrar os hex duplicados para `COLORS[...]`.
- [x] T006 [US1] Migrar raios/paddings excepcionais para os tokens, inclusive
  stylesheets com formatação `%`.
- [x] T007 [US1] Executar teste dedicado e confirmar GREEN.

## Phase 3 — Artefatos públicos

- [x] T008 [US1] Regenerar screenshots e revisar diffs visuais.

## Phase 4 — Convergência e entrega

- [x] T009 Rodar suíte completa, smoke UI, compileall e diff-check.
- [ ] T010 Atualizar checklist/evidências e abrir PR vinculada à #96.

## Evidence

- RED: 3 invariantes falharam antes da implementação (hex e medidas).
- GREEN: `tests/test_issue96_design_tokens.py` — 3 passed.
- Regressões: `tests/test_issue66_ui_craft.py` + `tests/test_issue96_design_tokens.py` — 11 passed.
- Suíte completa: exit 0, 100% dos testes passaram.
- Captura de screenshots: concluída, sem diff visual não intencional.

## Dependencies & Execution Order

- T002 → T003 → T004/T005/T006 → T007 → T008 → T009 → T010.
