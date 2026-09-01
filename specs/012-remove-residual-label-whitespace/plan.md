# Implementation Plan: Remover whitespace residual das labels

**Branch**: `fix/remove-residual-label-whitespace` | **Spec**: [spec.md](spec.md) | **Created**: 2026-08-29

**Status**: Convergido localmente; aguardando commit/PR

## Summary

Limpar whitespace prefixado e múltiplo usado como mecanismo de apresentação em
labels, botões, títulos e status da UI, mantendo o conteúdo semântico e
substituindo a dependência textual de `Play`/`Cancel` por valores limpos.
Adicionar uma regressão runtime/fonte e regenerar as screenshots afetadas.

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
| II. Honestidade de estado | PASS | Play/Cancel continuam refletindo playback real |
| III. Fakes no CI | PASS | Auditoria usa janela real e fakes offscreen |
| IV. Regressão com teste | PASS | Teste dedicado será RED antes do fix |
| V. Domínio no core | PASS | Mudança fica na apresentação da UI |
| VI. Menor mudança completa | PASS | Somente copy e teste, sem redesign |
| VII. Verificação dupla | PASS | Runtime, fonte, suíte e screenshots |
| VIII. UX honesta e consistente | PASS | Layout não depende de caracteres invisíveis |

## Design

1. Remover prefixos dos presets de DPI, labels de macro, nomes de itens,
   títulos/status de Configurações e título da janela.
2. Normalizar separadores de copy de dois espaços para um espaço quando forem
   texto visível, sem alterar o conteúdo das informações.
3. Atualizar `_update_play_status()` e o callback de playback para comparar e
   escrever exatamente `Play` e `Cancel`.
4. Construir a janela real com fakes, percorrer todas as páginas e auditar
   `QLabel`, `QPushButton`, `QGroupBox` e o título da janela; permitir apenas
   espaços internos legítimos de nomes/copy e o sufixo de unidade controlado
   pelo Qt.
5. Regenerar screenshots de DPI, Macros, Perfis e Configurações em desktop,
   pequena e preview.

## Verification Plan

- TDD: teste dedicado RED com os resíduos atuais, depois GREEN.
- `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue89_residual_label_whitespace.py -q`.
- `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q`.
- `xvfb-run -a python3 -m unittest tests.smoke_ui_init`.
- `python3 -m compileall -q mouse_hub tests app` e `git diff --check`.
- CI real no PR: `test`, `ui_smoke` e `deb_package`.

## Local Verification Results

- O teste dedicado passou com 3 testes, após RED confirmado antes do fix.
- Os testes relacionados de macros, perfis e capacidades passaram.
- A suíte completa `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q`
  terminou com exit 0.
- O smoke `tests.smoke_ui_init`, `compileall` e `git diff --check` passaram.
- O pipeline de screenshots foi executado para as sete telas, variantes small
  e `preview.png`; somente imagens afetadas foram alteradas.
- CI real permanece pendente até a abertura do PR.
