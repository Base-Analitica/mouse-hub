---
description: "Tarefas do espaçamento semântico dos botões do Auto-Clicker"
---

# Tasks: Espaçamento semântico dos botões do Auto-Clicker

**Input**: Design documents from `/specs/025-autoclicker-label-spacing/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md` e `quickstart.md`.

## Phase 1: Spec e contrato

- [x] T001 Preencher os artifacts Spec Kit com os requisitos do issue #79, a decisão de nome puro e os oito gates da constituição.
- [x] T002 Criar `checklists/requirements.md` e mapear cada requisito a uma verificação observável.

## Phase 2: User Story 1 - Rótulos sem whitespace (P1)

**Goal**: Os três botões mostram somente `Esquerdo`, `Meio` e `Direito`.

**Independent Test**: `tests/test_issue79_autoclicker_label_spacing.py` constrói a página real com controlador fake e verifica textos, ordem, estado ativo e seleção.

### Testes antes da implementação

- [ ] T003 Escrever o teste dedicado antes da produção, verificando texto exato e ausência de whitespace invisível.
- [ ] T004 Rodar o teste focado e registrar RED causado pelos dois espaços atuais.

### Implementação

- [ ] T005 Remover o iterável de ícones vazios e construir cada `QPushButton` com o nome puro em `app/mouse_hub_app.py`.
- [ ] T006 Rodar o teste focado novamente e confirmar GREEN sem alterar seleção, gating ou estilos.

## Phase 3: User Story 2 - Seleção e responsividade (P2)

**Goal**: A seleção continua funcional e os botões permanecem equilibrados nos dois viewports.

- [ ] T007 Cobrir clique/seleção dos três códigos, estado ativo inicial e gating de capacidade.
- [ ] T008 Verificar geometria em 1050×680 e 760×560, sem overlap ou overflow horizontal.
- [ ] T009 Regenerar `3_clicker.png`, `small_clicker.png` e `preview.png`, repetir a captura e verificar bytes/áreas esperadas.

## Phase 4: Verificação e entrega

- [ ] T010 Executar compileall, `git diff --check`, smoke Xvfb, suíte determinística completa e empacotamento `.deb`.
- [ ] T011 Atualizar `spec.md`, `plan.md` e `checklists/requirements.md` com evidência real e rechecagem da constituição.
- [ ] T012 Fazer revisão read-only do diff com agente usando somente `openai-codex/gpt-5.6-luna` via Codex Auth ou `opencode-go/deepseek-v4-flash` via OpenCode Go.
- [ ] T013 Commitar em inglês com Conventional Commit, publicar a branch e abrir PR com `Closes #79`, sem merge.
- [ ] T014 Consultar os três checks reais do PR, confirmar todos verdes, PR aberto e `mergedAt == null`, e registrar IDs.

## Dependencies & Execution Order

- T001-T002 precedem qualquer alteração de código.
- T003-T004 precedem T005-T006 por exigência de TDD.
- T005-T009 precedem T010-T011.
- T012 deve ocorrer antes de T013; T014 ocorre após o CI remoto.

## Implementation Strategy

1. Manter o worktree isolado e confirmar baseline.
2. Criar o teste e observar RED.
3. Remover somente a composição textual baseada em ícone vazio.
4. Validar seleção, gating, geometria, screenshots, suíte, smoke e pacote.
5. Revisar, publicar e confirmar CI real sem merge.
