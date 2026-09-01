# Feature Specification: Card do Auto-Clicker sem coluna de ícone vazia

**Feature Branch**: `fix/remove-autoclicker-empty-icon`
**Feature Directory**: `033-autoclicker-empty-icon`
**Created**: 2026-08-30
**Status**: implementação concluída; validação local concluída; revisão, PR e CI remoto pendentes
**Issue**: [#77](https://github.com/Base-Analitica/mouse-hub/issues/77)

**Input**: O card de status da `AutoClickerPage` reserva uma coluna permanente para `QLabel("")` com fonte de 44 px. O widget não comunica nada nos estados parado, ativo ou bloqueado, desloca a hierarquia do card e reduz a largura útil no viewport small. A correção deve remover o placeholder sem alterar o motor ou inventar um indicador visual.

## User Scenarios & Testing

### User Story 1 - Status sem espaço morto (Priority: P1)

Ao abrir o Auto-Clicker, a pessoa deve encontrar o título e o subtítulo do status alinhados diretamente no card, sem uma coluna vazia à esquerda.

**Why this priority**: O placeholder é o defeito visual central da issue e afeta todos os estados do card.

**Independent Test**: Instanciar `AutoClickerPage` com fakes determinísticos, ajustar a página aos viewports 1050×680 e 760×560 e verificar que o frame contém somente os labels textuais do status, sem label vazio nem espaço estrutural reservado.

**Acceptance Scenarios**:

1. **Given** a página no estado parado, **When** o card é construído, **Then** `Auto-Clicker Desligado` e `Clique em iniciar para começar` ficam visíveis e não existe `QLabel` vazio dentro do card de status.
2. **Given** a página em 1050×680 ou 760×560, **When** o card é exibido, **Then** o bloco textual começa no conteúdo útil do frame, permanece contido no viewport e não há coluna morta antes dele.
3. **Given** a página com uma mensagem de estado que muda, **When** o texto é atualizado, **Then** a mesma composição continua sendo usada sem criar ou reintroduzir um placeholder.

---

### User Story 2 - Estados do motor continuam honestos (Priority: P1)

O Auto-Clicker deve continuar projetando o estado real do motor. Remover o placeholder não pode quebrar as transições de parado, ativo, aguardando foco ou erro.

**Why this priority**: A limpeza visual não pode degradar o contrato funcional nem a fonte de verdade do estado.

**Independent Test**: Exercitar `_update()` e `_toggle()` com fakes para estados `stopped`, `running`, `blocked_by_focus` e `failed`, verificando os títulos/subtítulos e que nenhuma transição acessa um widget removido.

**Acceptance Scenarios**:

1. **Given** o motor parado, **When** `_update()` é executado, **Then** o título e o subtítulo de desligado permanecem corretos.
2. **Given** o motor ativo ou aguardando foco, **When** `_update()` é executado, **Then** o título e o subtítulo correspondentes permanecem visíveis e o botão continua refletindo a ação real.
3. **Given** o motor em falha, **When** `_update()` é executado, **Then** o título de erro e a causa textual permanecem visíveis sem emoji, glyph ou acesso a um placeholder inexistente.
4. **Given** o usuário alterna iniciar/parar, **When** `_toggle()` é executado, **Then** as transições não lançam `AttributeError` e preservam o estilo e o texto dos controles existentes.

---

### User Story 3 - Artefatos visuais coerentes (Priority: P2)

As screenshots públicas mostram o card sem a coluna vazia, nos dois viewports oficiais, e as demais páginas permanecem inalteradas.

**Why this priority**: O defeito é visual e os PNGs versionados fazem parte da documentação pública do produto.

**Independent Test**: Executar o capturador oficial duas vezes em diretórios temporários, comparar as 15 PNGs por bytes e comparar o diff contra `origin/main` para limitar as alterações às imagens do Auto-Clicker e ao mosaico que as incorpora.

**Acceptance Scenarios**:

1. **Given** o código corrigido, **When** `3_clicker.png` e `small_clicker.png` são regeneradas, **Then** o card não reserva a coluna de ícone vazia e as dimensões oficiais são preservadas.
2. **Given** duas execuções consecutivas do capturador, **When** os PNGs são comparados, **Then** todos os 15 arquivos têm bytes idênticos.
3. **Given** as páginas que não são Auto-Clicker, **When** as capturas são comparadas com `origin/main`, **Then** elas não mudam por efeito colateral desta issue.

## Edge Cases

- `status_title` e `status_sub` devem continuar visíveis quando a janela tem 1050×680 e 760×560.
- Estado `failed` não pode depender do `status_icon` removido e não deve reintroduzir emoji/glyph.
- `_toggle()` deve funcionar nos ramos de iniciar e parar com o mesmo fake de motor.
- `_update()` deve continuar usando o estado do motor e o serviço de foco fornecidos, sem criar regras de domínio na UI.
- A indisponibilidade de `autoclick_available` continua sendo projetada pelos controles existentes e pelo `caps_hint`; ela não pertence ao placeholder removido.
- A issue não altera o motor, capacidade, CPS, seleção de botão, captura, persistência, core, platform, ícones de título, outros cards ou o contrato do pacote.

## Requirements

### Functional Requirements

- **FR-001**: O card de status da `AutoClickerPage` MUST deixar de criar e adicionar um `QLabel` vazio como coluna estrutural.
- **FR-002**: O título e o subtítulo do status MUST permanecer visíveis e alinhados diretamente no conteúdo útil do card nos viewports 1050×680 e 760×560.
- **FR-003**: A implementação MUST remover todas as referências de produção ao placeholder retirado, inclusive nos ramos de `_toggle()` e `_update()`.
- **FR-004**: Os estados `stopped`, `running`, `blocked_by_focus` e `failed` MUST continuar exibindo suas mensagens textuais corretas, sem sucesso falso e sem emoji/glyph novo.
- **FR-005**: O botão de iniciar/parar, o estilo do frame, o gating de capacidade, o slider de CPS e a seleção de botão MUST manter seus contratos atuais.
- **FR-006**: A mudança MUST permanecer restrita à projeção da `AutoClickerPage`; nenhuma regra deve ser movida ou criada em `app/` além da composição visual necessária, e nenhum arquivo de `mouse_hub/core` ou `mouse_hub/platform` deve mudar.
- **FR-007**: Deve existir teste offscreen determinístico que falhe no baseline e cubra a ausência do placeholder, a geometria dos dois viewports e as transições textuais do motor.
- **FR-008**: `3_clicker.png`, `small_clicker.png` e `preview.png` MUST ser regeneradas pelo capturador oficial se a mudança alterar a composição, preservando 1050×680, 760×560 e 2130×2770.
- **FR-009**: A entrega MUST passar a suíte determinística, smoke Xvfb, compilação/imports, diff-check, empacotamento e os três checks reais do CI no HEAD final.

### Key Entities

- **`status_frame`**: frame visual que contém a composição do estado do Auto-Clicker.
- **`status_title`**: label textual do estado principal do motor.
- **`status_sub`**: label textual auxiliar com instrução, CPS, botão ou causa de falha.
- **`AutoClickerState`**: estado real do motor projetado pela UI, sem ser substituído por indicador decorativo.
- **`caps_hint`**: hint independente de disponibilidade do Auto-Clicker, fora do escopo do placeholder.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Em 1050×680 e 760×560, o frame de status contém 2 labels textuais não vazios, nenhum `QLabel` vazio e nenhum slot visual reservado antes do texto.
- **SC-002**: Os estados `stopped`, `running`, `blocked_by_focus` e `failed` são exercitados sem exceção e mantêm título/subtítulo correspondentes.
- **SC-003**: O teste dedicado falha no baseline por causa do placeholder/referências residuais e passa após a remoção mínima.
- **SC-004**: As 15 capturas oficiais têm dimensões esperadas e duas execuções consecutivas produzem bytes idênticos.
- **SC-005**: O diff visual contra `origin/main` fica limitado a `3_clicker.png`, `small_clicker.png` e `preview.png`, em regiões do card do Auto-Clicker.
- **SC-006**: A suíte completa, smoke Xvfb, compileall/imports, diff-check e pacote terminam com exit code 0.
- **SC-007**: Os três checks reais do CI do PR no HEAD final terminam em `SUCCESS`, com o PR aberto e não merged.

## Assumptions and Scope Boundaries

- A solução escolhida é remover o slot vazio, não adicionar um novo ícone. Assim, não há nova metáfora visual nem dependência de fonte.
- A mensagem de erro textual continua sendo a evidência de estado quando o motor falha; esta issue não redesenha o estado de erro.
- O capturador oficial continua sendo a única origem dos PNGs versionados.
- PRs abertos #144, #145, #146 e #148 tocam regiões próximas do Auto-Clicker. Esta branch parte de `origin/main` e mantém o diff independente para o mantenedor resolver eventual integração.
- Testes offscreen, Xvfb e CI demonstram comportamento de software; não constituem validação física de mouse ou sessão X11 real.
