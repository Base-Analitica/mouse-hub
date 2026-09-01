# Tasks: Estado explícito do formulário de perfis

**Input**: Design documents from `/specs/019-formulario-perfis-modo/`

**Prerequisites**: `plan.md` e `spec.md`

**Tests**: Incluídos porque o fluxo TDD foi solicitado e a constituição exige regressão junto do fix.

**Organization**: Tasks grouped by user story; stories share the existing `ProfilesPage` and are executed sequentially to avoid conflicting edits in `app/mouse_hub_app.py`.

## Phase 1: Setup (Shared Context)

**Purpose**: Fixar o contexto da feature e confirmar que a branch parte de `main` sem mudanças não relacionadas.

- [x] T001 Confirmar a issue #112, o plano e a estrutura existente de `ProfilesPage` em `specs/019-formulario-perfis-modo/plan.md`, `specs/019-formulario-perfis-modo/spec.md` e `app/mouse_hub_app.py`

---

## Phase 2: Foundational (Existing Contracts)

**Purpose**: Preservar os contratos de domínio e persistência antes da mudança de UX.

- [x] T002 Verificar que `ProfileStore` continua sendo a fonte única e que os testes existentes de perfis em `tests/test_issue6_profiles_polling.py` cobrem criação, atualização e persistência

**Checkpoint**: Contratos existentes identificados; nenhuma alteração em `mouse_hub/core/` é necessária.

---

## Phase 3: User Story 1 - Criar um perfil sem ambiguidade (Priority: P1) 🎯 MVP

**Goal**: O formulário inicial comunica criação e não oferece cancelamento de edição inexistente.

**Independent Test**: Instanciar `ProfilesPage` com um `ProfileStore` temporário e verificar título, visibilidade do botão e valores iniciais.

### Tests for User Story 1

> Escrever e executar o teste antes da implementação para registrar RED.

- [x] T003 [US1] Criar teste RED para o estado inicial do formulário em `tests/test_issue112_profiles_form.py`

### Implementation for User Story 1

- [x] T004 [US1] Tornar o título do formulário acessível e inicializá-lo como `Criar Perfil`, mantendo `Cancelar` oculto no modo de criação em `app/mouse_hub_app.py`

**Checkpoint**: A abertura da tela distingue criação sem alterar persistência.

---

## Phase 4: User Story 2 - Editar um perfil identificado (Priority: P1)

**Goal**: Escolher `Editar` identifica o perfil alvo e torna `Cancelar` disponível.

**Independent Test**: Iniciar a edição de um perfil do `ProfileStore` e verificar título, campos carregados e ação visível.

### Tests for User Story 2

- [x] T005 [US2] Adicionar teste RED para entrada no modo de edição e carregamento dos valores em `tests/test_issue112_profiles_form.py`

### Implementation for User Story 2

- [x] T006 [US2] Registrar a identidade da edição e atualizar título e visibilidade de `Cancelar` ao selecionar um perfil em `app/mouse_hub_app.py`

**Checkpoint**: O formulário identifica deterministicamente qual perfil está sendo editado.

---

## Phase 5: User Story 3 - Sair da edição sem alterar a persistência (Priority: P1)

**Goal**: Cancelar abandona alterações locais e retorna ao modo de criação; salvamento confirmado mantém o fluxo existente e também retorna ao modo inicial.

**Independent Test**: Editar um perfil, mudar os campos, cancelar, comparar o `ProfileStore` e verificar o estado inicial do formulário.

### Tests for User Story 3

- [x] T007 [US3] Adicionar testes RED para cancelamento sem escrita e retorno ao modo de criação após salvamento em `tests/test_issue112_profiles_form.py`

### Implementation for User Story 3

- [x] T008 [US3] Fazer `_clear_form` sair explicitamente da edição e garantir que `_save_custom` limpe o modo somente após sucesso em `app/mouse_hub_app.py`

