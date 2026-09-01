# Feature Specification: Design system sem drift de tokens

**Feature Branch**: `fix/design-token-drift`

**Created**: 2026-08-29

**Status**: Convergido localmente; aguardando CI do PR

**Input**: Issue #96 — eliminar cores, raios e paddings hardcoded em
`app/mouse_hub_app.py` quando já existe um token visual equivalente ou quando
uma exceção repetida precisa de contrato nomeado.

## User Scenarios & Testing

### User Story 1 — Aparência consistente e ajustável (Priority: P1)

Como mantenedor, quero que a UI use uma única fonte de verdade para tokens
visuais, para que alterar o tema não deixe gradientes, cards ou estados com
valores antigos escondidos.

**Independent Test**: o teste de invariantes compara literais hex da UI com
`app.ui.theme.COLORS` e rejeita as medidas excepcionais identificadas no issue.

**Acceptance Scenarios**:

1. **Given** uma cor já nomeada no tema, **When** um estilo da UI a usa,
   **Then** o estilo referencia o token, sem repetir o hex literal.
2. **Given** um card ou estado que usa repetidamente uma exceção de raio ou
   espaçamento, **When** seu stylesheet é construído, **Then** ele referencia
   um token nomeado com o mesmo valor visual.
3. **Given** um tema central alterado em uma futura manutenção, **When** a UI
   é reconstruída, **Then** esses estilos acompanham o token central.

### User Story 2 — Regressão protegida (Priority: P1)

Como mantenedor, quero que novos drifts sejam detectados automaticamente,
sem exigir hardware ou uma sessão gráfica real.

**Independent Test**: `pytest tests/test_issue96_design_tokens.py` em CI.

## Requirements

### Functional Requirements

- **FR-001**: As cores `accent_lighter`, `danger_light` e `danger_lighter`
  MUST ser referenciadas por `COLORS[...]`, nunca por seus hex literais na UI.
- **FR-002**: O tema MUST expor tokens nomeados para o raio de card (16 px),
  o espaçamento interno de card/ação (20 px) e o padding do empty state
  (30 px), mantendo os valores atuais.
- **FR-003**: O raio de pill da sidebar MUST usar o token `pill` existente,
  sem repetir `18px` no stylesheet da aplicação.
- **FR-004**: Gradientes, cards e empty states afetados MUST preservar os
  valores visuais atuais após a migração.
- **FR-005**: A mudança MUST incluir testes determinísticos contra o retorno
  dos literais e tokens ausentes.
- **FR-006**: Nenhuma regra de domínio ou lógica funcional MUST ser alterada.
- **FR-007**: Screenshots afetadas MUST ser regeneradas no mesmo PR.

## Scope

Inclui os três hex duplicados e as exceções repetidas explicitamente listadas
no issue. Não inclui a migração de toda medida inline existente na aplicação,
nem a criação de um sistema genérico de estilos.

## Edge Cases

- Um hex novo que não exista em `COLORS` pode ser legítimo para transparência
  ou uma cor específica, mas deve ser revisado separadamente.
- O valor do token não deve ser arredondado para a escala mais próxima quando
  isso mudar a aparência aprovada.
- O teste roda sem Qt visível e não prova a aparência física em todas as
  plataformas.

## Success Criteria

- Zero cópias dos três hex nomeados permanecem na UI.
- Zero ocorrências das medidas excepcionais sem token permanecem no stylesheet.
- A suíte dedicada passa e a suíte existente permanece integralmente verde.
- Screenshots regeneradas não apresentam alteração não intencional fora dos
  estilos previstos.

## Key Entities

- `app.ui.theme.COLORS`: tokens de cor centrais.
- `app.ui.theme.RADIUS`: escala de raios, incluindo a exceção de card.
- `app.ui.theme.SPACE`: escala de espaçamento, incluindo card e empty state.

## Review & Acceptance Checklist

- [x] Cores hardcoded migradas para tokens.
- [x] Exceções dimensionais têm nomes e valores documentados.
- [x] Aparência preservada.
- [x] Teste TDD falha antes e passa depois.
- [x] Screenshots atualizadas/verificadas.
- [ ] CI verde.
