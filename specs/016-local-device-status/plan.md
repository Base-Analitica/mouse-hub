# Implementation Plan: Status local inequívoco do dispositivo

**Branch**: `fix/local-device-status`
**Spec**: `specs/016-local-device-status/spec.md`
**Issue**: #115
**Status**: Em implementação

## Technical Context

- **Aplicação**: Python + PyQt5 5.15.11.
- **Superfície**: `MouseHubApp._update_sidebar_status` em
  `app/mouse_hub_app.py`.
- **Estado consumido**: `CapabilityState` composto por evidências do core e
  overrides da instância de automação.
- **Comportamento atual**: `Online` quando `mouse_detected` e `hid_available`,
  `Detectado` quando apenas `mouse_detected`, e `Offline` nos demais casos.
- **Problema**: os textos atuais parecem estado de serviço web ou são vagos para
  um dispositivo local.
- **Teste**: Qt offscreen com `FakeState`, `CapabilityModel` e fakes do hotplug.
  Nenhum hardware é necessário.
- **Dependências novas**: nenhuma.

## Problem and Goals

A sidebar deve responder sem ambiguidade o que ocorreu com o dispositivo local,
sem fingir que DPI, HID e conexão são uma única capacidade.

Goals:

1. Usar `G403 conectado` para mouse detectado com endpoint HID acessível.
2. Usar `Mouse detectado` quando o mouse foi localizado, mas HID não está
   acessível.
3. Usar `Mouse não detectado` quando não há evidência do mouse.
4. Manter cores, dimensões compactas e atualização por troca de página/hotplug.
5. Provar que DPI indisponível não muda o texto de conexão.

## Design

### 1. Copy curta com matriz explícita

Definir os textos de apresentação na UI e substituir somente o texto escolhido em
`_update_sidebar_status`. A matriz mantém a precedência existente: ausência de
`mouse_detected` é `Mouse não detectado`; mouse detectado sem `hid_available` é
`Mouse detectado`; ambas as capacidades são `G403 conectado`.

A cor verde continua indicando a combinação detectado + HID acessível, warning
indica detectado sem HID e muted indica ausência do mouse. Nenhuma decisão usa
`hardware_dpi_available`, `sensitivity_available` ou a sessão gráfica.

### 2. Teste first

Adicionar teste dedicado com as três combinações e um quarto caso em que DPI
está indisponível apesar de mouse/HID confirmados. Atualizar as expectativas de
#7 e #67 para os textos novos, preservando a verificação de hotplug e troca de
página. Executar RED antes de editar a produção e GREEN depois.

### 3. Prova visual

Executar `scripts/capture_screenshots.py` com o G403 fake. Como a sidebar aparece
em todas as telas, conferir o conjunto exato de imagens alteradas e regenerar
somente as capturas produzidas pelo estado novo. O texto precisa caber em
1050×680 e 760×560.

## Constitution Compliance

| Princípio | Aplicação nesta mudança | Evidência planejada |
|---|---|---|
| I. Correção de Hardware em Primeiro Lugar | Nenhuma operação de hardware muda; a UI apenas projeta evidências existentes. | Regressões de capabilities e suíte completa. |
| II. Honestidade de Estado | Conexão, HID e DPI não são colapsados em `Online`. | Matriz com DPI indisponível e HID ausente. |
| III. Fakes no CI, Hardware Fora | Testes usam `CapabilityModel`, `FakeState` e monitor fake. | Teste dedicado em Qt offscreen. |
| IV. Regressão Com Teste Junto do Fix | Expectativas novas falham com a copy antiga e passam após a alteração. | Execuções RED e GREEN registradas. |
| V. Regras de Domínio Somente no Core | Não há regra nova de domínio; apenas copy na camada UI. | Diff restrito a app, testes e screenshots. |
| VI. Menor Mudança Completa | Troca mínima dos três textos, sem alterar a máquina de estados. | Revisão do diff e `git diff --check`. |
| VII. Verificação Dupla | CI e testes provam software, não conectividade física. | Suíte, smoke, pacote e workflow remoto. |
| VIII. UX Honesta e Consistente | pt-BR específico para dispositivo local e cores coerentes. | Teste de copy, dimensões e screenshots. |

## Risks and Mitigations

- **Risco**: `G403 conectado` ser interpretado como DPI disponível.
  **Mitigação**: a regra depende apenas de mouse + HID, e o teste cobre DPI
  indisponível como estado independente.
- **Risco**: texto maior deslocar a sidebar em small.
  **Mitigação**: medir as capturas desktop/small e preservar o layout fixo.
- **Risco**: esquecer atualização de hotplug.
  **Mitigação**: manter `_on_device_changed` e atualizar as expectativas do teste
  de hotplug.
- **Risco**: expor detalhes internos.
  **Mitigação**: não incluir hidraw, HID++ ou nomes de backend na copy.

## Verification Plan

### Local

1. Criar teste dedicado e executar RED antes da mudança.
2. Executar o teste em GREEN e as regressões `test_issue7_ui_caps.py` e
   `test_issue67_hotplug.py`.
3. `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q`.
4. `QT_QPA_PLATFORM=offscreen xvfb-run -a python3 -m unittest tests.smoke_ui_init`.
5. `python3 -m compileall -q mouse_hub tests app` e `git diff --check`.
6. `QT_QPA_PLATFORM=offscreen python3 scripts/capture_screenshots.py`.

### Remote

1. Criar commit convencional e abrir PR vinculado à #115.
2. Aguardar lint/testes determinísticos, pacote `.deb` e smoke Xvfb.
3. Registrar workflow real, manter PR aberto e não fazer merge.

## Rollback

Reverter o commit restaura os textos anteriores sem alterar dados, hardware ou
protocolo.
