---
description: "Tarefas do issue #81: microcopy de permissões HID"
---

# Tasks: Microcopy de permissões HID

**Input**: Design documents from `specs/027-hid-permission-microcopy/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`

**Scope**: trocar somente o texto informativo `hid_info`; preservar botão,
capabilities, autorização, hardware e regra udev.

## Phase 1: Setup

**Purpose**: confirmar isolamento, base e artefatos antes do teste.

- [x] T001 [US1] Confirmar o worktree `/home/pedro/.jcode/scratch/issue81-hid-microcopy` na branch `fix/hid-permission-microcopy`, baseado em `origin/main` no commit `abad8b1`.
- [x] T002 [US1] Criar e revisar `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `checklists/requirements.md` e `.specify/feature.json` para `specs/027-hid-permission-microcopy/`.
- [x] T003 [US1] Executar `QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/ -q -rA` no baseline; o log em `$JCODE_SCRATCH_DIR/issue81-baseline-suite.log` registrou 544 testes `PASSED` e exit code 0.

---

## Phase 2: Foundational

**Purpose**: usar o fluxo real já existente, sem infraestrutura nova.

- [x] T004 [US1] Confirmar no código que `hid_info` é um `QLabel` com `setWordWrap(True)`, que `_permission_btn` continua conectado a `_grant_hid_access()` e que `_sync_permission_ui()` permanece a fonte de verdade de `hid_available`. A inspeção confirmou os três contratos em `app/mouse_hub_app.py:2643-2681` e `:2722-2765`.

**Checkpoint**: a fundação existente é suficiente para testar a copy em uma `SettingsPage` real.

---

## Phase 3: User Story 1 - Entender e autorizar o acesso HID (Priority: P1) 🎯 MVP

**Goal**: a seção explica finalidade e próximo passo gráfico sem instrução obsoleta.

**Independent Test**: construir `SettingsPage` em offscreen com fakes, obter o
texto do `hid_info`, verificar termos obrigatórios/proibidos, estados do botão,
callback e geometria nos dois viewports.

### Tests for User Story 1

> Escrever primeiro e observar RED contra a copy que pede regra manual e terminal.

- [x] T005 [US1] Criar `tests/test_issue81_hid_permission_microcopy.py` com fixture de `QApplication`, `SettingsPage` real e fake state determinístico, sem hardware físico; manter o teste limitado à copy e aos invariantes do fluxo existente. O arquivo foi criado com cinco casos, incluindo os dois viewports oficiais.
- [x] T006 [US1] Adicionar teste que exija no texto de `hid_info` referência à finalidade de controle do DPI físico, ao Mouse Hub/aplicativo, à autorização administrativa e à instalação da regra necessária. Cobertura implementada em `test_hid_intro_explains_graphical_authorization_flow`.
- [x] T007 [US1] Adicionar asserts negativos que rejeitem `crie uma regra`, instruções de terminal, alteração manual de permissões e `:` final; verificar que o texto não afirma acesso concedido antecipadamente. O caso `test_hid_intro_removes_obsolete_manual_instructions_and_orphan_punctuation` cobre as proibições e a pontuação.
- [x] T008 [US1] Adicionar teste de regressão que preserve o texto/estado do botão, sua conexão com `_grant_hid_access()` e os estados de sucesso e atenção de `_sync_permission_ui()`. O caso `test_hid_permission_states_and_button_contract_remain_unchanged` cobre os estados do botão e o helper existente cobre o clique assíncrono.
- [x] T009 [US1] Adicionar teste parametrizado para 1050×680 e 760×560 que construa a página, aplique a largura oficial, processe eventos e confirme que `hid_info` permanece contido sem scrollbar horizontal ou clipping. O caso `test_hid_intro_fits_official_viewports` cobre os dois tamanhos.
- [x] T010 [US1] Executar `QT_QPA_PLATFORM=offscreen python3 -m pytest -q tests/test_issue81_hid_permission_microcopy.py` e confirmar RED atribuível à copy antiga, antes de alterar `app/mouse_hub_app.py`. O RED observado foi 2 falhas nos contratos de copy e 3 casos passantes.

### Implementation for User Story 1

- [x] T011 [US1] Alterar somente o literal de `hid_info` em `app/mouse_hub_app.py` para a copy aprovada: `Para controlar o DPI físico do mouse, o Mouse Hub precisa de acesso HID ao G403 HERO. Se faltar permissão de escrita, clique em “Conceder acesso ao hardware” para o aplicativo solicitar autorização administrativa e instalar a regra necessária.` A produção mudou somente nesse literal.
- [x] T012 [US1] Executar novamente o teste dedicado e confirmar GREEN em todos os casos, incluindo termos obrigatórios, proibições, callback/estados e os dois viewports. O resultado foi 5 passed.
- [x] T013 [US1] Executar regressões relacionadas de capabilities e SettingsPage: `QT_QPA_PLATFORM=offscreen python3 -m pytest -q tests/test_issue7_ui_caps.py tests/test_hid_permission_helper.py tests/test_issue3_ui_integration.py`. O resultado foi 51 passed; combinado com a dedicação, 56 passed.

**Checkpoint**: a copy orienta o fluxo gráfico e os contratos reais de capability/autorização permanecem inalterados.

---

## Phase 4: Polish & Cross-Cutting Validation

**Purpose**: confirmar cada saída pública e a integração de entrega.

- [ ] T014 [US1] Executar `python3 scripts/capture_screenshots.py` duas vezes, registrar as 15 imagens, dimensões oficiais e hashes idênticos das duas execuções; conferir especificamente `6_settings.png`, `small_settings.png` e `preview.png`.
- [ ] T015 [US1] Comparar as capturas do branch com a baseline `origin/main`, calcular bboxes de diferença e confirmar que mudanças ficam somente na seção de permissões HID das três imagens esperadas.
- [ ] T016 [US1] Executar `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q -rA` e registrar contagem, falhas e erros completos; nenhum teste pode falhar.
- [ ] T017 [US1] Executar `xvfb-run -a env QT_QPA_PLATFORM=offscreen python3 -m unittest tests.smoke_ui_init`, `python3 -m compileall -q app mouse_hub tests scripts` e `git diff --check`.
- [ ] T018 [US1] Executar `packaging/deb/build_deb.sh`, extrair o `.deb` em diretório limpo e verificar launcher, fonte subset, regra udev e código da aplicação presentes.
- [ ] T019 [US1] Executar revisão read-only com agente autorizado, comparando `origin/main` ao HEAD; corrigir qualquer achado Critical/Important antes da publicação.
- [ ] T020 [US1] Atualizar `spec.md`, `plan.md` e `tasks.md` somente com evidências observadas, marcando tarefas concluídas e preenchendo a matriz requisito→teste→resultado.
- [ ] T021 [US1] Fazer commits convencionais em inglês contendo código, teste, screenshots e artifacts Spec Kit; confirmar `git status` limpo e `git diff --check` sem saída.
- [ ] T022 [US1] Publicar `fix/hid-permission-microcopy`, abrir PR vinculado à issue #81 com `Closes #81`, aguardar lint/testes determinísticos, pacote `.deb` e smoke Xvfb, e manter o PR aberto sem merge.

