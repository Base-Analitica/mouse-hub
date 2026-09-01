# Implementation Plan: Hint de capacidade do Auto-Clicker visível

**Branch**: `fix/autoclicker-capability-hint` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

## Summary

O `AutoClickerPage` já possui um `caps_hint` que recebe a causa real de `CapabilityState`, mas o widget não é adicionado ao `QVBoxLayout`. O plano adiciona esse widget existente entre `mc_status` e o bloco de controles, preserva o gating e prova os estados disponível/indisponível com testes Qt offscreen, screenshots e CI.

## Technical Context

**Language/Version**: Python 3.10+

**Primary Dependencies**: PyQt5 5.15.11 em runtime; pytest e Xvfb no desenvolvimento/CI.

**Storage**: N/A. Nenhum dado ou configuração é alterado.

**Testing**: pytest offscreen, smoke Xvfb, compileall, diff check, captura oficial e empacotamento `.deb`.

**Target Platform**: Linux Mint, aplicativo desktop nativo, viewports 1050×680 e 760×560.

**Project Type**: Aplicativo desktop Python/PyQt5.

**Performance Goals**: Nenhuma operação nova em runtime; um `QLabel` já criado será apenas inserido no layout.

**Constraints**: Sem mudança em `mouse_hub/core/`, protocolo, dependências ou regras de automação. Preservar os textos e o escopo editorial de #83.

**Scale/Scope**: Uma inserção de layout, um teste dedicado ou extensão focada, três capturas afetadas e artifacts Spec Kit.

## Constitution Check

*GATE: Deve passar antes da implementação e ser reavaliado após a validação.*

| Princípio | Status pré-implementação | Evidência prevista |
|---|---|---|
| I. Correção de Hardware | N/A | O diff não toca HID++, udev, descoberta ou dispositivo. |
| II. Honestidade de Estado | PASS | O hint projeta a disponibilidade e a causa existentes; não simula capacidade. |
| III. Fakes no CI | PASS | Testes usam `CapabilityModel` fake e Qt offscreen/Xvfb, sem hardware. |
| IV. Regressão Com Teste | PASS planejado | O teste do widget no layout falhará antes de inserir o `addWidget`. |
| V. Domínio no Core | PASS | Nenhuma regra de domínio ou constante será criada. |
| VI. Menor Mudança Completa | PASS | Reutiliza `caps_hint`, sem helper ou dependência nova. |
| VII. Verificação Dupla | PASS planejado | Evidência de software será separada de qualquer alegação física. |
| VIII. UX Honesta e Consistente | PASS | Causa visível e status de foco permanecem semanticamente distintos. |

**Resultado do gate**: PASS. Não há violação constitucional prevista.

## Recheck after implementation

| Princípio | Status | Evidência observada |
|---|---|---|
| I. Correção de Hardware | N/A | O diff não toca HID++, udev, descoberta ou dispositivo. |
| II. Honestidade de Estado | PASS | O hint projeta `is_available` e `reason_for` do capability state e não usa foco como substituto. |
| III. Fakes no CI | PASS | 24 regressões focadas, smoke Xvfb e 549 testes completos passaram sem hardware físico. |
| IV. Regressão Com Teste | PASS | RED com 5 falhas antes do patch e GREEN com 5 testes depois. |
| V. Domínio no Core | PASS | Nenhuma regra de domínio foi criada ou movida. |
| VI. Menor Mudança Completa | PASS | Um widget existente foi reposicionado/inserido; não houve dependência ou refatoração drive-by. |
| VII. Verificação Dupla | PASS | Testes, package, geometria e capturas foram observados como software; nenhuma validação física foi alegada. |
| VIII. UX Honesta e Consistente | PASS | A causa aparece perto dos controles e `mc_status` continua independente. |

**Resultado do gate**: PASS após implementação local. Revisão e CI remoto ainda são gates de entrega.

## Project Structure

### Documentation

```text
specs/024-autoclicker-capability-hint/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
└── tasks.md
```

Não há `contracts/`: a mudança não cria API externa, persistência ou contrato de domínio.

### Source Code

```text
app/mouse_hub_app.py                         # inserir caps_hint no layout existente
tests/test_issue78_autoclicker_capability_hint.py  # regressão do hint e dos dois estados
docs/screenshots/3_clicker.png              # captura desktop afetada
docs/screenshots/small_clicker.png          # captura small afetada
docs/screenshots/preview.png                # mosaico público afetado
```

