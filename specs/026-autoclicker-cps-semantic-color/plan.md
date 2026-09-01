# Implementation Plan: Cor semântica do valor CPS

**Branch**: `026-autoclicker-cps-semantic-color` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

## Summary

Substituir somente o token de cor permanente do `cps_display` na
`AutoClickerPage`: `warning` será trocado por `accent_light`, mantendo o valor,
a unidade, o slider, o engine e todos os estados reais inalterados. O contrato
será protegido por teste offscreen dedicado, screenshots regeneradas e
validação completa local/remota.

## Technical Context

**Language/Version**: Python 3.10+

**Primary Dependencies**: PyQt5 5.15.11, pytest, dependências já presentes; nenhuma nova

**Storage**: N/A; o valor CPS continua vindo do engine e da configuração existente

**Testing**: pytest offscreen, smoke PyQt5 via Xvfb, compileall, `git diff --check`, captura determinística e empacotamento `.deb`

**Target Platform**: Linux Mint; UI desktop nativa PyQt5

**Project Type**: aplicação desktop single-project

**Performance Goals**: nenhuma alteração de runtime ou caminho quente; custo adicional zero

**Constraints**: não tocar em core, plataforma, persistência, hardware, foco, capability gating ou limites 1–50 CPS; preservar warning em estados reais

**Scale/Scope**: um QLabel na AutoClickerPage, um teste dedicado e três PNGs públicas

## Constitution Check

| Princípio | Status | Nota |
| --- | --- | --- |
| I. Correção de Hardware em Primeiro Lugar | N/A | A mudança não toca HID++, udev ou hardware. |
| II. Honestidade de Estado (UI Não Simula) | PASS | O valor e os estados permanecem os mesmos; apenas a cor deixa de simular atenção. |
| III. Fakes no CI, Hardware Fora | PASS | Testes usam páginas reais, fakes existentes e `QT_QPA_PLATFORM=offscreen`. |
| IV. Regressão Com Teste Junto do Fix | PASS | O teste novo será executado RED contra o token warning atual antes do fix. |
| V. Regras de Domínio Somente no Core | PASS | Nenhuma regra de domínio ou limite é criado na UI. |
| VI. Menor Mudança Completa | PASS | Um valor de stylesheet, teste rastreável, docs Spec Kit e screenshots afetadas. |
| VII. Verificação Dupla (Software e Realidade) | PASS | Claims serão limitadas à evidência de software; não há claim de hardware/X11 real. |
| VIII. UX Honesta e Consistente | PASS | Warning fica reservado a atenção real e CPS normal usa destaque neutro. |

## Project Structure

### Documentation (this feature)

```text
specs/026-autoclicker-cps-semantic-color/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
app/mouse_hub_app.py                         # estilo do QLabel cps_display
app/ui/theme.py                              # tokens COLORS existentes, somente leitura

tests/test_issue80_autoclicker_cps_color.py # regressão da cor e interação CPS
tests/test_hid_permission_helper.py          # contrato existente de warning HID usado como referência

docs/screenshots/3_clicker.png              # captura desktop afetada
docs/screenshots/small_clicker.png          # captura small afetada
docs/screenshots/preview.png                # mosaico regenerado
```

**Structure Decision**: manter a arquitetura existente. A regra é puramente
visual, portanto o código de produção continua em `app/mouse_hub_app.py`; não
há motivo para criar helper, token novo ou camada adicional.

## Design Decisions

1. Usar `COLORS['accent_light']`, já definido no tema, no `cps_display`.
2. Cobrir 1, 25 e 50 CPS e a interação do slider com uma página real offscreen.
3. Verificar que uma mensagem de permissão HID que requer atenção continua com
   `COLORS['warning']`.
4. Regerar apenas as imagens realmente afetadas e confirmar que o diff visual
   não se espalhou para outras telas.

## Traceability Matrix

| Requisito | Implementação | Verificação |
| --- | --- | --- |
| FR-001 / SC-001 | `cps_display` usa `accent_light`, não `warning` | teste dedicado nos valores 1, 25 e 50 |
| FR-002 / SC-002 | `_on_cps` e unidade permanecem inalterados | teste de slider, texto e unidade |
| FR-003 | nenhuma condição/threshold nova | inspeção do diff + teste de estados |
| FR-004 / SC-003 | `_sync_permission_ui` permanece intacto | teste real de SettingsPage com permissão negada |
| FR-005 / SC-006 | somente apresentação da UI é modificada | `git diff --name-only` e revisão |
| FR-006 / SC-004 | pipeline oficial | duas capturas, hashes e bbox de diff |
| FR-007 / SC-005 | teste dedicado RED/GREEN | pytest focado e suíte completa |

## Validation Gates

- Baseline completo no worktree: passou com 553 testes antes da mudança.
- RED: teste de cor deve falhar contra `COLORS['warning']` atual.
- GREEN: teste dedicado e regressões passam após a troca mínima.
- Antes da entrega: suíte, smoke, compileall, diff check, pacote e capturas.
- Após push: os três checks reais do GitHub precisam estar verdes.
- O PR fica aberto para decisão do mantenedor; este agente não faz merge.

## Complexity Tracking

Nenhuma violação da Constituição. Não há complexidade adicional a justificar.
