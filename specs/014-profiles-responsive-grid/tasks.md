# Tasks: Grid responsivo da página de Perfis

**Spec**: `specs/014-profiles-responsive-grid/spec.md`
**Plan**: `specs/014-profiles-responsive-grid/plan.md`
**Issue**: #100
**Status**: Concluído, CI verde

## Phase 1 - Specify

- [x] T001 Registrar o problema reproduzível, cenários e critérios de geometria
  em `spec.md`.
- [x] T002 Registrar causa provável, solução mínima e conformidade com a
  constituição em `plan.md`.
- [x] T003 Confirmar que a correção fica restrita ao sizing do container e não
  altera `ProfileStore` nem serviços de hardware.

## Phase 2 - Test-First

- [x] T004 Criar `tests/test_issue100_profiles_responsive.py` com configuração
  isolada, fakes do capturador e fluxo desktop → small.
- [x] T005 Executar os testes antes do fix e registrar RED: dois testes falharam
  com interseção entre `minecraft` e `default` e scrollbar horizontal visível.

## Phase 3 - Implement

- [x] T006 Fazer o wrapper preservar a altura mínima calculada pelo layout,
  permitindo rolagem vertical em vez de compressão das rows.
- [x] T007 Desabilitar a scrollbar horizontal do `QScrollArea` e confirmar que
  cards e controles continuam dentro da largura útil.

## Phase 4 - Verify

- [x] T008 Executar o teste novo em GREEN e os testes existentes de Perfis.
- [x] T009 Regenerar `5_perfis.png` e `small_perfis.png`, sem alterar telas não
  relacionadas.
- [x] T010 Executar suíte completa, smoke Xvfb, compileall e `git diff --check`.

## Phase 5 - Deliver

- [x] T011 Revisar diff, adicionar `.specify/feature.json` e criar commit
  convencional em inglês (`67b2a4f`).
- [x] T012 Fazer push e abrir PR vinculado à issue #100, sem merge
  ([#134](https://github.com/Base-Analitica/mouse-hub/pull/134)).
- [x] T013 Aguardar os checks reais de lint/testes, pacote `.deb` e smoke de UI;
  workflow `33253419583` passou nos três checks.
- [x] T014 Registrar o resultado final na spec e manter o PR aberto para o
  mantenedor.

## Notes

O teste RED reproduz a sequência usada pelo capturador oficial, inclusive a
transição da janela desktop para 760×560. A evidência é de software com Qt
offscreen e fakes, não uma medição física do hardware.
