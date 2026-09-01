# Feature Specification: Estado explícito do formulário de perfis

**Feature Branch**: `019-formulario-perfis-modo`

**Created**: 2026-08-29

**Status**: Implemented locally; pending PR/CI

**Input**: Issue #112 — `[P2][UX] Formulário de Perfis não distingue visualmente criação de edição`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Criar um perfil sem ambiguidade (Priority: P1)

Quando a pessoa abre a tela de Perfis sem ter selecionado um perfil, ela identifica imediatamente que está preenchendo um novo perfil e encontra apenas ações pertinentes à criação.

**Why this priority**: O estado inicial é o primeiro contato com o formulário. Uma indicação incorreta de edição pode levar a pessoa a acreditar que alterará um perfil existente ou que há uma operação pendente.

**Independent Test**: Abrir a tela sem iniciar uma edição e verificar o título do formulário, as ações disponíveis e os valores iniciais, sem precisar clicar em um card.

**Acceptance Scenarios**:

1. **Given** a tela de Perfis aberta sem uma edição em andamento, **When** a pessoa observa o formulário, **Then** o título informa `Criar Perfil`.
2. **Given** o formulário no modo de criação, **When** a pessoa observa as ações, **Then** não há uma ação apresentada como cancelamento de uma edição inexistente.

---

### User Story 2 - Editar um perfil identificado (Priority: P1)

Quando a pessoa escolhe editar um card, o formulário deixa claro qual perfil está sendo alterado e carrega os valores persistidos desse perfil.

**Why this priority**: Identificar o alvo da edição evita alterações acidentais e torna a relação entre card e formulário visível sem depender da memória dos cliques.

**Independent Test**: Selecionar um perfil conhecido para edição e verificar título, identificação, valores e ação de cancelamento.

**Acceptance Scenarios**:

1. **Given** um perfil persistido, **When** a pessoa escolhe `Editar`, **Then** o formulário informa que está editando aquele perfil e carrega seu nome, DPI e sensibilidade.
2. **Given** o formulário em modo de edição, **When** a pessoa observa as ações, **Then** uma ação `Cancelar` fica disponível para sair da edição.

---

### User Story 3 - Sair da edição sem alterar a persistência (Priority: P1)

Quando a pessoa cancela uma edição, o formulário volta ao estado de criação e nenhum valor do perfil persistido é alterado.

**Why this priority**: Cancelar deve ter uma consequência previsível e segura, especialmente antes de a pessoa salvar qualquer mudança.

**Independent Test**: Entrar em edição, modificar campos, cancelar e comparar o formulário e o conteúdo persistido antes e depois.

**Acceptance Scenarios**:

1. **Given** uma edição em andamento com campos modificados, **When** a pessoa escolhe `Cancelar`, **Then** o formulário volta a informar `Criar Perfil`, limpa o nome, restaura os valores iniciais e oculta a ação de cancelamento.
2. **Given** uma edição cancelada, **When** o perfil é lido novamente, **Then** nome, DPI e sensibilidade persistidos permanecem inalterados.

### Edge Cases

- Se o salvamento falhar, o formulário mantém o modo atual e os valores digitados para que a pessoa possa corrigir ou cancelar sem perder contexto.
- Se a configuração de perfis estiver ilegível, o estado de erro continua visível e os controles de mutação permanecem bloqueados; o título do modo não deve sugerir uma edição ativa que não existe.
- Depois de salvar com sucesso, o formulário retorna ao modo de criação, mesmo quando o salvamento foi uma atualização de perfil existente.
- Abrir novamente a tela sem uma seleção explícita de edição inicia sempre no modo de criação.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O formulário MUST identificar o estado inicial sem edição como `Criar Perfil`.
- **FR-002**: Ao iniciar a edição de um perfil, o formulário MUST identificar que está editando o perfil selecionado, incluindo seu nome visível.
- **FR-003**: A ação `Cancelar` MUST aparecer somente enquanto houver uma edição em andamento.
- **FR-004**: Ao cancelar, o sistema MUST retornar ao estado de criação e restaurar os valores iniciais do formulário.
- **FR-005**: Cancelar MUST NOT alterar ou remover os dados persistidos do perfil que estava sendo editado.
- **FR-006**: Salvar um novo perfil ou atualizar um perfil existente MUST preservar o fluxo de persistência já suportado e retornar o formulário ao estado de criação após sucesso.
- **FR-007**: Uma falha de leitura ou gravação MUST continuar sendo comunicada sem declarar uma operação concluída e sem liberar mutações bloqueadas.
- **FR-008**: A semântica do formulário MUST ser equivalente nas larguras desktop e small suportadas pelo produto.

### Key Entities *(include if feature involves data)*

- **Formulário de perfil**: conjunto de campos e ações que representa o modo atual de criação ou edição de um perfil.
- **Perfil persistido**: configuração identificada por nome, DPI e sensibilidade, mantida pela fonte de dados existente.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% das aberturas do formulário sem seleção de card, o título exibido é `Criar Perfil` e nenhuma ação de cancelamento de edição fica visível.
- **SC-002**: Em 100% das entradas no modo de edição cobertas pelos testes, o nome do perfil selecionado aparece no título e seus três valores são carregados.
- **SC-003**: Em 100% dos cancelamentos cobertos pelos testes, os dados persistidos permanecem byte a byte equivalentes e o formulário retorna ao estado de criação.
- **SC-004**: As capturas desktop de 1050×680 e small de 760×560 comunicam a mesma semântica de modo e ações, sem depender de inferência visual.
- **SC-005**: A suíte determinística existente permanece verde e nenhuma operação de hardware é introduzida ou alterada por esta mudança de UX.

## Assumptions

- O fluxo existente de `Editar` já seleciona um perfil e carrega seus valores; esta feature torna esse estado explícito sem redefinir a persistência.
- `Cancelar` no modo de edição apenas abandona os valores não salvos; não há necessidade de confirmação adicional porque não há escrita persistida nessa ação.
- O modo de criação usa os valores iniciais já adotados pelo formulário e mantém o mesmo CTA de salvamento.
- A lista de perfis e o armazenamento permanecem a fonte única de verdade; não será criado um modelo paralelo na interface.
- A validação física de hardware não é relevante para esta mudança de apresentação e estado do formulário.
