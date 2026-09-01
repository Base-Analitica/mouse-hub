# Requirements Checklist: Labels persistentes no formulário de Perfis

**Spec**: `../spec.md`
**Issue**: #114
**Status**: Em implementação

## Spec Quality

- [x] O problema do placeholder/sufixo como identificação única está descrito.
- [x] Os cenários cobrem formulário vazio e campos preenchidos.
- [x] Os critérios cobrem labels, buddies, nomes acessíveis e unidades.
- [x] O escopo preserva a correção responsiva da issue #100.
- [x] O escopo não inclui mudanças de domínio, hardware ou dependências novas.

## Constitution and Architecture

- [x] O teste usa Qt offscreen, `ProfileStore` isolado e nenhum hardware.
- [x] A mudança não adiciona regra de domínio na UI.
- [x] `ProfileStore` e serviços de aplicação permanecem intactos.
- [x] O plano registra os oito princípios da constituição.
- [x] A dependência do PR #134 está explícita, sem duplicar seu diff.

## Test-Driven Development

- [x] Teste dedicado escrito antes da implementação.
- [x] RED observado: quatro testes falharam por ausência dos labels públicos.
- [x] GREEN observado após a implementação.

## Verification

- [x] Testes dedicados de labels, acessibilidade e limites passam.
- [x] Capturador oficial executado para as imagens afetadas.
- [x] Suíte determinística completa passa.
- [x] Smoke Xvfb, compileall e `git diff --check` passam.
- [ ] CI real do PR está verde.
- [ ] PR aberto e não mergeado.

## Traceability

- [x] FR-001 e FR-002 têm teste de texto, visibilidade, buddy e acessibilidade.
- [x] FR-003 tem teste dos sufixos `DPI` e `%`.
- [x] FR-004 tem teste nas larguras 562 e 862.
- [x] FR-005 é protegido por manter a construção e os serviços existentes.
- [x] FR-006 tem teste Qt determinístico dedicado.
- [x] FR-007 tem conferência dos caminhos de screenshot alterados.
- [ ] FR-008 depende dos checks reais e da abertura do PR.
