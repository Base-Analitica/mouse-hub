# Feature Specification: Espaçamento semântico dos botões do Auto-Clicker

**Feature Branch**: `fix/autoclicker-label-spacing`

**Created**: 2026-08-29

**Status**: Especificação aprovada; implementação TDD pendente

**Input**: Issue #79, `[P3][UI] Remover espaçamento fantasma dos botões de seleção do Auto-Clicker`

## User Scenarios & Testing

### User Story 1 - Ler os botões sem whitespace invisível (Priority: P1)

Quando a pessoa escolhe o botão do mouse para o Auto-Clicker, os rótulos devem ser compostos apenas pelo nome visível. Espaços usados por um ícone que não existe não devem alterar a posição óptica nem o texto acessível do botão.

**Why this priority**: A seleção é uma ação central da página. Um rótulo que depende de caracteres invisíveis é uma pequena falha de acabamento e dificulta manter a composição consistente.

**Independent Test**: Construir uma `AutoClickerPage` real com um controlador fake, inspecionar os três `QPushButton` de `btn_buttons` e verificar texto exato, ordem, estado ativo e comportamento de clique.

**Acceptance Scenarios**:

1. **Given** a página do Auto-Clicker, **When** os botões de seleção são construídos, **Then** seus textos são exatamente `Esquerdo`, `Meio` e `Direito`, sem espaços no início, no fim ou duplicados.
2. **Given** o botão central ativo, **When** a página é renderizada, **Then** os três botões preservam quantidade, ordem, altura, estilo ativo e spacing do layout.
3. **Given** um botão não ativo, **When** a pessoa o seleciona, **Then** a escolha continua atualizando o controlador e o estilo ativo sem depender do texto do botão.

---

### User Story 2 - Preservar leitura responsiva (Priority: P2)

A remoção dos espaços não deve criar uma nova composição específica para um viewport. Os três botões continuam visíveis e equilibrados no desktop e no small.

**Why this priority**: `small_clicker.png` é o cenário mais estreito e torna qualquer composição baseada em padding textual mais perceptível.

**Independent Test**: Dimensionar a página em 1050×680 e 760×560, processar o layout e verificar limites, ordem e ausência de sobreposição. Reproduzir as capturas oficiais.

**Acceptance Scenarios**:

1. **Given** qualquer viewport oficial, **When** a página é renderizada, **Then** cada botão permanece dentro da largura da página e todos continuam acessíveis.
2. **Given** a captura oficial, **When** o script é executado duas vezes, **Then** os PNGs afetados são byte a byte idênticos em cada execução.

## Edge Cases

- O controlador pode iniciar com `button` 1, 2 ou 3; exatamente um botão deve continuar ativo.
- A capacidade do Auto-Clicker pode estar indisponível; o gating dos botões permanece inalterado e o texto dos rótulos continua limpo.
- O botão pode ser selecionado por clique ou pelo teste de página; ambos os caminhos continuam usando `_set_button()`.
- Se no futuro um ícone for adotado, ele deve ser um elemento vetorial explícito com spacing de layout, não whitespace manual. Este issue não adiciona esse ícone.
- A mudança não altera a copy do hint de capacidade, o card de status, CPS, timer ou segurança.

## Requirements

### Functional Requirements

- **FR-001**: Os três botões do seletor MUST expor exatamente os nomes `Esquerdo`, `Meio` e `Direito`, sem espaços artificiais derivados de um ícone vazio.
- **FR-002**: A implementação MUST preservar a ordem, o número de botões, o `btn_row.setSpacing(12)`, a altura e os estilos de seleção existentes.
- **FR-003**: A implementação MUST preservar o fluxo de clique que atualiza `ac.button` e o estilo ativo por meio de `_set_button()`.
- **FR-004**: O gating de capacidade MUST continuar habilitando ou desabilitando os mesmos três widgets junto com o restante do Auto-Clicker.
- **FR-005**: Testes determinísticos MUST cobrir texto exato, ausência de whitespace, estado ativo, seleção e os viewports oficiais, sem hardware.
- **FR-006**: `3_clicker.png`, `small_clicker.png` e `preview.png` MUST ser regenerados quando a captura oficial demonstrar a mudança.
- **FR-007**: A implementação MUST não criar ícone novo, regra de domínio, alteração de hardware/protocolo, dependência ou lógica paralela.

## Key Entities

Esta correção não introduz entidade de domínio, persistência ou API nova.

| Elemento | Tipo existente | Papel | Invariante |
|---|---|---|---|
| `btn_buttons` | lista de pares `(QPushButton, int)` | Expor os controles e seus códigos | Mantém três itens na ordem esquerdo, meio, direito |
| `QPushButton.text()` | texto de UI | Apresentar o nome do botão | Não contém whitespace de composição |
| `ac.button` | estado do controlador fake/real | Fonte da seleção ativa | Continua sendo atualizado por `_set_button()` |
| `btn_row` | `QHBoxLayout` | Controlar composição horizontal | Mantém spacing explícito de 12 px |

## Success Criteria

### Measurable Outcomes

- **SC-001**: Uma regressão determinística comprova que os três textos são exatamente os nomes esperados e não contêm whitespace prefixado, sufixado ou duplicado.
- **SC-002**: Os testes comprovam que a seleção de cada botão ainda atualiza `ac.button` e deixa somente o botão escolhido com estilo ativo.
- **SC-003**: Os botões permanecem contidos, sem sobreposição e sem overflow horizontal em 1050×680 e 760×560.
- **SC-004**: A captura oficial é repetível em duas execuções, com as três imagens afetadas idênticas entre si por execução repetida.
- **SC-005**: A suíte determinística, o smoke Xvfb, o pacote `.deb`, `compileall`, `git diff --check`, revisão read-only e os três checks reais do PR passam sem merge.

## Assumptions

- A lacuna está em `app/mouse_hub_app.py`, na construção `QPushButton(f"{icon}  {name}")` com `icon` vazio.
- O spacing visual deve continuar vindo de `btn_row.setSpacing(12)` e das propriedades existentes do QPushButton.
- Não é necessário introduzir ícone para satisfazer este issue.
- A validação de software usa fakes, Qt offscreen e Xvfb. Ela não constitui validação física do G403 HERO ou de uma sessão X11 real.
- A remoção de jargão e a disponibilidade do Auto-Clicker pertencem aos issues #83 e #78, respectivamente.

## Scope Boundary

O diff deve ficar restrito à montagem dos rótulos, seus testes, screenshots afetados e artifacts Spec Kit. Não alterar core, protocolo, capacidade, segurança, timer ou o restante da página.
