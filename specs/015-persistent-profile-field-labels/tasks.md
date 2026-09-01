# Tasks: Labels persistentes no formulário de Perfis

**Spec**: `specs/015-persistent-profile-field-labels/spec.md`
**Plan**: `specs/015-persistent-profile-field-labels/plan.md`
**Issue**: #114
**Status**: Em implementação

## Phase 1 - Specify

- [x] T001 Registrar o problema, cenários, critérios de acessibilidade e
  responsividade em `spec.md`.
- [x] T002 Registrar a solução mínima, dependência do PR #134 e conformidade com
  os oito princípios em `plan.md`.
- [x] T003 Criar o checklist de requisitos em
  `checklists/requirements.md`.

## Phase 2 - Test-First

- [x] T004 Criar `tests/test_issue114_profiles_field_labels.py` com configuração
  isolada, campos preenchidos, buddies, nomes acessíveis e larguras 562/862.
- [x] T005 Executar os testes antes do fix e registrar RED: quatro testes
  falharam porque os labels públicos ainda não existiam em `ProfilesPage`.

## Phase 3 - Implement

- [x] T006 Criar labels persistentes para nome, DPI e Sensibilidade e associá-los
  aos controles com `QLabel.setBuddy`.
- [x] T007 Definir nomes acessíveis equivalentes nos três controles e posicionar
  labels acima dos campos sem remover sufixos ou alterar serviços.

## Phase 4 - Verify

- [x] T008 Executar o teste novo em GREEN nas larguras small e desktop.
- [x] T009 Regenerar o capturador oficial e conferir as imagens afetadas:
  `5_perfis.png`, `small_perfis.png` e `preview.png`.
- [x] T010 Executar suíte completa, smoke Xvfb, compileall e `git diff --check`.

## Phase 5 - Deliver

- [ ] T011 Revisar diff, forçar `.specify/feature.json` e criar commit
  convencional em inglês.
- [ ] T012 Fazer push e abrir PR #114 vinculado à issue, com base no PR #134 e
  sem merge.
- [ ] T013 Aguardar os checks reais de lint/testes, pacote `.deb` e smoke de UI.
- [ ] T014 Registrar a validação final na spec/checklist e manter o PR aberto
  para o mantenedor.

## Notes

O teste RED foi executado antes da implementação. A validação local usa Qt
offscreen e configuração temporária, portanto prova o comportamento do software
e não uma medição física do G403 HERO.
