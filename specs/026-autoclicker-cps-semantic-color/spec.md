# Feature Specification: Cor semântica do valor CPS

**Feature Branch**: `026-autoclicker-cps-semantic-color`
**Created**: 2026-08-29
**Status**: Draft
**Issue**: #80
**Input**: Corrigir o uso permanente de `COLORS['warning']` no valor normal de CPS do Auto-Clicker.

## User Scenarios & Testing

### User Story 1 - Interpretar CPS como valor normal (Priority: P1)

Como usuário do Auto-Clicker, quero que o número de CPS configurado pareça um valor normal de configuração, para não interpretar a cor como um alerta quando nenhuma condição de atenção existe.

**Why this priority**: A cor é exibida no controle principal em todos os valores válidos de 1 a 50 CPS. Corrigir sua semântica remove um alerta falso sem mudar a operação do Auto-Clicker.

**Independent Test**: Construir a página do Auto-Clicker offscreen com fakes, inspecionar o estilo do display em valores de borda e intermediários, mover o slider e confirmar que o número permanece legível e não usa o token de warning.

**Acceptance Scenarios**:

1. **Given** o Auto-Clicker está em seu estado inicial com um CPS válido, **When** a página é exibida, **Then** o valor numérico usa uma cor neutra/de destaque não semântica de warning e continua acompanhado da unidade `CPS`.
2. **Given** o slider aceita valores entre 1 e 50, **When** o usuário muda o CPS para 1, 25 ou 50, **Then** o display atualiza o número e mantém a mesma cor normal, sem criar limiar ou aviso artificial.
3. **Given** a capacidade do Auto-Clicker está indisponível, **When** a página desabilita seus controles, **Then** a indisponibilidade continua sendo comunicada pelo hint próprio e não transforma o valor normal de CPS em warning.

---

### Edge Cases

- Os limites válidos 1 e 50 CPS devem usar a mesma cor normal do valor intermediário.
- A mudança do slider deve atualizar o display e o subtítulo do status sem alterar persistência, engine, foco ou seleção de botão.
- O estado de capacidade indisponível deve manter sua mensagem de causa separada do display numérico.
- Cores de warning existentes para estados reais de permissão/resultado não podem ser removidas ou substituídas por esta correção.
- A solução não deve depender de hardware, X11 real ou uma fonte/glyph externo.

## Requirements

### Functional Requirements

- **FR-001**: O display numérico de CPS na página do Auto-Clicker MUST usar um token visual normal (`accent_light`), e MUST NOT usar `COLORS['warning']` para os valores válidos de 1 a 50.
- **FR-002**: O display MUST continuar mostrando o valor atual do engine e a unidade `CPS`, atualizando quando o slider muda.
- **FR-003**: A implementação MUST NOT introduzir limiar, regra de risco ou novo estado semântico para CPS normal.
- **FR-004**: A correção MUST preservar o uso de `warning` em estados reais existentes da UI, incluindo mensagens de atenção da página de Configurações.
- **FR-005**: A mudança MUST permanecer restrita à apresentação do Auto-Clicker, sem alterar domínio, persistência, hardware, engine, foco ou gating de capacidades.
- **FR-006**: As screenshots públicas afetadas do Auto-Clicker MUST ser regeneradas pelo pipeline determinístico do projeto na mesma branch.
- **FR-007**: A implementação MUST incluir teste determinístico que falhe no estado atual e passe após a correção, sem hardware físico.

### Key Entities

- **Display de CPS**: valor numérico apresentado ao usuário para o CPS configurado no `AutoClickerEngine`; não é uma entidade persistida separada.
- **Token de cor**: entrada existente em `app.ui.theme.COLORS`; `accent_light` representa destaque visual normal e `warning` permanece reservado para atenção semântica.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Em 1, 25 e 50 CPS, o display usa `accent_light` ou outro token normal aprovado, e nenhum desses estados referencia o token `warning`.
- **SC-002**: O teste offscreen comprova que 1, 25 e 50 aparecem corretamente, que a unidade `CPS` permanece presente e que a mudança do slider atualiza o texto.
- **SC-003**: Pelo menos um estado de atenção real da UI continua usando o token `warning`, comprovando que a correção não remove sua disponibilidade semântica.
- **SC-004**: As capturas `3_clicker.png`, `small_clicker.png` e `preview.png` são reproduzidas duas vezes com bytes idênticos em ambiente determinístico; qualquer diferença visual fica restrita ao display de CPS.
- **SC-005**: Os testes dedicados, regressões completas, smoke Xvfb, compilação, verificação de diff, empacotamento `.deb` e os três jobs reais do CI passam no commit publicado.
- **SC-006**: Nenhum arquivo de core, plataforma ou persistência é alterado para atender esta issue.

## Assumptions

- O contrato atual do Auto-Clicker continua sendo 1–50 CPS, definido no core, e esta issue não altera seus limites.
- `accent_light` é um token já existente, legível nos dois viewports oficiais e apropriado para destacar um valor normal sem carregar semântica de warning.
- O hint de capacidade e as mensagens de Configurações continuam sendo fontes separadas para indisponibilidade e atenção.
- A validação usa PyQt5 5.15.11, `QT_QPA_PLATFORM=offscreen`, fakes existentes e o pipeline oficial de screenshots.
- A evidência de software não representa medição física do G403 nem disponibilidade de uma sessão X11 real.

## Scope Boundaries

- Não alterar o valor, o intervalo, a persistência ou o cálculo de CPS.
- Não implementar qualquer threshold de risco.
- Não redesenhar o card, os botões ou a disponibilidade do Auto-Clicker, que pertencem a outras issues.
- Não remover usos legítimos de `COLORS['warning']` em outras páginas.
