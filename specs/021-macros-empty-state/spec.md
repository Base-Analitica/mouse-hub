# Feature Specification: Empty state de Macros próximo ao heading

**Feature Branch**: `fix/macros-empty-state-position`

**Created**: 2026-08-29

**Status**: Draft

**Input**: User description: "Corrigir o empty state da página de Macros para que a mensagem fique próxima de `Macros Salvas`, sem grande área vazia, mantendo o CTA de gravação e a lista preenchida (issue #105)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Encontrar o estado vazio de Macros (Priority: P1)

O usuário abre a página de Macros quando ainda não existe nenhuma macro salva. A
interface mostra o heading `Macros Salvas` e, logo abaixo, explica que não há
macros gravadas e como criar a primeira. A mensagem deve aparecer no início da
região em que a lista seria exibida, sem interromper a relação visual entre o
heading e seu estado.

**Why this priority**: É o problema central da issue #105. A mensagem precisa
ser localizada imediatamente para que o usuário entenda o estado e a próxima ação
sem procurar em uma área vazia.

**Independent Test**: Renderizar a página sem macros em 1050×680 e 760×560 e
inspecionar a posição relativa da mensagem ao heading `Macros Salvas`, além de
confirmar que o CTA `Gravar Macro` continua disponível no card de gravação.

**Acceptance Scenarios**:

1. **Given** a página de Macros sem macros salvas, **When** a seção de macros é
   renderizada, **Then** `Macros Salvas` e a mensagem de estado vazio formam um
   bloco visual contínuo, com a primeira linha da mensagem no início da região da
   lista e sem conteúdo intermediário.
2. **Given** a janela em 1050×680 ou 760×560, **When** o estado vazio é exibido,
   **Then** a mensagem permanece visível na mesma relação espacial com o heading,
   sem ser empurrada para o centro da área disponível.
3. **Given** o estado vazio, **When** o usuário procura uma forma de criar a
   primeira macro, **Then** encontra o CTA existente `Gravar Macro` no card de
   gravação, sem um segundo botão de criação no empty state.

### User Story 2 - Preservar a lista preenchida (Priority: P2)

O usuário abre a página quando há uma ou mais macros salvas. A lista continua
exibindo cada macro e seus controles normalmente, sem a mensagem de estado vazio
ou alterações na posição relativa da lista causadas pela correção.

**Why this priority**: O ajuste deve resolver apenas o estado vazio e não pode
regredir o fluxo de uso das macros existentes.

**Independent Test**: Renderizar a página com macros fake determinísticas e
confirmar que cada item permanece visível, que a mensagem vazia não existe e que
a transição entre lista vazia e preenchida não deixa widgets antigos na tela.

**Acceptance Scenarios**:

1. **Given** uma ou mais macros salvas, **When** a seção `Macros Salvas` é
   renderizada, **Then** os itens e seus controles aparecem e a mensagem
   `Nenhuma macro gravada ainda.` não é exibida.
2. **Given** uma página inicialmente vazia, **When** uma macro é gravada ou a
   lista é atualizada para conter uma macro, **Then** o estado vazio é removido e
   o item da macro ocupa a região da lista sem duplicação de mensagens.

### User Story 3 - Manter evidência visual pública (Priority: P2)

As screenshots públicas da página de Macros devem representar o estado vazio
corrigido nos tamanhos desktop e small, para que a documentação não contradiga o
produto.

**Why this priority**: A correção visual precisa ser verificável tanto na
interface quanto nos artefatos públicos gerados pelo projeto.

**Independent Test**: Executar o capturador determinístico de screenshots e
inspecionar `4_macros.png`, `small_macros.png` e o mosaico `preview.png`.

**Acceptance Scenarios**:

1. **Given** a captura determinística sem macros, **When** as screenshots são
   regeneradas, **Then** os arquivos mostram a mensagem próxima ao heading
   `Macros Salvas` nos dois tamanhos suportados.

### Edge Cases

