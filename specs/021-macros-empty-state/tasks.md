---

description: "Task list for the empty state de Macros feature"
---

# Tasks: Empty state de Macros próximo ao heading

**Input**: Design documents from `specs/021-macros-empty-state/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md` and
`quickstart.md`.

**Tests**: Obrigatórios. O projeto exige TDD, testes determinísticos sem
hardware e regressão acompanhando cada correção visual.

## Phase 1: Setup e Design (Shared Infrastructure)

**Purpose**: Confirmar os artefatos e o escopo antes de tocar no código.

- [x] T001 Conferir `specs/021-macros-empty-state/spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md` e `checklists/requirements.md` contra a issue #105
- [x] T002 Confirmar em `app/mouse_hub_app.py` o ramo vazio de `MacrosPage` e em `scripts/capture_screenshots.py` as três imagens afetadas
- [x] T003 Registrar no `plan.md` o gate constitucional inicial como PASS e manter `contracts/` ausente por não haver interface externa

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Preparar o harness Qt fake que será usado por todas as histórias.

- [x] T004 [P] Preparar em `tests/test_issue105_macro_empty_state.py` o fixture `QApplication` offscreen e um fake de `list_all()` sem hardware
- [x] T005 [P] Definir no mesmo arquivo os helpers para montar, mostrar, redimensionar e fechar `MacrosPage` nos viewports 1050×680 e 760×560

**Checkpoint**: O teste pode construir a página real sem hardware, persistência ou sessão X11.

---

## Phase 3: User Story 1 - Encontrar o estado vazio de Macros (Priority: P1) 🎯 MVP

**Goal**: Tornar o estado vazio imediatamente localizável após `Macros Salvas`, preservando o CTA existente.

**Independent Test**: Renderizar a página vazia nos dois viewports e verificar texto, alinhamento superior, proximidade ao viewport da lista e CTA único.

### Tests for User Story 1 (TDD RED first)

- [x] T006 [US1] Adicionar em `tests/test_issue105_macro_empty_state.py` teste do texto pt-BR e do alinhamento superior do empty state
- [x] T007 [US1] Adicionar no mesmo arquivo teste de posição relativa da mensagem no início da região de lista em 1050×680 e 760×560
- [x] T008 [US1] Adicionar teste que confirma em `tests/test_issue105_macro_empty_state.py` a presença de um único CTA `Gravar Macro` e ausência de botão dentro do empty state
- [x] T009 [US1] Executar `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue105_macro_empty_state.py -q` contra a implementação atual e registrar a falha esperada antes do código de produção

### Implementation for User Story 1

- [x] T010 [US1] Ajustar somente o ramo `not macros` de `MacrosPage._refresh_list` em `app/mouse_hub_app.py` para alinhamento no topo e padding intencionalmente menor, sem alterar o card de gravação ou o CTA
- [x] T011 [US1] Reexecutar o teste focado e confirmar GREEN para os dois viewports, preservando exatamente a copy do empty state

**Checkpoint**: A página vazia entrega a hierarquia visual corrigida e continua oferecendo somente `Gravar Macro` como ação de criação.

---

## Phase 4: User Story 2 - Preservar a lista preenchida (Priority: P2)

**Goal**: Garantir que itens existentes e transições vazio/preenchido não sofram regressão.

**Independent Test**: Alternar um fake entre lista vazia e uma macro determinística, atualizando a lista e inspecionando widgets visíveis.

### Tests for User Story 2

- [x] T012 [US2] Adicionar em `tests/test_issue105_macro_empty_state.py` teste de lista preenchida com item e controles existentes, sem mensagem vazia
- [x] T013 [US2] Adicionar teste de transição vazio→preenchido→vazio sem widgets ou mensagens residuais
- [x] T014 [US2] Executar os testes focados de US1 e US2 e confirmar que o ajuste não altera o fluxo da lista preenchida

**Checkpoint**: Estado preenchido e transições continuam estáveis e independentes do empty state.

---

## Phase 5: User Story 3 - Manter evidência visual pública (Priority: P2)

**Goal**: Atualizar as evidências públicas do estado vazio nos tamanhos desktop e small.

