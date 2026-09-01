# Tasks: CTA HID como estado contextual (issue #116)

**Input**: Design documents from `/specs/017-hid-permission-state/`

**Status**: Convergido localmente; aguardando PR/CI

## Phase 1: Spec e teste (TDD)

- [x] T001 Criar `spec.md`, `plan.md` e matriz dos oito princípios da constituição.
- [x] T002 Definir o contrato de visibilidade para granted, permission-denied,
  not-actionable, estado ausente e operação assíncrona.
- [x] T003 Escrever `tests/test_issue116_hid_permission_ui.py` e executar RED
  antes da alteração de `SettingsPage`.

## Phase 2: User Story 1 — estado concedido (P1)

- [x] T004 [US1] Fazer `_sync_permission_ui()` ocultar a CTA quando
  `hid_available` estiver confirmado, preservando o status verde.
- [x] T005 [US1] Cobrir a transição de causa acionável para granted sem deixar
  visibilidade ou tooltip residual.

## Phase 3: User Story 2 — permissão acionável (P1)

- [x] T006 [US2] Restaurar explicitamente `show()` e `setEnabled(True)` no ramo
  de falta de permissão reconhecida.
- [x] T007 [US2] Preservar o bloqueio temporário durante a thread e ocultar a CTA
  após resultado bem-sucedido; manter falha/cancelamento honesto.

## Phase 4: User Story 3 — causa não acionável (P2)

- [x] T008 [US3] Ocultar a CTA para estado ausente, exceção de leitura e causa
  que não pode ser resolvida pela regra udev.
- [x] T009 [US3] Atualizar regressões em `tests/test_hid_permission_helper.py`
  para distinguir visibilidade de habilitação.

## Phase 5: Artefatos públicos e convergência

- [x] T010 Regenerar `6_settings.png`, `small_settings.png` e `preview.png` com
  o script oficial e revisar a compactação da seção.
- [x] T011 Executar teste focado, suíte completa, smoke Xvfb, compileall e
  `git diff --check`.
- [x] T012 Atualizar checklist e registrar evidências locais; a spec aguarda o
  identificador do workflow final para ser marcada como entregue.
- [ ] T013 Commit convencional, push e abrir PR vinculada à #116 para a branch
  dependente; obter checks reais verdes sem fazer merge.

## Dependencies & Execution Order

- T001/T002 → T003 → T004/T006/T008 → T005/T007/T009.
- T004/T006/T008 e os testes ficaram verdes antes de T010.
- T010/T011 → T012 → T013.
- A base `fix/vector-status-icons` (PR #129/#84) deve permanecer como dependência
  até que os PRs sejam integrados pelo mantenedor.

## Evidence Log

- **RED**: `QT_QPA_PLATFORM=offscreen python3 -m pytest
  tests/test_issue116_hid_permission_ui.py -q` falhou em 3 de 4 casos antes
  da mudança: granted, causa não acionável e estado ausente mantinham a CTA.
- **GREEN focado**: `tests/test_issue116_hid_permission_ui.py` e
  `tests/test_hid_permission_helper.py` — 20 passed.
- **Dependência #84**: teste de ausência de glifos junto dos testes HID — 26
  passed.
- **Suíte completa**: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q`
  terminou com exit 0.
- **Smoke**: `QT_QPA_PLATFORM=offscreen xvfb-run -a python3 -m unittest
  tests.smoke_ui_init` — 1 test OK.
- **Integridade**: `python3 -m compileall -q mouse_hub tests app` e
  `git diff --check` — OK.
- **Capturas**: script oficial regenerou 7 telas desktop, variantes small e
  `preview.png`; os arquivos alterados são `6_settings.png`,
  `small_settings.png` e `preview.png`.
