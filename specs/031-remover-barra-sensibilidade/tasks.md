# Tasks: remover a barra decorativa de Sensibilidade

**Spec:** `specs/031-remover-barra-sensibilidade/spec.md`  
**Branch:** `fix/remove-sensitivity-decorative-bar`

## Preparação

- [x] T001 Confirmar worktree isolado, branch baseada em `origin/main` e árvore limpa.
- [x] T002 Executar a suíte baseline completa antes do teste novo e registrar contagem e exit code (544 testes, exit 0).
- [x] T003 Atualizar `.specify/feature.json` para apontar para esta feature e revisar a spec, o plano e o checklist.

## TDD e implementação

- [x] T004 Escrever `tests/test_issue91_sensitivity_bar.py` com teste offscreen que exige ausência do `QFrame#speedBar`, preserva o `QSlider` horizontal de 0–100, os sinais de preview/commit, as labels `Lento`/`Rápido`, o estado e o polling.
- [x] T005 Executar o teste novo no baseline e registrar RED causado pela existência do widget `speedBar` (2 falhas parametrizadas, sem erro de infraestrutura).
- [x] T006 Remover somente a construção, stylesheet e adição do `speedBar` em `SensitivityPage._build`.
- [ ] T007 Executar GREEN focado e regressões de Sensibilidade, capacidades e integração da UI.

## Verificação visual e integração

- [ ] T008 Executar `python3 scripts/capture_screenshots.py` duas vezes em diretórios temporários e comparar bytes, dimensões e bboxes de `2_sens.png`, `small_sens.png` e `preview.png`.
- [ ] T009 Executar suíte completa, smoke Xvfb, `compileall`, AST, `git diff --check` e empacotamento `.deb`.
- [ ] T010 Fazer revisão independente read-only, resolver qualquer achado e atualizar matriz de rastreabilidade.

## Entrega

- [ ] T011 Atualizar spec, plano, tasks e checklist com evidências observadas.
- [ ] T012 Commitar em commits convencionais e confirmar worktree limpo.
- [ ] T013 Publicar a branch e abrir PR com `Closes #91`, sem merge.
- [ ] T014 Confirmar no HEAD final os três checks reais do CI, marcar SC-008 e registrar os links.

## Critérios de conclusão

A feature só pode ser declarada concluída quando T004–T014 tiverem evidência
observada. A validação local sob fakes não será descrita como teste do G403 físico.
