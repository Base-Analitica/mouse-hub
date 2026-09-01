# Feature Specification: Labels persistentes no formulário de Perfis

**Feature Branch**: `fix/persistent-profile-field-labels-v2`

**Created**: 2026-08-29

**Status**: Em implementação

**Input**: Issue #114 — `[P1][UX] Formulário de Perfis não tem labels persistentes para os campos`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Nome do perfil permanece identificado (Priority: P1)

Quando o usuário cria ou edita um perfil, o campo de nome deve continuar
identificado depois que o placeholder deixa de ser visível ou quando o campo já
está preenchido.

**Why this priority**: O placeholder atual não é uma identificação persistente
e deixa o formulário ambíguo durante a edição.

**Independent Test**: Renderizar `ProfilesPage` com Qt offscreen, preencher o
campo de nome e verificar o texto, a visibilidade e a associação do label ao
`name_input`.

**Acceptance Scenarios**:

1. **Given** o formulário de Perfis vazio, **When** ele é exibido, **Then** há
   um label visível `Nome do perfil` acima do campo de nome.
2. **Given** o campo de nome preenchido, **When** o usuário continua editando,
   **Then** o label permanece visível e não depende do placeholder.

### User Story 2 - DPI e Sensibilidade têm identificação e unidade (Priority: P1)

O usuário deve distinguir os controles de DPI e Sensibilidade por labels
persistentes, enquanto os sufixos `DPI` e `%` continuam indicando as unidades
dos valores.

**Independent Test**: Inspecionar `dpi_label`, `sens_label`, seus buddies,
nomes acessíveis e os sufixos dos respectivos spinboxes.

**Acceptance Scenarios**:

1. **Given** qualquer valor nos controles, **When** o formulário é exibido,
   **Then** `DPI` e `Sensibilidade` aparecem acima dos respectivos campos.
2. **Given** os valores 1200 e 65, **When** os campos são preenchidos,
   **Then** os labels continuam visíveis e os sufixos `DPI` e `%` permanecem.
3. **Given** uma tecnologia assistiva consulta um campo, **When** o suporte de
   nome acessível está disponível, **Then** o nome corresponde ao label humano.

### User Story 3 - Formulário continua responsivo e comprovado (Priority: P1)

A inclusão dos labels não deve reintroduzir o overlap corrigido na issue #100,
nem overflow horizontal. Em uma viewport pequena o conteúdo pode continuar
rolável verticalmente.

**Independent Test**: Renderizar o formulário nas larguras small e desktop,
medir os limites dos labels e campos e executar o capturador oficial.

**Acceptance Scenarios**:

1. **Given** a página em largura small, **When** o formulário é exibido,
   **Then** cada label e campo permanece dentro dos limites da página.
2. **Given** a página desktop, **When** o formulário é exibido,
   **Then** os labels e controles usam as duas colunas sem cortar texto.
3. **Given** a altura da viewport não comporta todo o formulário, **When** o
   usuário rola a página, **Then** os campos continuam acessíveis sem barra
   horizontal espúria.
4. **Given** as telas públicas, **When** as capturas são regeneradas,
   **Then** somente as imagens afetadas por Perfis refletem os labels novos.

## Edge Cases

- Preencher o nome, DPI e Sensibilidade não pode remover ou substituir os labels.
- Configuração de perfis corrompida continua bloqueando o formulário conforme o
  comportamento existente; labels não são fonte de verdade da configuração.
- A largura mínima suportada deve manter labels e campos com largura positiva e
  sem sair do retângulo da página.
- O sufixo do spinbox é informação complementar, não o único identificador do
  controle.
- A solução não pode depender da quantidade, ordem ou nomes dos cards de perfil.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `ProfilesPage` MUST exibir labels persistentes `Nome do perfil`,
  `DPI` e `Sensibilidade` acima dos respectivos controles.
- **FR-002**: Cada label MUST estar associado ao controle correspondente por
  `QLabel.setBuddy` e cada controle MUST expor nome acessível equivalente quando
  o toolkit oferecer esse suporte.
- **FR-003**: `dpi_input` MUST manter o sufixo `DPI` e `sens_input` MUST manter o
  sufixo `%` como unidades complementares.
- **FR-004**: Labels e controles MUST permanecer dentro dos limites da página em
  larguras small e desktop, com largura positiva e sem overflow horizontal.
- **FR-005**: A mudança MUST preservar `ProfileStore`, ações de salvar/cancelar,
  edição, aplicação de perfil e o comportamento de configuração inválida.
- **FR-006**: A regressão MUST ter teste Qt determinístico com configuração
  isolada, cobrindo texto, associação, acessibilidade, preenchimento e limites.
- **FR-007**: Screenshots desktop e small de Perfis, além de previews derivados
  afetados, MUST ser regenerados no mesmo PR; telas não relacionadas não devem
  mudar.
- **FR-008**: O PR MUST passar a suíte determinística, smoke Xvfb e empacotamento
  `.deb`, permanecendo aberto para revisão do mantenedor.

### Key Entities

- `ProfilesPage.name_label`, `dpi_label` e `sens_label`: labels persistentes do
  formulário.
- `ProfilesPage.name_input`, `dpi_input` e `sens_input`: controles associados.
- `MouseHubApp._wrap_scrollable`: container que fornece rolagem vertical para o
  conteúdo que excede a viewport.
- `ProfileStore`: fonte de verdade dos perfis, mantida fora da UI.

## Out of Scope

- Alterar limites de DPI ou Sensibilidade, o modelo `ProfileStore` ou serviços de
  hardware.
- Redesenhar cards, mudar a quantidade de colunas ou alterar a correção de
  sizing da issue #100 além do necessário para acomodar o formulário.
- Adicionar biblioteca de acessibilidade ou dependência nova.
- Declarar validação física do G403 HERO; esta mudança é de UI e será validada
  com Qt offscreen, fakes e CI.

## Review & Acceptance Checklist

- [ ] Labels persistentes aparecem para os três campos
- [ ] Cada label tem buddy e nome acessível correspondente
- [ ] Sufixos `DPI` e `%` permanecem
- [ ] Small e desktop permanecem dentro dos limites
- [ ] Teste dedicado reproduz RED antes do fix e GREEN depois
- [ ] Screenshots afetadas foram regeneradas sem mudanças alheias
- [ ] Suíte local, smoke, compileall e `git diff --check` passam
- [ ] CI real está verde
- [ ] PR aberto e não mergeado

## Dependencies

- O PR depende do #134 (issue #100), que corrige o sizing da página de Perfis
  em viewport small. Esta branch usa `fix/profiles-responsive-grid` como base
  para manter os PRs separados e evitar duplicação no alvo `main`.
