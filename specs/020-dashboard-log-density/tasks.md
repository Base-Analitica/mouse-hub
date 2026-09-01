# Tasks: Densidade adaptativa do log do Dashboard

**Input**: Design documents from `/specs/020-dashboard-log-density/`

**Prerequisites**: `plan.md` e `spec.md`

**Tests**: Incluídos porque o fluxo TDD foi solicitado e a constituição exige regressão junto do fix.

**Organization**: As tarefas seguem as três histórias de usuário. A implementação permanece sequencial porque as transições compartilham a mesma superfície de log em `DashboardPage`.

## Phase 1: Setup (Shared Context)

**Purpose**: Fixar o contexto da issue, a branch e os artefatos Spec Kit.

- [x] T001 Confirmar a issue #106, o comportamento atual de `DashboardPage.log` e o contrato de `log_msg` em `app/mouse_hub_app.py`.
- [x] T002 Validar a especificação, o plano, a checklist e a constituição em `specs/020-dashboard-log-density/` e `.specify/memory/constitution.md`.

---

## Phase 2: Foundational (Existing UI Contract)

**Purpose**: Preservar a superfície existente antes de alterar sua densidade.

- [x] T003 Confirmar que não há persistência ou modelo separado para o Log de Atividade e que os doubles de Dashboard em `tests/test_issue7_ui_caps.py` e `tests/test_issue3_ui_integration.py` são suficientes.

**Checkpoint**: Contrato de texto, ordem, registro e rolagem identificado. Nenhuma mudança de domínio ou dependência é necessária.

---

## Phase 3: User Story 1 - Estado vazio compacto (Priority: P1) 🎯 MVP

**Goal**: Mostrar a mensagem de estado vazio em uma superfície compacta, sem reservar a altura de conteúdo preenchido.

**Independent Test**: Instanciar o Dashboard vazio com QApplication offscreen e verificar a mensagem intacta e a altura compacta.

### Tests for User Story 1

> Escrever e executar o teste antes da implementação para registrar RED.

- [x] T004 [US1] Criar teste RED para a altura compacta e a mensagem do estado vazio em `tests/test_issue106_activity_log.py`.

### Implementation for User Story 1

- [x] T005 [US1] Implementar a transição de densidade vazia na superfície do log em `app/mouse_hub_app.py`, sem alterar a copy ou o registro das atividades.

**Checkpoint**: O Dashboard vazio apresenta somente a área necessária para a mensagem orientativa.

---

## Phase 4: User Story 2 - Conteúdo real navegável (Priority: P1)

**Goal**: Restaurar a área normal do log ao receber atividades e manter entradas longas acessíveis por rolagem interna.

**Independent Test**: Adicionar entradas pelo fluxo existente, verificar a altura normal, a ordem do texto e a recuperação de todas as entradas.

### Tests for User Story 2

> Os testes devem falhar antes da implementação da transição dinâmica.

- [x] T006 [US2] Adicionar testes RED para a transição vazio → preenchido, múltiplas entradas, rolagem interna e retorno após limpeza em `tests/test_issue106_activity_log.py`.

### Implementation for User Story 2

- [x] T007 [US2] Sincronizar a altura do log quando o conteúdo textual mudar e preservar a altura normal e a rolagem interna para entradas reais em `app/mouse_hub_app.py`.

**Checkpoint**: O log vazio é compacto e o log preenchido continua utilizável sem alterar o contrato de atividades.

---

## Phase 5: User Story 3 - Semântica consistente nos viewports (Priority: P2)

**Goal**: Garantir que o estado vazio compacto e o estado preenchido mantenham a mesma semântica em 1050×680 e 760×560.

**Independent Test**: Medir o componente nos dois tamanhos oficiais e confirmar que a mensagem não é cortada e que o Dashboard small não ganha rolagem por causa do estado vazio.

### Tests for User Story 3

- [x] T008 [US3] Adicionar teste determinístico de geometria e visibilidade para os viewports desktop e small em `tests/test_issue106_activity_log.py`.

### Implementation for User Story 3

- [x] T009 [US3] Ajustar somente os limites de densidade necessários para manter alinhamento e legibilidade nos dois viewports em `app/mouse_hub_app.py`.

**Checkpoint**: Os dois tamanhos oficiais apresentam o mesmo contrato de estado vazio e conteúdo.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Regressão completa, evidência visual e entrega independente.

- [x] T010 Executar os testes focados de `tests/test_issue106_activity_log.py`, `tests/test_issue3_ui_integration.py` e `tests/test_issue7_ui_caps.py`.
- [x] T011 Regenerar `docs/screenshots/0_dashboard.png`, `docs/screenshots/small_dashboard.png` e `docs/screenshots/preview.png` usando `scripts/capture_screenshots.py`.
- [x] T012 Executar a suíte completa offscreen, smoke Xvfb, `python3 -m compileall -q app mouse_hub tests`, `git diff --check` e revisar o diff da feature.
- [ ] T013 Atualizar as evidências em `specs/020-dashboard-log-density/`, commitar convencionalmente em inglês, publicar `fix/dashboard-empty-log-density` e abrir PR vinculado ao issue #106 sem fazer merge.
- [ ] T014 Aguardar e verificar os três checks reais do CI no PR do issue #106, registrando os IDs e resultados em `specs/020-dashboard-log-density/plan.md` e `specs/020-dashboard-log-density/tasks.md`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependências. Confirma contexto e contratos.
- **Foundational (Phase 2)**: Depende de T001 e T002 e bloqueia as histórias.
- **User Story 1 (Phase 3)**: Depende de T003. T004 deve falhar antes de T005.
- **User Story 2 (Phase 4)**: Depende de T005. T006 deve falhar antes de T007.
- **User Story 3 (Phase 5)**: Depende de T007. T008 deve falhar antes de T009.
- **Polish (Phase 6)**: Depende de T009 e fecha a regressão, a evidência e a entrega.

### User Story Dependencies

- **US1**: Pode ser validada sozinha após o contexto existente.
- **US2**: Depende da superfície inicial de US1, mas mantém teste independente de conteúdo real.
- **US3**: Exercita a mesma solução de US1 e US2 nos dois viewports oficiais.

### Parallel Opportunities

- T010 pode executar os três arquivos de regressão na mesma etapa, mas a mudança de produção e o teste dedicado compartilham a mesma superfície.
- T011 pode executar após a implementação em paralelo com revisão textual dos artefatos Spec Kit, sem editar os mesmos arquivos.

### Within Each User Story

- Testes devem ser escritos e observados falhando antes da implementação correspondente.
- A mudança de produção deve preservar `log_msg`, a copy atual e a ordem das entradas.
- Cada checkpoint deve passar antes da próxima história.

## Implementation Strategy

### MVP First

1. Completar T001–T003.
2. Completar T004 e T005 para o estado vazio compacto.
3. Validar a US1 independentemente.
4. Completar T006 e T007 para fechar a transição com conteúdo.
5. Completar T008 e T009 para os dois viewports.
6. Executar T010–T014 antes de declarar o PR pronto.

### Notes

- Nenhuma tarefa altera `mouse_hub/core/` ou o formato de configuração.
- A altura normal de conteúdo permanece 120 px e a altura vazia proposta é 64 px.
- O placeholder não é uma entrada real e não deve alterar a densidade do componente.
- A validação de CI deve vir das checks reais do GitHub, não de uma suposição local.
- O PR permanece aberto e não é mesclado pelo agente.
