# Feature Specification: Densidade adaptativa do log do Dashboard

**Feature Branch**: `fix/dashboard-empty-log-density`

**Created**: 2026-08-29

**Status**: Ready for planning

**Input**: Issue #106, `[P2][UI] Log de Atividade vazio mantém card alto e força scroll desnecessário`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver um Dashboard vazio sem área morta (Priority: P1)

Quando o Dashboard ainda não tem atividades, a pessoa deve encontrar a mensagem de estado vazio logo abaixo do título do log, em uma superfície compacta. A tela não deve reservar uma grande área que sugira conteúdo ausente.

**Why this priority**: O estado vazio é a primeira experiência da tela e atualmente consome espaço útil sem entregar informação proporcional.

**Independent Test**: Abrir o Dashboard sem atividades e verificar que a mensagem continua visível em um bloco compacto, sem o grande espaço reservado observado nas capturas atuais.

**Acceptance Scenarios**:

1. **Given** o Dashboard sem atividades, **When** a tela é exibida, **Then** o log apresenta a mensagem de estado vazio em uma área compacta próxima ao título.
2. **Given** o Dashboard em uma janela de 760×560 sem atividades, **When** a tela é exibida, **Then** o estado vazio não exige rolagem adicional causada apenas pela altura do log.

---

### User Story 2 - Continuar usando o log quando há atividades (Priority: P1)

Quando uma ação do aplicativo gera uma entrada, o log deve crescer para uma área adequada ao conteúdo e continuar permitindo a leitura das entradas recentes. A compactação do estado vazio não pode esconder, cortar ou remover atividades reais.

**Why this priority**: O log precisa continuar útil exatamente quando deixa de estar vazio, sem trocar uma área morta por uma área insuficiente.

**Independent Test**: Inserir uma ou várias atividades e verificar que as entradas aparecem, que o componente deixa de usar a densidade do estado vazio e que uma lista longa permanece navegável.

**Acceptance Scenarios**:

1. **Given** o Dashboard vazio, **When** uma atividade é registrada, **Then** a entrada aparece e a superfície do log assume a densidade normal de conteúdo.
2. **Given** o log com mais entradas do que sua área visível, **When** a lista é consultada, **Then** as entradas continuam acessíveis por rolagem interna sem expandir a página indefinidamente.

---

### User Story 3 - Manter a mesma semântica em diferentes tamanhos (Priority: P2)

A relação entre título, estado vazio e conteúdo do log deve permanecer intencional tanto na captura desktop quanto na captura small. A mudança de densidade não deve alterar o texto nem a forma de registrar atividades.

**Why this priority**: A issue foi observada nos dois viewports, e uma correção que funciona apenas no desktop deixaria a experiência inconsistente.

**Independent Test**: Capturar o Dashboard em 1050×680 e 760×560 no estado vazio e confirmar que os dois viewports mostram o mesmo estado, com espaçamento compacto e sem conteúdo cortado.

**Acceptance Scenarios**:

1. **Given** o Dashboard sem atividades, **When** ele é capturado nos dois viewports oficiais, **Then** o título e a mensagem formam um bloco contínuo com densidade equivalente.
2. **Given** o Dashboard com atividades, **When** ele é aberto nos dois viewports, **Then** as entradas permanecem legíveis e a navegação da tela continua utilizável.

## Edge Cases

- A mensagem de placeholder não deve ser tratada como uma atividade persistida.
- Ao remover ou limpar todas as atividades, o log deve retornar à densidade compacta do estado vazio.
- Uma atividade muito longa deve continuar legível sem aumentar a página indefinidamente.
- O estado vazio não pode alterar o texto ou registrar uma atividade por efeito colateral.
- A transição entre vazio e preenchido deve preservar o título, a ordem das entradas e o comportamento de rolagem.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O Dashboard MUST apresentar o estado vazio do Log de Atividade em uma área compacta, suficiente para a mensagem completa.
- **FR-002**: O Dashboard MUST manter a mensagem de estado vazio próxima ao título `Log de Atividade`, sem grande área vertical intermediária.
- **FR-003**: O Log de Atividade MUST assumir uma área adequada ao conteúdo quando existir ao menos uma entrada real.
- **FR-004**: O Log de Atividade MUST manter todas as entradas acessíveis quando o conteúdo exceder a área visível.
- **FR-005**: A transição entre estado vazio e preenchido MUST preservar o texto, a ordem e o registro já existente das atividades.
- **FR-006**: A remoção de todas as entradas MUST retornar o componente ao estado vazio compacto.
- **FR-007**: A semântica de densidade MUST ser equivalente nos viewports oficiais desktop e small.
- **FR-008**: A mudança MUST preservar as demais áreas do Dashboard e não criar rolagem de página causada somente pelo estado vazio do log.

### Key Entities *(include if feature involves data)*

- **Log de Atividade**: Superfície de leitura que apresenta as ações registradas pela sessão atual, podendo estar vazia ou conter uma sequência ordenada de entradas.
- **Estado vazio**: Representação do log sem entradas reais, composta pela mensagem orientativa existente.
- **Entrada de atividade**: Registro textual de uma ação executada pelo aplicativo, preservando a ordem em que foi adicionada.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No estado vazio, a altura visual do log é reduzida em relação à implementação atual e permanece suficiente para exibir integralmente a mensagem orientativa.
- **SC-002**: Em 760×560, o Dashboard vazio não exige rolagem vertical adicional causada exclusivamente pelo Log de Atividade.
- **SC-003**: Após registrar atividades, 100% das entradas adicionadas permanecem recuperáveis na superfície do log, inclusive quando excedem a área visível.
- **SC-004**: As capturas desktop e small exibem o mesmo texto e a mesma relação espacial entre o título e o estado vazio.
- **SC-005**: Os testes determinísticos de regressão cobrem a transição vazio → preenchido e a preservação do comportamento existente do registro.

## Assumptions

- O Dashboard já possui uma única superfície de leitura para atividades e uma mensagem de estado vazio existente.
- A issue não solicita persistência de atividades, alteração de texto ou novo mecanismo de filtragem.
- A altura normal usada atualmente para conteúdo real é adequada e pode continuar sendo o limite de leitura do componente.
- A rolagem interna existente é suficiente para listas maiores, sem necessidade de criar uma nova tela ou modelo de dados.
- Os viewports oficiais para validação visual permanecem 1050×680 e 760×560.
