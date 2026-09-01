---
description: "Tarefas do issue #80: cor semântica do valor CPS"
---

# Tasks: Cor semântica do valor CPS

**Input**: Design documents from `specs/026-autoclicker-cps-semantic-color/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`

**Scope**: corrigir apenas a cor normal do `cps_display`; não alterar domínio,
persistência, engine, foco, capability gating, hardware ou outros usos de warning.

## Phase 1: Setup

**Purpose**: confirmar isolamento e artefatos antes do código.

- [x] T001 [US1] Confirmar o worktree `/home/pedro/.jcode/scratch/issue80-cps-semantic-color` na branch `fix/autoclicker-cps-semantic-color`, com árvore limpa e base `origin/main` em `abad8b1`.
- [x] T002 [US1] Criar e revisar `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `checklists/requirements.md` e `.specify/feature.json` para `specs/026-autoclicker-cps-semantic-color/`.
- [x] T003 [US1] Executar `QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/ -q -rA` no baseline e registrar que os 553 testes passaram antes da mudança.

---

## Phase 2: Foundational

**Purpose**: este issue não possui infraestrutura nova; o tema e os fakes existentes são a fundação.

- [x] T004 [US1] Confirmar que `app/ui/theme.py` já fornece `COLORS['accent_light']` e `COLORS['warning']`, que `tests/fakes.py` não precisa de mudança e que nenhum novo pacote é necessário.

**Checkpoint**: a fundação é existente e o teste pode ser escrito diretamente contra a página real.

---

## Phase 3: User Story 1 - Interpretar CPS como valor normal (Priority: P1) 🎯 MVP

**Goal**: o display numérico usa destaque normal, não warning, sem mudar seu valor ou comportamento.

**Independent Test**: construir `AutoClickerPage` com fakes em offscreen, verificar a cor em 1, 25 e 50 CPS, mover o slider e confirmar unidade/status, além de verificar um warning real na `SettingsPage`.

### Tests for User Story 1

> Escrever primeiro e observar RED contra `COLORS['warning']` atual.

- [x] T005 [US1] Criar `tests/test_issue80_autoclicker_cps_color.py` com fixture de `QApplication`, `AutoClickerPage` real e os fakes determinísticos de UI já usados em `tests/test_issue7_ui_caps.py`, sem tocar em hardware; reutilizar o helper existente de `tests/test_hid_permission_helper.py` para a verificação da `SettingsPage`.
- [x] T006 [US1] Adicionar teste parametrizado para CPS `1`, `25` e `50` que exija `COLORS['accent_light']` no stylesheet de `page.cps_display` e rejeite `COLORS['warning']`, preservando o texto numérico.
- [x] T007 [US1] Adicionar teste de interação que mova `page.cps_slider` para `1`, `25` e `50`, verificando display, unidade `CPS` e subtítulo com o valor atualizado.
- [x] T008 [US1] Adicionar teste de capacidade indisponível que confirme os controles desabilitados, o hint de causa separado e a mesma cor normal do valor CPS.
- [x] T009 [US1] Adicionar teste de não regressão da `SettingsPage` com permissão HID negada, verificando que `_permission_status` permanece com `COLORS['warning']` e botão habilitado.
- [x] T010 [US1] Executar `QT_QPA_PLATFORM=offscreen python3 -m pytest -q tests/test_issue80_autoclicker_cps_color.py` e confirmar RED com falha causada exclusivamente pelo uso atual de `COLORS['warning']`; o RED observado foi 4 falhas de cor e 4 testes passantes.

### Implementation for User Story 1

- [x] T011 [US1] Alterar somente a declaração de estilo de `self.cps_display` em `app/mouse_hub_app.py` para usar `COLORS['accent_light']` no lugar de `COLORS['warning']`; não mudar `_on_cps`, limites, unidade ou outros usos de warning.
- [x] T012 [US1] Executar novamente `QT_QPA_PLATFORM=offscreen python3 -m pytest -q tests/test_issue80_autoclicker_cps_color.py` e confirmar GREEN em todos os testes dedicados: 8 passed.
- [x] T013 [US1] Executar regressões de UI/capability com `QT_QPA_PLATFORM=offscreen python3 -m pytest -q tests/test_issue7_ui_caps.py tests/test_issue66_ui_craft.py tests/test_hid_permission_helper.py`: 35 passed; combinado com a dedicação, 43 passed.

**Checkpoint**: a story é funcional, a cor normal não carrega warning e um warning real continua funcionando.

---

## Phase 4: Polish & Cross-Cutting Validation

**Purpose**: confirmar cada saída pública e a integração de entrega.

- [ ] T014 [US1] Executar `python3 scripts/capture_screenshots.py` duas vezes, conferir que `3_clicker.png`, `small_clicker.png` e `preview.png` têm bytes idênticos entre as execuções e registrar dimensões oficiais.
- [ ] T015 [US1] Comparar screenshots contra `origin/main`, verificando que mudanças de pixels ficam restritas ao display de CPS nas três imagens e não aparecem em outras telas.
- [ ] T016 [US1] Executar `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q -rA` e registrar contagem, falhas e erros completos.
- [ ] T017 [US1] Executar `xvfb-run -a env QT_QPA_PLATFORM=offscreen python3 -m unittest tests.smoke_ui_init`, `python3 -m compileall -q app mouse_hub tests scripts` e `git diff --check`.
- [ ] T018 [US1] Executar `packaging/deb/build_deb.sh` e verificar o `.deb` em ambiente limpo, incluindo launcher, fonte subset e arquivos do app.
- [ ] T019 [US1] Executar revisão read-only com agente autorizado, comparando `origin/main` ao HEAD, e corrigir qualquer achado Critical/Important antes da entrega.
- [ ] T020 [US1] Atualizar `spec.md`, `plan.md` e `tasks.md` somente com evidências observadas, marcar tarefas concluídas e registrar a matriz requisito→teste→resultado.
- [ ] T021 [US1] Fazer commits convencionais em inglês contendo código, teste, screenshots e artifacts Spec Kit; confirmar `git status` limpo e `git diff --check` sem saída.
- [ ] T022 [US1] Publicar `fix/autoclicker-cps-semantic-color`, abrir PR vinculado à issue #80 com `Closes #80`, aguardar os jobs reais de lint/testes, pacote `.deb` e smoke Xvfb, e manter o PR aberto sem merge.

