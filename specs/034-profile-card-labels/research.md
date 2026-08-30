# Research: cards de Perfis (#85/#86)

## Observações do baseline

- `ProfileStore` fornece perfis com `profile.name` igual às chaves persistidas `minecraft`, `csgo`, `fortnite` e `default`.
- `ProfilesPage._add_card()` usa `profile.name` diretamente no `QLabel` do título.
- O mesmo método cria `ic = QLabel("")`, adiciona `addStretch()` e cria `active_badge` vazio dentro de uma linha superior.
- `profile_cards` é indexado pela chave interna e os callbacks fecham sobre o objeto `profile`. Essa identidade deve permanecer.
- `_refresh_active()` e `active_profile()` projetam estado confirmado e não devem ganhar uma regra de apresentação.
- O baseline completo da branch baseada em `origin/main` passou com 544 testes.

## Decisões

### 1. Mapa somente na UI

**Decisão:** usar uma constante de apresentação em `app/mouse_hub_app.py` e fallback para a string original.

**Motivo:** a issue pede separação entre storage key e display label. Mover os labels para `mouse_hub/core` criaria domínio falso e poderia contaminar persistência.

**Alternativas rejeitadas:**

- Renomear as chaves no `ProfileStore`: quebra compatibilidade e não é necessário.
- Adicionar um campo persistido `display_name`: amplia schema para um problema visual.
- Capitalizar genericamente todas as chaves: não resolve branding de `CS:GO` nem garante fallback de nomes customizados.

### 2. Título dentro do header

**Decisão:** o header passa a conter o título não vazio, um stretch e um badge ativo ocultável. O placeholder `ic` é removido.

**Motivo:** o título dá conteúdo à linha em todos os estados, o badge pode ocupar espaço somente quando necessário e a altura fixa do card permanece coerente.

**Alternativas rejeitadas:**

- Manter uma linha separada com badge vazio: preserva exatamente o espaço morto da issue #86.
- Remover o header e posicionar o badge por overlay: aumenta complexidade e fragilidade geométrica.
- Adicionar um novo ícone: viola o escopo e reintroduz uma metáfora sem requisito.

### 3. Badge oculto no estado inativo

**Decisão:** o badge mantém o texto `✔ Ativo`, mas fica invisível quando não há estado ativo confirmado.

**Motivo:** evita QLabel visualmente vazio e permite que o layout colapse o espaço horizontal do badge, sem alterar a fonte de verdade.

**Limite:** o título continua sendo o primeiro conteúdo do card e a visibilidade do badge é apenas projeção de `active_profile()`.

## Questões não abertas

- Não há necessidade de alterar core, platform, schema, dependências ou captura.
- O hardware físico não participa da feature.
- A validação de software não será descrita como validação física do G403 HERO.

## Evidências observadas após a implementação

- O teste dedicado passou pelo ciclo TDD: RED reproduzível com 4 testes passando e 4 falhando, seguido de GREEN com 8 testes passando.
- Regressões de Perfis/config/UI, smoke Xvfb, compileall, `git diff --check`, empacotamento Debian e a suíte completa passaram; a suíte completa terminou com 552 testes e exit 0.
- O capturador oficial produziu duas execuções independentes com 15/15 PNGs byte a byte idênticos. As três imagens esperadas mantiveram as dimensões oficiais e foram as únicas alteradas contra `origin/main`.
- Os artefatos PNG estão copiados no worktree, mas a revisão independente, o commit final, o PR e o CI remoto ainda não foram realizados. Nenhuma evidência local é tratada como substituta desses gates.
