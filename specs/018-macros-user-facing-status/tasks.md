# Tasks: Status de Macros orientado à tarefa (issue #113)

**Input**: Design documents from `/specs/018-macros-user-facing-status/`

**Status**: Convergido localmente; aguardando PR/CI

## Phase 1: Spec e teste (TDD)

- [x] T001 Criar `spec.md`, `plan.md` e matriz dos oito princípios.
- [x] T002 Mapear os textos operacionais e separar copy de produto de causa
  técnica interna.
- [x] T003 Escrever `tests/test_issue113_macro_copy.py` e confirmar RED antes da
  alteração de produção.

## Phase 2: User Story 1 — disponibilidade de gravação (P1)

- [x] T004 [US1] Trocar a copy disponível por “Gravação de macros disponível”,
  sem nome de backend.
- [x] T005 [US1] Traduzir a indisponibilidade de sessão gráfica para consequência
  orientada ao usuário, preservando a causa interna no modelo.

## Phase 3: User Story 2 — feedback operacional (P2)

- [x] T006 [US2] Remover `XRecord` da mensagem de início e manter o próximo passo
  compreensível.
- [x] T007 [US2] Sanitizar falhas técnicas antes de exibi-las em `record_status` e
  `play_status`, sem alterar o resultado real da operação.
- [x] T008 [US2] Confirmar que sucesso, cancelamento e truncamento mantêm a
  semântica e a copy existente.

## Phase 4: Artefatos públicos e convergência

- [x] T009 Atualizar regressões de gravação e executar os testes focados.
- [x] T010 Regenerar `4_macros.png`, `small_macros.png` e `preview.png` com o
  script oficial; revisar desktop e 760×560.
- [x] T011 Executar suíte completa offscreen, smoke Xvfb, compileall e
  `git diff --check`.
- [x] T012 Atualizar checklist e registrar evidências locais.
- [ ] T013 Commit convencional, push e abrir PR vinculada à #113; obter checks
  reais verdes sem fazer merge.

## Dependencies & Execution Order

- T001/T002 → T003 → T004/T005/T006/T007 → T008/T009.
- T009 → T010/T011 → T012 → T013.
- Não há dependência em PRs visuais não integrados; a branch parte de `main`.

## Evidence Log

- **RED**: `QT_QPA_PLATFORM=offscreen python3 -m pytest
  tests/test_issue113_macro_copy.py -q` falhou nos 4 casos antes da mudança,
  pois a copy disponível, indisponível, inicialização e falha expunham jargão.
- **GREEN focado**: `tests/test_issue113_macro_copy.py`,
  `tests/test_issue4_macro_recording.py` e `tests/test_issue7_ui_caps.py` —
  26 passed.
- **Suíte completa**: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q`
  terminou com exit 0.
- **Smoke**: `QT_QPA_PLATFORM=offscreen xvfb-run -a python3 -m unittest
  tests.smoke_ui_init` — 1 test OK.
- **Integridade**: `python3 -m compileall -q mouse_hub tests app` e
  `git diff --check` — OK.
- **Capturas**: script oficial regenerou as variantes desktop e small; os
  arquivos alterados são `4_macros.png`, `small_macros.png` e `preview.png`.
