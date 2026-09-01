# Implementation Plan: Densidade adaptativa do log do Dashboard

**Branch**: `fix/dashboard-empty-log-density` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/020-dashboard-log-density/spec.md`

## Summary

O Dashboard mantém o Log de Atividade com a altura reservada para conteúdo mesmo quando só exibe o estado vazio. A mudança introduz uma transição visual explícita entre log vazio e log preenchido dentro da `DashboardPage`: o estado vazio usa uma altura compacta suficiente para a mensagem, enquanto qualquer entrada real restaura a altura de leitura já existente e mantém a rolagem interna. O texto, a ordem e o método atual de registro não serão alterados.

## Technical Context

**Language/Version**: Python 3.10+

**Primary Dependencies**: PyQt5 5.15.11, `QTextEdit`, `QTimer` e layouts Qt existentes

**Storage**: N/A. O log é uma superfície de leitura da sessão e não ganha persistência.

**Testing**: pytest, QApplication offscreen, testes determinísticos de UI, smoke de UI com Xvfb, `compileall` e `git diff --check`

**Target Platform**: Aplicativo desktop Linux Mint, viewports oficiais de 1050×680 e 760×560

**Project Type**: Aplicativo desktop Python/PyQt5

**Performance Goals**: A transição de altura ocorre somente quando o conteúdo do log muda. O tick periódico do Dashboard não deve criar operações extras nem subprocessos.

**Constraints**: Preservar a mensagem atual, a ordem das entradas, o método `log_msg`, a rolagem interna e as demais áreas do Dashboard. Não adicionar dependências, persistência ou um segundo modelo de atividades.

**Scale/Scope**: Uma superfície da `DashboardPage`, dois estados de densidade, um teste de regressão dedicado e três capturas oficiais afetadas.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Verificação do plano |
|---|---|
| I. Correção de Hardware | A mudança não toca hardware, HID, udev ou estado físico. |
| II. Honestidade de Estado | A altura representa apenas se existem entradas reais. O placeholder não será confundido com atividade. |
| III. Fakes no CI | Os testes usam `QApplication` offscreen e doubles existentes para Dashboard, sem depender de display real ou mouse. |
| IV. Regressão Com Teste | O teste dedicado falhará antes da mudança por encontrar a altura atual no estado vazio e validará a transição para conteúdo. |
| V. Domínio no Core | Não há regra de domínio nova. A página apenas projeta o conteúdo visual já existente. |
| VI. Menor Mudança Completa | O escopo fica restrito à `DashboardPage`, teste dedicado, Spec Kit e screenshots diretamente afetadas. |
| VII. Verificação Dupla | Serão separados os resultados dos testes determinísticos, smoke e CI da ausência de validação física, que não é necessária para esta alteração de layout. |
| VIII. UX Honesta | A área vazia deixa de sugerir conteúdo ausente, sem alterar a copy ou expor detalhes técnicos. |

**Resultado do gate**: PASS. Não há violação constitucional nem operação física nova.

## Project Structure

### Documentation (this feature)

```text
specs/020-dashboard-log-density/
├── spec.md
├── plan.md
├── tasks.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
app/
└── mouse_hub_app.py                 # DashboardPage e densidade do Log de Atividade

tests/
├── test_issue106_activity_log.py    # contrato RED/GREEN dos estados vazio e preenchido
├── test_issue3_ui_integration.py    # regressões de Dashboard e estados desconhecidos
└── test_issue7_ui_caps.py            # fakes e contratos de capacidades usados pela UI

