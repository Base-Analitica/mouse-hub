# Tasks: Label visual do nome da macro

**Input**: Design documents from `/specs/022-macros-label-input/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md` e `quickstart.md`

**Tests**: Incluídos porque a Constituição exige regressão junto do fix e o
fluxo TDD foi aprovado.

**Organization**: As tarefas seguem as três histórias de usuário e mantêm a
mudança restrita a `MacrosPage`, seu teste determinístico, screenshots e docs.

## Phase 1: Setup (Shared Context)

**Purpose**: Fixar o contexto e os contratos antes de editar produção.

- [x] T001 Confirmar a issue #104, `MacrosPage._build()`, `name_input`, o limite 32, os tokens de `app.ui.theme` e os três PNGs afetados.
- [x] T002 Confirmar que não há alteração de domínio, persistência, serviço de gravação ou hardware, e executar a linha de base das regressões de Macros/capacidades: 21 testes passaram.

**Checkpoint**: Contexto confirmado e baseline das regressões verde.

## Phase 2: User Story 1 - Label sem aparência de input (Priority: P1) 🎯 MVP

**Goal**: Fazer o texto `Nome da macro:` ser reconhecido como label e deixar o
campo real como a única superfície editável.

**Independent Test**: Construir `MacrosPage` com fake de `list_all()` e
QApplication offscreen, encontrando o label pelo texto e verificando stylesheet
transparente, padding zero, ausência de borda e exatamente um `QLineEdit`.

### Tests for User Story 1

> Escrever e executar antes do código de produção, observando RED pelo
> stylesheet vazio do label atual.

- [x] T003 [US1] Criar `tests/test_issue104_macro_label.py` com fake mínimo de serviço, fixture QApplication e teste runtime do label, único `QLineEdit` e valor inicial `minha_macro`.
- [x] T004 [US1] Adicionar no mesmo arquivo os casos parametrizados para 1050×680 e 760×560, verificando que label e campo permanecem distintos e que o label fica acima do campo.
- [x] T005 [US1] Executar os testes novos em RED com `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue104_macro_label.py -q`: 2 falhas esperadas por `styleSheet()` vazio, sem erro de fixture.

### Implementation for User Story 1

- [x] T006 [US1] Aplicar somente ao `QLabel("Nome da macro:")` em `app/mouse_hub_app.py` o stylesheet com `COLORS["text_secondary"]`, `TYPE_SCALE["body"]`, `background: transparent`, `padding: 0` e sem borda.
- [x] T007 [US1] Executar o teste focado em GREEN e confirmar que o stylesheet observado passa sem modificar `name_input` ou `record_btn`: 4 testes passaram.

**Checkpoint**: O label é texto de formulário e o único input continua sendo o
campo de nome.

## Phase 3: User Story 2 - Fluxo e espaçamento preservados (Priority: P1)

**Goal**: Preservar o campo, foco, limite, habilitação e gravação nos dois
viewports oficiais.

**Independent Test**: Medir a geometria após `show()` nos dois tamanhos e
executar as regressões assíncronas e de capacidades existentes.

- [x] T008 [US2] Completar asserts em `tests/test_issue104_macro_label.py` para texto `Nome da macro:`, valor `minha_macro`, `maxLength() == 32`, ordem geométrica e ausência de sobreposição nos dois viewports.
- [x] T009 [US2] Executar `tests/test_issue4_macro_recording.py` e `tests/test_issue7_ui_caps.py` e confirmar que gravação, cancelamento, capacidade indisponível e habilitação do campo permanecem verdes: 25 testes focados passaram em conjunto com a regressão do issue #104.

**Checkpoint**: O ajuste visual não altera comportamento ou layout utilizável do
formulário.

## Phase 4: User Story 3 - Screenshots públicas consistentes (Priority: P2)

**Goal**: Atualizar o material público para refletir a distinção entre label e
campo.

**Independent Test**: Rodar o capturador oficial e revisar os três PNGs afetados
em desktop, small e preview.

- [x] T010 [US3] Executar `QT_QPA_PLATFORM=offscreen python3 scripts/capture_screenshots.py` e verificar que `4_macros.png`, `small_macros.png` e `preview.png` foram regeneradas: o capturador concluiu as 7 telas, variantes small e `preview.png` no worktree do issue #104.
- [x] T011 [US3] Inspecionar visualmente as três imagens, confirmar label sem faixa de input, campo real preservado e ausência de alteração não relacionada; comparar hashes ou diff com o estado anterior: `4_macros.png`, `small_macros.png` e `preview.png` mostram o label como texto secundário transparente e o único campo real preservado; os hashes mudaram somente pela correção visual.