---

## Dependencies & Execution Order

- T001–T004 devem estar concluídas antes dos testes.
- T005–T010 são a fase RED e devem preceder T011.
- T011 é a única mudança de produção prevista e depende de T005–T010.
- T012–T013 são o gate GREEN local.
- T014–T018 são gates de saída e devem ocorrer antes de T021–T022.
- T019 pode ocorrer em paralelo com T014, mas qualquer achado bloqueia T020–T022.
- T020–T022 são sequenciais: documentar evidências, commit/push, então conferir CI real.

## Traceability

| Requisito | Tasks | Evidência esperada |
| --- | --- | --- |
| FR-001 / SC-001 | T006, T011, T012 | finalidade DPI físico presente |
| FR-002 / SC-001 | T006, T011, T012 | autorização administrativa e regra necessária explicadas |
| FR-003 / SC-002 | T007, T011, T012 | terminal, alteração manual e regra criada pelo usuário ausentes |
| FR-004 / SC-002 | T007, T012 | sem `:` órfão e sem afirmação antecipada de sucesso |
| FR-005 / SC-003 | T008, T013, T019 | botão, callback, capabilities e estados reais preservados |
| FR-006 / SC-007 | T004, T011, T015, T017, T019 | diff restrito sem core/platform/persistência/hardware |
| FR-007 / SC-005 | T014, T015 | screenshots determinísticas e diferença restrita |
| FR-008 / SC-006 | T010, T012, T016–T018, T022 | RED/GREEN, suíte, smoke, pacote e CI |

## Implementation Strategy

1. Fechar setup, especificação e baseline.
2. Escrever os testes dedicados e observar RED.
3. Fazer a troca mínima do literal e observar GREEN.
4. Validar estados, geometria, screenshots, suíte, smoke e pacote.
5. Revisar, documentar, publicar PR e confirmar CI sem fazer merge.
