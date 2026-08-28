# Feature Specification: Microcopy consistente do heading CPS

**Feature Branch**: `001-corrigir-microcopy-cps`

**Created**: 2026-08-28

**Status**: Draft

**Input**: User description: "Corrigir microcopy híbrida 'CPS (Clicks Por Segundo)' do heading do controle de velocidade do auto-clicker (issue #117)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Heading do controle CPS sem mistura de idiomas (Priority: P1)

O usuário abre a página do Auto-Clicker (desktop ou janela pequena) e lê o
heading do controle de velocidade. A interface é toda em pt-BR, mas o heading
atual expande a sigla CPS misturando inglês ("Clicks") com português
("Por Segundo") e usa capitalização de título no meio da frase. O heading deve
expander a sigla de forma consistente com o idioma da UI.

**Why this priority**: É o único ponto da mudança — o heading é o elemento
visível afetado; corrigi-lo resolve integralmente a issue #117.

**Independent Test**: Abrir a UI (offscreen) e inspecionar o texto do QLabel do
heading CPS: deve ser exatamente `CPS (Cliques por segundo)`.

**Acceptance Scenarios**:

1. **Given** a aplicação aberta na página do Auto-Clicker, **When** o heading do
   controle de velocidade é renderizado, **Then** o texto é
   `CPS (Cliques por segundo)` (sigla + expansão em pt-BR, minúsculas após a
   primeira palavra, como no restante da UI).
2. **Given** a aplicação aberta em layout small (janela estreita), **When** a
   mesma seção é renderizada, **Then** a copy é idêntica ao desktop.

### User Story 2 - Screenshots públicas refletem a correção (Priority: P2)

As screenshots incorporadas no README (`3_clicker.png`,
`small_clicker.png`) mostram o estado atual da UI e não podem exibir o texto
antigo após a correção.

**Why this priority**: Dependente da US1; garante que o material público não
contradiz o produto.

**Independent Test**: Rodar o pipeline de screenshots do projeto
(`docs/screenshots/`) e verificar que os arquivos gerados não contêm o texto
antigo.

**Acceptance Scenarios**:

1. **Given** o repositório com a correção aplicada, **When** o pipeline de
   screenshots é executado, **Then** `3_clicker.png` e `small_clicker.png`
   mostram `CPS (Cliques por segundo)`.

### Edge Cases

- O que acontece quando a janela é estreita demais para o heading completo?
  Fora de escopo: o comportamento de truncamento/quebra de linha do QLabel é o
  já existente e não é alterado por esta feature.
- E se outros textos da UI tiverem misturas parecidas? Fora de escopo desta
  feature (o sweep de QA visual já registrou os demais nas issues #108–#117);
  esta spec cobre apenas o heading CPS da issue #117.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O heading do controle de velocidade do auto-clicker MUST exibir
  exatamente o texto `CPS (Cliques por segundo)` no layout desktop.
- **FR-002**: O heading MUST exibir a mesma copy no layout small.
- **FR-003**: O significado da configuração (limite de 1–50 CPS, comportamento
  do slider e do valor numérico) MUST permanecer inalterado.
- **FR-004**: As screenshots públicas do clicker (`3_clicker.png`,
  `small_clicker.png`) MUST ser regeneradas refletindo o novo texto.
- **FR-005**: A correção MUST vir acompanhada de verificação automatizada
  (teste offscreen que assegure o texto do heading), seguindo o Princípio IV
  (regressão com teste) da constituição.

### Key Entities

- `cps_title` (QLabel em `app/mouse_hub_app.py`, função `_build` da página do
  clicker): único ponto de alteração de texto.

## Review & Acceptance Checklist

Gate derivado da constituição e da issue #117:

- [ ] Heading não mistura idiomas dentro da mesma expansão de sigla
- [ ] Desktop e small usam exatamente a mesma copy
- [ ] Comportamento do auto-clicker inalterado (testes existentes passam)
- [ ] Screenshots atualizadas
- [ ] CI verde (test + ui_smoke)