**Independent Test**: Rodar o capturador determinístico e verificar os três arquivos afetados.

- [x] T015 [US3] Regenerar `docs/screenshots/4_macros.png`, `docs/screenshots/small_macros.png` e `docs/screenshots/preview.png` com `QT_QPA_PLATFORM=offscreen python3 scripts/capture_screenshots.py`
- [x] T016 [US3] Inspecionar visualmente as screenshots e confirmar proximidade entre `Macros Salvas` e o empty state sem alterar telas não relacionadas

**Checkpoint**: As screenshots públicas representam a mesma hierarquia visual testada.

---

## Phase 6: Polish, Verification & Delivery

**Purpose**: Fechar o ciclo de feedback e publicar um PR aberto, sem merge.

- [x] T017 Executar a suíte completa `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q` e investigar qualquer falha antes da entrega
- [x] T018 Executar smoke Xvfb, `python3 -m compileall -q app mouse_hub tests scripts` e `git diff --check`
- [x] T019 Atualizar `spec.md`, `plan.md`, `tasks.md` e `checklists/requirements.md` com o registro de validação e reavaliar os oito princípios da Constituição
- [ ] T020 Fazer revisão final do diff, commitar com mensagem convencional em inglês e publicar a branch `fix/macros-empty-state-position`
- [ ] T021 Abrir PR vinculado à issue #105 com contexto, abordagem, testes, screenshots, riscos e `Closes #105`; manter o PR aberto para o mantenedor
- [ ] T022 Aguardar os checks reais do GitHub no PR e registrar o resultado final, sem executar merge
- [x] T023 Incorporar o feedback da revisão em `tests/test_issue105_macro_empty_state.py`, cobrindo ordem heading→mensagem e remoção dos widgets antigos

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup e Design (Phase 1)**: independente, mas deve preceder os testes.
- **Foundational (Phase 2)**: depende da leitura da estrutura e bloqueia as histórias.
- **US1 (Phase 3)**: deve completar o ciclo RED-GREEN antes das outras histórias.
- **US2 (Phase 4)**: usa a mesma página e fake, portanto segue a implementação da US1.
- **US3 (Phase 5)**: depende do layout GREEN e dos testes de US1/US2.
- **Polish/Delivery (Phase 6)**: depende de todas as histórias e da regeneração das screenshots.

### User Story Dependencies

- **US1**: não depende de outra história e é o MVP.
- **US2**: depende apenas da página construída pela US1, mas verifica fluxo independente.
- **US3**: depende do resultado visual de US1 e da estabilidade de US2.

### Parallel Opportunities

- T004 e T005 podem ser preparados em paralelo dentro do mesmo arquivo antes da execução dos testes.
- T012 e T013 são casos independentes depois que o helper de fake existe.
- T015 e T018 operam em superfícies distintas, mas a regeneração deve ocorrer antes da revisão final.

## Implementation Strategy

### MVP First

1. Completar Phase 1 e Phase 2.
2. Executar T006–T009 e observar o RED correto.
3. Implementar T010–T011.
4. Validar US1 antes de ampliar o escopo.

### Incremental Delivery

1. Fechar US2 com testes de lista preenchida e transição.
2. Regenerar screenshots para US3.
3. Rodar todos os checks locais, atualizar evidências e publicar PR.
4. Confirmar checks reais do GitHub e parar antes de qualquer merge.

## Validation Record

- RED observado antes da produção: 2 falhas nos casos parametrizados de alinhamento, causadas por `Qt.AlignCenter` e padding de 30 px.
- GREEN confirmado: 7 testes dedicados passaram nos viewports 1050×680 e 760×560.
- Regressões de Macros e capacidades: 21 testes passaram.
- Capturador executado e screenshots `4_macros.png`, `small_macros.png` e `preview.png` inspecionadas.
- Suíte completa: 551 testes passaram, sem falhas.
- Smoke Xvfb: 1 teste passou.
- `compileall` e `git diff --check` passaram.

A evidência é de software determinístico, sem validação física do Logitech G403
ou de uma sessão X11 real.
