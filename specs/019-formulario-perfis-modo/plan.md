# Implementation Plan: Estado explícito do formulário de perfis

**Branch**: `fix/profile-form-mode-labels` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/019-formulario-perfis-modo/spec.md`

## Summary

O formulário de Perfis atualmente apresenta `Criar / Editar Perfil` e `Cancelar` mesmo quando nenhum perfil foi selecionado. A mudança mantém o `ProfileStore` e o fluxo de persistência existentes, mas torna o modo do formulário um estado explícito da UI: criação sem cancelamento; edição identificada pelo nome do perfil e com cancelamento. O estado de edição será limpo somente ao cancelar ou após salvamento confirmado.

## Technical Context

**Language/Version**: Python 3.10+

**Primary Dependencies**: PyQt5 5.15.11, `ProfileStore` existente

**Storage**: Arquivo de configuração XDG por meio de `mouse_hub.core.profiles.ProfileStore`; nenhuma alteração de formato

**Testing**: pytest, QApplication offscreen, smoke de UI com Xvfb, `compileall` e `git diff --check`

**Target Platform**: Aplicativo desktop nativo em Linux Mint, viewports de 1050×680 e 760×560

**Project Type**: Aplicativo desktop Python/PyQt5

**Performance Goals**: Nenhum custo de runtime além de atualizar textos e visibilidade de widgets durante transições do formulário

**Constraints**: Não alterar `mouse_hub/core`, `ProfileStore`, regras de domínio ou persistência. Usar somente estado já presente na `ProfilesPage`, preservar o layout compacto e manter copy em pt-BR.

**Scale/Scope**: Uma página, três transições de UI, um teste dedicado e as capturas oficiais de Perfis e preview.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Verificação do plano |
|---|---|
| I. Correção de Hardware | Não há nova operação de hardware nem alteração de confirmação física. |
| II. Honestidade de Estado | O título e as ações representam explicitamente criação ou edição, sem estado implícito. |
| III. Fakes no CI | A mudança é somente UI/persistência existente; o teste usa `ProfileStore` temporário e `QApplication` offscreen. |
| IV. Regressão Com Teste | O teste dedicado falha no copy/visibilidade atuais e passa com as transições implementadas. |
| V. Domínio no Core | Nenhuma regra de perfil, limite ou persistência será movida para a UI ou duplicada. |
| VI. Menor Mudança Completa | O escopo fica restrito à `ProfilesPage`, teste dedicado, artefatos Spec Kit e screenshots afetadas. |
| VII. Verificação Dupla | Serão reportadas separadamente evidências determinísticas locais/CI e ausência de validação física necessária para esta UX. |
| VIII. UX Honesta | Copy em pt-BR, `Cancelar` somente em edição e mesma semântica nos dois viewports. |

**Resultado após o design e implementação**: PASS. A mudança não adiciona operação de hardware, preserva `ProfileStore` e todos os testes determinísticos relacionados passaram.

## Validation Record

- RED inicial: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue112_profiles_form.py -q` — 5 falhas esperadas antes da implementação.
- GREEN focado: `tests/test_issue112_profiles_form.py tests/test_issue6_profiles_polling.py` — 25 testes passaram.
- Suíte completa: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q` — exit 0.
- Smoke: `QT_QPA_PLATFORM=offscreen xvfb-run -a python3 -m unittest tests.smoke_ui_init` — 1 teste passou.
- Integridade: `python3 -m compileall -q app mouse_hub tests` e `git diff --check` — passaram.
- Evidência visual: `scripts/capture_screenshots.py` regenerou `5_perfis.png`, `small_perfis.png` e `preview.png`; dimensões 1050×680, 760×560 e 2130×2770.
- Estado de hardware: não aplicável a esta mudança de UX; os testes permanecem determinísticos e sem alegação de validação física.

## Convergence Record

- Revisão independente identificou que uma edição podia duplicar o perfil se o campo de nome fosse alterado antes do salvamento.
- RED da convergência: os dois testes de identidade falharam antes da correção, confirmando o campo editável e o salvamento pelo nome alterado.
- GREEN da convergência: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue112_profiles_form.py tests/test_issue6_profiles_polling.py -q`. Resultado: 27 testes passaram.
- Suíte completa pós-convergência: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q`. Resultado: exit 0.
- Smoke pós-convergência: `QT_QPA_PLATFORM=offscreen xvfb-run -a python3 -m unittest tests.smoke_ui_init`. Resultado: 1 teste passou.
- Integridade pós-convergência: `python3 -m compileall -q app mouse_hub tests` e `git diff --check`. Resultado: passaram.
- Capturas oficiais: `scripts/capture_screenshots.py` foi executado novamente; `5_perfis.png`, `small_perfis.png` e `preview.png` permaneceram sem alterações adicionais.
- A correção torna o nome somente leitura durante a edição e ancora o salvamento na identidade original. A criação continua com o campo editável.

## Project Structure

### Documentation (this feature)

```text
specs/019-formulario-perfis-modo/
├── spec.md
├── plan.md
├── tasks.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
app/
└── mouse_hub_app.py                 # ProfilesPage e estado visual do formulário

