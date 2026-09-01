---
description: "Tarefas de implementação do hint de capacidade do Auto-Clicker"
---

# Tasks: Hint de capacidade do Auto-Clicker visível

**Input**: Design documents from `/specs/024-autoclicker-capability-hint/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md` e `quickstart.md`.

## Phase 1: Spec e contrato

- [x] T001 Preencher `spec.md`, `research.md`, `data-model.md`, `plan.md` e `quickstart.md` com os requisitos do issue #78 e os oito gates da constituição.
- [x] T002 Criar `checklists/requirements.md` e mapear cada requisito a uma verificação observável.

## Phase 2: User Story 1 - Explicar controles indisponíveis (P1) 🎯 MVP

**Goal**: O motivo real de indisponibilidade aparece no layout próximo aos controles desabilitados.

**Independent Test**: `tests/test_issue78_autoclicker_capability_hint.py` constrói a página com capability fake indisponível e verifica layout, causa e gating.

### Testes antes da implementação

- [x] T003 [US1] Escrever o teste dedicado antes da produção, verificando `caps_hint` como item do layout, causa real e controles desabilitados.
- [x] T004 [US1] Rodar o teste focado e registrar RED causado exclusivamente pela ausência do widget no layout.

### Implementação

- [x] T005 [US1] Adicionar somente `layout.addWidget(self.caps_hint)` após `mc_status` e antes do título de CPS em `app/mouse_hub_app.py`.
- [x] T006 [US1] Rodar o teste focado novamente e confirmar GREEN sem alterar `CapabilityModel`, gating ou copy de #83.

## Phase 3: User Story 2 - Disponibilidade e estados distintos (P2)

**Goal**: O mesmo hint comunica disponível/indisponível e permanece separado do foco do Minecraft.

**Independent Test**: Testes com `CapabilityState` disponível e indisponível verificam texto, enabled state, instância única e `mc_status` independente.

- [x] T007 [US2] Completar a cobertura do teste para estado disponível, atualização de estado e separação de `mc_status`.
- [x] T008 [US2] Rodar regressões de capabilities/UI e confirmar que o gating existente continua intacto.

## Phase 4: User Story 3 - Responsividade e evidência visual (P2)

**Goal**: O hint cabe sem clipping ou sobreposição em desktop e small.

**Independent Test**: A página é dimensionada nos dois viewports oficiais e as capturas do Auto-Clicker são reproduzidas.

- [x] T009 [US3] Adicionar asserts geométricos mínimos para o hint e os controles em 1050×680 e 760×560, sem depender de pixel frágil.
- [x] T010 [US3] Regenerar `3_clicker.png`, `small_clicker.png` e `preview.png`, repetir a captura e verificar bytes/áreas esperadas.

## Phase 5: Verificação e entrega

- [x] T011 Executar compileall, `git diff --check`, smoke Xvfb, suíte determinística completa e empacotamento `.deb`.
- [x] T012 Atualizar `spec.md`, `plan.md` e `checklists/requirements.md` com evidência real e rechecagem da constituição.
- [ ] T013 Fazer revisão read-only do diff com agente usando somente `openai-codex/gpt-5.6-luna` via Codex Auth ou `opencode-go/deepseek-v4-flash` via OpenCode Go.
- [ ] T014 Commitar em inglês com Conventional Commit, publicar a branch e abrir PR com `Closes #78`, sem merge.
- [ ] T015 Consultar os três checks reais do PR, confirmar todos verdes, PR aberto e `mergedAt == null`, e registrar IDs.

## Dependencies & Execution Order

- T001-T002 precedem qualquer alteração de código.
- T003-T004 precedem T005-T006 por exigência de TDD.
- T005-T006 precedem T007-T010.
- T011-T012 dependem das screenshots estabilizadas.
- T013 deve ocorrer antes de T014; T015 ocorre após o CI remoto.

## Implementation Strategy

1. Manter o worktree isolado e verificar baseline.
2. Criar o teste e observar RED.
3. Inserir o widget existente no layout, sem refatoração.
4. Validar estados, geometria, screenshots, suíte, smoke e pacote.
5. Revisar, publicar e confirmar CI real sem merge.
