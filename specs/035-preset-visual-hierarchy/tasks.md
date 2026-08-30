# Tarefas: hierarquia visual dos presets

Formato: `[ID] [P?] Descrição`

## Preparação

- [x] T001 Confirmar issue #94, Constituição e escopo sem tocar core/hardware.
- [x] T002 Criar worktree isolado `fix/preset-visual-hierarchy` a partir de `origin/main`.
- [x] T003 Executar baseline completo: 544 testes, exit 0.

## TDD

- [x] T004 Escrever `tests/test_issue94_preset_hierarchy.py` cobrindo composição, valores, clique e viewports.
- [x] T005 Observar RED por ausência de `PresetButton`.
- [x] T006 Implementar `PresetButton` e a tabela derivada de `DPI_PRESETS`.
- [x] T007 Atualizar Dashboard e DPI preservando callbacks e contratos existentes.
- [x] T008 Reexecutar GREEN e regressões focadas.

## Artefatos e validação

- [x] T009 Regenerar screenshots oficiais.
- [x] T010 Repetir captura em diretórios temporários e confirmar igualdade byte a byte.
- [x] T011 Confirmar que somente Dashboard, DPI e `preview.png` mudaram contra `origin/main`.
- [x] T012 Executar suíte completa pós-implementação: **551 testes**, exit 0.
- [x] T013 Executar smoke Xvfb, compileall, diff check e teste de pacote: smoke 1 OK e pacote 7 passed.

## Entrega

- [x] T014 Atualizar este registro com as contagens finais e evidências locais.
- [x] T015 Commitar a mudança em branch isolada: `b51e35d`.
- [ ] T016 Publicar branch e abrir PR com `Closes #94`.
- [ ] T017 Confirmar os três jobs reais do CI no SHA final.
- [x] T018 Não fazer merge sem autorização explícita; nenhum merge foi executado.

## Evidências observadas

- O diff visual contra `origin/main` ficou restrito a `0_dashboard.png`,
  `1_dpi.png`, `small_dashboard.png`, `small_dpi.png` e `preview.png`.
  Uma alteração incidental em `small_clicker.png` foi identificada e restaurada
  antes do commit.
- Duas capturas oficiais em diretórios temporários produziram os 15 PNGs com
  igualdade byte a byte; dimensões desktop `1050x680`, small `760x560` e
  `preview.png` `2130x2770` foram preservadas.
- O teste dedicado passou com 7 casos, as regressões focadas com 32 casos e a
  suíte completa pós-implementação passou com 551 casos.
- `compileall`, `git diff --check`, smoke Xvfb e `tests/test_deb_packaging.py`
  passaram. Nenhum arquivo de `mouse_hub/core` ou `mouse_hub/platform` foi
  alterado.
- O PR e os três checks remotos ainda não existem para esta branch. T016 e
  T017 continuam pendentes até o push e a confirmação no SHA final.
