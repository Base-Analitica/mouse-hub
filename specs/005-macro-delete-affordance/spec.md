# Feature Specification: Botão de excluir macro com affordance real

**Feature Branch**: `fix/macro-delete-affordance`

**Created**: 2026-08-29

**Status**: Draft

**Input**: User description: "Issue #88 — ação de exclusão criada como
`QPushButton("")` 32×32 sem texto, ícone nem tooltip: alvo destrutivo
visível apenas como caixa vazia. Affordance inexistente; usuário pode
clicar sem compreender a ação."

## Decisões

- **Rótulo textual "Excluir"** em vez de ícone: o subset embutido de
  ícones (Remix, 2,7 KB) não inclui glifo de lixeira; adicionar um
  glifo novo expandiria o bundle só para isto. O contrato de
  `app/ui/icons.py` é "ícone indisponível nunca derruba a UI" — texto
  puro é o fallback legítimo e, aqui, é a solução primária.
- Botão 80×32 (mesmo tamanho do "Play"), tooltip
  "Excluir esta macro (ação destrutiva)", `accessibleName`
  ("Excluir macro {nome}") e `accessibleDescription`.
- Hover/focus ganham borda + texto vermelhos — mas a função já é
  compreensível SEM depender da cor (rótulo sempre presente).
- **Semântica de persistência inalterada**: continua `me.delete(name)`
  com re-render da lista.

## Acceptance Criteria

- botão de excluir nunca aparece vazio (rótulo permanente);
- função compreensível antes do clique (tooltip + rótulo);
- ação identificável sem depender exclusivamente da cor;
- teste offscreen cria macro e verifica representação visual/acessível;
- pipeline de screenshots passa a ter estado de QA com lista NÃO vazia
  (`qa_macros.png`, `small_qa_macros.png`);
- CI verde.

## Principles Check

| Princípio | Aplicação |
| --- | --- |
| UX honesta | ação destrutiva declarada antes do clique |
| Menor mudança completa | 1 botão + constantes + estado de QA no pipeline |
| Estado honesto | nenhuma mudança de comportamento de dados |
| Dupla verificação | 5 testes novos + artefato visual QA |
