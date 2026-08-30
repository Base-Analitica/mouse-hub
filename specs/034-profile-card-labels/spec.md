# Feature Specification: Nomes de apresentação e cabeçalho dos cards de Perfis

**Feature Branch**: `fix/profile-card-labels-empty-header`
**Feature Directory**: `034-profile-card-labels`
**Created**: 2026-08-30
**Status**: Implementação e validação local concluídas; revisão independente, PR e CI remoto pendentes
**Issues**: [#85](https://github.com/Base-Analitica/mouse-hub/issues/85) e [#86](https://github.com/Base-Analitica/mouse-hub/issues/86)

**Input**: Os cards da página de Perfis exibem diretamente chaves internas de persistência (`minecraft`, `csgo`, `fortnite` e `default`) e criam uma linha superior composta por placeholders vazios. A correção deve separar identidade de armazenamento da apresentação e remover o espaço estrutural morto, sem alterar persistência, aplicação de perfis, estado ativo ou regras de domínio.

## User Scenarios & Testing

### User Story 1 - Presets com nomenclatura de produto (Priority: P1)

Ao abrir a página de Perfis, a pessoa deve ler nomes humanos e consistentes nos presets oficiais. Os identificadores usados no arquivo de configuração não devem vazar para o título do card.

**Why this priority**: A chave interna é um detalhe de implementação e torna a primeira experiência inconsistente. O título do card é a representação principal do perfil.

**Independent Test**: Instanciar `ProfilesPage` com um `ProfileStore` determinístico, inspecionar os títulos dos cards e confirmar a tabela de apresentação sem alterar o conteúdo persistido.

**Acceptance Scenarios**:

1. **Given** os quatro presets oficiais do `ProfileStore`, **When** a página é renderizada, **Then** os títulos são exatamente `Minecraft`, `CS:GO`, `Fortnite` e `Padrão` para as chaves `minecraft`, `csgo`, `fortnite` e `default`.
2. **Given** um perfil criado pelo usuário com nome `stream_2026`, **When** o card é renderizado, **Then** o título continua exatamente `stream_2026`.
3. **Given** um preset com label de apresentação diferente da chave, **When** a pessoa clica em Aplicar ou Editar, **Then** a operação continua recebendo o perfil original e resolve a chave interna correta.

---

### User Story 2 - Cards sem linha vazia (Priority: P1)

Os cards devem usar o espaço vertical para conteúdo real. Um card inativo não deve reservar uma linha composta somente por um ícone vazio e um badge vazio. Quando o perfil estiver ativo, o badge deve continuar claramente visível.

**Why this priority**: O cabeçalho residual é um artefato de uma iconografia removida e afeta todos os cards, inclusive no viewport pequeno.

**Independent Test**: Construir `ProfilesPage` offscreen com estado desconhecido e conhecido, inspecionar a composição do layout dos cards e verificar o badge nos dois viewports oficiais.

**Acceptance Scenarios**:

1. **Given** um card inativo, **When** a composição é criada, **Then** não existe placeholder de ícone nem uma linha de cabeçalho sem conteúdo visível.
2. **Given** um card ativo com estado confirmado, **When** o estado ativo é atualizado, **Then** o mesmo card exibe `✔ Ativo` e a borda/estilo de ativo continua sendo aplicado.
3. **Given** o estado passa de ativo para desconhecido ou outro perfil, **When** `_refresh_active()` é executado, **Then** o badge anterior desaparece sem deixar uma linha vazia e nenhum card é marcado como ativo incorretamente.
4. **Given** os viewports 1050×680 e 760×560, **When** a página é exibida, **Then** os cards permanecem alinhados, contidos e com alturas coerentes.

---

### User Story 3 - Material público consistente (Priority: P2)

As screenshots versionadas da página de Perfis devem mostrar os nomes de apresentação e os cards sem o cabeçalho vazio. As demais páginas não devem mudar por efeito colateral.

**Why this priority**: Os PNGs fazem parte da documentação pública e são usados para avaliar o design sem executar o aplicativo.

**Independent Test**: Executar o capturador oficial duas vezes em diretórios temporários, comparar os 15 PNGs por bytes e limitar o diff a `5_perfis.png`, `small_perfis.png` e `preview.png`.

**Acceptance Scenarios**:

1. **Given** a implementação concluída, **When** as capturas oficiais são regeneradas, **Then** os dois PNGs de Perfis mostram os labels novos e o card sem espaço estrutural morto.
2. **Given** duas execuções consecutivas do capturador, **When** os arquivos são comparados, **Then** todos os 15 PNGs são byte a byte idênticos entre si.
3. **Given** as outras cinco páginas e suas variantes, **When** o diff é comparado com `origin/main`, **Then** não há alterações fora das imagens de Perfis e do mosaico que as incorpora.

## Edge Cases

- Uma chave de perfil não conhecida pelo mapa de apresentação deve usar a própria chave como fallback, preservando perfis legados ou criados fora da UI.
- Um perfil cujo nome personalizado coincide com um label conhecido só deve ser transformado se a chave persistida for exatamente uma das quatro chaves oficiais. Nomes personalizados permanecem literais.
- Com estado ativo desconhecido, nenhum badge deve ficar visível e nenhum perfil pode ser inferido como ativo por valores default.
- Ao aplicar ou editar um preset, a apresentação pode diferir da identidade persistida, mas `profile_cards`, `active_profile()` e callbacks devem continuar usando a chave/objeto original.
- O layout small deve refluír apenas conforme as regras existentes, sem h-scrollbar, clipping ou sobreposição.
- A feature não altera DPI, sensibilidade, polling, persistência, `ProfileStore`, capacidades, hardware, `mouse_hub/core`, `mouse_hub/platform` ou dependências.
- Nenhum emoji novo, ícone de fonte ou metáfora visual deve substituir o placeholder removido.

## Requirements

### Functional Requirements

- **FR-001**: A UI MUST apresentar os presets oficiais com a tabela `minecraft → Minecraft`, `csgo → CS:GO`, `fortnite → Fortnite` e `default → Padrão`.
- **FR-002**: Perfis que não sejam exatamente uma chave oficial MUST exibir o nome informado pelo usuário sem alteração adicional.
- **FR-003**: As chaves persistidas, os valores dos perfis e a fonte `ProfileStore` MUST permanecer inalterados.
- **FR-004**: `Aplicar`, `Editar`, `profile_cards` e `active_profile()` MUST continuar resolvendo a identidade interna original, independentemente do label exibido.
- **FR-005**: A composição de cada card MUST deixar de criar o placeholder `ic = QLabel("")` e MUST não reservar uma linha composta apenas por widgets vazios quando o card está inativo.
- **FR-006**: O indicador `✔ Ativo` MUST permanecer visível somente para o perfil cujo estado confirmado corresponde exatamente, e MUST desaparecer quando o estado não for determinável ou deixar de corresponder.
- **FR-007**: Cards MUST manter alturas coerentes, alinhamento do grid e contenção nos viewports 1050×680 e 760×560, sem clipping, sobreposição ou h-scrollbar novo.
- **FR-008**: A mudança MUST permanecer restrita à projeção visual de `ProfilesPage`, seu teste dedicado, screenshots afetadas e artefatos Spec Kit. Nenhum arquivo de `mouse_hub/core` ou `mouse_hub/platform` deve mudar.
- **FR-009**: Deve existir teste offscreen determinístico que falhe no baseline e cubra labels oficiais, fallback personalizado, identidade dos callbacks, ausência da linha vazia, estados ativo/inativo e os dois viewports.
- **FR-010**: `5_perfis.png`, `small_perfis.png` e `preview.png` MUST ser regeneradas pelo capturador oficial quando a composição mudar, preservando as dimensões 1050×680, 760×560 e 2130×2770.
- **FR-011**: A entrega MUST passar testes focados, regressões de Perfis/UI, suíte completa, smoke Xvfb, compileall/imports, `git diff --check`, empacotamento Debian e os três checks reais do CI no HEAD final.

### Key Entities

- **`profile.name`**: chave/identidade persistida do perfil, usada para lookup, aplicação e indicador ativo.
- **`display_name`**: label de apresentação derivado somente na UI para as quatro chaves oficiais, com fallback literal.
- **`profile_cards`**: índice de widgets da UI, que deve continuar usando a chave interna como identidade.
- **`active_badge`**: indicador visual condicionado ao estado confirmado, sem criar estado novo.
- **`ProfileStore`**: fonte única dos perfis e valores persistidos, fora do escopo de alteração.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Os quatro presets oficiais exibem exatamente os quatro labels definidos, e um perfil personalizado é exibido sem alteração.
- **SC-002**: A inspeção dos cards confirma que nenhum placeholder de ícone existe e que um card inativo não tem cabeçalho visualmente vazio.
- **SC-003**: Aplicar e editar continuam recebendo os objetos/chaves originais, e os testes históricos de identidade e persistência continuam passando.
- **SC-004**: A matriz de estado desconhecido, ativo e troca de ativo não produz badge falso, exceção ou linha vazia residual.
- **SC-005**: Todos os cards são contidos e não se sobrepõem em 1050×680 e 760×560, com alturas coerentes entre as linhas do grid.
- **SC-006**: O teste dedicado falha no baseline por encontrar os títulos crus e a composição residual, e passa após a mudança mínima.
- **SC-007**: As 15 capturas oficiais têm dimensões esperadas e duas execuções consecutivas produzem bytes idênticos.
- **SC-008**: Contra `origin/main`, somente `5_perfis.png`, `small_perfis.png` e `preview.png` mudam, nas regiões esperadas dos cards.
- **SC-009**: Suíte completa, smoke Xvfb, compileall/imports, diff-check e empacotamento terminam com exit code 0.
- **SC-010**: O PR final permanece aberto e não merged, com os três checks reais do CI em `SUCCESS` no HEAD publicado.

## Assumptions and Scope Boundaries

- O mapa de labels é uma decisão de apresentação da UI, não uma nova regra de domínio. As strings não serão movidas para `mouse_hub/core`.
- A solução para #86 usa o próprio título do perfil como conteúdo do cabeçalho e mantém o badge ativo condicionalmente visível. Não será criado um novo ícone.
- A identidade persistida não será renomeada ao alterar a apresentação. O formulário de edição e o fluxo de salvamento existentes ficam fora desta feature, salvo para confirmar que os callbacks continuam usando a identidade original.
- A branch parte de `origin/main`, que está no baseline do projeto. PRs abertos que alteram `ProfilesPage` ou screenshots próximas não são base desta implementação.
- Testes offscreen, Xvfb e CI comprovam comportamento de software. Eles não constituem validação física do G403 HERO.

## Validation Status

- O desenho combinado foi aprovado explicitamente pelo usuário em 2026-08-30.
- O teste dedicado cobriu labels oficiais, fallback, identidade dos callbacks, composição do header, estados ativo/desconhecido/troca e os dois viewports. O ciclo TDD observado foi RED com 4 pass e 4 fail, seguido de GREEN com 8 pass.
- As regressões de Perfis/config/UI, smoke Xvfb, compileall, `git diff --check`, empacotamento Debian e a suíte completa passaram localmente. A suíte completa terminou com 552 testes e exit 0.
- O capturador oficial foi executado duas vezes em diretórios temporários. Os 15 PNGs foram byte a byte idênticos; `5_perfis.png` (1050×680), `small_perfis.png` (760×560) e `preview.png` (2130×2770) mudaram somente nas regiões esperadas contra `origin/main`.
- Os três PNGs afetados estão copiados no worktree, mas ainda aguardam commit. A revisão independente, o PR e os três checks reais do CI no HEAD final permanecem pendentes.
