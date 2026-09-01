# Implementation Plan: Label visual do nome da macro

**Branch**: `fix/macro-label-input-distinction` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/022-macros-label-input/spec.md`

## Summary

A página de Macros cria o label `Nome da macro:` sem estilo explícito, e a composição visual faz esse texto parecer uma segunda superfície de entrada. A mudança aplica ao label um estilo de formulário explícito, transparente e baseado nos tokens existentes. O `QLineEdit`, o botão, o fluxo de gravação, as capacidades e a lista permanecem intocados.

## Technical Context

**Language/Version**: Python 3.10+

**Primary Dependencies**: PyQt5 5.15.11 e tokens existentes de `app.ui.theme`

**Storage**: N/A. A mudança não altera o nome persistido nem o formato de macros.

**Testing**: pytest com QApplication offscreen, regressões de Macros/capacidades, smoke Xvfb, capturador oficial, compileall e git diff --check

**Target Platform**: Linux Mint, aplicativo desktop nativo, viewports 1050×680 e 760×560

**Project Type**: Aplicativo desktop Python/PyQt5

**Performance Goals**: Nenhuma operação nova em runtime; somente estilo e teste em uma superfície já existente.

**Constraints**: Nenhuma dependência nova, nenhuma alteração em `mouse_hub/core/`, nenhum hardware físico, nenhum novo card ou ornamentação, preservação do `QLineEdit` e do fluxo de gravação.

**Scale/Scope**: Um label em `MacrosPage`, um teste dedicado, três screenshots e artefatos Spec Kit.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Status | Evidência planejada |
|---|---|---|
| I. Correção de Hardware | N/A | A mudança não toca HID++, udev ou dispositivo. |
| II. Honestidade de Estado | PASS | O label deixa de sugerir uma affordance inexistente. |
| III. Fakes no CI | PASS | QApplication offscreen e fake mínimo de serviço; nenhum hardware. |
| IV. Regressão Com Teste | PASS | O teste exige estilo transparente ausente antes do fix. |
| V. Domínio no Core | PASS | Microcopy/estilo são UI e não introduzem regra de domínio. |
| VI. Menor Mudança Completa | PASS | Um estilo explícito, teste dedicado, screenshots e docs. |
| VII. Verificação Dupla | PASS | Claims limitadas a software determinístico; não há alegação física. |
| VIII. UX Honesta e Consistente | PASS | Label, campo e spacing seguem a linguagem visual existente. |

**Resultado do gate**: PASS. Nenhuma violação constitucional ou complexidade adicional foi identificada.

## Project Structure

### Documentation (this feature)

```text
specs/022-macros-label-input/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
└── tasks.md
```

Não há `contracts/`: a mudança é visual e não cria interface externa.

### Source Code (repository root)

```text
app/mouse_hub_app.py                    # label e QLineEdit de MacrosPage
tests/test_issue104_macro_label.py      # contrato offscreen do label e viewports
docs/screenshots/4_macros.png           # captura desktop afetada
docs/screenshots/small_macros.png       # captura small afetada
docs/screenshots/preview.png            # mosaico público afetado
```

**Structure Decision**: Manter a alteração no bloco existente de construção do formulário em `MacrosPage`. O teste dedicado usa um fake de `list_all()` e não cria uma camada ou helper de produção.

## Design and Data Flow

1. `MacrosPage._build()` cria um `QLabel` instrucional para `Nome da macro:`.
2. O label recebe `color: COLORS['text_secondary']`, tamanho `TYPE_SCALE['body']`, peso moderado, `background: transparent` e `padding: 0`, sem borda.
3. O `QLineEdit` existente continua recebendo `minha_macro`, limite 32, estilo de input, foco e habilitação controlada por `_sync_caps()`.
4. O layout vertical existente preserva a ordem label → campo → ação.
5. Nenhum método de gravação, lista, serviço, persistência ou capacidade é alterado.
6. O capturador oficial atualiza somente os PNGs cuja superfície contém o formulário de Macros.

## Research Decisions

### Decision 1: estilo explícito no label

- **Decision**: Aplicar um stylesheet local curto ao `QLabel`, usando tokens existentes e transparência explícita.
- **Rationale**: A ausência de estilo explícito permite a composição que parece input. Transparência, ausência de padding e cor de texto distinguem o label sem criar uma nova superfície.
- **Alternatives considered**: Apenas remover o `:` ou trocar o texto por um placeholder. Rejeitadas porque não resolvem a affordance visual nem preservam a clareza do formulário.

### Decision 2: teste dedicado

- **Decision**: Criar `tests/test_issue104_macro_label.py` com fake mínimo, teste de stylesheet e casos parametrizados nos dois viewports.
- **Rationale**: O contrato é específico da MacrosPage e precisa provar RED antes da linha de produção, sem depender dos testes de gravação assíncrona.
- **Alternatives considered**: Teste somente estático em fonte. Rejeitado por não observar a renderização do widget real.

### Decision 3: screenshots oficiais

- **Decision**: Rodar `scripts/capture_screenshots.py` após o GREEN e revisar `4_macros.png`, `small_macros.png` e `preview.png`.
- **Rationale**: É o pipeline público já adotado pelo projeto e cobre os três arquivos listados no issue.

## Test Strategy

- Criar o teste dedicado antes da alteração de produção e observar falha porque o label atual não declara `background: transparent`.
- Confirmar GREEN nos dois viewports com QApplication offscreen.
- Reexecutar `tests/test_issue4_macro_recording.py` e `tests/test_issue7_ui_caps.py` para garantir que o fluxo e o gate de capacidade não mudaram.
- Regenerar e revisar as três screenshots afetadas.
- Executar suíte completa offscreen, smoke Xvfb, compileall e diff check.
- Consultar os três checks reais do GitHub antes de abrir o PR como concluído.

## Implementation Phases

### Phase 0: Context and contract

- Confirmar o issue, o bloco de construção do formulário e os tokens visuais.
- Criar o teste RED com fake de lista vazia e dois viewports.

### Phase 1: Label style

- Aplicar somente o stylesheet do label de nome.
- Executar o foco GREEN e confirmar a preservação do QLineEdit.

### Phase 2: Visual evidence and regression

- Regenerar screenshots oficiais e revisar os PNGs.
- Rodar regressões específicas, suíte, smoke e verificações de integridade.

### Phase 3: Delivery

- Atualizar checklist e registros Spec Kit.
- Commitar em inglês, publicar branch, abrir PR com `Closes #104` e não fazer merge.
- Aguardar e registrar os checks reais do GitHub.

