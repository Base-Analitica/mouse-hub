# Feature Specification: Cópia explícita para estado desconhecido

**Feature Branch**: `fix/explicit-unknown-state-copy`

**Created**: 2026-08-29

**Status**: Concluído, CI verde

**Input**: Issue #110 — `[P2][UI] Estado desconhecido usa “traço colorido” que parece indicador/progresso`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dashboard comunica ausência de leitura (Priority: P1)

Quando o usuário abre o dashboard sem um valor aplicado confirmado, os cards de
DPI e sensibilidade não devem sugerir que um valor numérico esteja sendo medido,
carregado ou aplicado. O traço isolado atualmente recebe uma cor de destaque e
pode ser interpretado como indicador visual de progresso. Os cards devem usar uma
mensagem textual explícita e uma cor neutra.

**Why this priority**: O dashboard é a primeira superfície de leitura do estado
da aplicação. Uma mensagem explícita evita uma interpretação incorreta antes de
o usuário abrir qualquer página de configuração.

**Independent Test**: Construir `MouseCoreState` com fakes, sem leitura aplicada,
renderizar `DashboardPage` em modo offscreen e verificar que os dois cards exibem
exatamente `Aguardando leitura`, sem em dash e com `COLORS["text_secondary"]`.

**Acceptance Scenarios**:

1. **Given** que `applied_dpi` e `applied_sensitivity` são desconhecidos,
   **When** o dashboard é atualizado, **Then** os cards exibem exatamente
   `Aguardando leitura`.
2. **Given** o mesmo estado desconhecido, **When** os cards são renderizados,
   **Then** o texto usa a cor neutra de estado secundário e não uma cor de valor
   confirmado.
3. **Given** que os valores aplicados são conhecidos, **When** o dashboard é
   atualizado, **Then** os números e as cores semânticas existentes permanecem
   inalterados.

### User Story 2 - Heroes distinguem estado desconhecido de valor aplicado (Priority: P1)

Nas páginas de DPI e sensibilidade, o valor em destaque deve comunicar quando a
leitura ainda não está disponível. A mensagem não pode parecer uma barra, um
marcador de progresso ou um valor padrão. Depois de uma leitura ou confirmação
bem-sucedida, o hero volta a exibir o valor numérico com a cor semântica da
configuração.

**Why this priority**: Os heroes são a principal representação visual de cada
configuração e atualmente concentram o problema apontado pela issue.

**Independent Test**: Instanciar `DPIPage` e `SensitivityPage` com um estado fake
sem valor confirmado e verificar a copy e o estilo do QLabel principal, incluindo
os caminhos de refresh e de falha que invalidam o valor.

**Acceptance Scenarios**:

1. **Given** que o DPI aplicado é desconhecido, **When** a página de DPI é
   construída ou sincronizada, **Then** o hero exibe `Aguardando leitura` em
   estilo neutro.
2. **Given** que a sensibilidade do sistema é desconhecida, **When** a página de
   sensibilidade é construída ou atualizada, **Then** o hero exibe
   `Aguardando leitura` em estilo neutro.
3. **Given** que o usuário apenas move um slider, **When** a prévia é exibida,
   **Then** o valor em consideração continua sendo distinguido do estado
   desconhecido e nenhuma operação física nova é introduzida.
4. **Given** que uma leitura ou escrita é confirmada, **When** o estado conhecido
   é renderizado, **Then** o hero exibe o número confirmado e recupera sua cor
   semântica.

### User Story 3 - Material visual público acompanha a correção (Priority: P2)

As screenshots do dashboard, DPI e sensibilidade, em tamanho desktop e small,
devem representar a mesma linguagem visual da aplicação e não mostrar o traço
colorido como estado desconhecido.

**Why this priority**: Evita que a documentação pública continue ensinando uma
interpretação ambígua já corrigida no produto.

**Independent Test**: Executar `scripts/capture_screenshots.py` com Qt offscreen e
verificar que os sete arquivos afetados são regenerados sem alterar telas não
relacionadas.

**Acceptance Scenarios**:

1. **Given** a implementação do novo estado desconhecido, **When** as screenshots
   são capturadas, **Then** `0_dashboard.png`, `1_dpi.png`, `2_sens.png` e suas
   variantes small exibem a copy explícita.
2. **Given** o preview público, **When** ele é regenerado, **Then** a composição
   incorpora a mesma alteração sem texto antigo nos cards ou heroes.

