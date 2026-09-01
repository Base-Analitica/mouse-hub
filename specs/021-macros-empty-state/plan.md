# Implementation Plan: Empty state de Macros próximo ao heading

**Branch**: `fix/macros-empty-state-position` | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/021-macros-empty-state/spec.md`

## Summary

O estado vazio da página de Macros deve aparecer no início da região de lista,
logo após `Macros Salvas`, em vez de ficar visualmente isolado no espaço livre.
A menor mudança completa é ajustar o alinhamento vertical e o espaçamento do
`QLabel` criado somente quando `MacroEngine.list_all()` retorna vazio. O card de
gravação, o CTA `Gravar Macro`, o fluxo de macros preenchidas e o domínio de
persistência permanecem inalterados. Testes Qt offscreen com fake de `list_all()`
provarão posição, transições e os dois viewports; as screenshots públicas serão
regeneradas pelo capturador existente.

## Technical Context

**Language/Version**: Python >= 3.10

**Primary Dependencies**: PyQt5 5.15.11 no CI; pytest; ferramentas já existentes
de captura de screenshots

**Storage**: N/A para a correção; a lista continua sendo fornecida pelo
`MacroEngine` e pelo store existente

**Testing**: `pytest` com `QT_QPA_PLATFORM=offscreen`; smoke UI em Xvfb;
`compileall`; `git diff --check`

**Target Platform**: Aplicativo desktop nativo para Linux Mint, com layouts
desktop e small

**Project Type**: Aplicativo desktop PyQt5

**Performance Goals**: Nenhum custo novo de runtime; a atualização continua
sendo uma operação de renderização da lista já existente

**Constraints**: Sem dependência nova, sem hardware/X11 real nos testes, sem
alterar regras de domínio, sem duplicar CTA, mantendo a copy pt-BR e os tamanhos
oficiais 1050×680 e 760×560

**Scale/Scope**: Uma ramificação de layout em `MacrosPage`, um arquivo de testes
dedicado, três screenshots afetadas e os artefatos Spec Kit desta feature

## Constitution Check

*GATE: deve passar antes da implementação e ser reavaliado após os testes e a
regeneração dos artefatos.*

| Princípio | Avaliação inicial | Evidência planejada |
|---|---|---|
| I. Correção de Hardware em Primeiro Lugar | PASS. A mudança não toca hardware. | Testes usam fake e não alteram HID/X11. |
| II. Honestidade de Estado | PASS. O empty state continua derivado de `list_all()`. | Testes cobrem lista vazia, preenchida e transições sem estado inventado. |
| III. Fakes no CI, Hardware Fora | PASS. A página será construída com fake determinístico. | `tests/test_issue105_macro_empty_state.py` sem mouse físico. |
| IV. Regressão Com Teste Junto do Fix | PASS condicionado ao ciclo RED-GREEN. | Teste novo deve falhar com o alinhamento atual antes do código de produção. |
| V. Regras de Domínio Somente no Core | PASS. Nenhuma regra de macro ou persistência será movida para a UI. | Diff limitado ao layout e aos testes. |
| VI. Menor Mudança Completa | PASS. Ajuste restrito ao ramo vazio, testes, specs e screenshots. | `git diff --check` e revisão de escopo. |
| VII. Verificação Dupla | PASS. O requisito é visual e será validado por Qt offscreen e screenshots. | Evidência de software será rotulada como determinística; não há claim física. |
| VIII. UX Honesta e Consistente | PASS. Copy pt-BR e CTA existente são preservados. | Testes impedem botão duplicado e regressão do conteúdo preenchido. |

**Gate inicial**: PASS. Não há violação que exija exceção.

## Research Notes

### Decision 1: Corrigir somente a apresentação do estado vazio

- **Decision**: O empty state usará alinhamento no topo da região de lista e
  espaçamento vertical menor, sem novo card, botão ou abstração.
- **Rationale**: A issue descreve uma quebra de hierarquia espacial, e o código
  já possui uma ramificação explícita para a lista vazia. A mudança menor resolve
  a causa sem alterar gravação, reprodução ou persistência.
- **Alternatives considered**: Criar um card de empty state, remover a área de
  rolagem ou adicionar outro CTA. Todas introduzem elementos ou mudanças de fluxo
  que a issue não pede.

### Decision 2: Verificar posição relativa ao viewport da lista

- **Decision**: Os testes devem medir a mensagem em relação ao widget da região
  de lista, não por coordenadas absolutas da janela.
- **Rationale**: Isso prova o contrato visual nos dois tamanhos e evita acoplar o
  teste a margens externas ou a métricas de fonte do ambiente CI.
- **Alternatives considered**: Comparar apenas screenshot pixel a pixel ou usar
  coordenadas absolutas. A primeira não explica a regressão; a segunda é frágil
  entre fontes e plataformas.

### Decision 3: Usar o harness fake já existente

- **Decision**: Construir `MacrosPage` com um fake mínimo cujo `list_all()` pode
  alternar entre `{}` e uma macro determinística.
- **Rationale**: Mantém o teste sem hardware, exercita o código real da página e
  permite provar a transição sem modificar o core.
- **Alternatives considered**: Instanciar a aplicação completa ou mockar widgets.
  A aplicação completa adiciona ruído e mocks de widgets não provariam o layout
  real.

## Project Structure

### Documentation (this feature)

```text
specs/021-macros-empty-state/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
app/
└── mouse_hub_app.py                 # MacrosPage e empty state

