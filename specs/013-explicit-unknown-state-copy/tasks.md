# Tasks: Cópia explícita para estado desconhecido

**Spec**: `specs/013-explicit-unknown-state-copy/spec.md`
**Plan**: `specs/013-explicit-unknown-state-copy/plan.md`
**Issue**: #110
**Status**: Concluído, CI verde

## Phase 1 - Specify

- [x] T001 Criar a spec com cenários de dashboard, heroes, input editável e
  screenshots em `spec.md`.
- [x] T002 Registrar no plano a solução mínima e a tabela dos oito princípios
  da constituição em `plan.md`.

## Phase 2 - Test-First

- [x] T003 Criar `tests/test_issue110_unknown_state_copy.py` com fakes e
  asserções para copy explícita, estilo neutro e separação do input.
- [x] T004 Executar o teste antes da implementação e registrar RED: os três
  testes falharam porque os displays exibiam `—` ou não tinham a constante de
  estado explícito.

## Phase 3 - Implement

- [x] T005 Adicionar `UNKNOWN_STATE_TEXT = "Aguardando leitura"` sem remover o
  placeholder `UNKNOWN_VALUE_TEXT` do input editável.
- [x] T006 Atualizar os cards do dashboard para mostrar copy explícita e cor
  neutra quando o valor aplicado for desconhecido.
- [x] T007 Atualizar os heroes de DPI e sensibilidade nos caminhos inicial,
  refresh, prévia, confirmação e invalidação, restaurando estilos semânticos
  para valores conhecidos.
- [x] T008 Atualizar as asserções de integração do issue #3 para o novo contrato
  visual, preservando a verificação do placeholder no input.

## Phase 4 - Verify

- [x] T009 Executar os testes dedicados e de integração em GREEN.
- [x] T010 Regenerar as screenshots afetadas do dashboard, DPI e sensibilidade
  em desktop, small e preview.
- [x] T011 Executar a suíte completa localmente; resultado: exit code 0.
- [x] T012 Executar smoke Xvfb, `compileall` e `git diff --check` após o último
  ajuste; smoke OK (1 teste), compileall OK e diff sem erros.

## Phase 5 - Deliver

- [x] T013 Revisar diff, adicionar a spec e `.specify/feature.json`, e criar
  commit convencional em inglês (`6d9a1a3`).
- [x] T014 Fazer push da branch e abrir PR vinculado à issue #110, sem merge
  ([#133](https://github.com/Base-Analitica/mouse-hub/pull/133)).
- [x] T015 Aguardar os checks reais de lint/testes, pacote `.deb` e smoke de UI;
  workflow `33252603466` passou nos três checks.
- [x] T016 Após CI verde, atualizar esta documentação com a evidência remota e
  manter o PR aberto para decisão do mantenedor.

## Notes

A validação local comprova o comportamento de software com fakes e Qt offscreen.
Ela não constitui medição física do G403 HERO nem validação de uma sessão X11
real.
