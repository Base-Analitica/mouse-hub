# Feature Specification: Perfis — reflow responsivo, sem overlap nem h-scrollbar

**Feature Branch**: `fix/profiles-reflow-760`

**Created**: 2026-08-29

**Status**: Draft

**Input**: User description: "Issue #100 — `small_perfis.png` mostra
segunda linha de cards começando antes do fim da primeira, cards
cobrindo botões `Editar`, formulário começando antes do fim da grade e
scrollbar horizontal em 760×560. Contradiz o contrato da issue #66."

## Diagnóstico (medido, não presumido)

Em largura útil ~760px, três colunas de cards (mínimo 140px + espaçamento
16px + margens 24px) NÃO cabem no viewport do scroll (~562px):
`QGridLayout` mantém 3 colunas e o estado transitório de relayout produz
o frame capturado: widget 570px > viewport 562px (h-bar pisca), cards
sobrepostos e formulário subindo sobre a grade. Em geometria assentada
o overlap desaparece — o bug é o estado de relayout capturado, visível
no artefato que serve de prova visual.

## Correção

- **Reflow por largura**: o número de colunas passa a derivar da largura
  disponível (`_columns_for_width`): 3 colunas só quando couberem
  (3×140 + 2×16 ≤ largura útil); 2 colunas abaixo disso; 1 coluna em
  larguras muito estreitas.
- `_reload()` reavalia as colunas; `resizeEvent`/`showEvent` re-montam a
  grade quando o número de colunas muda (barato: poucos cards).
- **Nada é escondido**: todos os cards, `Aplicar`/`Editar` e o heading
  "Criar / Editar Perfil" permanecem visíveis e separados.

## Acceptance Criteria

- em 760×560, nenhum card/controle sobrepõe outro (geometria medida no
  MESMO estado transitorio da captura: um processEvents após
  `_switch_page`);
- `Aplicar` e `Editar` de todos os cards integralmente visíveis;
- heading `Criar / Editar Perfil` visível e abaixo do fim da grade
  (top ≥ grid bottom);
- sem scrollbar horizontal (h-bar maximum == 0) já no primeiro
  processEvents;
- desktop 1050×680 permanece com 3 colunas e sem overlap;
- `5_perfis.png` e `small_perfis.png` regeneradas na mesma PR;
- CI verde.

## Principles Check

| Princípio | Aplicação |
| --- | --- |
| Menor mudança completa | reflow de colunas; zero mudança de dados |
| Craft responsivo | colunas derivadas da largura real, não fixas |
| Dupla verificação | teste mede geometria no estado de captura |
| Estado honesto | nenhum conteúdo escondido |
