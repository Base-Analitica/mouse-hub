# Feature Specification: Grid responsivo da página de Perfis

**Feature Branch**: `fix/profiles-responsive-grid`

**Created**: 2026-08-29

**Status**: Concluído, CI verde

**Input**: Issue #100 — `[P1][UI regression] Perfis se sobrepõem e criam overflow horizontal em 760×560`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cards de Perfis mantêm regiões independentes (Priority: P1)

Quando o usuário abre a página de Perfis em uma janela small, cada card deve
reservar sua altura real. A segunda linha não pode começar antes de a primeira
terminar, e os botões `Aplicar` e `Editar` precisam continuar integralmente
visíveis dentro de seus cards.

**Why this priority**: Sobreposição de cards destrói a legibilidade e pode
ocultar ações legítimas. É uma regressão objetiva de layout, não apenas uma
preferência visual.

**Independent Test**: Renderizar a janela principal com configuração isolada,
passar por todas as páginas na largura desktop e depois em 760×560, selecionar
Perfis e medir os `QRect` dos cards. Qualquer interseção entre irmãos falha.

**Acceptance Scenarios**:

1. **Given** quatro ou mais perfis, **When** a página é exibida em 760×560,
   **Then** os cards de cada linha e coluna não se sobrepõem.
2. **Given** a mesma janela small, **When** a grade é exibida,
   **Then** os botões `Aplicar` e `Editar` de todos os cards permanecem dentro
   dos limites do respectivo card.
3. **Given** uma janela desktop de 1050×680, **When** a página é exibida,
   **Then** a grade continua usando o espaço disponível sem regressão visual.

### User Story 2 - Formulário fica separado da grade (Priority: P1)

Depois da última linha de cards, o heading `Criar / Editar Perfil` e seus
controles devem começar em uma região própria. Se o conteúdo não couber na
altura disponível, a página pode rolar verticalmente, mas não pode comprimir a
grade a ponto de produzir overlap nem esconder conteúdo para mascarar o
problema.

**Independent Test**: Medir a posição do heading e dos widgets do formulário em
relação ao retângulo inferior de todos os cards. O heading deve começar depois
da grade e os controles devem permanecer dentro do conteúdo rolável.

**Acceptance Scenarios**:

1. **Given** a grade com duas linhas, **When** o formulário é renderizado,
   **Then** o heading não intersecta nenhum card e fica abaixo da última linha.
2. **Given** que a altura mínima do conteúdo é maior que a viewport,
   **When** a página é envolvida pelo `QScrollArea`, **Then** somente a rolagem
   vertical é usada para alcançar o formulário completo.
3. **Given** qualquer valor de perfil preenchido, **When** o formulário é
   exibido, **Then** os campos e botões continuam visíveis e identificáveis, sem
   overflow horizontal.

### User Story 3 - Prova visual e contrato automatizado (Priority: P2)

As screenshots públicas de Perfis devem refletir o reflow corrigido. O teste de
regressão deve cobrir a geometria que originou a issue, usando fakes e sem
hardware.

**Independent Test**: Executar `scripts/capture_screenshots.py`, conferir as
imagens de Perfis desktop e small e executar o teste de geometria com Qt
offscreen.

**Acceptance Scenarios**:

1. **Given** a implementação corrigida, **When** as screenshots são capturadas,
   **Then** `5_perfis.png` e `small_perfis.png` não mostram cards ou formulário
   sobrepostos.
2. **Given** o `QScrollArea` da página, **When** a viewport tem 760×560,
   **Then** a barra horizontal não é visível e seu alcance máximo é zero.

## Edge Cases

- Uma configuração com perfil customizado adicional deve seguir o mesmo cálculo
de linhas e não alterar as regiões ocupadas pelos demais cards.
- Uma janela desktop larga deve continuar distribuindo os cards em três colunas,
sem reduzir a altura útil ou forçar uma coluna desnecessária.
- O conteúdo pode ser mais alto que a viewport small; a rolagem vertical é o
mecanismo suportado para acessar o restante.
- A correção não pode depender do nome, da ordem ou da quantidade exata dos
presets oficiais.
- O estado de configuração corrompida continua exibindo a causa e bloqueando o
formulário, sem alterar o contrato de geometria dos widgets existentes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A grade de Perfis MUST reservar a altura mínima real de cada linha,
  impedindo que `QGridLayout` comprima rows abaixo da altura dos cards.
