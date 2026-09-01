# Microcopy de permissões HID Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Atualizar a copy de permissões HID para refletir o fluxo gráfico de autorização do Mouse Hub sem alterar capabilities ou hardware.

**Architecture:** Reutilizar o `QLabel` informativo existente em `SettingsPage` e trocar somente seu literal. A autorização, o botão e o modelo de capabilities permanecem nas camadas atuais.

**Tech Stack:** Python 3.10+, PyQt5 5.15.11, pytest, Xvfb e pipeline de screenshots determinísticas.

**Spec:** `specs/027-hid-permission-microcopy/spec.md`

## Global Constraints

- Não tocar em core, platform, persistência, hardware, polkit/pkexec, capabilities ou no botão existente.
- Manter copy pt-BR, word wrap e compatibilidade com 1050×680 e 760×560.
- Escrever o teste antes do código e observar RED contra a copy atual.
- Validar com fakes no CI, sem alegar autorização ou hardware físico real.

---

**Branch**: `027-hid-permission-microcopy` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

## Summary

Substituir somente o texto introdutório de `SettingsPage.hid_info` para refletir
que o próprio Mouse Hub pode solicitar autorização administrativa e instalar a
regra necessária. O fluxo de botão, capabilities e hardware permanece intacto.

## Technical Context

**Language/Version**: Python 3.10+

**Primary Dependencies**: PyQt5 5.15.11, pytest e dependências já presentes

**Storage**: N/A; nenhuma configuração ou regra persistida é alterada

**Testing**: pytest offscreen, smoke PyQt5 via Xvfb, compileall, `git diff --check`,
captura determinística e empacotamento `.deb`

**Target Platform**: Linux Mint; aplicação desktop nativa PyQt5

**Project Type**: aplicação desktop single-project

**Constraints**: não tocar em core, platform, persistência, hardware, polkit/pkexec,
capabilities ou no botão existente; manter copy pt-BR e word wrap nos dois viewports

## Constitution Check

| Princípio | Status | Nota |
| --- | --- | --- |
| I. Correção de Hardware em Primeiro Lugar | N/A | Nenhum caminho HID ou hardware será alterado. |
| II. Honestidade de Estado (UI Não Simula) | PASS | A copy descreve o fluxo sem afirmar permissão concedida antes da evidência. |
| III. Fakes no CI, Hardware Fora | PASS | O teste instancia a página real com fakes existentes e offscreen. |
| IV. Regressão Com Teste Junto do Fix | PASS | O teste falha contra a instrução antiga e passa após a troca mínima. |
| V. Regras de Domínio Somente no Core | PASS | Nenhuma regra de domínio será criada na UI. |
| VI. Menor Mudança Completa | PASS | Um texto, um teste dedicado, capturas e documentação rastreável. |
| VII. Verificação Dupla (Software e Realidade) | PASS | Claims ficam limitadas ao fluxo de software; não há claim de hardware real. |
| VIII. UX Honesta e Consistente | PASS | A mensagem comunica o próximo passo suportado e remove instrução obsoleta. |

## Project Structure

```text
app/mouse_hub_app.py                              # QLabel hid_info, somente copy
 tests/test_issue81_hid_permission_microcopy.py   # regressão da copy e layout
 docs/screenshots/6_settings.png                  # captura desktop afetada
 docs/screenshots/small_settings.png              # captura small afetada
 docs/screenshots/preview.png                     # mosaico regenerado
.specify/feature.json                             # ponte para esta feature
specs/027-hid-permission-microcopy/                # artefatos Spec Kit
```

## Design Decisions

1. Reutilizar o `QLabel` atual e trocar somente seu texto.
2. Nomear a finalidade do acesso como controle de DPI físico.
3. Descrever a ação suportada pelo botão como autorização administrativa do
   aplicativo e instalação automática da regra necessária.
4. Manter `_sync_permission_ui()`, `_grant_hid_access()` e o botão sem mudanças.
5. Verificar copy, termos proibidos, callback/estados, geometria e screenshots.

## Traceability Matrix

| Requisito | Implementação | Verificação |
| --- | --- | --- |
| FR-001 / SC-001 | novo texto de `hid_info` | teste procura finalidade DPI físico |
| FR-002 / SC-001 | copy explica autorização e regra | teste de termos e botão existente |
| FR-003 / SC-002 | remove instrução manual obsoleta | asserts negativos contra copy |
| FR-004 / SC-002 | frase termina em ponto final completo | teste de pontuação e conteúdo |
| FR-005 / SC-003 | fluxo existente não tocado | testes de `SettingsPage` e diff |
| FR-006 / SC-007 | somente UI/teste/docs/PNGs | diff de nomes, revisão e compileall |
| FR-007 / SC-005 | pipeline oficial | duas capturas, hashes e bbox |
| FR-008 / SC-006 | teste dedicado RED/GREEN | pytest, suíte, smoke, pacote e CI |

## Validation Gates

- Baseline completo passa antes do teste novo.
- RED deve mostrar falhas atribuíveis à copy obsoleta.
- GREEN deve passar no teste dedicado e nas regressões existentes.
- Screenshots desktop/small/preview devem ser reproduzidas e comparadas.
- Suíte, smoke, compileall, diff check e pacote devem passar.
- Após push, os três jobs reais do GitHub devem passar no PR.
- O PR fica aberto para decisão do mantenedor; este agente não faz merge.

## Complexity Tracking

Nenhuma violação da Constituição. Não há complexidade adicional a justificar.
