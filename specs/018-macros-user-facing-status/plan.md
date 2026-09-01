# Implementation Plan: Status de Macros orientado à tarefa

**Branch**: `fix/macros-user-facing-status` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/018-macros-user-facing-status/spec.md`

**Status**: Convergido localmente; aguardando PR/CI

## Summary

Substituir o jargão de backend exposto pela `MacrosPage` por mensagens orientadas
à capacidade e à tarefa. A UI deve transformar somente a copy apresentada, sem
alterar `macro_capture_available`, o gating dos controles ou o backend de captura.
Mensagens técnicas recebidas durante uma falha serão reduzidas a uma consequência
compreensível quando o texto mencionar detalhes internos.

## Technical Context

**Language/Version**: Python 3.10+

**Primary Dependencies**: PyQt5 5.15.11, pytest e fakes existentes

**Storage**: N/A

**Testing**: pytest offscreen, testes de UI fakeados, smoke Xvfb, compileall

**Target Platform**: Linux Mint/X11; CI sem hardware físico

**Project Type**: Aplicação desktop PyQt5

**Performance Goals**: Nenhum custo novo de polling, subprocesso ou backend

**Constraints**: Não mudar core, `InputCapture`, `AutomationService` ou o modelo
de capacidades; copy deve caber em 1050×680 e 760×560.

**Scale/Scope**: `MacrosPage`, testes de copy e três capturas públicas.

## Constitution Check

| Princípio | Status | Nota |
| --- | --- | --- |
| I. Correção de hardware | PASS | Nenhuma operação de hardware é alterada. |
| II. Honestidade de estado | PASS | Disponibilidade continua vindo da capacidade real. |
| III. Fakes no CI | PASS | Testes usam `CapabilityState` e `FakeMe`; sem sessão real. |
| IV. Regressão com teste | PASS | Testes rejeitam o jargão antes da mudança. |
| V. Domínio no core | PASS | Só copy de apresentação muda em `app/`. |
| VI. Menor mudança completa | PASS | Helper local, testes, specs e capturas, sem refactor. |
| VII. Verificação dupla | PASS | Claim limitada a software e renderização fakeada. |
| VIII. UX honesta e consistente | PASS | Status explica capacidade sem expor implementação. |

## Design

1. **Copy disponível**: `_sync_caps()` usa `Gravação de macros disponível`.
2. **Copy indisponível**: mapear causas que mencionam `X11`, `XRecord`, `XTest` ou
   `DISPLAY` para uma explicação de sessão gráfica; outras causas adequadas podem
   permanecer como diagnóstico de capacidade.
3. **Feedback de operação**: trocar o texto de início para “Iniciando gravação…”
   e sanitizar mensagens de exceção/falha antes de colocá-las em `record_status`.
4. **Sanitização local**: um helper privado da página remove nomes de backend da
   copy operacional, sem mutar `CapabilityState`, `capture_failed` ou logs.
5. **Regressão**: testes offscreen verificam estados disponível, indisponível,
   início e falha técnica; os testes atuais de gravação continuam intactos.

## Project Structure

```text
app/mouse_hub_app.py                         # copy operacional da MacrosPage
tests/test_issue113_macro_copy.py            # contrato de copy sem backend
tests/test_issue4_macro_recording.py         # regressões de gravação existentes
docs/screenshots/4_macros.png                # captura desktop
docs/screenshots/small_macros.png            # captura 760×560
docs/screenshots/preview.png                 # preview público
specs/018-macros-user-facing-status/         # artefatos Spec Kit
```

**Structure Decision**: Manter o limite entre core e UI. O helper de sanitização
fica junto da página porque só traduz mensagens para apresentação.

## Verification Plan

- TDD: escrever teste que observa backend na copy atual e confirmar RED.
- Implementar copy e sanitização mínima, confirmar GREEN focado.
- Rodar suíte completa offscreen, smoke Xvfb, compileall e `git diff --check`.
- Regenerar capturas oficiais e revisar somente Macros/preview.
- Abrir PR baseado em `main`, sem merge, e confirmar os três jobs reais do CI.

## Local Convergence Evidence

- **RED**: `QT_QPA_PLATFORM=offscreen python3 -m pytest
  tests/test_issue113_macro_copy.py -q` falhou nos 4 casos antes da mudança,
  pois a copy disponível, indisponível, inicialização e falha expunham jargão.
- **GREEN focado**: `tests/test_issue113_macro_copy.py`,
  `tests/test_issue4_macro_recording.py` e `tests/test_issue7_ui_caps.py` —
  26 passed.
- **Suíte completa**: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q`
  terminou com exit 0.
- **Smoke**: `QT_QPA_PLATFORM=offscreen xvfb-run -a python3 -m unittest
  tests.smoke_ui_init` — 1 test OK.
- **Integridade**: `python3 -m compileall -q mouse_hub tests app` e
  `git diff --check` — OK.
- **Capturas**: script oficial regenerou as variantes desktop e small; somente
  `4_macros.png`, `small_macros.png` e `preview.png` mudaram.

## Delivery Gate

- PR deve partir de `main`, fechar a #113 e manter a validação física de um
  G403 fora das claims.
- Os três jobs reais do CI ainda precisam passar no commit final.