**Checkpoint**: Cancelar não toca no store; falhas preservam contexto; sucesso retorna a criação.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Evidência visual, regressão e entrega do PR.

- [x] T009 [P] Atualizar somente expectativas diretamente afetadas e executar os testes focados de perfis em `tests/test_issue6_profiles_polling.py` e `tests/test_issue112_profiles_form.py`
- [x] T010 Regenerar as capturas oficiais `docs/screenshots/5_perfis.png`, `docs/screenshots/small_perfis.png` e `docs/screenshots/preview.png` usando `scripts/capture_screenshots.py`
- [x] T011 Executar a suíte completa, smoke Xvfb, `compileall`, `git diff --check` e revisar o diff da feature em `tests/`, `app/`, `docs/screenshots/` e `specs/019-formulario-perfis-modo/`
- [ ] T012 Atualizar o checklist e os artefatos Spec Kit com a evidência final, commitar a mudança convencionalmente, publicar a branch e abrir PR vinculado ao issue #112 sem fazer merge
- [ ] T013 Aguardar e verificar os três checks reais do CI no PR do issue #112, registrando o resultado em `specs/019-formulario-perfis-modo/plan.md` e `specs/019-formulario-perfis-modo/tasks.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: concluída; confirma contexto e branch.
- **Foundational (Phase 2)**: concluída; não há mudança de domínio ou persistência.
- **User Story 1 (Phase 3)**: T003 deve falhar antes de T004.
- **User Story 2 (Phase 4)**: T005 deve falhar antes de T006; depende do formulário construído em T004.
- **User Story 3 (Phase 5)**: T007 deve falhar antes de T008; depende das transições de T004 e T006.
- **Polish (Phase 6)**: depende das três histórias e do teste focado verde.

### User Story Dependencies

- **US1**: independente de outras histórias após o contexto existente.
- **US2**: depende somente da estrutura inicial do formulário da US1.
- **US3**: depende das transições de criação e edição das US1/US2.

### Parallel Opportunities

- T009 pode executar os dois arquivos de teste na mesma etapa, mas a implementação permanece sequencial porque todas as histórias compartilham `ProfilesPage`.
- T010 só começa após a UI final e pode ser executada em paralelo com uma revisão textual dos artefatos, sem editar os mesmos arquivos.

## Implementation Strategy

### MVP First

1. Completar T003 e T004.
2. Validar independentemente o estado inicial de criação.
3. Completar T005–T008 para fechar edição e cancelamento.
4. Executar T009–T013 antes de declarar o PR pronto.

### Notes

- Cada teste novo deve ser observado falhando antes da mudança correspondente.
- Nenhum task altera `mouse_hub/core/` ou o formato da configuração.
- O estado de CI reportado em T013 deve vir das checks reais do GitHub, não de uma suposição local.

---

## Phase 7: Convergence

**Reason**: A revisão independente identificou que o nome original da edição era armazenado, mas não era usado no salvamento; uma alteração do campo podia duplicar o perfil em vez de atualizar sua identidade.

- [x] T014 [US2] Adicionar testes RED para tornar o nome somente leitura durante a edição e impedir duplicação ao salvar em `tests/test_issue112_profiles_form.py`
- [x] T015 [US2] Ancorar o salvamento na identidade original e alternar o campo de nome entre editável na criação e somente leitura na edição em `app/mouse_hub_app.py`
- [x] T016 Executar novamente testes focados, suíte completa, smoke Xvfb, `compileall`, `git diff --check` e revisar o diff após a convergência em `tests/`, `app/`, `docs/screenshots/` e `specs/019-formulario-perfis-modo/`
- [x] T017 Atualizar a evidência Spec Kit, commitar e publicar a correção de convergência no PR #139 sem fazer merge em `specs/019-formulario-perfis-modo/plan.md` e `specs/019-formulario-perfis-modo/tasks.md`
- [ ] T018 Aguardar e verificar os checks reais do CI para o commit de convergência do PR #139 em `specs/019-formulario-perfis-modo/plan.md`
