# Tasks: Card do Auto-Clicker sem coluna de ícone vazia

**Input**: Documentos em `specs/033-autoclicker-empty-icon/`
**Branch**: `fix/remove-autoclicker-empty-icon`
**Issue**: [#77](https://github.com/Base-Analitica/mouse-hub/issues/77)

## Phase 1: Setup e baseline

- [x] T001 Confirmar que a branch parte de `origin/main`, que o worktree da issue 77 está limpo e que o worktree principal permanece sem alterações.
- [x] T002 Executar `QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/ -q -rA` no baseline e registrar exit code, contagem e log fora do repositório.
- [x] T003 Revisar Constituição, `spec.md` e `plan.md`, confirmar que o diff permitido é `app/mouse_hub_app.py`, teste dedicado, três PNGs e artefatos Spec Kit.

## Phase 2: User Story 1 — status sem espaço morto

**Goal**: O card parado e o card exibido nos dois viewports não contêm label vazio nem coluna estrutural anterior ao texto.

**Independent Test**: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue77_autoclicker_empty_icon.py -q` com 1050×680 e 760×560.

- [x] T004 Criar `tests/test_issue77_autoclicker_empty_icon.py` com fixture `QApplication`, `FakeAc`, `FakeSvc` e helpers de geometria, sem alterar produção.
- [x] T005 Escrever primeiro os testes para estado parado, ausência de `QLabel` vazio, dois labels textuais, alinhamento e contenção nos dois viewports.
- [x] T006 Executar o teste dedicado antes da mudança de produção e registrar RED por placeholder ainda presente ou referências residuais.
- [x] T007 Remover de `app/mouse_hub_app.py` a criação/adição do `status_icon` vazio e adicionar o layout `info` diretamente ao `status_frame`, sem mudar estilos ou textos.
- [x] T008 Remover todas as chamadas restantes a `status_icon` em `_toggle()` e `_update()`, mantendo as transições textuais e o estado real do motor.
- [x] T009 Executar os testes da User Story 1 novamente e registrar GREEN com os dois viewports.

## Phase 3: User Story 2 — estados do motor preservados

**Goal**: A limpeza visual não quebra `stopped`, `running`, `blocked_by_focus` ou `failed`, nem os caminhos de iniciar/parar.

**Independent Test**: O teste dedicado injeta cada `state.value`, chama `_update()` e exercita `_toggle()` com fakes determinísticos.

- [x] T010 Adicionar antes da edição de produção as asserções de título/subtítulo para os quatro estados e de ausência de `AttributeError` em `_toggle()`.
- [x] T011 Executar novamente o RED específico dos estados, confirmando que os testes são capazes de detectar referências ao widget removido.
- [x] T012 Executar GREEN para os estados, verificando `Auto-Clicker Desligado`, `Auto-Clicker Ativo!`, `Aguardando jogo em foco...` e `Auto-Clicker com erro` com suas mensagens auxiliares.
- [x] T013 Rodar regressões `tests/test_issue5_autoclicker.py`, `tests/test_issue7_ui_caps.py` e `tests/test_issue66_ui_craft.py`.

## Phase 4: User Story 3 — capturas e validação de integração

**Goal**: As imagens públicas mostram o card corrigido e nenhuma página não relacionada muda.

- [x] T014 Executar `scripts/capture_screenshots.py` duas vezes em diretórios temporários e comparar as 15 PNGs por bytes antes de copiar artefatos.
- [x] T015 Verificar dimensões 1050×680 para `3_clicker.png`, 760×560 para `small_clicker.png` e 2130×2770 para `preview.png`; comparar bboxes contra `origin/main` e aceitar somente as regiões previstas.
- [x] T016 Confirmar por `git diff --name-only origin/main...HEAD` e `git diff --check` que não há mudança em `mouse_hub/core` ou `mouse_hub/platform` nem whitespace inválido.
- [x] T017 Executar `xvfb-run -a env QT_QPA_PLATFORM=offscreen python3 -m unittest tests.smoke_ui_init` e `python3 -m compileall -q app mouse_hub tests scripts`.
- [x] T018 Executar `python3 -m pytest tests/test_deb_packaging.py -q -rA` e a suíte completa `QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/ -q -rA`.

## Phase 5: Revisão e entrega

- [ ] T019 Solicitar revisão independente read-only contra `origin/main...HEAD`, com FR/SC, Constituição, conflitos nos PRs Auto-Clicker existentes e ausência de core/platform.
- [ ] T020 Corrigir achados Critical/Important e reforçar qualquer teste que não cubra um requisito explícito; repetir os gates afetados.
- [ ] T021 Atualizar `spec.md`, `plan.md`, `tasks.md`, `quickstart.md` e `checklists/requirements.md` apenas com evidências observadas.
- [ ] T022 Commitar em inglês, confirmar worktree da issue 77 e worktree principal limpos, e preservar o diff mínimo.
- [ ] T023 Publicar `fix/remove-autoclicker-empty-icon` e abrir PR com `Closes #77`, descrição pt-BR, testes e riscos, sem merge.
- [ ] T024 Confirmar no HEAD final exatamente os três checks reais do CI em `SUCCESS`.
- [ ] T025 Fazer verificação final de SHA local/remoto, PR `OPEN`, não draft e não merged, corpo com `Closes #77`, worktrees limpos e matriz FR/SC completa.

## Requirement Traceability

| Requisito | Tarefas e evidências |
| --- | --- |
| FR-001 / SC-001 | T004–T009, T014–T015 |
| FR-002 | T005, T009, T014–T015 |
| FR-003 | T008, T010–T012, T016 |
| FR-004 / SC-002 | T010–T012 |
| FR-005 | T013, T016–T018 |
| FR-006 | T003, T007–T008, T016, T019, T025 |
| FR-007 / SC-003 | T004–T006, T010–T012 |
| FR-008 / SC-004 / SC-005 | T014–T015 |
| FR-009 / SC-006 / SC-007 | T016–T025 |

## Dependencies and Order

- T001–T003 são pré-requisitos de confiança e não alteram produção.
- T004–T006 devem terminar antes de T007–T008 para preservar o RED.
- T010–T011 devem ser escritos e observados no RED antes de qualquer alteração de produção que remova as referências.
- T009 e T012–T013 dependem do fix e formam o GREEN/regressão.
- T014–T018 dependem de todo o GREEN e produzem os artefatos públicos.
- T019–T025 dependem dos gates locais e não fazem merge.

## Observed Evidence

- Especificação aprovada explicitamente pelo usuário em 2026-08-30.
- Branch `fix/remove-autoclicker-empty-icon` criada a partir de `origin/main` no worktree isolado; o baseline completo passou com exit 0 e o log foi mantido fora do repositório.
- O teste dedicado foi escrito antes da edição de produção e o RED reproduzível teve 8 falhas por encontrar a composição antiga/referências `status_icon`.
- A implementação mínima removeu apenas o placeholder e suas seis atualizações, mantendo textos, estados, gating, estilos e core; o teste dedicado passou nos dois viewports e as regressões passaram (62 testes).
- Duas execuções do capturador oficial produziram 15/15 PNGs byte a byte idênticas; as versões publicadas foram atualizadas somente para `3_clicker.png`, `small_clicker.png` e `preview.png`, com dimensões 1050×680, 760×560 e 2130×2770. As outras 12 capturas ficaram inalteradas.
- Smoke Xvfb passou (1 teste), compileall passou, diff-check passou, pacote Debian passou (7 testes) e a suíte final passou com 552 testes; o baseline passou com 544 testes.