tests/
├── test_issue6_profiles_polling.py  # regressões de persistência e aplicação
└── test_issue112_profiles_form.py   # contrato RED/GREEN dos modos do formulário

docs/screenshots/
├── 5_perfis.png
├── small_perfis.png
└── preview.png
```

**Structure Decision**: Aplicativo Python desktop existente. A regra de fonte única continua em `mouse_hub/core/profiles.py`; a página somente projeta o modo atual e chama o `ProfileStore` já existente. Não haverá novo modelo, dependência ou camada.

## Design and Data Flow

1. `ProfilesPage` inicia sem perfil selecionado no modo de criação.
2. A página exibe `Criar Perfil`, mantém o CTA de salvamento e não exibe `Cancelar`.
3. O callback de `Editar` carrega os três valores já persistidos, registra o nome original como identidade da edição, atualiza o título para `Editar <nome>` e exibe `Cancelar`.
4. `Cancelar` limpa o formulário, restaura os valores iniciais e volta ao modo de criação sem chamar o store.
5. O salvamento mantém a chamada existente ao `ProfileStore`; sucesso limpa o modo e recarrega a lista, enquanto falha preserva o contexto atual.
6. `showEvent` e erros de configuração não criam uma edição implícita.

## Test Strategy

- Escrever primeiro `tests/test_issue112_profiles_form.py` cobrindo modo inicial, entrada em edição, cancelamento sem persistência e retorno após salvamento.
- Executar o teste novo antes da alteração para registrar RED.
- Implementar o menor estado visual necessário em `ProfilesPage` e executar o teste novo para GREEN.
- Executar os testes de perfis relacionados e a suíte completa offscreen.
- Rodar smoke de UI, `compileall`, `git diff --check` e o capturador oficial de screenshots.
- Verificar textualmente que as duas capturas de Perfis usam a mesma semântica, sem alegar validação física.

## Implementation Phases

### Phase 0: Context and contract

- Confirmar a issue #112, o fluxo atual de `_start_edit`, `_clear_form`, `_save_custom` e os contratos existentes de `ProfileStore`.
- Criar testes RED sem alterar o comportamento de domínio.

### Phase 1: UI state

- Guardar o modo de edição e a identidade do perfil selecionado dentro de `ProfilesPage`.
- Tornar o heading acessível e dinâmico.
- Mostrar/ocultar `Cancelar` conforme o modo.
- Garantir que cancelamento e salvamento confirmado retornem ao modo de criação.

### Phase 2: Regression and visual evidence

- Atualizar apenas expectativas diretamente afetadas, se necessário.
- Regenerar `5_perfis.png`, `small_perfis.png` e `preview.png`.
- Executar as validações locais e revisar o diff.

### Phase 3: Delivery

- Marcar tasks e checklist de implementação como concluídos.
- Fazer commit convencional em inglês, publicar a branch e abrir PR vinculado ao issue #112.
- Aguardar e verificar os três checks reais do CI; não fazer merge.

## Risks and Mitigations

- **Risco**: o formulário perder valores quando o salvamento falhar. **Mitigação**: somente limpar o modo após `outcome.success`.
- **Risco**: `Cancelar` alterar a persistência. **Mitigação**: teste compara o perfil no store antes/depois e o callback não chama o store.
- **Risco**: o título ficar obsoleto após recarregamento. **Mitigação**: toda entrada/saída de edição passa por transição explícita e `showEvent` não inventa seleção.
- **Risco**: small viewport perder o botão ou o heading. **Mitigação**: captura oficial em 760×560 e smoke de UI.

## Complexity Tracking

Nenhuma violação constitucional ou complexidade adicional prevista.
