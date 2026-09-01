# Feature Specification: Copy de leitura com contraste adequado

**Feature Branch**: `fix/readable-muted-copy`

**Created**: 2026-08-29

**Status**: Concluído; CI verde

**Input**: Issue #90 — `text_muted`/`text_dim` estão sendo usados em copy
visível que o usuário precisa ler, apesar de o design system reservar esses
tokens para estados desabilitados ou decoração.

## User Scenarios & Testing

### User Story 1 — Explicações legíveis (Priority: P1)

Como usuário, quero ler estados, hints e unidades importantes sem que a
hierarquia visual torne a informação excessivamente fraca sobre a superfície
escura.

**Independent Test**: construir a janela com fakes offscreen e auditar QLabel
com texto, além de proteger no código os pontos de copy citados no issue.

**Acceptance Scenarios**:

1. **Given** um hint de capacidade, estado de hardware, unidade ou empty state,
   **When** ele é exibido, **Then** usa `text_secondary` ou uma cor semântica
   de estado, nunca `text_muted`/`text_dim` como default de leitura.
2. **Given** um valor real `OFF`, um controle desabilitado ou um ponto
   decorativo, **When** ele aparece, **Then** `text_muted` continua permitido
   para manter a distinção semântica de baixa ênfase.
3. **Given** a UI em janela desktop ou pequena, **When** as páginas são
   renderizadas, **Then** a copy e a lógica permanecem inalteradas, mudando
   apenas o token de apresentação.

### User Story 2 — Contrato de manutenção (Priority: P1)

Como mantenedor, quero que uma regressão de copy fraca seja detectada sem
medir ou declarar conformidade WCAG sem uma medição reproduzível.

**Independent Test**: `pytest tests/test_issue90_readable_muted_copy.py` em CI,
sem hardware e sem sessão X11 real.

## Requirements

### Functional Requirements

- **FR-001**: Labels de leitura de Dashboard, DPI, Sensibilidade,
  Auto-Clicker, Macros, Perfis e Configurações MUST usar `text_secondary` ou
  token de estado apropriado.
- **FR-002**: Os usos legítimos em controles desabilitados, valores `OFF` e
  decoração MUST permanecer visualmente distintos.
- **FR-003**: Nenhuma lógica funcional, capacidade, persistência ou texto
  semântico MUST mudar como consequência da migração.
- **FR-004**: O teste MUST auditar labels construídos em runtime com fakes e
  proteger os pontos de estado inicial que podem começar vazios.
- **FR-005**: A mudança MUST incluir screenshots atualizadas quando o pipeline
  detectar alteração visual.
- **FR-006**: A documentação não MUST declarar um nível WCAG sem uma medição
  reproduzível; a claim é de aderência ao contrato de tokens do tema.

## Scope

Inclui a auditoria de `text_muted` e `text_dim` em copy visível na UI e os
pontos listados no issue. Não inclui recalibrar cores, redesenhar hierarquia
ou medir contraste em todas as combinações de plataforma.

## Edge Cases

- Um QLabel vazio pode ter estilo inicial muted sem ser copy exibida; o teste
  protege também os pontos conhecidos para evitar regressão quando ganharem
  texto.
- `OFF` é estado de baixa ênfase intencional e não é tratado como uma
  explicação ignorável.
- O ponto da sidebar e a cor de `QPushButton:disabled` são decoração/estado
  desabilitado, não copy de leitura comum.

## Success Criteria

- Nenhum QLabel de leitura não permitido aparece com o valor de
  `text_muted` em runtime.
- Os pontos de copy identificados no issue não referenciam `text_muted` no
  código-fonte.
- Teste dedicado e suíte existente passam sem thresholds enfraquecidos.
- Screenshots são regeneradas e não apresentam regressão estrutural.

## Key Entities

- `COLORS["text_secondary"]`: token de copy secundária legível.
- `COLORS["text_muted"]`: token restrito a disabled, `OFF` e decoração.
- QLabel de hints, estados, unidades e empty states nas páginas da aplicação.

## Review & Acceptance Checklist

- [ ] Copy de leitura usa token adequado.
- [ ] OFF/disabled/decorativo continuam distintos.
- [ ] Testes offscreen cobrem runtime e fonte.
- [ ] Screenshots atualizadas/verificadas.
- [ ] CI verde.
