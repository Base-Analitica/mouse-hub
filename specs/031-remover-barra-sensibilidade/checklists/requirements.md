# Checklist de requisitos: issue #91

## Escopo

- [ ] A issue oficial #91 foi consultada.
- [ ] A mudança de produção está limitada ao `speedBar` decorativo.
- [ ] Nenhum arquivo de `mouse_hub/core/` ou `mouse_hub/platform/` foi alterado.
- [ ] Nenhuma segunda fonte de verdade ou indicador novo foi criado.

## Comportamento preservado

- [ ] O slider continua horizontal, com faixa 0–100 e os mesmos callbacks.
- [ ] As labels `Lento` e `Rápido` continuam visíveis.
- [ ] Valor, estado do sistema, `caps_hint` e gating continuam corretos.
- [ ] A seção de polling e suas mensagens continuam presentes.
- [ ] Construção em desktop e small não causa clipping ou erro.

## Regressão e evidências

- [ ] O teste dedicado falhou antes da implementação e passou depois.
- [ ] Testes focados e regressões de UI/capacidades passaram.
- [ ] A suíte completa passou.
- [ ] Smoke Xvfb passou.
- [ ] `compileall`, AST e `git diff --check` passaram.
- [ ] Pacote `.deb` foi construído e inspecionado.
- [ ] Capturas oficiais foram repetidas duas vezes e comparadas por bytes/dimensões.
- [ ] Diferenças das três imagens afetadas ficaram restritas à remoção esperada.
- [ ] Revisão independente não deixou achado sem tratamento.

## Entrega

- [ ] Commits convencionais e worktree limpo.
- [ ] PR referencia #91 e contém `Closes #91`.
- [ ] PR está aberto e não foi merged.
- [ ] Lint/testes determinísticos, smoke Xvfb e pacote `.deb` estão SUCCESS no HEAD final.
