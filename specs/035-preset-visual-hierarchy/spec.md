# Especificação: hierarquia visual dos presets de DPI

**Issue:** [#94](https://github.com/Base-Analitica/mouse-hub/issues/94)
**Status:** implementação em validação

## Contexto

Dashboard e Controle de DPI exibem presets como um único `QPushButton` com duas linhas de texto. O mesmo peso tipográfico é aplicado ao nome/contexto e ao valor, dificultando a leitura rápida do DPI acionável.

## Objetivo

Dar hierarquia real entre contexto e valor sem transformar o alvo em um card aninhado, mantendo a mesma linguagem visual nas duas telas e preservando os contratos de hardware, callbacks e fonte de verdade.

## Histórias de usuário

### US-001: identificar o DPI rapidamente

Como usuário em modo Operate, quero reconhecer o valor `NNN DPI` antes do nome do preset para escolher uma configuração sem ler o botão inteiro.

**Aceitação:** o valor usa uma hierarquia tipográfica mais forte e o contexto permanece legível, porém secundário.

### US-002: reconhecer a mesma linguagem nas duas telas

Como usuário, quero que Ações Rápidas do Dashboard e Presets Rápidos de DPI tenham a mesma composição, para que o significado visual seja previsível.

**Aceitação:** os dois grupos usam o mesmo componente e os mesmos tokens de estilo.

### US-003: usar presets sem risco de regressão

Como usuário, quero continuar acionando um preset com um único clique, sem alteração de valores ou comportamento de hardware.

**Aceitação:** os valores continuam vindo de `DPI_PRESETS`, os callbacks existentes permanecem conectados e cada clique mantém o limite de uma operação HID.

### US-004: usar a tela pequena

Como usuário em uma janela de 760×560, quero que os presets continuem compactos e sem overflow horizontal.

**Aceitação:** Dashboard e DPI cabem em seus containers scrolláveis oficiais sem barra horizontal ou clipping dos labels.

## Requisitos funcionais

- **FR-001:** Cada preset MUST renderizar nome/contexto e valor em labels independentes.
- **FR-002:** O label do valor MUST ter hierarquia maior que o label do nome usando somente tokens existentes de tipografia e cor.
- **FR-003:** Dashboard e DPI MUST usar a mesma composição reutilizável e o mesmo estilo base.
- **FR-004:** Os valores MUST ser derivados de `mouse_hub.core.constants.DPI_PRESETS`; nenhum valor duplicado deve ser criado na UI.
- **FR-005:** A composição MUST manter um único `QPushButton` como alvo clicável, sem botão ou card aninhado.
- **FR-006:** Os callbacks `_quick_dpi` e `_set_preset` MUST continuar recebendo os valores corretos, sem tocar a separação de responsabilidades do core.
- **FR-007:** A composição MUST caber nos viewports oficiais 1050×680 e 760×560 sem barra horizontal ou clipping.
- **FR-008:** A mudança MUST preservar a semântica visual uniforme, sem cores diferentes por jogo/preset.
- **FR-009:** Screenshots de Dashboard e DPI, incluindo `preview.png`, MUST ser regenerados e versionados.
- **FR-010:** Testes dedicados, regressões, smoke, compilação, empacotamento e os três jobs reais de CI MUST passar antes da entrega.

## Fora de escopo

- Não alterar `mouse_hub/core`, protocolos HID++, persistência, limites de DPI ou automação.
- Não criar cores semânticas por jogo.
- Não mudar o fluxo de aplicação, confirmação ou atualização do estado físico.
- Não fazer merge do PR sem autorização explícita do mantenedor.

## Casos de borda

- `Max Speed` deve exibir `25600 DPI` sem clipping.
- Nomes com duas palavras devem permanecer legíveis no viewport small.
- Labels filhos não podem capturar o mouse no lugar do botão.
- O estado da fonte de verdade deve continuar refletido mesmo se um preset for alterado no core.

## Critérios de sucesso

- **SC-001:** Teste dedicado comprova labels separados e hierarquia tipográfica.
- **SC-002:** Teste dedicado comprova o componente compartilhado nas duas páginas.
- **SC-003:** Teste dedicado comprova os cinco pares nome/valor contra `DPI_PRESETS`.
- **SC-004:** Testes de integração comprovam acionamento único e callbacks existentes.
- **SC-005:** Testes de layout comprovam contenção nos dois viewports e ausência de barra horizontal.
- **SC-006:** Duas capturas oficiais consecutivas são byte a byte idênticas.
- **SC-007:** Screenshots modificadas ficam limitadas ao Dashboard, DPI e mosaico `preview.png`.
- **SC-008:** Suíte completa, smoke Xvfb, compilação, pacote `.deb` e lint passam.
- **SC-009:** Os três checks reais do CI (`Lint de sintaxe e testes determinísticos`, `Smoke da UI (Xvfb)` e `Pacote .deb`) ficam verdes no HEAD final.
