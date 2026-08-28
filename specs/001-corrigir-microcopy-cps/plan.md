# Implementation Plan: Microcopy consistente do heading CPS

**Branch**: `001-corrigir-microcopy-cps` | **Spec**: [spec.md](spec.md) | **Created**: 2026-08-28

## Summary

Trocar o texto do QLabel `cps_title` na página do Auto-Clicker de
`CPS (Clicks Por Segundo)` para `CPS (Cliques por segundo)`, com teste de
regressão offscreen e regeneração das screenshots públicas do clicker.

## Technical Context

**Language/Version**: Python 3.10+ (produto), PyQt5 5.15.11 (CI)
**Dependencies**: PyQt5, python-xlib (produção); pytest (dev) — nenhuma nova
**Storage**: N/A (mudança de microcopy; persistência de CPS/botão não é tocada)
**Testing**: pytest com `QT_QPA_PLATFORM=offscreen`; smoke de UI via Xvfb no CI
**Target Platform**: Linux Mint, app desktop PyQt5
**Project Type**: single app (`app/mouse_hub_app.py`) — sem mudança de arquitetura

## Constitution Check

| Princípio | Status | Nota |
| --- | --- | --- |
| I. Correção de hardware | N/A | Não toca em HID++/hardware |
| II. Honestidade de estado | PASS | Texto apenas; sem mudança de estado |
| III. Fakes no CI | PASS | Teste novo roda offscreen, sem hardware |
| IV. Regressão com fix | PASS | Teste de heading entra no mesmo PR |
| V. Domínio no core | PASS | Microcopy é UI; nenhuma regra de domínio |
| VI. Menor mudança completa | PASS | 1 linha de produto + 1 teste + screenshots |
| VII. Verificação dupla | PASS | Claim limitada ao software (texto da UI) |
| VIII. UX honesta e consistente | PASS | É o objetivo da feature |

## Project Structure

### Documentation (this feature)

```text
specs/001-corrigir-microcopy-cps/
├── spec.md          # Spec da feature (issue #117)
├── plan.md          # Este arquivo
├── research.md      # Fase 0 — decisões
├── quickstart.md    # Fase 1 — como verificar
└── tasks.md         # Gerado por /speckit-tasks
```

### Source Code (repository root)

```text
app/mouse_hub_app.py                       # linha ~1591: cps_title
tests/test_issue66_ui_craft.py             # suíte de UI craft onde o teste entra
docs/screenshots/                          # pipeline de screenshots (regenerar)
```

**Structure Decision**: Mudança de 1 ponto no monólito de UI existente; nenhuma
nova estrutura. Teste entra na suíte de UI craft já existente (`offscreen`).

## Phase 0: Outline & Research

Decisões (research.md inline — sem unknowns):

1. **Copy final**: `CPS (Cliques por segundo)`
   - Decision: expansão completa em pt-BR, minúsculas após a primeira palavra.
   - Rationale: a issue #117 oferece `CPS (Cliques por segundo)` ou apenas
     `CPS`; a expansão preserva o valor didático para novos usuários e elimina
     a mistura de idiomas. Capitalização em sentence case segue o padrão do
     resto da UI.
   - Alternatives considered: apenas `CPS` (mais curto, mas perde a expansão
     que ajuda o usuário novo a entender o controle).

2. **Localização do teste**: `tests/test_issue66_ui_craft.py`
   - Decision: novo teste na suíte de craft de UI, verificando o texto do
     QLabel via `QT_QPA_PLATFORM=offscreen`.
   - Rationale: é a suíte que já valida textos/estados da UI sem exibir janela;
     aderente ao Princípio III (fakes/offscreen no CI).
   - Alternatives considered: teste novo dedicado (arquivo extra sem necessidade).

3. **Screenshots**: regeneradas pelo pipeline do projeto
   - Decision: usar o fluxo documentado em `docs/screenshots/` após o fix.
   - Rationale: FR-004 exige screenshots atualizadas; o pipeline é a prática
     permanente estabelecida na PR #76.
   - Alternatives considered: nenhuma.

**Output**: sem NEEDS CLARIFICATION pendentes.

## Phase 1: Design & Contracts

Sem modelos de dados, contratos de API ou integrações — a feature altera texto
de um widget. `quickstart.md` documenta a verificação manual/automática.

**Post-design Constitution Check**: sem violações novas (tabela acima permanece
válida — a mudança continua sendo texto de UI + teste offscreen).

## Progress Tracking

**Phase Status**:
- [x] Phase 0: Research complete
- [x] Phase 1: Design complete
- [ ] Phase 2: Task planning complete (/speckit-tasks)
- [ ] Phase 3: Implementation complete
- [ ] Phase 4: Validation complete (/speckit-converge)

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved
