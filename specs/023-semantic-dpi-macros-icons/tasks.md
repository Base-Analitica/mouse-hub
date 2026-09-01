---

description: "Tarefas de implementação dos ícones semânticos de DPI e Macros"
---

# Tasks: Ícones sem metáforas de mídia para DPI e Macros

**Input**: Documentos de design em `/specs/023-semantic-dpi-macros-icons/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md` e
`quickstart.md`.

## Phase 1: Spec e contrato

- [x] T001 Preencher `spec.md`, `research.md`, `data-model.md`, `plan.md` e
  `quickstart.md` com os requisitos do issue #111 e os oito gates da
  constituição.
- [x] T002 Criar `checklists/requirements.md` e mapear cada requisito a uma
  verificação observável.

## Phase 2: User Story 1 e User Story 2, glifos semânticos

**Goal**: DPI usa foco/precisão e Macros usa teclas, nos dois tamanhos oficiais.

**Independent Test**: `tests/test_issue111_semantic_icons.py` passa em modo
offscreen e verifica mapeamento, presença real no TTF e renderização.

- [ ] T003 [US1] Escrever `tests/test_issue111_semantic_icons.py` antes da
  produção, cobrindo `dpi == 0xED4C`, `macros == 0xEE75` e
  `QRawFont.supportsCharacter()` para os dois codepoints.
- [ ] T004 [US1] Rodar `QT_QPA_PLATFORM=offscreen python3 -m pytest
  tests/test_issue111_semantic_icons.py -q` e registrar RED por mapeamento e
  glyphos ausentes, sem modificar produção para mascarar a falha.
- [ ] T005 [US1] Regenerar `app/ui/fonts/remixicon-subset.ttf` a partir da fonte
  Remix local, preservando os 12 codepoints atuais e adicionando U+ED4C/U+EE75,
  sem adicionar a fonte completa ou dependência ao projeto.
- [ ] T006 [US1] Alterar somente `app/ui/icons.py:_CODEPOINTS` para mapear `dpi`
  a `0xED4C` com comentário `ri-focus-3-line` e `macros` a `0xEE75` com
  comentário `ri-keyboard-line`.
- [ ] T007 [US2] Rodar o teste focado novamente e confirmar GREEN nos tamanhos
  18 px e 24 px, incluindo pixels não transparentes e ausência de `None` com o
  asset válido.

## Phase 3: User Story 3, consistência e regressão

**Goal**: Sidebar, headings e fallback continuam coerentes sem tocar domínio ou
hardware.

**Independent Test**: Regressões de UI e smoke inicializam as páginas reais sem
hardware, e o teste de fallback retorna `None` quando a fonte é indisponível.

- [ ] T008 [US3] Completar no teste dedicado o contrato de fallback para fonte
  indisponível/nome desconhecido e a verificação textual de que sidebar e
  headings usam as chaves `dpi` e `macros` existentes.
- [ ] T009 [US3] Rodar `tests/test_issue66_ui_craft.py` e
  `tests/test_issue7_ui_caps.py`, confirmando que navegação, layout, capacidades
  e dimensões não mudaram.
- [ ] T010 [US3] Executar `QT_QPA_PLATFORM=offscreen python3
  scripts/capture_screenshots.py` e verificar que somente os cinco PNGs
  previstos mudaram: `1_dpi.png`, `small_dpi.png`, `4_macros.png`,
  `small_macros.png` e `preview.png`.

## Phase 4: Verificação e entrega

- [ ] T011 Executar `python3 -m compileall -q app mouse_hub tests scripts` e
  `git diff --check`.
- [ ] T012 Executar o smoke com `QT_QPA_PLATFORM=offscreen xvfb-run -a
  python3 -m unittest tests.smoke_ui_init`.
- [ ] T013 Executar `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q -rA`
  e registrar contagem e falhas reais, incluindo benchmark de playback.
- [ ] T014 Atualizar `spec.md`, `plan.md` e `checklists/requirements.md` com a
  evidência real, rechecagem dos oito princípios e hashes/dimensões das imagens.
- [ ] T015 Fazer revisão read-only do diff com um agente usando somente
  `openai-codex/gpt-5.6-luna` via Codex Auth ou
  `opencode-go/deepseek-v4-flash` via OpenCode Go. Corrigir todo achado antes
  da entrega.
- [ ] T016 Commitar em inglês com Conventional Commit, publicar
  `fix/semantic-dpi-macros-icons`, abrir PR vinculado com `Closes #111` e não
  fazer merge.
- [ ] T017 Consultar os três checks reais do PR, confirmar todos verdes, PR
  aberto e `mergedAt == null`, e registrar os IDs no Spec Kit.

## Dependencies & Execution Order

- T001-T002 precedem qualquer alteração de código.
- T003-T004 precedem T005-T007 por exigência de TDD.
- T005 e T006 são o menor fix funcional e T007 deve passar antes das
  regressões.
- T008-T010 dependem do GREEN focado.
- T011-T014 dependem das screenshots estabilizadas.
- T015 deve ocorrer antes de T016; T017 ocorre após os checks remotos.

## Implementation Strategy

1. Manter a branch isolada e o baseline verde documentado.
2. Completar T003-T004 e observar o RED esperado.
3. Fazer somente a regeneração do subset e a troca dos dois codepoints.
4. Validar GREEN, regressões, screenshots, suíte e integridade.
5. Revisar, publicar e aguardar CI real sem merge.
