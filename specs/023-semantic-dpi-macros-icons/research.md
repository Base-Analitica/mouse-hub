# Research: Ícones sem metáforas de mídia para DPI e Macros

## Contexto observado

`app/ui/icons.py` mantém um dicionário `_CODEPOINTS` com nomes semânticos e
carrega `app/ui/fonts/remixicon-subset.ttf` uma única vez. `SidebarButton`
renderiza a chave em 18 px, enquanto `DPIPage` e `MacrosPage` usam a mesma
chave em `icon_label()` com 24 px. Portanto, uma mudança no dicionário mantém a
consistência entre sidebar e heading sem tocar nos call sites.

O estado atual usa `ri-speed-line` (U+F177), visualmente fast-forward, para DPI,
e `ri-film-line` (U+ED21), visualmente filmstrip, para Macros. Esses são os dois
casos apontados pela issue #111.

## Decisão 1: glifo de DPI

- **Decision**: mapear `dpi` para `focus-3-line` (U+ED4C).
- **Rationale**: o alvo/crosshair comunica foco, precisão e sensor melhor que
  uma metáfora de reprodução de mídia e continua legível em 18 px.
- **Alternatives considered**: manter `speed-line`, usar `mouse-line` ou
  introduzir um SVG. Foram rejeitadas por preservarem a associação com mídia,
  duplicarem o ícone do Auto-Clicker ou aumentarem o escopo/complexidade.

## Decisão 2: glifo de Macros

- **Decision**: mapear `macros` para `keyboard-line` (U+EE75).
- **Rationale**: teclas representam a entrada automatizada por uma macro e
  eliminam a associação com vídeo. O codepoint existe na fonte Remix local
  usada para gerar o subset e permanece um único glifo vetorial.
- **Alternatives considered**: `keyboard-box-line` e `function-line`. Foram
  rejeitadas porque o primeiro perde presença no tamanho da sidebar e o segundo
  é menos imediatamente compreensível como teclas.

## Decisão 3: subset embutido

- **Decision**: regenerar o TTF com os 12 codepoints atuais mais U+ED4C e
  U+EE75, usando o `pyftsubset` do FontTools durante o desenvolvimento.
- **Rationale**: o runtime continua sem dependência nova e o asset permanece
  pequeno. A fonte completa disponível no ambiente local é apenas insumo de
  build e não será adicionada ao repositório.
- **Alternatives considered**: carregar a fonte completa via qtawesome ou
  depender de uma fonte instalada no sistema. Foram rejeitadas por introduzir
  dependência pesada, fragilidade de ambiente e regressão do fallback.

## Decisão 4: contrato de fallback

- **Decision**: manter `_family()`, `icon()` e `icon_label()` inalterados além do
  novo mapeamento. Testes usam `QRawFont.supportsCharacter()` para verificar que
  os codepoints chegaram ao subset e forçam `_FONT_FAMILY = ""` para verificar
  o retorno `None`.
- **Rationale**: a issue pede correção visual, não uma nova abstração. O
  contrato existente já permite que os chamadores permaneçam em texto puro.

## Insumos e licenciamento

A fonte Remix Icon local, versão 2.5.0, fornecida pelo pacote de desenvolvimento
qtawesome, foi consultada somente para a geração do subset. O projeto já contém
`app/ui/fonts/LICENSE-RemixIcon.txt`, que continua cobrindo o asset entregue.
Nenhum pacote local será adicionado às dependências de runtime ou ao repositório.