## Risks and Mitigations

- **Risco**: o label continuar parecendo input por herança visual. **Mitigação**: stylesheet explícito com transparência, padding zero e sem borda, além de teste runtime do estilo.
- **Risco**: espaçamento mudar nos viewports. **Mitigação**: asserts de ordem geométrica em 1050×680 e 760×560 e revisão das screenshots.
- **Risco**: o campo ser alterado indiretamente. **Mitigação**: assert do único `QLineEdit`, valor inicial e regressões existentes de gravação/capacidades.
- **Risco**: claim física indevida. **Mitigação**: declarar que a validação é software determinístico, sem hardware ou sessão X11 real.

## Complexity Tracking

Nenhuma violação constitucional ou complexidade adicional prevista.

## Validation Record

RED observado antes do código: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue104_macro_label.py -q` produziu 2 falhas esperadas nos dois viewports, porque o label atual tinha `styleSheet()` vazio e não declarava `background: transparent`.

GREEN focado: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue104_macro_label.py -q` passou com 4 testes, cobrindo estilo, campo único, valor inicial, limite e ordem geométrica nos dois viewports.

Regressões focadas: `tests/test_issue104_macro_label.py tests/test_issue4_macro_recording.py tests/test_issue7_ui_caps.py` passaram juntas com 25 testes.

Baseline antes do TDD: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue4_macro_recording.py tests/test_issue7_ui_caps.py -q` passou com 21 testes.

Screenshots: `QT_QPA_PLATFORM=offscreen python3 scripts/capture_screenshots.py` concluiu as 7 telas, variantes small e `preview.png`. A inspeção de `4_macros.png` (1050×680), `small_macros.png` (760×560) e `preview.png` confirmou que `Nome da macro:` aparece como texto secundário sobre fundo transparente, sem faixa/borda de input, e que `minha_macro` permanece no único `QLineEdit`; não foi observada alteração não relacionada. Os hashes mudaram apenas nos três PNGs esperados.

Suíte e integridade: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q -rA` passou com 548 testes, incluindo o benchmark de playback; `QT_QPA_PLATFORM=offscreen xvfb-run -a python3 -m unittest tests.smoke_ui_init` passou com 1 teste; `python3 -m compileall -q app mouse_hub tests scripts` e `git diff --check` passaram.

Recheck constitucional pós-implementação: os oito princípios continuam atendidos. Não houve alteração em hardware, domínio, persistência ou serviço; o teste offscreen usa fake; o teste RED foi observado antes do fix; a mudança permanece mínima e a verificação local combina comportamento, visual, integração e empacotamento a ser confirmado no CI real.

## Delivery Record

Validação local concluída no worktree isolado. A revisão independente do range `abad8b138..303e662` não encontrou achados Critical, Important ou Minor e confirmou que a mudança fica restrita ao label, teste, screenshots e Spec Kit.

O branch `fix/macro-label-input-distinction` foi publicado e o PR #142 foi aberto com `Closes #104`: https://github.com/Base-Analitica/mouse-hub/pull/142. O PR permanece aberto, sem merge.

CI real do commit publicado: workflow `33268985103` passou nos três jobs. Lint/testes determinísticos: job `99143947480`; pacote `.deb`: job `99143947455`; smoke da UI (Xvfb): job `99143947413`. O workflow validou a implementação funcional, os testes determinísticos, o empacotamento e a inicialização visual sem hardware físico.
