---
description: "Tarefas dos issues #82 e #83: microcopy de segurança do Auto-Clicker"
---

# Tasks: Microcopy de segurança do Auto-Clicker

**Input**: Design documents from `specs/028-autoclicker-security-copy/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`

**Scope**: alterar somente o texto e a cor do `safety_text` em `SettingsPage`; preservar o motor e o gating.

## Phase 1: Setup

- [ ] T001 [US1] Confirmar worktree `fix/autoclicker-security-copy` em `origin/main` e registrar o baseline.
- [ ] T002 [US1] Criar e revisar os artefatos Spec Kit e `.specify/feature.json` para #82/#83.
- [ ] T003 [US1] Executar a suíte completa no baseline e registrar contagem, falhas e exit code.

## Phase 2: Foundational

- [ ] T004 [US1] Confirmar no código que `safety_text` é QLabel com word wrap, que o grupo permanece na `SettingsPage` e que engine/checker/capabilities estão fora do diff.

**Checkpoint**: o mesmo bloco pode resolver os dois issues sem infraestrutura nova.

## Phase 3: User Story 1 - Explicar a proteção (Priority: P1)

### Tests for User Story 1

> Escrever primeiro e observar RED contra a copy verde com jargão atual.

- [ ] T005 [US1] Criar `tests/test_issue82_83_security_copy.py` com fakes e viewport parametrizado.
- [ ] T006 [US1] Exigir foco de Minecraft/Lunar Client e bloqueio fora do jogo.
- [ ] T007 [US1] Rejeitar `X11`, `XRecord`, `cache`, `TTL`, `500 ms` e xdotool na copy operacional.
- [ ] T008 [US1] Exigir `text_secondary` e rejeitar `mc_green` no stylesheet do texto.
- [ ] T009 [US1] Confirmar visibilidade e contenção do QLabel em 1050×680 e 760×560.
- [ ] T010 [US1] Executar o teste dedicado antes do código e registrar RED atribuível à copy/estilo atual.

### Implementation

- [ ] T011 [US1] Trocar somente o literal e stylesheet de `safety_text` pela copy aprovada e cor neutra.
- [ ] T012 [US1] Executar GREEN dedicado.
- [ ] T013 [US1] Executar regressões do Auto-Clicker, automação e capabilities.

**Checkpoint**: a explicação é acionável e o motor continua fail-closed fora do foco.

## Phase 4: Polish & Cross-Cutting Validation

- [ ] T014 [US1] Executar `scripts/capture_screenshots.py` duas vezes e confirmar 15 PNGs byte-idênticas.
- [ ] T015 [US1] Comparar com `origin/main` e confirmar mudanças somente em `6_settings.png`, `small_settings.png` e `preview.png` na região esperada.
- [ ] T016 [US1] Executar a suíte completa e registrar contagem, falhas e exit code.
- [ ] T017 [US1] Executar smoke Xvfb, compileall e `git diff --check`.
- [ ] T018 [US1] Construir/extrair o pacote `.deb` e verificar árvore, launchers e código empacotado.
- [ ] T019 [US1] Executar revisão read-only com agente autorizado e corrigir achados Critical/Important.
- [ ] T020 [US1] Atualizar Spec Kit com matriz requisito→teste→resultado e evidências observadas.
- [ ] T021 [US1] Fazer commits convencionais, confirmar branch limpa e diff check.
- [ ] T022 [US1] Publicar branch, abrir PR com `Closes #82` e `Closes #83`, aguardar os três jobs reais, manter PR aberto sem merge.

## Traceability

| Requisito | Tasks | Evidência |
| --- | --- | --- |
| FR-001 / SC-001 | T006, T011, T012 | termos de foco presentes |
| FR-002 / SC-001 | T006, T011, T012 | bloqueio fora do jogo presente |
| FR-003 / SC-003 | T008, T011, T012 | token neutro, sem verde semântico |
| FR-004 / SC-002 | T007, T011, T012 | jargão ausente |
| FR-005 / SC-005 | T004, T013, T019 | regressões funcionais e revisão |
| FR-006 / SC-008 | T004, T015, T017, T019 | diff restrito |
| FR-007 / SC-006 | T014, T015 | capturas determinísticas |
| FR-008 / SC-007 | T010, T012, T016–T018, T022 | RED/GREEN e integração |

## Execution Order

T001–T004 → T005–T010 → T011–T013 → T014–T018 → T019–T022.

O PR conjunto é permitido somente porque #82 e #83 são alterações inseparáveis no mesmo parágrafo e nas mesmas três screenshots.