docs/screenshots/
├── 0_dashboard.png
├── small_dashboard.png
└── preview.png
```

**Structure Decision**: Manter a implementação na `DashboardPage` existente e a regressão em um teste dedicado. O componente de log continua sendo a única superfície de leitura, sem novo modelo, serviço ou camada.

## Design and Data Flow

1. `DashboardPage` cria o Log de Atividade com a mensagem de estado vazio existente.
2. Uma rotina pequena de sincronização verifica se há texto real no log, ignorando o placeholder.
3. Sem entradas, a superfície usa altura compacta de 64 px, suficiente para a mensagem no layout oficial.
4. Com uma ou mais entradas, a superfície retorna à altura de conteúdo atual de 120 px. O excesso de entradas permanece acessível pela rolagem interna existente.
5. A rotina é chamada na criação e em cada mudança de texto do log. `log_msg` continua adicionando timestamp e mensagem pela mesma API.
6. Limpar o conteúdo retorna automaticamente ao estado compacto, sem registrar atividade ou alterar outras áreas do Dashboard.

## Test Strategy

- Criar primeiro `tests/test_issue106_activity_log.py` e observar RED no estado vazio e na transição para conteúdo.
- Usar `DashboardPage` com doubles determinísticos para o serviço de foco e o estado do mouse.
- Validar altura compacta no estado vazio, mensagem intacta, altura normal após uma entrada e retorno ao compacto após limpeza.
- Validar que várias entradas permanecem no documento e que a rolagem vertical interna continua disponível.
- Executar testes de Dashboard relacionados, a suíte completa offscreen, smoke Xvfb, `compileall` e `git diff --check`.
- Regenerar `0_dashboard.png`, `small_dashboard.png` e `preview.png` com o capturador oficial e revisar o diff visual.

## Implementation Phases

### Phase 0: Context and contract

- Confirmar o comportamento atual de `DashboardPage.log`, `log_msg` e os contratos dos doubles existentes.
- Criar o teste RED sem modificar o comportamento de registro.

### Phase 1: Adaptive density

- Definir as duas alturas visuais da superfície no escopo da UI.
- Sincronizar a altura com o conteúdo real do log sem mudar texto ou ordem.
- Preservar rolagem interna para conteúdo que exceda a altura normal.

### Phase 2: Regression and visual evidence

- Executar o teste dedicado e as regressões de Dashboard.
- Regenerar as capturas desktop, small e preview.
- Executar suíte completa, smoke, compilação e revisão de diff.

### Phase 3: Delivery

- Atualizar checklist, tasks e evidências Spec Kit.
- Fazer commit convencional em inglês, publicar a branch e abrir PR vinculado ao issue #106.
- Aguardar e verificar os três checks reais do CI. Não fazer merge.

## Risks and Mitigations

- **Risco**: uma mensagem longa ser cortada no estado vazio. **Mitigação**: escolher altura suficiente para o texto nos dois viewports e testar a mensagem completa.
- **Risco**: entradas reais perderem acessibilidade. **Mitigação**: manter a altura normal e a rolagem interna existentes, com teste para várias entradas.
- **Risco**: o placeholder ser contado como conteúdo. **Mitigação**: testar o documento vazio e consultar apenas texto real, não o placeholder.
- **Risco**: a página continuar exigindo scroll em 760×560. **Mitigação**: capturar o viewport small e verificar a geometria após a compactação.

## Complexity Tracking

Nenhuma violação constitucional ou complexidade adicional prevista.

## Validation Record

- RED inicial: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue106_activity_log.py -q` falhou nos cinco cenários esperados antes da mudança.
- GREEN focado: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue106_activity_log.py tests/test_issue3_ui_integration.py tests/test_issue7_ui_caps.py -q` passou.
- Suíte completa pós-implementação: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q` terminou com exit 0.
- Smoke: `QT_QPA_PLATFORM=offscreen xvfb-run -a python3 -m unittest tests.smoke_ui_init` passou com 1 teste.
- Integridade: `python3 -m compileall -q app mouse_hub tests` e `git diff --check` passaram.
- Evidência visual: `scripts/capture_screenshots.py` regenerou `0_dashboard.png`, `small_dashboard.png` e `preview.png`; dimensões 1050×680, 760×560 e 2130×2770.
- Estado de hardware: não aplicável a esta correção de layout. A validação usa doubles e não alega validação física.
