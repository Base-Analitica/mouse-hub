# Implementation Plan: Design system sem drift de tokens

**Branch**: `fix/design-token-drift` | **Spec**: [spec.md](spec.md) | **Created**: 2026-08-29

**Status**: Convergido localmente; aguardando CI do PR

## Summary

Adicionar três tokens dimensionais nomeados preservando os valores atuais e
substituir os cinco usos de cores/medidas hardcoded identificados no issue.
Adicionar um teste de invariantes. A mudança permanece restrita ao tema, à
UI e aos testes, sem alterar comportamento funcional.

## Technical Context

**Language/Version**: Python 3.10+; PyQt5 5.15.11 no CI
**Dependencies**: existentes; nenhuma dependência nova
**Storage**: N/A
**Testing**: pytest offscreen, suíte completa e smoke UI
**Target Platform**: Linux Mint/X11; fakes e screenshots determinísticos
**Project Type**: aplicação desktop PyQt5

## Constitution Check

| Princípio | Status | Nota |
| --- | --- | --- |
| I. Correção de hardware | N/A | Nenhum caminho HID é alterado |
| II. Honestidade de estado | PASS | Só tokens visuais mudam |
| III. Fakes no CI | PASS | Teste estático, sem hardware |
| IV. Regressão com teste | PASS | Invariante RED antes do fix |
| V. Domínio no core | PASS | Tema/UI, sem regra de domínio |
| VI. Menor mudança completa | PASS | Tokens mínimos e ocorrências listadas |
| VII. Verificação dupla | PASS | Claim visual limitada ao software |
| VIII. UX honesta e consistente | PASS | Fonte única de tokens é o objetivo |

## Design

1. Adicionar `RADIUS["card"] = 16`, `SPACE["card"] = 20` e
   `SPACE["empty_state"] = 30`, mantendo os números atuais.
2. Importar `RADIUS` na UI e substituir raios/paddings excepcionais por
   expressões dos tokens, inclusive nos stylesheets formatados com `%`.
3. Substituir `#c4b5fd`, `#f87171` e `#fca5a5` pelos tokens correspondentes.
4. O teste verifica somente o contrato do issue e não proíbe a UI inteira de
   conter qualquer valor inline legado.
5. Regenerar screenshots depois do fix e revisar diffs binários.

## Verification Plan

- TDD: teste dedicado falha antes da implementação e passa depois.
- `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue96_design_tokens.py -q`.
- `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q`.
- `xvfb-run -a python3 -m unittest tests.smoke_ui_init`.
- `python3 -m compileall -q mouse_hub tests app` e `git diff --check`.
- `tests/test_issue96_design_tokens.py` — 3 passed.
- Regressões de UI: 11 passed.
- Suíte completa: exit 0, todos os testes passaram.
- Captura de screenshots: concluída e sem diff visual não intencional.
- `compileall` e `git diff --check`: OK.