**Structure Decision**: Reutilizar a montagem e sincronização existentes de `AutoClickerPage`. O teste deve observar o widget real no layout e o texto derivado do capability provider, sem criar camada de apresentação paralela.

## Design and Data Flow

1. `_build()` cria `mc_status`, `caps_hint` e os controles como já faz hoje.
2. `layout.addWidget(self.caps_hint)` é executado depois de `mc_status` e antes de `cps_title`.
3. `_sync_caps()` continua consultando `is_available("autoclick_available")` e `reason_for(...)`.
4. O mesmo `caps_hint` recebe a copy de disponibilidade ou indisponibilidade, sem duplicação.
5. O gating atual continua habilitando/desabilitando slider, seletor e CTA.
6. O capturador oficial atualiza as superfícies do Auto-Clicker e o preview se houver diferença.

## Test Strategy

- Criar primeiro o teste dedicado, antes da linha de produção, verificando que `caps_hint` está no layout e que o estado indisponível expõe a causa.
- Rodar o teste focado em RED. A falha esperada deve ser a ausência do widget no layout, não erro de fixture/import.
- Inserir somente `layout.addWidget(self.caps_hint)` e rodar GREEN.
- Cobrir estado disponível, estado indisponível, mudança de estado e independência de `mc_status`.
- Exercitar geometria nos dois viewports, regressões de capabilities, smoke Xvfb, suíte completa e pacote `.deb`.
- Capturar duas vezes e comparar bytes das três imagens afetadas e regiões não relacionadas.
- Fazer revisão read-only na rota de swarm autorizada antes de abrir PR.

## Implementation Phases

### Phase 0: Spec and contract

- Completar estes artifacts sem placeholders.
- Criar teste antes de qualquer alteração em produção.

### Phase 1: Capability explanation

- Adicionar o `caps_hint` existente ao `QVBoxLayout` no ponto definido.
- Não alterar `CapabilityModel`, gating, timers, foco ou textos do issue #83.

### Phase 2: Regression and visual evidence

- Rodar teste dedicado e regressões de UI/capabilities.
- Verificar os dois viewports e regenerar capturas oficiais.
- Rodar compileall, diff check, smoke, suíte e empacotamento.

### Phase 3: Delivery

- Atualizar artifacts com evidência real e reavaliar a constituição.
- Revisar diff, commitar em inglês, publicar branch e abrir PR com `Closes #78`.
- Confirmar os três checks reais do GitHub, PR aberto e `mergedAt == null`.

## Risks and Mitigations

- **Risco**: inserir uma linha causar overflow no viewport small. **Mitigação**: `wordWrap`, teste geométrico e screenshots desktop/small.
- **Risco**: hint duplicar ou substituir o status de foco. **Mitigação**: assert de identidade/ordem no layout e teste de `mc_status` independente.
- **Risco**: UI afirmar capacidade sem evidência. **Mitigação**: manter `CapabilityState` como fonte e testar os dois estados.
- **Risco**: misturar #78 com remoção de jargão de #83. **Mitigação**: não alterar as strings existentes neste diff.
- **Risco**: alegar validação física indevida. **Mitigação**: registrar somente fakes, offscreen/Xvfb e package checks.

## Complexity Tracking

Nenhuma violação constitucional ou complexidade adicional prevista.

## Validation Record

- **Baseline**: `origin/main` passou com 544 testes antes da alteração.
- **TDD RED**: `tests/test_issue78_autoclicker_capability_hint.py` falhou em 5 asserts esperados porque o label não estava no layout.
- **GREEN focado**: o teste dedicado passou com 5 testes após a inserção do widget existente.
- **Regressões**: o teste dedicado, `tests/test_issue7_ui_caps.py` e `tests/test_issue66_ui_craft.py` passaram com 24 testes.
- **Geometria**: os viewports 1050x680 e 760x560 mantiveram o hint visível, com word-wrap, e o CTA dentro da página.
- **Screenshots**: a captura oficial foi repetida e `3_clicker.png`, `small_clicker.png` e `preview.png` foram idênticos entre as duas execuções; somente esses arquivos mudaram contra `origin/main`.
- **Integridade**: compileall e `git diff --check` passaram.
- **Smoke**: `tests.smoke_ui_init` passou com 1 teste OK via Xvfb.
- **Suíte completa**: `pytest tests/ -q -rA` passou com 549 testes, sem falhas.
- **Pacote**: `.deb` válido gerado com `dpkg-deb`, contendo o launcher e a fonte embutida esperada.
- **Entrega pendente**: revisão read-only, commit/publicação, PR com `Closes #78` e os três checks reais do GitHub.
