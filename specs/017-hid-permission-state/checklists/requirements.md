# Requirements Checklist: CTA HID como estado contextual

**Feature**: issue #116
**Spec**: [../spec.md](../spec.md)
**Status**: Convergido localmente; aguardando PR/CI

## Critérios do issue

- [x] Estado `hid_available` confirmado mantém status verde e não exibe botão
  desabilitado.
- [x] Falta de permissão classificada como acionável exibe CTA clara e
  habilitada.
- [x] Causa não acionável mantém o motivo visível e oculta a CTA.
- [x] Estado sem `MouseCoreState` mantém aviso honesto e oculta a CTA.
- [x] Durante a operação assíncrona não é possível empilhar threads.
- [x] Após sucesso, a CTA é ocultada; após falha, só reaparece se a causa for
  acionável.
- [x] Fluxo polkit e a reavaliação de hardware permanecem preservados.
- [x] Dependência de remoção de glifos do #84 não é regredida.
- [x] Capturas desktop e 760×560 mostram a seção compacta.

## Evidências requeridas

- [x] Teste RED antes da mudança de produção: 3 falhas esperadas em 4 testes.
- [x] Testes focados GREEN com fakes: 20 testes passaram.
- [x] Suíte completa determinística: exit 0.
- [x] Smoke da UI via Xvfb: 1 teste OK.
- [x] `compileall` e `git diff --check`: OK.
- [ ] Três checks reais do CI verdes no commit final do PR.

## Revisão de constituição

- [x] Hardware continua sendo confirmado pelo core.
- [x] Estados conhecidos, desconhecidos e falhos continuam distintos.
- [x] Nenhum teste depende de hardware físico.
- [x] Toda regressão do issue tem teste que falha antes do fix e passa depois.
- [x] Nenhum domínio novo foi colocado na UI.
- [x] Mudança permanece mínima e rastreável à #116.
- [x] Claims finais distinguem evidência de software de validação física.
- [x] Copy e affordance seguem UX honesta em pt-BR.
