# Tasks: Status local inequívoco do dispositivo

**Spec**: `specs/016-local-device-status/spec.md`
**Plan**: `specs/016-local-device-status/plan.md`
**Issue**: #115
**Status**: Em implementação

## Phase 1 - Specify

- [x] T001 Registrar a matriz de estados, cenários e critérios de copy local em
  `spec.md`.
- [x] T002 Registrar a mudança mínima, os riscos e a conformidade com a
  constituição em `plan.md`.
- [x] T003 Criar o checklist de requisitos em
  `checklists/requirements.md`.

## Phase 2 - Test-First

- [x] T004 Criar teste dedicado para os três estados da sidebar, independência
  de DPI e dimensões small.
- [x] T005 Executar o teste antes do fix e registrar RED pelas strings vagas.

## Phase 3 - Implement

- [x] T006 Substituir os textos globais por copy específica do G403 e do mouse
  detectado, preservando as cores existentes.
- [x] T007 Garantir que a matriz continue dependendo apenas de
  `mouse_detected`/`hid_available`, sem mudar o core ou o hotplug.

## Phase 4 - Verify

- [x] T008 Executar o teste dedicado em GREEN e atualizar regressões de
  capabilities/hotplug.
- [x] T009 Regenerar screenshots desktop, small e preview e revisar somente os
  arquivos afetados.
- [x] T010 Executar suíte completa, smoke Xvfb, compileall e `git diff --check`.

## Phase 5 - Deliver

- [ ] T011 Revisar diff, atualizar `.specify/feature.json` e criar commit
  convencional em inglês.
- [ ] T012 Fazer push e abrir PR vinculado à issue #115, sem merge.
- [ ] T013 Aguardar os checks reais de lint/testes, pacote `.deb` e smoke de UI.
- [ ] T014 Registrar a validação final na spec/checklist e manter o PR aberto
  para o mantenedor.

## Notes

A validação usa fakes e Qt offscreen. Ela comprova o comportamento da aplicação,
não a conexão física ou as permissões do G403 HERO.
