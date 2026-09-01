# Implementation Plan: Cópia explícita para estado desconhecido

**Branch**: `fix/explicit-unknown-state-copy`
**Spec**: `specs/013-explicit-unknown-state-copy/spec.md`
**Issue**: #110
**Status**: Concluído, CI verde

## Technical Context

- **Aplicação**: Python + PyQt5, com páginas e cards em
  `app/mouse_hub_app.py`.
- **Estado consumido pela UI**: `MouseCoreState.applied_dpi` e
  `MouseCoreState.applied_sensitivity`.
- **Testes**: pytest offscreen, fakes em `tests/fakes.py`, smoke da UI com
  Xvfb e pipeline de screenshots existente.
- **Persistência de neutralidade**: `UNKNOWN_VALUE_TEXT = "—"` continua sendo
  válido para o input editável de DPI. A nova copy de estado não deve reutilizar
  esse placeholder em cards ou heroes.
- **Dependências**: nenhuma dependência nova.

## Problem and Goals

O traço isolado usado nos estados desconhecidos recebe estilos de destaque e se
parece com um indicador de carregamento ou progresso. O plano substitui esse
sinal ambíguo por `UNKNOWN_STATE_TEXT = "Aguardando leitura"`, em cor neutra,
sem alterar a origem ou a semântica do estado.

Goals:

1. Comunicar explicitamente o estado desconhecido no dashboard.
2. Aplicar a mesma linguagem aos heroes de DPI e sensibilidade.
3. Recuperar o estilo e o texto semânticos quando o valor for confirmado.
4. Preservar a distinção entre placeholder de edição e estado aplicado.
5. Entregar regressão automatizada, screenshots e checks reais do CI.

## Design

### 1. Constante de apresentação

Adicionar `UNKNOWN_STATE_TEXT` próximo às constantes já usadas para valores
neutros. O texto é de UI e permanece em pt-BR. `UNKNOWN_VALUE_TEXT` não será
removido, pois o campo editável possui uma semântica diferente.

### 2. Cards do dashboard

Estender a atualização de `StatCard` para aceitar a cor correspondente ao
valor atual. Quando o valor aplicado for `None`, o card recebe a copy explícita
e `COLORS["text_secondary"]`; quando for conhecido, conserva o número e a cor
semântica de DPI ou sensibilidade.

### 3. Heroes de DPI e sensibilidade

Centralizar a aplicação do estilo do valor em pequenos helpers locais de cada
página. Os caminhos inicial, refresh, falha e invalidação renderizam
`UNKNOWN_STATE_TEXT` com fonte menor e cor neutra. Os caminhos de prévia e de
confirmação restauram o estilo destacado e exibem o número correspondente.

A mudança não cria leitura, escrita ou regra de hardware. Ela somente representa
os valores já fornecidos pelo estado do core.

### 4. Testes e material visual

- Criar teste dedicado com `FakeHidAccess`, `FakeSystemInput` e persister neutro.
- Executar o teste primeiro sem a implementação para registrar RED.
- Verificar dashboard, heroes, cor neutra e separação do input.
- Atualizar as asserções de integração que descrevem o contrato visual antigo.
- Regenerar apenas as screenshots afetadas pela mudança.
- Executar suíte completa, compile/lint, smoke e `git diff --check`.

## Constitution Compliance

| Princípio | Aplicação nesta mudança | Evidência planejada |
|---|---|---|
| I. Correção de Hardware em Primeiro Lugar | Nenhuma confirmação nova é inferida; valor desconhecido continua desconhecido. | Testes de estado e caminhos de falha existentes. |
| II. Honestidade de Estado | Copy explícita e cor neutra distinguem unknown de valor aplicado. | `tests/test_issue110_unknown_state_copy.py`. |
| III. Fakes no CI, Hardware Fora | O cenário usa fakes e Qt offscreen; não requer G403 ou sessão gráfica real. | Suíte determinística e smoke Xvfb. |
| IV. Regressão Com Teste Junto do Fix | O teste dedicado foi executado em RED antes do código e em GREEN depois. | Histórico dos comandos e teste dedicado. |
| V. Regras de Domínio Somente no Core | A alteração só apresenta `MouseCoreState`; não adiciona regra de domínio na UI. | Diff restrito à apresentação e inspeção do core. |
| VI. Menor Mudança Completa | Constante, estilo, testes e screenshots são as menores superfícies necessárias para a issue. | `git diff --check`, revisão de escopo e spec. |
| VII. Verificação Dupla | Resultado local/CI será rotulado como evidência de software, sem alegar medição física. | Suíte, smoke, CI e nota de ausência de validação física. |
| VIII. UX Honesta e Consistente | Copy em pt-BR, sem jargão interno e sem indicador visual ambíguo. | Testes de texto, screenshots e revisão visual. |

## Risks and Mitigations

- **Risco**: O estilo neutro não ser restaurado após uma prévia.
  **Mitigação**: testar os caminhos de preview e confirmação e manter helper
  explícito para estilos.
- **Risco**: O input de DPI perder sua indicação de edição neutra.
  **Mitigação**: teste de fonte que proíbe `UNKNOWN_VALUE_TEXT` nos displays e
  mantém a asserção do input.
- **Risco**: Screenshots não refletirem o estado inicial real.
  **Mitigação**: executar o capturador oficial e conferir somente os arquivos
  derivados esperados.
- **Risco**: CI detectar incompatibilidade visual ou de empacotamento.
  **Mitigação**: executar localmente a suíte, smoke e compileall, depois aguardar
  os checks reais do PR.

## Verification Plan

### Local

1. Teste novo em isolamento e testes de integração afetados.
2. Suíte completa `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q`.
3. Smoke `xvfb-run -a python3 -m unittest tests.smoke_ui_init`.
4. `python3 -m compileall -q mouse_hub tests app`.
5. `git diff --check`.
6. `QT_QPA_PLATFORM=offscreen python3 scripts/capture_screenshots.py`.

### Remote

1. Push da branch sem tocar em `main`.
2. PR vinculado à issue #110 com spec, riscos e comandos executados.
3. Aguardar e conferir lint/testes determinísticos, pacote `.deb` e smoke de UI.
4. Se houver ajuste, repetir verificação local e checks reais.
5. Atualizar spec/checklist com o resultado final, sem fazer merge.

## Verification Results (remote)

- Workflow `33252603466`: lint e testes determinísticos, pacote `.deb` e smoke
  da UI com Xvfb passaram.
- PR: [#133](https://github.com/Base-Analitica/mouse-hub/pull/133), aberto e
  não mergeado.

## Verification Results (local)

- O teste dedicado e `tests/test_issue3_ui_integration.py` passaram em GREEN.
- `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q` terminou com exit code 0.
- `QT_QPA_PLATFORM=offscreen xvfb-run -a python3 -m unittest tests.smoke_ui_init` terminou com 1 teste OK.
- `python3 -m compileall -q mouse_hub tests app` terminou sem erro.
- `git diff --check` terminou sem erro.
- `QT_QPA_PLATFORM=offscreen python3 scripts/capture_screenshots.py` regenerou os sete artefatos esperados: dashboard, DPI e sensibilidade em desktop, small e preview.

Os resultados acima são evidência de software no ambiente local. Não houve
medição física no G403 HERO nem validação de uma sessão X11 real.


O rollback é limitado à reversão do commit do PR. Não há migração de dados,
alteração de protocolo nem mudança de configuração persistida.
