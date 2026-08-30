# Requirements Checklist: cards de Perfis (#85/#86)

**Purpose**: Revisão de qualidade dos requisitos antes da implementação e da entrega.
**Created**: 2026-08-30
**Feature**: [spec.md](../spec.md)
**Review Ownership**: checklist de revisão, não substitui os testes de implementação.

## Rastreabilidade e escopo

- [ ] CHK001 As quatro chaves oficiais e seus labels de apresentação estão definidos sem ambiguidade.
- [ ] CHK002 O fallback para perfis customizados e chaves desconhecidas está mensurável.
- [ ] CHK003 A spec separa explicitamente identidade persistida de label visual.
- [ ] CHK004 A spec proíbe alterações no core, platform, schema e hardware.

## Estados e layout

- [ ] CHK005 O estado ativo é definido por estado confirmado, sem inferência por default.
- [ ] CHK006 O comportamento inativo não deixa header visualmente vazio.
- [ ] CHK007 Os viewports 1050×680 e 760×560 têm critérios observáveis de contenção e alinhamento.
- [ ] CHK008 A remoção do placeholder não exige ícone, emoji ou nova dependência.

## Verificação e entrega

- [ ] CHK009 Existe teste offscreen que falha no baseline e cobre cada requisito funcional.
- [ ] CHK010 As screenshots, dimensões, determinismo e bboxes estão definidos.
- [ ] CHK011 Os gates locais e os três checks reais do CI estão nomeados exatamente.
- [ ] CHK012 O PR permanece aberto e não merged, conforme a governança do projeto.

## Notas

- Marcar somente após a revisão correspondente. Não usar este checklist para antecipar resultados de testes.
