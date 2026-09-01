# Feature Specification: Hint de capacidade do Auto-Clicker visível

**Feature Branch**: `fix/autoclicker-capability-hint`

**Created**: 2026-08-29

**Status**: Implementação local validada; revisão, PR e CI pendentes

**Input**: Issue #78, `[P2][UI] Exibir a causa de indisponibilidade do Auto-Clicker no layout`

## User Scenarios & Testing

### User Story 1 - Explicar controles indisponíveis (Priority: P1)

Quando o Auto-Clicker não está disponível no ambiente atual, a pessoa deve ver a causa junto dos controles desabilitados, sem precisar inferir o motivo a partir de uma ação que não funciona.

**Why this priority**: Um controle desabilitado sem explicação quebra a relação entre estado, causa e ação e é especialmente confuso em ambientes sem X11 suportado.

**Independent Test**: Construir `AutoClickerPage` com um `CapabilityModel` fake indisponível, verificar que o `caps_hint` pertence ao layout visível e contém a causa real, enquanto slider, seletor e CTA permanecem desabilitados.

**Acceptance Scenarios**:

1. **Given** `autoclick_available` indisponível com uma causa explícita, **When** a página é construída, **Then** a causa aparece em `caps_hint` no layout entre o status contextual e os controles.
2. **Given** a capacidade indisponível, **When** a pessoa olha a página, **Then** os controles continuam desabilitados e a mensagem não é substituída pelo status de foco do Minecraft.

---

### User Story 2 - Confirmar capacidade disponível sem competir com a ação (Priority: P2)

Quando a capacidade está disponível, a página deve manter uma indicação curta e discreta de disponibilidade, sem alterar a capacidade real nem tornar a mensagem mais importante que o CTA.

**Why this priority**: O mesmo componente deve explicar os dois estados sem criar uma diferença estrutural inesperada ou uma fonte de verdade paralela.

**Independent Test**: Construir a página com `autoclick_available` disponível, confirmar a mensagem de disponibilidade, a habilitação dos controles e a presença independente do status de foco.

**Acceptance Scenarios**:

1. **Given** `autoclick_available` disponível, **When** a página é exibida, **Then** `caps_hint` fica visível com a indicação de disponibilidade e os controles permanecem habilitados.
2. **Given** o Minecraft não está em foco, **When** a capacidade de automação está disponível, **Then** o hint de capacidade e o status de foco continuam sendo estados distintos.

---

### User Story 3 - Preservar leitura responsiva (Priority: P2)

A explicação deve permanecer legível e dentro do layout nos viewports oficiais desktop e small.

**Why this priority**: O viewport de 760×560 é o cenário em que uma linha adicionada pode causar colisão, clipping ou scroll inesperado.

**Independent Test**: Exercitar a página em 1050×680 e 760×560 com capacidades disponível e indisponível, verificar geometria e regenerar as capturas oficiais do Auto-Clicker.

**Acceptance Scenarios**:

1. **Given** qualquer estado de capacidade, **When** a página é renderizada nos dois viewports oficiais, **Then** o hint permanece contido, legível e sem sobrepor os controles.
2. **Given** a causa é longa, **When** o hint é renderizado, **Then** o texto pode quebrar linha sem ampliar a janela nem ocultar o CTA.

### Edge Cases

- Se `caps_provider` for `None`, o comportamento existente da página permanece preservado e nenhum acesso a capacidade é inventado.
- Se a causa vier vazia, `_sync_caps()` continua usando a causa de reserva já existente.
- Se a capacidade mudar entre indisponível e disponível, uma nova sincronização atualiza o mesmo widget sem duplicá-lo.
- O status `Minecraft não detectado` continua separado do hint de capacidade e não é usado como explicação genérica.
- O texto existente de backend será tratado separadamente pelo issue #83; este change não mistura escopos nem altera a fonte da causa.
- A validação usa fakes e Qt offscreen/Xvfb, sem exigir hardware físico ou sessão X11 real.

## Requirements

### Functional Requirements

