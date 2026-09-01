# Feature Specification: DPI — slider como "valor desejado", distinto do readback

**Feature Branch**: `fix/dpi-slider-target-state`

**Created**: 2026-08-29

**Status**: Draft

**Input**: User description: "Issue #103 — em `1_dpi.png` o hero informa
`AGUARDANDO LEITURA DO HARDWARE`, mas o slider aparece posicionado e os
presets como ações normais. Sem distinção explícita, o usuário pode ler a
posição do slider como **DPI atual**. É preciso separar valor
atual/aplicado, valor solicitado/editável e valor persistido."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Papel do slider explícito (Priority: P1)

Quando o DPI físico aplicado ainda não está confirmado, o controle que
permite escolher um novo DPI é rotulado pelo seu papel real: **valor
desejado / próximo valor a aplicar** — nunca como representação implícita
do estado aplicado. O hero permanece reservado ao **DPI físico
confirmado** (ou ao estado de leitura "aguardando leitura").

**Why**: estado desconhecido não pode ser representado como valor
conhecido; controles de destino não devem se parecer com readback
confirmado.

### User Story 2 - Semântica idêntica nas duas janelas (Priority: P1)

A mesma legenda/papel do slider aparece na janela normal e na janela
pequena 760×560 — a semântica não pode desaparecer no layout compacto.

### Edge Cases

- Readback confirmado existe → a página mostra o valor aplicado no hero;
  o slider continua sendo controle de entrada (legenda de papel
  permanente, não condicional).
- Falha de operação → hero volta ao último confirmado ou UNKNOWN; a
  legenda do slider continua descrevendo o papel de entrada.
- Presets continuam operação válida quando a capability está confirmada
  (issue #95 já cobre o gate por `hardware_dpi_available`).

## Requirements *(mandatory)*

- **FR-1**: um rótulo/legenda adjacente ao slider descreve o papel de
  entrada ("Valor desejado (aplicar ao hardware)"), permanente — presente
  com readback conhecido ou desconhecido.
- **FR-2**: o hero (valor grande + sub-rótulo) permanece reservado ao
  estado aplicado/confirmado; nenhum texto do hero muda de significado
  quando o slider se move (preview atualiza o valor, o sub-rótulo de
  "aguardando leitura" permanece até haver confirmação).
- **FR-3**: quando não há readback confirmado, a posição do slider não
  pode ser apresentada como estado aplicado — o único texto que descreve
  o estado aplicado é "AGUARDANDO LEITURA DO HARDWARE" / "—".
- **FR-4**: nenhuma persistência é exibida como hardware aplicado sem
  confirmação (já garantido; não pode regredir).
- **FR-5**: desktop e 760×560 apresentam a mesma semântica.

## Acceptance Criteria

- usuário distingue visualmente `DPI atual/aplicado` de `valor a aplicar`;
- estado `aguardando leitura` não apresenta nenhum elemento como se fosse
  readback confirmado;
- testes cobrem readback conhecido vs desconhecado (legenda presente nos
  dois estados; hero inalterado durante preview sem confirmação);
- screenshots regeneradas no mesmo PR;
- CI verde.

## Principles Check (constituição)

| Princípio | Aplicação |
| --- | --- |
| Honestidade de estado | slider rotulado como entrada; hero só readback |
| Corretude de hardware | nenhum texto sugere readback sem confirmação |
| Menor mudança completa | legenda + ajustes de render, sem refactor |
| UX honesta | papel do controle explícito nos dois tamanhos de janela |