tests/
└── test_issue105_macro_empty_state.py  # testes Qt offscreen com fake

docs/screenshots/
├── 4_macros.png
├── small_macros.png
└── preview.png
```

**Structure Decision**: Aplicativo desktop único já existente. A lógica de
apresentação permanece em `app/mouse_hub_app.py`; o teste dedicado fica em
`tests/`; não há contrato externo nem mudança de modelo de dados.

## Phase 0: Research

1. Confirmar o contrato da issue #105, a ramificação vazia de `MacrosPage` e o
   harness de QApplication/fakes já usado pelo projeto.
2. Confirmar que o capturador usa estado vazio determinístico e que as screenshots
   afetadas são `4_macros.png`, `small_macros.png` e `preview.png`.
3. Registrar decisões de alinhamento, teste relativo ao viewport e ausência de
   mudança de domínio em `research.md`.

## Phase 1: Design

1. Mapear o estado vazio e preenchido em `data-model.md`.
2. Registrar o guia executável de validação em `quickstart.md`.
3. Não criar `contracts/`: a mudança não expõe API, CLI ou protocolo externo.
4. Gerar tarefas ordenadas por história de usuário em `tasks.md`.

## Phase 2: Implementation

1. Escrever os testes novos primeiro e executar o ciclo RED contra `origin/main`.
2. Aplicar apenas o ajuste de alinhamento e padding no ramo vazio.
3. Executar GREEN focado, depois a suíte completa e smoke UI.
4. Regenerar screenshots e atualizar os registros de validação dos artefatos.

## Constitution Re-check

Após a implementação, o gate será reavaliado com o diff, o ciclo RED-GREEN, os
testes focados, a suíte completa, o smoke Xvfb, `compileall`, `git diff --check`
e a inspeção visual das screenshots. Qualquer evidência de alteração do fluxo
preenchido ou do CTA bloqueará a entrega.

## Complexity Tracking

Nenhuma violação constitucional ou complexidade adicional foi identificada.

## Final Constitution Re-check

**Resultado: PASS.** O diff final permanece restrito ao ramo visual vazio de
`MacrosPage`, ao teste determinístico dedicado, às screenshots regeneradas e aos
artefatos Spec Kit. Não houve toque em hardware, regra de domínio, persistência,
CTA ou fluxo preenchido. O ciclo RED-GREEN, os `551 passed`, o smoke Xvfb,
`compileall`, `git diff --check` e a inspeção visual das screenshots fornecem a
evidência de software planejada; nenhuma validação física é alegada.

## Validation Record

- **RED**: antes da alteração de produção, `pytest tests/test_issue105_macro_empty_state.py -q` falhou nos dois casos parametrizados de alinhamento, porque o estado usava `Qt.AlignCenter` e padding de 30 px.
- **GREEN**: após o ajuste mínimo, os testes dedicados passaram: `7 passed` nos viewports 1050×680 e 760×560.
- **Regressões de Macros/capacidades**: `tests/test_issue4_macro_recording.py tests/test_issue7_ui_caps.py`: `21 passed`.
- **Screenshots**: `QT_QPA_PLATFORM=offscreen python3 scripts/capture_screenshots.py` regenerou as 7 telas, variantes small e `preview.png`; `4_macros.png`, `small_macros.png` e `preview.png` foram visualmente inspecionadas.
- **Smoke**: `QT_QPA_PLATFORM=offscreen xvfb-run -a python3 -m unittest tests.smoke_ui_init`: `1 test`, `OK`.
- **Sintaxe/diff**: `python3 -m compileall -q app mouse_hub tests scripts` e `git diff --check` passaram.
- **Suíte completa**: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q -rA` terminou com exit code 0 e `551 passed`, sem falhas.
- **Revisão independente**: a lacuna apontada sobre ordem e widgets residuais foi verificada e coberta; o teste dedicado reforçado passou novamente com `7 passed`.

A evidência acima é de software determinístico e não constitui medição física no
Logitech G403 nem validação de uma sessão X11 real.
