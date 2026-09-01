# Requirements Checklist: Status de Macros orientado à tarefa

**Feature**: issue #113
**Spec**: [../spec.md](../spec.md)
**Status**: Convergido localmente; aguardando PR/CI

## Critérios do issue

- [x] Mensagem disponível não expõe `X11`, `XRecord`, `XTest` ou backend.
- [x] Mensagem indisponível continua clara e explica a consequência para o
  usuário.
- [x] Mensagem de início não usa jargão de implementação.
- [x] Falha técnica é traduzida antes de chegar ao status operacional.
- [x] Disponibilidade real e gating dos controles permanecem inalterados.
- [x] Copy cabe em desktop e 760×560.
- [x] Screenshots de Macros e preview são regeneradas.

## Evidências requeridas

- [x] Teste RED antes da mudança de produção: 4 falhas esperadas.
- [x] Testes focados GREEN com fakes: 26 testes passaram.
- [x] Suíte completa determinística: exit 0.
- [x] Smoke da UI via Xvfb: 1 teste OK.
- [x] `compileall` e `git diff --check`.
- [ ] Três checks reais do CI verdes no commit final do PR.

## Revisão de constituição

- [x] Nenhuma operação de hardware foi alterada.
- [x] A capacidade continua vindo do modelo real.
- [x] Nenhum teste depende de hardware ou sessão gráfica real.
- [x] A regressão tem teste que falha antes do fix e passa depois.
- [x] Nenhuma regra de domínio foi colocada na UI.
- [x] A mudança permanece mínima e rastreável à #113.
- [x] Claims finais distinguem software fakeado de validação física.
- [x] Copy e affordance seguem UX honesta em pt-BR.
