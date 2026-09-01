# Tasks: Remover whitespace residual das labels (issue #89)

**Input**: Design documents from `/specs/012-remove-residual-label-whitespace/`

**Status**: Convergido localmente; aguardando commit/PR

## Phase 1 — Spec e teste (TDD)

- [x] T001 Criar spec, plano, tabela de princípios e checklist.
- [x] T002 Escrever teste runtime/fonte para whitespace e sincronização
  `Play`/`Cancel`.
- [x] T003 Executar antes do fix e confirmar RED nos resíduos conhecidos.

## Phase 2 — User Stories 1 e 2: copy e playback

- [x] T004 Remover whitespace prefixado das labels, botões, títulos e status.
- [x] T005 Normalizar múltiplos espaços de copy sem alterar conteúdo semântico.
- [x] T006 Atualizar a sincronização limpa de `Play`/`Cancel`.
- [x] T007 Executar o teste dedicado e confirmar GREEN.

## Phase 3 — Artefatos públicos

- [x] T008 Regenerar screenshots de DPI, Macros, Perfis e Configurações.

## Phase 4 — Convergência

- [x] T009 Rodar regressões, compileall, diff-check e suíte completa.
- [ ] T010 Commit, push e abrir PR vinculada à #89; não fazer merge.

## Evidence

- Spec-kit criado antes do TDD.
- RED confirmado: o teste encontrou 21 textos com padding/múltiplos espaços,
  literais de presets/títulos e a transição `Play` → `Cancel` não atualizada.
- GREEN: `tests/test_issue89_residual_label_whitespace.py` — 3 passed.
- Screenshots regeneradas nas variantes desktop, small e preview.
- A suíte completa terminou com exit 0; smoke UI, `compileall` e
  `git diff --check` também passaram.
- T010 permanece pendente até o commit, push e abertura do PR.
