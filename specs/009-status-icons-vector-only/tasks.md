# Tasks: Status sem glifos dependentes de fonte (issue #84)

**Input**: Design documents from `/specs/009-status-icons-vector-only/`

**Status**: Convergido localmente; aguardando CI/PR

## Phase 1 — Spec e teste (TDD)

- [x] T001 Criar `spec.md`, `plan.md` e tabela de princípios da constituição.
- [x] T002 Escrever `tests/test_issue84_no_status_glyphs.py` para rejeitar
  `✔`/`⚠`, emoji substituto, prefixo vazio e perda de tokens de cor.
- [x] T003 Guardar a implementação WIP e executar o teste dedicado: falha
  observada por ocorrência de `✔`/`⚠` (RED confirmado).

## Phase 2 — User Story 1: status vector-only

- [x] T004 [US1] Adicionar helper local na `AutoClickerPage` para limpar o
  indicador e aplicar `ui_icons.icon("alert", ...)`; `None` deve ser fallback
  seguro sem texto decorativo.
- [x] T005 [US1] Remover os prefixos `✔`/`⚠` das mensagens e badges de
  Auto-Clicker, Macros, Perfis e Configurações, preservando texto e cores.
- [x] T006 [US1] Acrescentar teste offscreen do estado de erro, incluindo o
  caminho com ícone vetorial e o fallback quando o subset não carrega.
- [x] T007 [US1] Executar o teste dedicado e confirmar GREEN.

## Phase 3 — Artefatos públicos

- [x] T008 [US1] Regenerar screenshots com
  `python3 scripts/capture_screenshots.py` e revisar diffs visuais.
- [x] T009 [US1] Confirmar que nenhum artefato público introduz emoji/glifo
  como status.

## Phase 4 — Convergência e entrega

- [x] T010 Rodar `compileall`, `git diff --check` e suíte completa sem
  enfraquecer thresholds ou remover testes.
- [x] T011 Atualizar esta lista e o checklist de requisitos com evidências.
- [ ] T012 Commit convencional, push da branch e abrir PR vinculada à #84;
  não fazer merge.

## Dependencies & Execution Order

- T002 → T003 → T004/T005 → T006 → T007.
- T007 → T008/T009 → T010 → T011 → T012.

## Evidence Log

- RED: `pytest tests/test_issue84_no_status_glyphs.py -q` falhou em
  `test_nenhuma_ocorrencia_de_check_ou_warning` antes da remoção.
- GREEN: `pytest tests/test_issue84_no_status_glyphs.py -q` — 6 passed.
- Regressões de UI: `tests/test_issue7_ui_caps.py` +
  `tests/test_issue6_profiles_polling.py` — 37 passed.
- Suíte completa: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q` —
  exit 0, 100% dos testes passaram.
- Smoke: `xvfb-run -a python3 -m unittest tests.smoke_ui_init` — OK.
- Integridade: `compileall`, `git diff --check` e grep de glifos — OK.