**Checkpoint**: As screenshots públicas não apresentam mais dois inputs
empilhados.

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Fechar regressões, integridade, Spec Kit e entrega.

- [x] T012 Executar a suíte completa `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q -rA` e investigar qualquer falha antes da entrega: 548 testes passaram, incluindo `tests/test_playback_cost.py`, sem falhas.
- [x] T013 Executar smoke Xvfb, `python3 -m compileall -q app mouse_hub tests scripts` e `git diff --check`: smoke `tests.smoke_ui_init` passou com 1 teste, compileall passou e o diff não apresentou erro.
- [x] T014 Atualizar `spec.md`, `plan.md`, `tasks.md` e `checklists/requirements.md` com resultados RED/GREEN, screenshots, regressões, suíte local, integridade e recheck dos oito princípios; a checklist de entrega permanece pendente apenas de push, PR e CI real.
- [x] T015 Revisar o diff final para confirmar que não há alteração em `mouse_hub/core/`, persistência ou fluxo de gravação, e commitar com mensagem convencional em inglês: revisão independente não encontrou achados; commits `0bf8b26`, `010cd6b`, `303e662` e `2e266ce` mantêm o escopo em UI, teste, screenshots e Spec Kit.
- [x] T016 Publicar `fix/macro-label-input-distinction`, abrir PR vinculado à issue #104 com `Closes #104`, registrar riscos e manter o PR aberto: PR #142 foi aberto em `https://github.com/Base-Analitica/mouse-hub/pull/142`, sem merge.
- [x] T017 Aguardar os checks reais do GitHub, registrar lint/testes determinísticos, pacote `.deb` e smoke Xvfb no Spec Kit, e não executar merge: workflow `33268985103` passou nos três jobs, e o PR #142 continua aberto e não mesclado.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Pode iniciar imediatamente e bloqueia as histórias.
- **US1 (Phase 2)**: Depende de T001–T002; T003–T005 devem preceder T006.
- **US2 (Phase 3)**: Depende do GREEN de US1 e valida o mesmo formulário sem nova produção.
- **US3 (Phase 4)**: Depende de T006–T009; screenshots só depois do estilo GREEN.
- **Polish (Phase 5)**: Depende de todas as histórias e fecha a entrega.

### User Story Dependencies

- **US1**: Independente após o contexto e entrega o MVP visual.
- **US2**: Usa o label e o campo da US1, mas valida comportamento preservado.
- **US3**: Usa o resultado das US1 e US2 para material público.

### Within Each User Story

- Testes devem ser escritos e observados falhando antes da alteração de produção.
- A implementação deve ser a menor mudança capaz de satisfazer os testes.
- Nenhum teste deve ser enfraquecido para acomodar a implementação.

### Requirement Traceability

| Requisito | Tarefas que o verificam |
|---|---|
| FR-001 | T003, T005, T006, T007 |
| FR-002 | T003, T004, T008 |
| FR-003 | T004, T008 |
| FR-004 | T009, T012 |
| FR-005 | T009, T012 |
| FR-006 | T010, T011 |
| FR-007 | T003, T005, T007, T012, T013, T017 |
| SC-001 | T003, T004, T007, T008 |
| SC-002 | T004, T008 |
| SC-003 | T009, T012 |
| SC-004 | T010, T011, T017 |

## Implementation Strategy

1. Completar T001–T002 e confirmar baseline.
2. Escrever T003–T004 e observar RED em T005.
3. Implementar somente T006 e confirmar GREEN em T007.
4. Fechar T008–T009 para proteger fluxo, foco, capacidade e espaçamento.
5. Regenerar e revisar screenshots em T010–T011.
6. Executar T012–T017, mantendo o PR aberto e sem merge.

## Notes

- A mudança não toca `mouse_hub/core/`, `AutomationService`, `MacroStore` ou
  protocolo HID++.
- O stylesheet do label usa tokens existentes e não cria números mágicos.
- A ausência de hardware ou de sessão X11 real é esperada nos testes; nenhuma
  validação física do G403 será alegada.
