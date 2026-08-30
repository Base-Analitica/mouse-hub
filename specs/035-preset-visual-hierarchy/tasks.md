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
- [ ] T011 Confirmar que somente Dashboard, DPI e `preview.png` mudaram contra `origin/main`.
- [ ] T012 Executar suíte completa pós-implementação.
- [ ] T013 Executar smoke Xvfb, compileall, diff check e teste de pacote.

## Entrega

- [ ] T014 Atualizar este registro com as contagens finais e evidências.
- [ ] T015 Commitar a mudança em branch isolada.
- [ ] T016 Publicar branch e abrir PR com `Closes #94`.
- [ ] T017 Confirmar os três jobs reais do CI no SHA final.
- [ ] T018 Não fazer merge sem autorização explícita.
