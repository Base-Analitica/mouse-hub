# Feature Specification: Label visual do nome da macro

**Feature Branch**: `fix/macro-label-input-distinction`

**Created**: 2026-08-29

**Status**: PR aberto; CI real da implementação verde

**Input**: Issue #104, `[P2][UI] Label “Nome da macro” parece um segundo campo de entrada`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Distinguir label e campo de nome (Priority: P1)

Quando a pessoa abre a página de Macros, deve reconhecer imediatamente que
`Nome da macro:` é uma instrução e que o controle editável é o campo logo
abaixo. Somente o campo editável deve usar a superfície visual de input.

**Why this priority**: A ambiguidade acontece no primeiro controle da página e
pode fazer a pessoa interpretar o label como um segundo campo.

**Independent Test**: Construir `MacrosPage` com QApplication offscreen e
verificar que o label tem estilo de texto transparente, enquanto existe um
único `QLineEdit` para a entrada do nome.

**Acceptance Scenarios**:

1. **Given** a página de Macros aberta, **When** o formulário de gravação é
   exibido, **Then** `Nome da macro:` aparece como texto de formulário sem
   fundo ou borda de input.
2. **Given** o mesmo formulário, **When** a pessoa lê o controle, **Then** o
   único elemento editável visível é o campo do nome da macro.

---

### User Story 2 - Preservar a edição e o espaçamento (Priority: P1)

A correção visual não deve alterar o campo real, seu valor inicial, foco,
limite de caracteres, habilitação por capacidade ou o botão de gravação. O
label deve continuar acima do campo com espaçamento legível.

**Why this priority**: O label só é útil se a affordance e o fluxo de gravação
continuarem funcionando como antes.

**Independent Test**: Construir a página nos viewports 1050×680 e 760×560,
verificar a ordem geométrica label → campo e executar as regressões existentes
de gravação/capacidades.

**Acceptance Scenarios**:

1. **Given** o formulário criado, **When** a página é redimensionada para
   desktop ou small, **Then** o label permanece acima do mesmo campo sem
   sobreposição ou deslocamento indevido.
2. **Given** o campo com `minha_macro`, **When** a página é criada, **Then** o
   valor, o limite de 32 caracteres, foco e habilitação permanecem inalterados.

---

### User Story 3 - Material público consistente (Priority: P2)

As capturas oficiais da página de Macros devem mostrar a mesma distinção entre
label e campo em desktop, small e no mosaico de preview.

**Why this priority**: Screenshots são material público e não devem perpetuar
a composição que motivou a issue.

**Independent Test**: Executar o capturador oficial e revisar as três imagens
afetadas, sem exigir hardware.

**Acceptance Scenarios**:

1. **Given** a correção aplicada, **When** as screenshots são regeneradas,
   **Then** `4_macros.png`, `small_macros.png` e `preview.png` mostram somente
   o campo real com aparência de input.

### Edge Cases

- O campo continua desabilitado quando `macro_capture_available` não está
  confirmado; o label continua sendo apenas texto e não deve parecer ação.
- O valor inicial `minha_macro` e nomes longos até o limite existente continuam
  no mesmo `QLineEdit`; a issue não muda validação nem persistência.
- O formulário permanece legível em 760×560, sem criar overflow horizontal ou
  sobreposição entre label e campo.
- O estado vazio ou preenchido da lista de macros não muda; a alteração cobre
  somente o formulário de gravação.
- A ausência de sessão X11 ou de mouse físico não impede os testes offscreen.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O label `Nome da macro:` MUST ser renderizado como texto de
  formulário, sem fundo, borda ou padding que imite um input.
- **FR-002**: O formulário MUST manter exatamente um campo editável para o nome
  da macro, com o valor inicial e limite de caracteres existentes.
- **FR-003**: O label MUST permanecer acima do campo em 1050×680 e 760×560,
  com espaçamento suficiente e sem sobreposição.
- **FR-004**: A correção MUST preservar foco, habilitação por capacidade, botão
  `Gravar Macro`, cancelamento e todo o fluxo de gravação existente.
- **FR-005**: A correção MUST manter o estado da lista de macros e suas
  transições inalterados.
- **FR-006**: As screenshots públicas `4_macros.png`, `small_macros.png` e
  `preview.png` MUST ser regeneradas após a mudança.
- **FR-007**: O comportamento MUST ser coberto por testes offscreen
  determinísticos sem hardware físico ou sessão X11 real.

### Key Entities

- **Label do nome da macro**: Texto instrucional não editável do formulário de
  gravação.
- **Campo do nome da macro**: O `QLineEdit` existente que recebe o nome usado
  pelo serviço de gravação.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em ambos os viewports oficiais, existe exatamente um `QLineEdit`
  para o nome e o label não possui a superfície visual de input.
- **SC-002**: Em 100% das renderizações determinísticas, a geometria mantém a
  ordem label → campo sem sobreposição.
- **SC-003**: Os testes de gravação e capacidades existentes continuam verdes,
  demonstrando que o fluxo não mudou.
- **SC-004**: As três screenshots oficiais afetadas são reproduzidas pelo
  capturador e não deixam o label com aparência de segundo input.

## Assumptions

- A página de Macros continuará usando `MacrosPage` e o `QLineEdit` existente.
- O texto `Nome da macro:` permanece em pt-BR, pois a issue é visual, não de
  tradução.
- Os tokens `COLORS['text_secondary']`, `TYPE_SCALE['body']` e os estilos
  globais existentes são suficientes; nenhuma dependência ou token novo é
  necessário.
- O produto continua sendo o app desktop nativo PyQt5 e os viewports oficiais
  permanecem 1050×680 e 760×560.
- A issue não exige alteração em `mouse_hub/core/`, no formato de configuração
  ou no protocolo HID++.

## Review & Acceptance Checklist

- [x] Label é visualmente texto, não input
- [x] Existe somente um campo editável de nome
- [x] Desktop e small preservam ordem e espaçamento
- [x] Fluxo de gravação e capacidades permanecem verdes
- [x] Screenshots atualizadas
- [x] CI verde, incluindo testes determinísticos, pacote e smoke Xvfb
