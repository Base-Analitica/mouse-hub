# Pesquisa: cor semântica do valor CPS

## Escopo confirmado

A issue #80 é uma correção de apresentação na `AutoClickerPage`. O valor de
`self.cps_display` é construído em `app/mouse_hub_app.py` e hoje recebe
`COLORS['warning']` de forma incondicional. O domínio do CPS continua no
`AutoClickerEngine`, com contrato de 1 a 50, e não será alterado.

## Decisão 1: reutilizar `accent_light`

- **Decision**: trocar somente a cor do display para o token já existente
  `COLORS['accent_light']`.
- **Rationale**: `accent_light` já é o destaque visual normal da aplicação e
  não comunica warning, erro ou sucesso. O valor de CPS é a informação
  escaneável do controle, portanto merece destaque sem semântica de alerta.
- **Alternatives considered**: `text_primary` também seria neutro e legível,
  mas reduziria a diferenciação do valor principal. Criar um novo token seria
  mudança desnecessária para um problema que o tema já resolve.
- **Contrast check**: com os tokens atuais, `accent_light` tem contraste de
  7,34:1 em `bg_darkest`, 7,05:1 em `bg_dark` e 6,27:1 em `bg_card`, acima do
  mínimo de leitura usado pelo projeto.

## Decisão 2: teste dedicado offscreen

- **Decision**: criar `tests/test_issue80_autoclicker_cps_color.py` com uma
  página real e fakes existentes, sem hardware ou X11 real.
- **Rationale**: o contrato é específico da UI e precisa proteger tanto a cor
  quanto o comportamento de atualização do slider. Um arquivo dedicado deixa a
  rastreabilidade da issue explícita.
- **Alternatives considered**: colocar apenas uma asserção textual em
  `test_issue66_ui_craft.py` seria menor, mas não cobriria os valores de borda,
  a interação do slider e a preservação de warning real.

## Decisão 3: preservar warning por caminho real

- **Decision**: o teste de regressão também instanciará `SettingsPage` com um
  estado fake de permissão HID negada e verificará que o status de atenção
  continua usando `COLORS['warning']`.
- **Rationale**: assim a correção não prova apenas que a palavra `warning`
  sobrevive no fonte, mas que um estado de usuário que realmente requer atenção
  continua renderizado com o token semântico.
- **Limites**: não alterar a lógica de permissão, o texto do status ou qualquer
  outro uso de warning.

## Decisão 4: screenshots pelo pipeline oficial

- **Decision**: regenerar `3_clicker.png`, `small_clicker.png` e `preview.png`
  executando `scripts/capture_screenshots.py` duas vezes, comparando bytes e
  registrando dimensões e região de diferença contra `origin/main`.
- **Rationale**: o script já fornece o estado fake determinístico e é a fonte
  pública do QA visual. Não haverá edição manual de PNG.

## Incertezas resolvidas

Não há decisões de produto pendentes. A issue não muda limites, persistência,
engine, foco, capability gating, hardware ou APIs públicas.
