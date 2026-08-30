# Requirements Checklist: cards de Perfis (#85/#86)

**Purpose**: Revisão de qualidade dos requisitos antes da implementação e da entrega.
**Created**: 2026-08-30
**Feature**: [spec.md](../spec.md)
**Review Ownership**: checklist de revisão, não substitui os testes de implementação.

## Rastreabilidade e escopo

- [x] CHK001 As quatro chaves oficiais e seus labels de apresentação estão definidos sem ambiguidade. A tabela está na spec e no teste dedicado.
- [x] CHK002 O fallback para perfis customizados e chaves desconhecidas está mensurável e coberto pelo teste dedicado.
- [x] CHK003 A spec separa explicitamente identidade persistida de label visual; callbacks e `profile_cards` são verificados com os objetos originais.
- [x] CHK004 A spec proíbe alterações no core, platform, schema e hardware; o diff observado não contém `mouse_hub/core` nem `mouse_hub/platform`.

## Estados e layout

- [x] CHK005 O estado ativo é definido por estado confirmado, sem inferência por default; a matriz dedicada cobre desconhecido, ativo e troca.
- [x] CHK006 O comportamento inativo não deixa header visualmente vazio; o título ocupa o header e o placeholder é rejeitado pelo teste.
- [x] CHK007 Os viewports 1050×680 e 760×560 têm critérios observáveis de contenção, ausência de overlap/h-scrollbar e alinhamento.
- [x] CHK008 A remoção do placeholder não exige ícone, emoji ou nova dependência; o diff de produção não adiciona nenhum desses elementos.

## Verificação e entrega

- [x] CHK009 Existe teste offscreen que falha no baseline e cobre cada requisito funcional local da feature; RED foi observado com 4 pass e 4 fail, e GREEN com 8 pass.
- [x] CHK010 As screenshots, dimensões, determinismo e bboxes estão definidos e foram verificados: 15/15 idênticas em duas capturas.
- [x] CHK011 Os gates locais e os três checks reais do CI estão nomeados exatamente na spec, no plano e no quickstart; os gates locais passaram e o CI remoto ainda aguarda PR.
- [ ] CHK012 O PR permanece aberto e não merged, conforme a governança do projeto. Ainda não há PR para esta feature.

## Notas

- A checklist registra somente observações reproduzidas. A revisão independente, o commit dos PNGs, o PR e a confirmação dos três checks remotos continuam pendentes.