- Quando a janela muda entre 1050×680 e 760×560, o empty state continua no topo
da região da lista e a página mantém os comportamentos de rolagem já existentes.
- Quando a lista muda de vazia para preenchida e volta a ficar vazia, apenas um
empty state é exibido e nenhum item ou mensagem obsoleta permanece.
- Quando a captura de macros está indisponível, o texto e a posição do empty state
não mudam; a causa da indisponibilidade continua sendo tratada pelo estado de
capacidade já existente.
- O texto do empty state permanece legível sem criar uma nova ação ou exigir
alterações na persistência de macros.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Quando não houver macros salvas, o sistema MUST exibir o estado
  vazio imediatamente abaixo do heading `Macros Salvas`, no início da região em
  que os itens da lista apareceriam.
- **FR-002**: O estado vazio MUST manter a mensagem pt-BR existente:
  `Nenhuma macro gravada ainda.` seguida da orientação para usar `Gravar Macro`.
- **FR-003**: O estado vazio MUST usar alinhamento e espaçamento intencionais,
  sem centralizar verticalmente a mensagem em toda a área livre da página.
- **FR-004**: O CTA existente `Gravar Macro` MUST permanecer no card de gravação
  como a ação de criação, sem botão duplicado no estado vazio.
- **FR-005**: Quando houver macros salvas, o sistema MUST exibir os itens e seus
  controles existentes e MUST ocultar o estado vazio.
- **FR-006**: A mudança MUST manter comportamento estável nos tamanhos 1050×680 e
  760×560, incluindo a transição entre lista vazia e preenchida.
- **FR-007**: A correção MUST incluir testes determinísticos de UI com fakes, sem
  depender de hardware, e MUST regenerar as screenshots públicas afetadas.

### Key Entities

- **Estado da lista de macros**: conjunto vazio ou preenchido que determina qual
  conteúdo é exibido na região `Macros Salvas`.
- **Mensagem de estado vazio**: orientação pt-BR apresentada quando o conjunto de
  macros está vazio; não cria persistência nem ação própria.
- **Ação de gravação**: CTA existente que inicia a criação da primeira macro e
  permanece no card de gravação.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 100% das renderizações determinísticas sem macros nos tamanhos
  1050×680 e 760×560, a primeira linha do empty state aparece no primeiro quinto
  da região destinada à lista e não há outro widget entre o heading e a mensagem.
- **SC-002**: Em 100% dos estados vazios, existe exatamente uma ação visível de
  criação, o CTA `Gravar Macro`, e nenhuma ação duplicada dentro do empty state.
- **SC-003**: Em 100% das renderizações com pelo menos uma macro, os itens da lista
  continuam presentes, a mensagem vazia está ausente e não há widgets residuais
  após a transição.
- **SC-004**: As três screenshots públicas afetadas (`4_macros.png`,
  `small_macros.png` e `preview.png`) são regeneradas pelo capturador determinístico
  e mostram o estado vazio corrigido.

## Assumptions

- A mensagem atual do empty state é o texto de referência e não exige revisão de
  microcopy nesta issue.
- O card de gravação e o CTA `Gravar Macro` já atendem ao fluxo de criação e não
  serão movidos ou duplicados.
- A lista de macros continuará podendo usar a rolagem existente quando houver
  conteúdo suficiente para exceder a área disponível.
- A validação de hardware e de disponibilidade X11 permanece fora do escopo;
  os testes usarão fakes determinísticas já aceitas pelo projeto.
- A mudança é exclusivamente visual e de layout; persistência, gravação,
  reprodução e exclusão de macros permanecem inalteradas.

## Review & Acceptance Checklist

Gate derivado da constituição e da issue #105:

- [x] Empty state fica próximo de `Macros Salvas` nos dois viewports
- [x] CTA `Gravar Macro` permanece único e inalterado
- [x] Lista preenchida não mostra estado vazio nem sofre regressão
- [x] Transições vazio/preenchido não deixam widgets residuais
- [x] Testes determinísticos cobrem os dois viewports
- [x] Screenshots públicas atualizadas
- [ ] CI verde (test, pacote e ui_smoke)
