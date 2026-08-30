---
description: "Tarefas da issue #63: configuração Serena somente leitura"
---

# Tasks: Serena em modo somente leitura

**Input**: Design documents from `specs/029-serena-read-only/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`

**Scope**: alterar somente `.serena/project.yml`, testes e documentação Spec Kit.

## Phase 1: Setup

- [x] T001 [US1] Confirmar branch `fix/serena-read-only-config`, worktree isolado, base `origin/main` e issue #63.
- [x] T002 [US1] Criar e revisar os artefatos Spec Kit e `.specify/feature.json`.
- [x] T003 [US1] Executar a suíte completa no baseline e registrar contagem, falhas e exit code. Baseline `origin/main` em `abad8b1`: 544 passed, exit 0.

## Phase 2: Foundational

- [x] T004 [US1] Confirmar no diff que a mudança fica fora de `app/`, `mouse_hub/`, launchers e packaging.
- [x] T005 [US1] Confirmar a chave `read_only` e os subcomandos existentes da ponte semântica.

## Phase 3: User Story 1 - Consultar sem editar (Priority: P1)

### Tests for User Story 1

> Escrever primeiro e observar RED com `read_only: false`.

- [x] T006 [US1] Criar `tests/test_issue63_serena_read_only.py` para validar YAML booleano, parser e launcher.
- [x] T007 [US1] Exigir `read_only: true` e rejeitar a configuração gravável.
- [x] T008 [US1] Exigir os subcomandos `tools`, `overview`, `find`, `refs` e `diagnostics` sem comandos de edição.
- [x] T009 [US1] Executar o teste dedicado antes da alteração e registrar RED.

### Implementation

- [x] T010 [US1] Trocar somente `read_only: false` por `read_only: true` em `.serena/project.yml`.
- [x] T011 [US1] Executar GREEN e o handshake real da Serena. Os cinco comandos retornaram exit code 0.
- [x] T012 [US1] Executar regressões do runtime para confirmar ausência de impacto no Mouse Hub. A suíte pós-mudança passou com 548 testes.

## Phase 4: Polish & Cross-Cutting Validation

- [x] T013 [US1] Executar suíte completa e registrar contagem, falhas e exit code. HEAD pós-mudança: 548 passed, exit 0.
- [x] T014 [US1] Executar smoke Xvfb, compileall e `git diff --check`. Smoke: 1 OK; compileall e diff check: OK.
- [x] T015 [US1] Construir/extrair o pacote `.deb` e verificar árvore sem alteração indevida. Staging Debian passou e o SHA do app empacotado coincide com o worktree.
- [ ] T016 [US1] Executar revisão read-only com agente autorizado.
- [x] T017 [US1] Atualizar Spec Kit com matriz requisito→teste→resultado e limitações honestas.
- [ ] T018 [US1] Fazer commits convencionais, confirmar branch limpa e diff check.
- [ ] T019 [US1] Publicar branch, abrir PR com `Closes #63`, aguardar três jobs reais e manter sem merge.

## Traceability

| Requisito | Tasks | Evidência |
| --- | --- | --- |
| FR-001 / SC-001 | T006–T011 | parsing e valor booleano |
| FR-002 / SC-002 | T005, T006, T008, T011 | parser/handshake das consultas |
| FR-003 / SC-002 | T005, T008, T011 | ponte e launcher sem escrita |
| FR-004 / SC-003 | T004, T012, T014 | diff de caminhos e regressões |
| FR-005 / SC-004 | T003, T012–T015, T019 | suíte, smoke, pacote e CI |
| FR-006 / SC-005 | T009, T011, T017 | RED/GREEN e documentação |

## Execution Order

T001–T005 → T006–T009 → T010–T012 → T013–T018 → T019.
