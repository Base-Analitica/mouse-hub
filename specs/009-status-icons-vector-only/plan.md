# Implementation Plan: Status sem glifos dependentes de fonte

**Branch**: `fix/vector-status-icons` | **Spec**: [spec.md](spec.md) | **Created**: 2026-08-29

**Status**: Convergido localmente; aguardando CI do PR

## Summary

Substituir os doze usos de `✔`/`⚠` em `app/mouse_hub_app.py` por texto
semântico + cor existente. O único indicador isolado, o alerta grande do
Auto-Clicker, usará `ui_icons.icon("alert", ...)` com fallback texto-only
conforme o contrato de `app/ui/icons.py`. Não haverá mudança de lógica.

## Technical Context

**Language/Version**: Python 3.10+; PyQt5 5.15.11 no CI
**Dependencies**: existentes; nenhuma dependência nova
**Storage**: N/A
**Testing**: pytest offscreen, fakes existentes, suíte completa e smoke UI
**Target Platform**: Linux Mint/X11; o CI não exige hardware ou X11 real
**Project Type**: aplicação desktop PyQt5 em `app/mouse_hub_app.py`

## Constitution Check

| Princípio | Status | Nota |
| --- | --- | --- |
| I. Correção de hardware | N/A | Nenhuma operação HID é alterada |
| II. Honestidade de estado | PASS | Texto e cores continuam distinguindo estados |
| III. Fakes no CI | PASS | Teste estático/offscreen, sem hardware |
| IV. Regressão com teste | PASS | Teste dedicado falha com glifos presentes |
| V. Domínio no core | PASS | Mudança é exclusivamente apresentação |
| VI. Menor mudança completa | PASS | 12 literais, helper do ícone, teste e artefatos |
| VII. Verificação dupla | PASS | Claim limitada à renderização/software |
| VIII. UX honesta e consistente | PASS | Iconografia não depende de fonte |

## Design

1. **Mensagens inline**: retirar o prefixo e manter copy, estilo e token de
   cor que já expressam sucesso, atenção ou falha.
2. **Alerta isolado**: adicionar um pequeno helper local à
   `AutoClickerPage` para limpar `status_icon` e aplicar o `QIcon` vetorial
   `alert`; se `ui_icons.icon()` retornar `None`, o QLabel fica vazio e o
   título/subtítulo textual permanece.
3. **Regressão**: o teste dedicado verifica ausência dos dois caracteres,
   ausência de emoji substituto, ausência de condicionais vazias e preservação
   dos tokens semânticos. O teste de UI verifica o caminho vetorial/fallback.
4. **Artefatos**: regenerar screenshots depois da alteração. O estado default
   não deve introduzir hardware real.

## Riscos e mitigação

- **Fonte subset indisponível**: contrato de `ui_icons` já prevê `None`; o
  fallback textual não lança exceção.
- **Mudança visual inesperada**: comparar imagens regeneradas e executar smoke
  da UI; nenhum layout ou comportamento de ação é alterado.

## Project Structure

```text
specs/009-status-icons-vector-only/
├── spec.md
├── plan.md
├── tasks.md
└── checklists/requirements.md
app/mouse_hub_app.py
app/ui/icons.py
tests/test_issue84_no_status_glyphs.py
docs/screenshots/
```

## Verification Plan

- TDD: guardar a implementação, executar o teste dedicado e observar falha
  pelos glifos; restaurar, implementar, observar verde.
- `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue84_no_status_glyphs.py -q`
- Suíte completa `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q`.
- `python3 -m compileall -q mouse_hub tests app`.
- Regenerar screenshots e validar `git diff --check`.
- CI real do PR: jobs `test`, `ui_smoke` e `deb_package`.

## Local Convergence Evidence

- Teste dedicado: 6 passed.
- Regressões de UI (`test_issue7_ui_caps.py` e `test_issue6_profiles_polling.py`): 37 passed.
- Suíte completa: exit 0, todos os testes passaram.
- Smoke UI via Xvfb: 1 test OK.
- `compileall`, `git diff --check` e busca de `✔`/`⚠`: OK.
