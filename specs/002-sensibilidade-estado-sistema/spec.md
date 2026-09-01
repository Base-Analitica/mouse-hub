# Feature Specification: Sensibilidade como estado do sistema

**Feature Branch**: `fix/sensitivity-system-state-hero`

**Created**: 2026-08-28

**Status**: Draft

**Input**: User description: "Issue #102 — a página Sensibilidade mistura leitura de hardware com estado do sistema. O hero apresenta 'aguardando leitura do hardware…' enquanto a própria página declara 'Sensibilidade do sistema disponível' — DPI físico e sensibilidade do sistema são conceitos distintos e não podem fundir-se visualmente."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Hero da Sensibilidade descreve o estado do sistema (Priority: P1)

O usuário abre a página Sensibilidade. O valor exibido é a sensibilidade
ATUAL DO SISTEMA (leitura do ponteiro via libinput/xinput), não um valor
aguardado do hardware do mouse. Nenhuma mensagem da página sugere que a
sensibilidade depende de leitura do hardware HID. Quando a leitura do
sistema não está disponível, o texto diz exatamente isso — sem mencionar
hardware do mouse.

**Why this priority**: É a correção central da issue #102 — a contradição
conceitual (hero de hardware + slider de sistema) é o defeito reportado.

**Independent Test**: Construir a página offscreen com fake de SystemInput
com valor de accel configurado: o hero exibe o valor lido do sistema; com
o tool de input indisponível, o hero exibe "—" com "valor atual do sistema
indisponível". Nenhum texto menciona "leitura do hardware".

**Acceptance Scenarios**:

1. **Given** um SystemInput fake com accel_state 0.5 (→ 75%), **When** a
   página é construída, **Then** o hero exibe `75%` lido do sistema.
2. **Given** um SystemInput indisponível (xinput ausente), **When** a
   página é construída, **Then** o hero exibe `—` com o texto
   `valor atual do sistema indisponível`.
3. **Given** a página renderizada (desktop ou small), **When** qualquer
   QLabel é inspecionado, **Then** nenhum texto contém "leitura do
   hardware" referindo-se à sensibilidade.

### User Story 2 - Nenhuma regressão na separação de domínios (Priority: P1)

DPI físico permanece governado por ACK do hardware (unknown até
confirmação). Sensibilidade permanece operação independente (falha de DPI
não altera sensibilidade e vice-versa). O commit do slider continua
gerando no máximo uma operação de sensibilidade.

**Why this priority**: Protege os invariantes absolutos do projeto
(separação issue #3 e unknown de DPI) enquanto muda a semântica de
sensibilidade.

**Independent Test**: Suíte existente `tests/test_issue3_ui_integration.py`
e `tests/test_issue6_profiles_polling.py` permanece verde; os testes de
unknown são atualizados para distinguir DPI (físico, unknown até ACK) de
sensibilidade (sistema, lido no startup).

**Acceptance Scenarios**:

1. **Given** um novo controller com device NÃO registrado, **When**
   `applied_dpi` e `applied_sensitivity` são consultados, **Then** DPI é
   `None` e a sensibilidade é o valor lido do sistema (75% no fake com
   accel 0.5) — porque sensibilidade não depende do device.
2. **Given** falha de SetSensorDPI, **When** a sensibilidade é lida
   novamente, **Then** o valor do sistema não é afetado.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-1**: O core lê a sensibilidade real do sistema (`get_sensitivity()`)
  na construção do controller e usa esse valor como estado inicial
  (`applied_sensitivity`). Falha de leitura → `None` (desconhecido
  honesto), nunca default conveniente.
- **FR-2**: A página Sensibilidade rotula o hero como estado do SISTEMA
  (`VELOCIDADE DO PONTEIRO NO SISTEMA`); o estado de leitura indisponível
  usa texto próprio (`valor atual do sistema indisponível`), distinto do
  unknown de DPI (`AGUARDANDO LEITURA DO HARDWARE`).
- **FR-3**: Nenhum texto da página Sensibilidade sugere dependência da
  leitura do hardware do mouse para a sensibilidade do sistema.
- **FR-4**: As operações (set/commit/slider/polling) permanecem
  inalteradas; a mudança é de semântica de estado inicial e copy.

### Assumptions

- Sensibilidade do sistema é propriedade do ponteiro, não do mouse: a
  leitura no startup via `SystemInput` é a fonte de verdade correta
  (Princípio V da constituição — regra de domínio no core).
- O fake `FakeSystemInput` responde `get_accel_speed` com 0.0 quando
  `accel_state` não foi configurado — o valor lido default nos testes é
  50%.

### Success Criteria

- SC-1: Hero da Sensibilidade exibe o valor lido do sistema em todos os
  fixtures (testes + screenshots).
- SC-2: Zero ocorrência de "aguardando leitura do hardware" na página de
  Sensibilidade.
- SC-3: Suíte completa verde; screenshots `2_sens`/`small_sens`/`preview`
  regeneradas refletindo o valor lido (50% no fake).

### Key Entities

- `MouseController.applied_sensitivity`: passa a representar "último valor
  confirmado do sistema" — lido no startup ou confirmado por
  `set_sensitivity` — nunca um valor aguardado do hardware do mouse.
