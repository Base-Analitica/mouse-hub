# Implementation Plan: Copy de leitura com contraste adequado

**Branch**: `fix/readable-muted-copy` | **Spec**: [spec.md](spec.md) | **Created**: 2026-08-29

**Status**: Concluído; CI verde

## Summary

Migrar somente copy visível necessária para `text_secondary` ou cores
semânticas, mantendo `text_muted` em OFF, disabled e decoração. Adicionar
invariante runtime + fonte e regenerar o pipeline de screenshots.

## Technical Context

**Language/Version**: Python 3.10+; PyQt5 5.15.11 no CI
**Dependencies**: existentes; nenhuma dependência nova
**Storage**: N/A
**Testing**: pytest offscreen, fakes, suíte completa e smoke UI
**Target Platform**: Linux Mint/X11; validação de software sem hardware
**Project Type**: aplicação desktop PyQt5

## Constitution Check

| Princípio | Status | Nota |
| --- | --- | --- |
| I. Correção de hardware | N/A | Não altera operações de hardware |
| II. Honestidade de estado | PASS | Estados continuam diferenciados |
| III. Fakes no CI | PASS | Janela usa fakes/offscreen |
| IV. Regressão com teste | PASS | Teste dedicado RED antes do fix |
| V. Domínio no core | PASS | Mudança é apresentação |
| VI. Menor mudança completa | PASS | Só copy afetada e teste |
| VII. Verificação dupla | PASS | Sem alegação WCAG não medida |
| VIII. UX honesta e consistente | PASS | É o objetivo da issue |

## Design

1. Alterar os estilos de subtitle, hints, unidade CPS, status secundário,
   empty state e feedback de Perfis/Configurações para `text_secondary`.
2. Alterar o estado “sem G403” para `text_secondary`, pois é copy de estado,
   não decoração.
3. Manter `text_muted` para botões disabled, valores `OFF` e `_status_dot`.
4. O teste constrói a janela real com `FakeHidAccess`/`FakeSystemInput`,
   audita labels não vazios e verifica os pontos de fonte que podem iniciar
   vazios.
5. Executar screenshots e revisar mudanças somente de contraste.

## Verification Plan

- TDD: teste dedicado RED com labels atuais, depois GREEN.
- `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue90_readable_muted_copy.py -q`.
- `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q`.
- `xvfb-run -a python3 -m unittest tests.smoke_ui_init`.
- `python3 -m compileall -q mouse_hub tests app` e `git diff --check`.
- CI real no PR: `test`, `ui_smoke` e `deb_package`.

## Local Verification Results

- O teste dedicado passou com 2 testes.
- A suíte completa `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q`
  terminou com exit 0.
- O smoke `tests.smoke_ui_init`, `compileall` e `git diff --check` passaram.
- O pipeline de screenshots foi executado e atualizou as variantes desktop,
  pequena e preview afetadas.
- CI real do PR #131 passou nos jobs de testes determinísticos, pacote `.deb`
  e smoke da UI.
