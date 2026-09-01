# Implementation Plan: CTA HID como estado contextual

**Branch**: `fix/hid-permission-status` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/017-hid-permission-state/spec.md`

**Status**: Convergido localmente; aguardando PR/CI

## Summary

Corrigir a affordance da seção de permissões HID em `SettingsPage`: o status de
acesso concedido continua como texto compacto, mas o botão de concessão deixa de
ser exibido quando não existe ação legítima. A CTA permanece visível e habilitada
somente quando `is_hid_permission_issue(reason)` confirma que polkit pode resolver
o problema. O fluxo assíncrono existente, a reavaliação de estado e as mensagens
de causa não serão reescritos.

## Technical Context

**Language/Version**: Python 3.10+

**Primary Dependencies**: PyQt5 5.15.11, pytest e fakes existentes

**Storage**: N/A

**Testing**: pytest offscreen, smoke PyQt5 via Xvfb, compileall

**Target Platform**: Linux Mint/X11; CI sem hardware físico

**Project Type**: Aplicação desktop PyQt5

**Performance Goals**: Nenhum custo novo de polling ou subprocesso

**Constraints**: Não tocar em core, HID++, udev ou polkit; manter a dependência
#129 explícita; atualizar capturas desktop e 760×560.

**Scale/Scope**: Uma classe de UI, testes de estados e capturas da página de
Configurações.

## Constitution Check

| Princípio | Status | Nota |
| --- | --- | --- |
| I. Correção de hardware | PASS | O PR só muda visibilidade; capacidade continua vindo do core. |
| II. Honestidade de estado | PASS | Status mantém a causa real; CTA só aparece para causa acionável. |
| III. Fakes no CI | PASS | Testes usam `FakeHidAccess` e `MouseCoreState`; nenhum hardware. |
| IV. Regressão com teste | PASS | Teste de visibilidade falha antes de `hide()`/`show()`. |
| V. Domínio no core | PASS | Nenhuma regra de domínio ou capacidade é criada na UI. |
| VI. Menor mudança completa | PASS | Ajuste localizado em `SettingsPage`, testes, specs e screenshots. |
| VII. Verificação dupla | PASS | Claim limitada à UI/software; não há alegação de teste físico. |
| VIII. UX honesta e consistente | PASS | Estado concluído não usa botão desabilitado como decoração. |

## Design

1. **Estado concedido**: `_sync_permission_ui()` mantém status verde e chama
   `self._permission_btn.hide()`; o texto da CTA não é usado como indicador.
2. **Causa acionável**: `_permission_btn.show()` seguido de `setEnabled(True)`;
   o texto de causa e o `fix_hid_permissions()` permanecem inalterados.
3. **Causa não acionável ou estado ausente**: status continua visível, CTA é
   ocultada e qualquer texto/tooltip residual é normalizado.
4. **Operação assíncrona**: ao iniciar, a CTA acionável permanece visível e fica
   desabilitada; no sucesso ela é ocultada, e em falha `_sync_permission_ui()` a
   torna novamente visível apenas se a causa continuar acionável.
5. **Idempotência**: cada ramo define visibilidade explicitamente para evitar que
   uma sincronização carregue o estado visual de uma chamada anterior.

## Project Structure

```text
app/mouse_hub_app.py                         # visibilidade da CTA HID
tests/test_issue116_hid_permission_ui.py     # contrato de visibilidade offscreen
tests/test_hid_permission_helper.py          # expectativas de regressão existentes
docs/screenshots/6_settings.png              # captura desktop
docs/screenshots/small_settings.png         # captura 760×560
docs/screenshots/preview.png                 # preview público
specs/017-hid-permission-state/               # especificação, plano, tarefas e checklist
```

**Structure Decision**: Manter a arquitetura desktop atual. A apresentação fica
em `app/`, os testes determinísticos em `tests/`, e nenhum novo módulo é criado.

## Dependency and Verification Plan

- Base funcional: PR #129 / issue #84, que remove os glifos de status.
- TDD: escrever asserções de visibilidade e executar RED antes da alteração de
  `SettingsPage`; implementar o menor ajuste; executar GREEN.
- Rodar teste focado, suíte completa, smoke Xvfb, compileall e `git diff --check`.
- Regenerar capturas com o script oficial e revisar somente os arquivos esperados.
- Abrir PR para a branch `fix/vector-status-icons`, sem merge. Como o workflow não
  dispara para base `fix/*`, usar temporariamente base `main` para obter checks
  reais no commit final e restaurar a base dependente depois.

## Local Convergence Evidence

- TDD RED: 3 de 4 testes novos falharam antes da alteração, porque a CTA
  continuava aparecendo nos estados granted, não acionável e sem estado.
- GREEN focado: `tests/test_issue116_hid_permission_ui.py` +
  `tests/test_hid_permission_helper.py` — 20 passed.
- Dependência #84: teste de glifos junto dos testes HID — 26 passed.
- Suíte completa offscreen: exit 0.
- Smoke Xvfb: 1 test OK.
- `compileall` e `git diff --check`: OK.
- Capturas oficiais: somente `6_settings.png`, `small_settings.png` e
  `preview.png` mudaram; as dimensões verificadas são 1050×680, 760×560 e
  2130×2770.

## Delivery Gate

- PR deve apontar para `fix/vector-status-icons` e fechar a #116.
- O workflow real precisa ficar verde no commit final; a validação física de
  um G403 não foi executada e não é alegada.