---

## Dependencies & Execution Order

- T001–T004 devem estar concluídas antes dos testes.
- T005–T010 são a fase RED e devem preceder T011.
- T011 depende de T005–T010 e é a única mudança de produção prevista.
- T012–T013 são o gate GREEN local.
- T014–T018 são gates de saída e devem ocorrer antes de T021–T022.
- T019 pode ocorrer em paralelo com T014, mas qualquer achado bloqueia T020–T022.
- T020–T022 são sequenciais: documentar evidências, commit/push, então conferir CI real.

## Traceability

| Requisito | Tasks | Evidência esperada |
| --- | --- | --- |
| FR-001 / SC-001 | T006, T011, T012 | 1/25/50 usam accent_light e não warning |
| FR-002 / SC-002 | T007, T012, T013 | display, unidade e status atualizam |
| FR-003 | T011, T013, T019 | diff sem threshold ou regra nova |
| FR-004 / SC-003 | T009, T013 | SettingsPage continua warning em atenção real |
| FR-005 / SC-006 | T011, T015, T019 | somente UI/testes/docs/PNGs no diff |
| FR-006 / SC-004 | T014, T015 | capturas determinísticas e bbox restrito |
| FR-007 / SC-005 | T010, T012, T016–T018, T022 | RED/GREEN, suíte, smoke, package e CI |

## Implementation Strategy

1. Fechar setup e baseline.
2. Escrever testes dedicados e observar RED.
3. Fazer a troca de um único token e observar GREEN.
4. Validar interação, capability, warning real, screenshots, suíte, smoke e pacote.
5. Revisar, documentar, publicar PR e confirmar CI sem fazer merge.