- **FR-001**: O `caps_hint` já existente MUST ser adicionado ao layout real de `AutoClickerPage` em posição próxima aos controles afetados, entre o contexto de Minecraft e o bloco de controles.
- **FR-002**: O hint MUST continuar exibindo a disponibilidade ou a causa retornada por `CapabilityState`, incluindo a causa de reserva existente quando necessário.
- **FR-003**: A mudança MUST preservar o gating atual de `cps_slider`, seletor de botão e CTA, sem alterar `CapabilityModel` ou regras de automação.
- **FR-004**: O status de foco do Minecraft MUST continuar sendo um elemento separado do estado de capacidade.
- **FR-005**: O hint MUST permanecer legível, quebrável e contido nos viewports oficiais de 1050×680 e 760×560.
- **FR-006**: Testes determinísticos MUST cobrir capacidade disponível, indisponível com causa real, atualização do estado e presença do widget no layout, sem hardware.
- **FR-007**: `3_clicker.png`, `small_clicker.png` e o `preview.png` MUST ser regenerados quando a captura oficial demonstrar mudança nessas superfícies.
- **FR-008**: A implementação MUST não criar lógica de domínio, alterar hardware/protocolo, adicionar dependência ou modificar o escopo editorial do issue #83.

## Key Entities

Esta feature não introduz entidades de domínio, persistência ou dados novos.

| Elemento | Tipo existente | Papel | Invariante |
|---|---|---|---|
| `caps_hint` | `QLabel` de UI | Exibir capacidade e causa | É um único widget presente no layout da página |
| `CapabilityState` | Estado de capacidade | Fonte da disponibilidade e causa | A UI apenas projeta `is_available` e `reason_for` |
| `mc_status` | `QLabel` de UI | Exibir contexto de foco/detecção | Não substitui nem é substituído pelo hint |

## Success Criteria

### Measurable Outcomes

- **SC-001**: Em estado indisponível, 100% dos controles afetados permanecem desabilitados e a causa real aparece no layout visível.
- **SC-002**: Em estado disponível, os controles permanecem habilitados e uma indicação de disponibilidade aparece no mesmo widget, sem duplicação.
- **SC-003**: Os testes verificam os dois estados, a presença do widget no layout e a separação do status de foco em ambos os viewports oficiais.
- **SC-004**: A suíte determinística, o smoke Xvfb e o pacote `.deb` terminam sem falhas relacionadas à mudança.
- **SC-005**: As capturas oficiais reproduzem byte a byte em duas execuções consecutivas e não mostram clipping, sobreposição ou scroll espúrio causado pelo hint.

## Assumptions

- `AutoClickerPage` já cria e atualiza `caps_hint`; a lacuna do issue é a ausência de `layout.addWidget(self.caps_hint)`.
- O `CapabilityModel` existente continua sendo a única fonte de disponibilidade e causa.
- Os textos atuais de capacidade permanecem neste PR; a remoção de jargão de backend é tratada pelo issue #83/PR correspondente.
- O produto continua sendo o app PyQt5 nativo para Linux, sem reintroduzir a UI web legada.
- A validação física de G403 e de uma sessão X11 real não é alegada por esta mudança de layout.

## Validation Evidence

Os gates locais foram executados no worktree isolado, sem hardware físico:

- O baseline em `origin/main` passou com **544 testes** antes da alteração.
- O ciclo TDD RED foi observado antes do código de produção: o teste dedicado teve **5 falhas** esperadas, todas pela ausência de `caps_hint` no layout (`indexOf(...) == -1`).
- Após inserir o widget existente no ponto definido, o teste dedicado passou com **5 testes**.
- As regressões focadas de capabilities e UI passaram com **24 testes**, incluindo o contrato anterior de gating.
- O smoke Xvfb passou com **1 teste OK**.
- A suíte determinística completa passou com **549 testes**, sem falhas.
- `python3 -m compileall -q app mouse_hub tests scripts` e `git diff --check` passaram.
- O pacote `.deb` foi gerado e validado com `dpkg-deb`; ele contém o launcher `/usr/bin/mouse-hub` e `app/ui/fonts/remixicon-subset.ttf`.
- A captura oficial foi repetida duas vezes; `3_clicker.png`, `small_clicker.png` e `preview.png` foram byte a byte idênticos entre as execuções. As dimensões são, respectivamente, 1050x680, 760x560 e 2130x2770.
- Contra `origin/main`, somente essas três imagens mudaram. As caixas RGB alteradas foram `3_clicker.png=(214,229,1026,457)`, `small_clicker.png=(214,229,736,457)` e `preview.png=(1284,929,2096,1157)`, correspondendo ao hint e ao reflow abaixo dele.
- A mudança de produção fica restrita a `app/mouse_hub_app.py`: o `caps_hint` existente é inicializado antes de ser inserido após `mc_status`; capability provider, gating, foco e domínio permanecem inalterados.

A evidência acima é de software em Qt offscreen/Xvfb e fakes. Não constitui validação física do G403 HERO nem de uma sessão X11 real. A revisão read-only, a publicação do PR e os checks remotos serão registrados após esses gates.