- **FR-002**: Cards irmãos MUST ter retângulos sem interseção em 760×560 e em
  1050×680.
- **FR-003**: O heading `Criar / Editar Perfil` MUST começar após a última linha
  da grade e não intersectar nenhum card.
- **FR-004**: Os campos `name_input`, `dpi_input` e `sens_input`, além dos botões
  do formulário, MUST ficar dentro dos limites do conteúdo da página.
- **FR-005**: O conteúdo de Perfis MUST poder exceder a altura da viewport por
  meio de rolagem vertical, sem depender de sobreposição para caber.
- **FR-006**: A página de Perfis MUST não exibir scrollbar horizontal em
  760×560 quando todos os controles cabem na largura útil.
- **FR-007**: A solução MUST preservar os dados, ações, fonte `ProfileStore`,
  aplicação de perfil e regras de estado confirmado existentes.
- **FR-008**: A regressão MUST ter teste Qt determinístico com configuração
  isolada, cobrindo interseção dos cards, separação do formulário e ausência da
  barra horizontal.
- **FR-009**: `5_perfis.png` e `small_perfis.png` MUST ser regenerados no mesmo
  PR, sem alterar screenshots não relacionadas.
- **FR-010**: O PR MUST passar testes determinísticos, smoke da UI, pacote `.deb`
  e permanecer aberto para revisão do mantenedor.

### Key Entities

- `ProfilesPage.grid`: `QGridLayout` que distribui os cards por linha e coluna.
- `ProfilesPage._grid_cols`: número de colunas da grade em layout desktop.
- `QScrollArea` criado por `MouseHubApp._wrap_scrollable`: container que deve
  permitir rolagem vertical sem mostrar uma barra horizontal espúria.
- `profile_cards`: mapa de cards e controles expostos para o teste de geometria.

## Out of Scope

- Alterar a quantidade de colunas por breakpoint ou redesenhar o card além do
necessário para preservar sua geometria.
- Mudar o modelo de perfis, a persistência XDG ou os serviços de DPI e
sensibilidade.
- Esconder cards, controles ou o formulário para eliminar visualmente o
overflow.
- Declarar validação física no G403 HERO; a regressão é de layout e é provada
com fakes e Qt offscreen.

## Review & Acceptance Checklist

- [x] Cards não se intersectam em 760×560
- [x] Botões `Aplicar` e `Editar` ficam integralmente visíveis
- [x] Heading e formulário começam depois da grade
- [x] Não há scrollbar horizontal
- [x] Desktop 1050×680 permanece correto
- [x] Teste de geometria falha no estado anterior e passa após o fix
- [x] Screenshots `5_perfis.png` e `small_perfis.png` atualizadas
- [x] CI verde
- [x] PR aberto e não mergeado

## Remote Validation

- Workflow CI `33253419583` passou nos três checks: lint e testes
  determinísticos, pacote `.deb` e smoke da UI com Xvfb.
- PR aberto: [#134](https://github.com/Base-Analitica/mouse-hub/pull/134).
- O PR permanece aberto e não foi mergeado. A decisão de merge cabe ao
  mantenedor.

## Local Validation

- O teste dedicado reproduziu RED no código anterior e passou em GREEN após a
  correção.
- A suíte focada do issue e `tests/test_issue6_profiles_polling.py` passou.
- A suíte completa `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q`
  terminou com exit code 0.
- O smoke Xvfb terminou com 1 teste OK, `compileall` não encontrou erros e
  `git diff --check` passou.
- O capturador oficial foi executado. `small_perfis.png` mudou; a captura de
  `5_perfis.png` permaneceu byte-identical porque o layout desktop não mudou.