## Edge Cases

- **Dispositivo ausente**: o estado continua desconhecido e usa a copy explícita;
  a UI não inventa um DPI ou uma sensibilidade padrão.
- **Falha ao ler ou confirmar**: o último valor não confirmado não é apresentado
  como aplicado; o componente volta à copy neutra.
- **Input editável de DPI**: o placeholder neutro `—` pode permanecer no campo de
  entrada, pois ele é um controle de edição e não um card/hero que comunica
  estado aplicado.
- **Layout small**: a copy é a mesma do desktop; comportamento de quebra ou
  truncamento fora do espaço disponível não é redesenhado nesta feature.
- **Prévia de slider**: a prévia numérica representa uma intenção local, não uma
  confirmação do hardware ou do sistema, e mantém as regras de commit existentes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A UI MUST definir uma copy única para estado desconhecido,
  `Aguardando leitura`, em pt-BR.
- **FR-002**: Os cards de DPI e sensibilidade do dashboard MUST exibir a copy de
  FR-001 sempre que o respectivo valor aplicado for `None`.
- **FR-003**: Os heroes de DPI e sensibilidade MUST exibir a copy de FR-001 nos
  estados inicial, refreshed e invalidado em que não exista valor confirmado.
- **FR-004**: A copy de FR-001 MUST usar estilo neutro (`text_secondary`) nos
  cards e heroes, sem aparência de indicador de progresso ou valor confirmado.
- **FR-005**: Valores aplicados conhecidos MUST continuar sendo renderizados com
  o número e a cor semântica já usados pela aplicação.
- **FR-006**: O `UNKNOWN_VALUE_TEXT` do input editável de DPI MUST continuar
  separado da copy de estado dos cards e heroes; a mudança não pode transformar
  placeholder de edição em afirmação de estado aplicado.
- **FR-007**: A mudança MUST preservar a separação entre estado e apresentação:
  `MouseCoreState` continua fornecendo o estado e nenhuma regra de hardware nova
  deve ser implementada em `app/`.
- **FR-008**: A correção MUST incluir teste determinístico com fakes que falhe
  sem a mudança e cubra dashboard, heroes, cor neutra e separação do input.
- **FR-009**: As screenshots desktop, small e preview afetadas MUST ser
  regeneradas no mesmo PR.
- **FR-010**: O PR MUST passar a suíte determinística, o smoke da UI e o empacotamento
  definidos pelo CI do projeto; nenhum PR desta iniciativa deve ser mergeado pelo
  agente.

### Key Entities

- `UNKNOWN_STATE_TEXT` em `app/mouse_hub_app.py`: copy de apresentação para
  estado não conhecido.
- `UNKNOWN_VALUE_TEXT` em `app/mouse_hub_app.py`: placeholder neutro preservado
  para input editável de DPI.
- `MouseCoreState.applied_dpi` e `MouseCoreState.applied_sensitivity`: fontes dos
  valores confirmados que determinam se o estado é conhecido.
- `StatCard.value_label`, `DPIPage.dpi_value` e `SensitivityPage.sens_value`:
  superfícies visuais cobertas pela issue.

## Out of Scope

- Alterar o protocolo HID++, a leitura de sensibilidade do sistema ou a política
  de confirmação do core.
- Redesenhar o layout, trocar a tipografia global ou criar animação de loading.
- Remover o traço do campo de edição de DPI quando ele estiver sem valor de
  entrada.
- Declarar validação física em um G403 HERO real; esta feature prova o contrato
  de software com fakes e testes offscreen.

## Review & Acceptance Checklist

- [x] Nenhum card ou hero usa em dash colorido para representar estado desconhecido
- [x] `Aguardando leitura` é consistente no desktop e no layout small
- [x] Estados confirmados preservam número e cor semântica
- [x] O input editável de DPI continua semanticamente separado
- [x] Testes RED e GREEN registrados no histórico da implementação
- [x] Screenshots atualizadas
- [x] Suíte determinística, smoke de UI e pacote `.deb` passam no CI
- [x] PR aberto e não mergeado

## Remote Validation

- Workflow CI `33252603466` passou nos três checks: lint e testes
  determinísticos, pacote `.deb` e smoke da UI com Xvfb.
- PR aberto: [#133](https://github.com/Base-Analitica/mouse-hub/pull/133).
- O PR permanece aberto e não foi mergeado; a decisão de merge cabe ao
  mantenedor.
