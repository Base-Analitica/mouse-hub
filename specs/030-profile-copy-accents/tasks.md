# Tasks: issue #97

## Spec e preparação

- [x] T001 Criar a especificação com escopo, requisitos, cenários e critérios de aceite.
- [x] T002 Criar plano, matriz da Constituição e matriz de rastreabilidade.
- [x] T003 Criar branch isolada `fix/profile-copy-accents` a partir de `origin/main`.
- [x] T004 Executar e registrar a suíte baseline antes do teste novo (544
      testes, exit 0, log `issue97-baseline-suite.log`).

## TDD

- [x] T005 Escrever teste RED para as strings acentuadas de leitura, aplicação e persistência.
- [x] T006 Executar o teste novo e confirmar falha pelos textos antigos, não por erro de teste (4 falhas esperadas e 1 cenário parcial verde).
- [x] T007 Atualizar assertions existentes sem enfraquecê-las.
- [x] T008 Alterar somente os literais de copy visível em `ProfilesPage`.
- [x] T009 Executar GREEN focado e confirmar os estados de sucesso, parcial, falha e configuração ilegível (25 testes, exit 0).

## Verificação local

- [ ] T010 Executar regressões de Perfis, capacidades e integração da UI.
- [ ] T011 Regenerar as três capturas oficiais duas vezes e comparar dimensões, regiões e bytes.
- [ ] T012 Executar suíte completa, smoke Xvfb, compileall, `git diff --check` e pacote `.deb`.
- [ ] T013 Fazer revisão read-only independente e resolver achados do escopo.

## Entrega

- [ ] T014 Atualizar esta matriz e o checklist com evidências observadas.
- [ ] T015 Commitar em commits convencionais e confirmar worktree limpo.
- [ ] T016 Publicar a branch e abrir PR com `Closes #97`, sem merge.
- [ ] T017 Confirmar os três checks reais do CI no HEAD final e registrar o resultado.

## Evidência TDD observada

- RED: `tests/test_issue97_profile_copy.py` falhou nos quatro textos ainda sem
  acento, com as mensagens antigas observadas nos widgets.
- GREEN: o mesmo teste e `tests/test_issue6_profiles_polling.py` passaram com
  25 testes após a troca dos cinco literais visíveis e das três assertions.
- O diff de produção contém somente os quatro pontos de copy previstos. Os
  detalhes de causa, estados e persistência permanecem exercitados pelos testes.
