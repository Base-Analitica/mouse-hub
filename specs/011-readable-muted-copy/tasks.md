# Tasks: Copy de leitura com contraste adequado (issue #90)

**Input**: Design documents from `/specs/011-readable-muted-copy/`

**Status**: Concluído; CI verde

## Phase 1 — Spec e teste (TDD)

- [x] T001 Criar spec, plano, tabela de princípios e checklist.
- [x] T002 Escrever `tests/test_issue90_readable_muted_copy.py` com auditoria
  runtime e proteção dos pontos de fonte.
- [x] T003 Executar antes do fix: RED confirmado em labels e subtitle.

## Phase 2 — User Story 1: copy legível

- [x] T004 Migrar labels de leitura para `text_secondary` ou cores semânticas.
- [x] T005 Manter `text_muted` apenas em OFF, disabled e decoração.
- [x] T006 Executar teste dedicado: 2 passed.

## Phase 3 — Artefatos públicos

- [x] T007 Regenerar screenshots e confirmar pipeline concluído.

## Phase 4 — Convergência

- [x] T008 Rodar regressões, compileall, diff-check e suíte completa.
- [x] T009 Commit, push e abrir PR vinculada à #90; não fazer merge.

## Evidence

- RED: teste runtime encontrou `Nenhuma macro gravada...`,
  `Clique em iniciar...` e `CPS`; teste de fonte encontrou subtitle muted.
- GREEN: `tests/test_issue90_readable_muted_copy.py` — 2 passed.
- Screenshots regeneradas pelo pipeline: clicker, macros e preview, em versões
  desktop e pequena.
- Regressão completa: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q`
  terminou com exit 0.
- Smoke UI, `compileall` e `git diff --check` também terminaram com sucesso.
- Commit `ba57db5`, push do branch `fix/readable-muted-copy` e PR #131 concluídos.
- CI do PR #131 passou nos jobs de testes determinísticos, pacote `.deb` e smoke
  da UI.
