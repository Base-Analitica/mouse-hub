# Tasks: Nomes de apresentação e cabeçalho dos cards de Perfis

**Input**: Documentos em `specs/034-profile-card-labels/`
**Branch**: `fix/profile-card-labels-empty-header`
**Issues**: [#85](https://github.com/Base-Analitica/mouse-hub/issues/85) e [#86](https://github.com/Base-Analitica/mouse-hub/issues/86)

## Phase 1: Setup e baseline

- [x] T001 Confirmar aprovação do desenho combinado, branch isolada baseada em `origin/main` e worktree limpo.
- [x] T002 Executar `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q -rA` no baseline e registrar exit code, contagem e log fora do repositório: 544 passed, exit 0.
- [x] T003 Revisar issue #85, issue #86, Constituição, `spec.md` e `plan.md`; confirmar que o diff permitido é UI, teste, três PNGs e docs Spec Kit.

## Phase 2: User Story 1 — labels de apresentação (#85)

**Goal**: Presets oficiais exibem labels humanos sem alterar chaves persistidas e perfis customizados mantêm seus nomes.

**Independent Test**: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue85_86_profile_cards.py -q`.

- [x] T004 Criar `tests/test_issue85_86_profile_cards.py` com `QApplication`, `ProfileStore` temporário e helpers para localizar o título real de cada card.
- [x] T005 Escrever primeiro os testes da tabela `minecraft → Minecraft`, `csgo → CS:GO`, `fortnite → Fortnite`, `default → Padrão` e do fallback literal de nomes customizados/desconhecidos.
- [x] T006 Testar que `profile_cards` continua indexado pelas chaves internas e que os callbacks de Aplicar/Editar recebem o perfil original, não o label.
- [x] T007 Executar o teste dedicado antes da mudança de produção e registrar RED reproduzível: 4 testes passaram e 4 falharam nos contratos ausentes.
- [x] T008 Adicionar o mapa/helper de display somente na UI e renderizar o título apresentado, preservando `ProfileStore` e os valores persistidos.
- [x] T009 Reexecutar os testes de labels e identidade e registrar GREEN: 8 testes passaram.

## Phase 3: User Story 2 — cards sem header vazio (#86)

**Goal**: O card inativo não reserva uma linha vazia, enquanto o badge ativo continua honesto e claro.

- [x] T010 Adicionar testes de composição que rejeitem `ic = QLabel("")`, contem o título no header e confirmem ausência de QLabel vazio visível no cabeçalho inativo.
- [x] T011 Adicionar a matriz de estados desconhecido, ativo, troca de ativo e estado não correspondente, verificando `✔ Ativo`, visibilidade e estilo.
- [x] T012 Adicionar testes parametrizados para 1050×680 e 760×560: contenção, ausência de overlap/h-scrollbar e alturas coerentes dos cards.
- [x] T013 Executar RED específico de #86 antes de editar produção: os contratos de composição e estado falharam de forma reproduzível.
- [x] T014 Remover o placeholder, fundir título e badge no header e tornar o badge condicionalmente visível, sem mudar `active_profile()` ou o grid.
- [x] T015 Reexecutar a matriz de estados e geometria e registrar GREEN: 8 testes dedicados passaram.

## Phase 4: Regressões, capturas e gates locais

- [x] T016 Rodar regressões de Perfis/config/UI: `tests/test_issue6_profiles_polling.py`, `tests/test_config_profiles.py`, `tests/test_issue66_ui_craft.py` e `tests/test_issue3_ui_integration.py`; todas terminaram com exit 0.
- [x] T017 Confirmar por inspeção e diff que nenhum arquivo em `mouse_hub/core` ou `mouse_hub/platform` mudou e que a persistência continua byte/semânticamente compatível.
- [x] T018 Executar o capturador oficial duas vezes em diretórios temporários e comparar os 15 PNGs por bytes antes de atualizar os artefatos versionados; 15/15 foram idênticos.
- [x] T019 Verificar dimensões `5_perfis.png` 1050×680, `small_perfis.png` 760×560 e `preview.png` 2130×2770; comparar bboxes contra `origin/main` e aceitar somente as regiões de Perfis.
- [ ] T020 Copiar e commitar somente `5_perfis.png`, `small_perfis.png` e `preview.png` após a verificação de determinismo/diff. A cópia foi feita; o commit será realizado após a revisão.
- [x] T021 Executar smoke Xvfb, `python3 -m compileall -q app mouse_hub tests scripts`, `git diff --check` e `python3 -m pytest tests/test_deb_packaging.py -q -rA`; todos terminaram com exit 0.
- [x] T022 Executar a suíte completa `QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/ -q -rA`; 552 testes passaram com exit 0. Log: `/home/pedro/.jcode/scratch/issue85-86-full-suite.log`.

## Phase 5: Revisão, documentação e entrega

- [ ] T023 Solicitar revisão independente read-only contra `origin/main...HEAD`, cobrindo FR/SC, Constituição, identidade interna, estados ativos, conflitos e ausência de core/platform.
- [ ] T024 Corrigir achados funcionais ou lacunas de cobertura e repetir todos os gates afetados.
- [ ] T025 Atualizar `spec.md`, `plan.md`, `tasks.md`, `research.md`, `quickstart.md` e `checklists/requirements.md` somente com evidências observadas; esta atualização local será completada após a revisão.
- [ ] T026 Commitar em inglês, confirmar worktree da issue e worktree principal limpos, e manter o diff mínimo.
- [ ] T027 Publicar `fix/profile-card-labels-empty-header` e abrir PR com `Closes #85` e `Closes #86`, descrição pt-BR, testes e riscos, sem merge.
- [ ] T028 Confirmar no HEAD final exatamente os três checks reais do CI em `SUCCESS`: lint/testes determinísticos, smoke Xvfb e pacote `.deb`.
- [ ] T029 Fazer verificação final de SHA local/remoto, PR `OPEN`, não draft e não merged, corpo com os dois `Closes`, worktrees limpos e matriz FR/SC completa.

## Requirement Traceability

| Requisito | Tarefas e evidências |
| --- | --- |
| FR-001 / SC-001 | T004–T005, T008–T009 |
| FR-002 / SC-001 | T005, T008–T009 |
| FR-003 / SC-003 | T006, T016–T017, T029 |
| FR-004 / SC-003 | T006, T016, T023–T029 |
| FR-005 / SC-002 | T010, T013–T015, T017 |
| FR-006 / SC-004 | T011, T013–T015 |
| FR-007 / SC-005 | T012, T015, T019, T021–T022 |
| FR-008 | T003, T017, T023, T029 |
| FR-009 / SC-006 | T004–T007, T010–T015 |
| FR-010 / SC-007 / SC-008 | T018–T020 |
| FR-011 / SC-009 / SC-010 | T016–T029 |

## Dependencies and Order

- T001–T003 são pré-requisitos de confiança e não alteram produção.
- T004–T007 devem terminar antes de T008 para preservar o RED de #85.
- T010–T013 devem ser escritos e observados antes de T014 para preservar o RED de #86.
- T009 e T015–T017 formam o GREEN e as regressões de comportamento.
- T018–T022 dependem do GREEN e produzem os artefatos públicos e gates locais.
- T023–T029 dependem dos gates locais e não fazem merge.

## Observed Evidence

- O desenho combinado foi aprovado explicitamente pelo usuário em 2026-08-30.
- O baseline em `origin/main` passou com 544 testes e exit 0 antes dos testes novos. Log: `/home/pedro/.jcode/scratch/issue85-86-baseline-suite.log`.
- O teste dedicado passou pelo ciclo TDD: RED reproduzível (4 pass, 4 fail), seguido de GREEN com 8 pass.
- A implementação final está nos commits `7875fdb` (teste) e `322ec7e` (produção). O diff de produção é limitado à projeção visual de `ProfilesPage`.
- As regressões de Perfis/config/UI, smoke Xvfb, compileall, `git diff --check`, empacotamento Debian (7 testes) e a suíte completa (552 testes) terminaram com exit 0.
- Duas capturas oficiais em diretórios temporários produziram 15/15 PNGs byte a byte idênticos. As dimensões oficiais foram preservadas e, contra `origin/main`, somente `5_perfis.png`, `small_perfis.png` e `preview.png` mudaram nas regiões esperadas.
- Os três PNGs afetados já foram copiados para o worktree, mas ainda não estão commitados. Revisão independente, PR e checks remotos permanecem pendentes.
