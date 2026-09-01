# Research: Hint de capacidade do Auto-Clicker visível

## Contexto observado

`AutoClickerPage._build()` cria `self.caps_hint` e configura `setWordWrap(True)`, mas não chama `layout.addWidget(self.caps_hint)`. A função `_sync_caps()` atualiza esse mesmo label com a disponibilidade e a causa retornadas pelo provider e também mantém o gating de `cps_slider`, botões e `toggle_btn`.

A ordem atual da página é: título, card de status do motor, `mc_status`, controles de CPS, seletor de botão e CTA. O melhor ponto para a explicação é logo depois de `mc_status` e antes de `cps_title`: a causa fica próxima aos controles sem entrar no card de status nem confundir capacidade do ambiente com foco do Minecraft.

O teste existente `tests/test_issue7_ui_caps.py` já verifica texto e gating, mas não verifica que o hint é um item efetivo do layout. O issue #78 precisa de uma regressão explícita para essa lacuna.

## Decisão 1: inserir o widget existente no layout

- **Decision**: adicionar `layout.addWidget(self.caps_hint)` imediatamente após `layout.addWidget(self.mc_status)`.
- **Rationale**: menor mudança possível; mantém o widget, o estilo, o word-wrap, a fonte da causa e o gating já implementados.
- **Alternatives considered**:
  - colocar o hint dentro do card de status: rejeitado porque capacidade do ambiente não é estado do motor;
  - adicionar o hint somente quando indisponível: rejeitado porque cria estrutura diferente e perde a confirmação discreta de capacidade disponível;
  - criar helper ou novo componente: rejeitado por aumentar escopo sem necessidade.

## Decisão 2: preservar a fonte e o copy atual

- **Decision**: não alterar `CapabilityModel`, `CapabilityState`, `_sync_caps()` ou as strings existentes neste issue.
- **Rationale**: #78 trata da visibilidade da explicação; #83 trata da remoção de jargão de implementação. Separar os PRs evita mega-PR e mantém cada regressão rastreável.
- **Alternatives considered**:
  - sanitizar `X11/XTest` no mesmo diff: rejeitado por sobrepor #83 e dificultar atribuição da regressão;
  - criar texto genérico novo: rejeitado porque esconderia a causa real exigida pelo issue.

## Decisão 3: teste dedicado com capability fake

- **Decision**: usar `CapabilityModel`/`CapabilityState` existentes e uma `AutoClickerPage` real, verificando índice no layout, texto, estados dos controles e independência de `mc_status`.
- **Rationale**: prova o comportamento observável sem depender de X11, XTest ou hardware físico.
- **Alternatives considered**:
  - teste textual do arquivo apenas: rejeitado porque não prova que o widget é visível;
  - smoke visual sem assert: rejeitado porque não garante a causa em estado indisponível;
  - mock da página: rejeitado porque não exercita o layout real.

## Escopo fora da feature

- Não alterar regras de foco, execução, timer ou clique.
- Não alterar textos de backend, que pertencem ao issue #83.
- Não tocar em `mouse_hub/core/`, protocolos HID++ ou persistência.
