# Microcopy de segurança do Auto-Clicker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolver conjuntamente #82 e #83 no mesmo bloco de segurança, removendo cor semântica indevida e jargão de implementação sem alterar a proteção funcional.

**Architecture:** Reutilizar o `QLabel` existente em `SettingsPage`, trocar seu texto por uma explicação de comportamento e aplicar `COLORS['text_secondary']`. O motor e o serviço de foco permanecem nas camadas atuais.

**Tech Stack:** Python 3.10+, PyQt5 5.15.11, pytest, Xvfb e pipeline de screenshots determinísticas.

**Spec:** `specs/028-autoclicker-security-copy/spec.md`

## Global Constraints

- Não tocar em `mouse_hub/core`, `mouse_hub/platform`, automação, persistência, capability gating ou controles.
- Manter copy pt-BR, word wrap e compatibilidade com 1050×680 e 760×560.
- Escrever os testes antes do código e observar RED contra a copy/estilo atuais.
- Usar fakes no CI e distinguir evidência de software de sessão X11 real.
- Um único PR pode fechar #82 e #83 porque ambos corrigem o mesmo parágrafo e as mesmas screenshots.

---

**Branch**: `fix/autoclicker-security-copy` | **Date**: 2026-08-30 | **Spec**: [spec.md](spec.md)

## Summary

Substituir o parágrafo verde de segurança por copy curta orientada ao comportamento e cor neutra de leitura. A regra real de foco continua intacta.

## Technical Context

**Language/Version**: Python 3.10+

**Primary Dependencies**: PyQt5 5.15.11, pytest e dependências já presentes

**Storage**: N/A; nenhuma configuração ou estado persistido é alterado

**Testing**: pytest offscreen, regressões de automação/capabilities, smoke PyQt5 via Xvfb, compileall, `git diff --check`, captura determinística e empacotamento `.deb`

**Target Platform**: Linux Mint, aplicação desktop nativa PyQt5

**Project Type**: aplicação desktop single-project

**Constraints**: só o texto e stylesheet do `safety_text`; nenhum backend de foco ou motor de clique

## Constitution Check

| Princípio | Status | Nota |
| --- | --- | --- |
| I. Correção de Hardware em Primeiro Lugar | N/A | Não há acesso a hardware nesta mudança. |
| II. Honestidade de Estado (UI Não Simula) | PASS | A copy descreve a condição de foco sem afirmar que o motor está ativo ou que clicou. |
| III. Fakes no CI, Hardware Fora | PASS | A página é construída com fakes; a segurança do motor é coberta por regressões existentes. |
| IV. Regressão Com Teste Junto do Fix | PASS | O teste dedicado deve falhar com cor/jargão atuais e passar com a mudança. |
| V. Regras de Domínio Somente no Core | PASS | Nenhuma regra de domínio é criada ou movida. |
| VI. Menor Mudança Completa | PASS | Um bloco de texto/estilo, teste dedicado, screenshots e Spec Kit. |
| VII. Verificação Dupla (Software e Realidade) | PASS | Claims ficam limitadas à evidência do software; não há claim de sessão X11 real. |
| VIII. UX Honesta e Consistente | PASS | A superfície usa linguagem acionável e reserva verde para estados reais. |

## Project Structure

```text
app/mouse_hub_app.py                              # QLabel safety_text, copy e cor neutra
 tests/test_issue82_83_security_copy.py          # regressão de copy/estilo/layout
docs/screenshots/6_settings.png                  # captura desktop afetada
docs/screenshots/small_settings.png              # captura small afetada
docs/screenshots/preview.png                     # mosaico regenerado
.specify/feature.json                             # ponte para esta feature
specs/028-autoclicker-security-copy/              # artefatos Spec Kit
```

## Design Decisions

1. Manter um único `QLabel` e trocar somente seu literal e stylesheet.
2. Dizer explicitamente que o jogo permitido deve estar em foco.
3. Dizer que o app verifica a janela antes de clicar e não clica fora do jogo.
4. Usar `text_secondary` para corpo explicativo, sem remover cores de estados reais.
5. Preservar `_update`, `_sync_caps`, `_toggle`, engine, cache e gating.

## Traceability Matrix

| Requisito | Implementação | Verificação |
| --- | --- | --- |
| FR-001 / SC-001 | copy orientada a foco | teste de termos de Minecraft/Lunar Client e foco |
| FR-002 / SC-001 | copy explicita bloqueio fora do jogo | teste de garantia de nenhum clique fora |
| FR-003 / SC-003 | stylesheet `text_secondary` | teste de token neutro e ausência de `mc_green` |
| FR-004 / SC-002 | remoção de backend/TTL | asserts negativos de jargão |
| FR-005 / SC-005 | motor e controles sem alteração | regressões de automação/capabilities |
| FR-006 / SC-008 | diff restrito | diff, compileall e revisão read-only |
| FR-007 / SC-006 | pipeline oficial | duas capturas, hashes e bbox |
| FR-008 / SC-007 | RED/GREEN e integração | pytest, suíte, smoke, pacote e CI |

## Validation Gates

- Baseline completo passa antes dos testes novos.
- RED deve mostrar falhas atribuíveis à copy/stylesheet antigas.
- GREEN deve passar no teste dedicado e nas regressões do motor/capabilities.
- Screenshots desktop/small/preview devem ser reproduzidas e comparadas.
- Suíte, smoke, compileall, diff check e pacote devem passar.
- Após push, os três jobs reais do GitHub devem passar no PR.
- O PR fica aberto para decisão do mantenedor; este agente não faz merge.

## Complexity Tracking

Nenhuma violação da Constituição. Não há complexidade adicional a justificar.
