# Nomes de apresentação e cabeçalho dos cards de Perfis: Plano de Implementação

> **Para agentes:** executar as tarefas em ordem, mantendo o ciclo RED → GREEN e atualizando `tasks.md` somente com evidências observadas.

**Goal:** Separar labels de apresentação das chaves persistidas dos presets e remover o cabeçalho visual vazio dos cards de Perfis, preservando identidade, estado ativo e layout responsivo.

**Architecture:** A mudança fica em `ProfilesPage` e trata a apresentação como uma projeção da identidade já fornecida por `ProfileStore`. Um mapa constante da UI converte somente as quatro chaves oficiais em labels humanos, com fallback literal. O card passa a usar uma única linha de cabeçalho com o título e um badge ativo condicionalmente visível, removendo o placeholder de ícone e o espaço morto sem criar um novo estado.

**Tech Stack:** Python 3.10+, PyQt5 5.15.11, pytest, unittest/Xvfb, Pillow, `dpkg-deb` e scripts Spec Kit existentes.

**Spec:** [spec.md](spec.md)

## Global Constraints

- A mudança deve ficar limitada à projeção visual de `ProfilesPage`, ao teste dedicado, às três screenshots afetadas e aos artefatos Spec Kit.
- `mouse_hub/core`, `mouse_hub/platform`, `ProfileStore`, persistência, DPI, sensibilidade, estado ativo e dependências não devem mudar.
- O mapa de apresentação é UI-only: `minecraft → Minecraft`, `csgo → CS:GO`, `fortnite → Fortnite`, `default → Padrão`; outras chaves passam sem transformação.
- O índice `profile_cards` e os callbacks continuam usando `profile.name`/objeto original, nunca o label exibido.
- O card inativo não pode mostrar linha visual vazia. O badge `✔ Ativo` permanece visível somente em estado confirmado compatível.
- Não adicionar emoji, glyph dependente de fonte ou ícone para substituir o placeholder.
- Testes usam `QT_QPA_PLATFORM=offscreen`, fakes determinísticos e não dependem de mouse físico ou sessão X11 real.
- Comentários, docstrings, specs e PR ficam em pt-BR. Identificadores e commits ficam em inglês.
- A branch é publicada como PR aberto, sem merge.

## Constitution Check

| Princípio | Status inicial | Evidência exigida |
| --- | --- | --- |
| I. Correção de hardware | PASS | Nenhuma operação de hardware será adicionada ou alterada. |
| II. Honestidade de estado | PASS | O badge continua derivado somente de `active_profile()` e estado confirmado. |
| III. Fakes no CI | PASS | O teste é offscreen e usa `ProfileStore` temporário e fakes já existentes. |
| IV. Regressão com teste | PASS | O teste dedicado será escrito e executado em RED antes da mudança de produção. |
| V. Domínio no core | PASS | Labels e composição são apresentação da UI. Nenhuma regra ou constante de domínio será movida. |
| VI. Menor mudança completa | PASS | Um helper/mapa de display, uma composição de header, teste, PNGs e docs. |
| VII. Verificação dupla | PASS | Claims serão separadas entre testes/capturas/CI de software e ausência de validação física. |
| VIII. UX honesta | PASS | A UI deixa de exibir IDs internos e deixa de reservar espaço sem significado. |

## Project Structure

```text
app/mouse_hub_app.py                                  # ProfilesPage e mapa de display
 tests/test_issue85_86_profile_cards.py               # contrato offscreen das duas issues
docs/screenshots/5_perfis.png                         # captura desktop afetada
docs/screenshots/small_perfis.png                     # captura small afetada
docs/screenshots/preview.png                          # mosaico que incorpora Perfis
specs/034-profile-card-labels/{spec,plan,tasks}.md    # rastreabilidade Spec Kit
specs/034-profile-card-labels/research.md              # decisões e alternativas
specs/034-profile-card-labels/quickstart.md            # comandos reproduzíveis
specs/034-profile-card-labels/checklists/requirements.md # revisão de requisitos
```

**Structure Decision:** Manter a classe monolítica existente. O helper de apresentação e a reorganização do header pertencem ao mesmo ponto de montagem visual. O teste é dedicado para separar os contratos novos das regressões históricas de aplicação e persistência.

## Phase 0: Research and baseline

- Confirmar a issue oficial, a Constituição, a branch baseada em `origin/main` e o worktree limpo.
- Registrar que o baseline completo passou com 544 testes aprovados, sem mudanças de produção.
- Confirmar que as chaves dos presets vivem no core e que o uso de `profile.name` na UI é o vazamento a corrigir.
- Confirmar que `ic = QLabel("")` e o `active_badge` vazio formam o header residual, enquanto o estado ativo é recalculado por `active_profile()`.

## Phase 1: Test contract and RED

Criar `tests/test_issue85_86_profile_cards.py` antes de editar `app/mouse_hub_app.py`. O teste deve usar `QApplication`, `ProfileStore` temporário, `ProfilesPage`, `QLabel`, `QHBoxLayout`/`QVBoxLayout` e os fakes existentes somente quando necessário.

Contratos observáveis:

```python
expected = {
    "minecraft": "Minecraft",
    "csgo": "CS:GO",
    "fortnite": "Fortnite",
    "default": "Padrão",
}
assert card_title(page.profile_cards[key]) == expected[key]
assert page.profile_cards["custom_name"]["profile_key"] == "custom_name"
```

O teste deve também verificar que o card usa a identidade interna para os callbacks, que não há o placeholder `ic`, que o título participa do primeiro header e que um badge inativo não deixa uma linha visual vazia. A matriz deve cobrir estado desconhecido, um perfil ativo e troca para outro estado confirmado. As medições dos dois viewports devem verificar contenção, ausência de sobreposição e alturas iguais/coerentes.

Executar o teste dedicado no baseline e registrar o RED reproduzível antes de qualquer edição de produção.

## Phase 2: Minimal implementation

Depois de observar o RED, aplicar somente estas mudanças em `app/mouse_hub_app.py`:

1. Adicionar o mapa UI-only `_PROFILE_DISPLAY_NAMES` e um helper pequeno que retorne o label conhecido ou o nome original.
2. Remover a criação e adição do `ic` vazio.
3. Construir um único header contendo o `QLabel` do título apresentado, `addStretch()` e o `active_badge` inicializado para o estado ativo e oculto quando inativo.
4. Manter `profile_cards` indexado por `profile.name` e conectar Aplicar/Editar aos objetos `profile` originais.
5. Atualizar `_refresh_active()` para alternar visibilidade/texto/estilo do badge sem criar estado derivado novo.
6. Usar o label de apresentação apenas nas mensagens explicitamente voltadas ao usuário se isso for necessário para não vazar a chave, sem alterar o armazenamento nem o formulário de edição.

Não alterar `ProfileStore`, `active_profile()`, `MouseCoreState`, limites, serviços de hardware ou o grid além do necessário para a composição do header.

## Phase 3: GREEN and integration

- Reexecutar o teste dedicado e confirmar GREEN para os labels, fallback, identidade, badge e viewports.
- Rodar regressões `tests/test_issue6_profiles_polling.py`, `tests/test_config_profiles.py`, `tests/test_issue66_ui_craft.py`, `tests/test_issue3_ui_integration.py` e o smoke de UI.
- Verificar que `profile_cards` mantém as quatro chaves oficiais, que criação/reload de perfil customizado continua funcionando e que aplicar/editar não usa o display label como lookup.
- Regenerar screenshots em dois diretórios temporários. Comparar todas as 15 PNGs por bytes e dimensões. Depois copiar somente `5_perfis.png`, `small_perfis.png` e `preview.png` para o worktree.
- Comparar bboxes contra `origin/main` e confirmar que páginas não relacionadas não mudaram.
- Rodar `compileall`, `git diff --check`, pacote Debian e suíte completa.

## Phase 4: Review and delivery

- Solicitar revisão independente read-only comparando `origin/main...HEAD`, com matriz FR/SC, Constituição, identidade de armazenamento, estados ativos e conflitos com PRs abertos de Perfis.
- Corrigir qualquer achado funcional ou lacuna de requisito e repetir os gates afetados.
- Atualizar `spec.md`, `plan.md`, `tasks.md`, `research.md`, `quickstart.md` e o checklist somente com resultados observados.
- Commitar em inglês, publicar `fix/profile-card-labels-empty-header` e abrir PR com `Closes #85` e `Closes #86`, descrição em pt-BR, testes e riscos.
- Confirmar no HEAD final exatamente os três checks reais `Lint de sintaxe e testes determinísticos`, `Smoke da UI (Xvfb)` e `Pacote .deb` em `SUCCESS`. Não fazer merge.

## Requirement-to-Check Matrix

| Requisito | Check concreto |
| --- | --- |
| FR-001 / SC-001 | Teste dedicado inspeciona os quatro títulos e a tabela exata de labels. |
| FR-002 / SC-001 | Teste cria nome customizado e confirma preservação literal, incluindo chave desconhecida. |
| FR-003 / SC-003 | Regressões de `ProfileStore`, config e `test_issue6_profiles_polling.py`; diff confirma ausência de alterações no core. |
| FR-004 / SC-003 | Teste aciona Aplicar/Editar e verifica chaves/objetos originais; testes históricos de `active_profile()` permanecem verdes. |
| FR-005 / SC-002 | Teste dedicado rejeita `ic`, QLabel vazio visível e header visualmente vazio. |
| FR-006 / SC-004 | Matriz de estado desconhecido, ativo e troca confirma visibilidade condicional do badge e ausência de falso ativo. |
| FR-007 / SC-005 | Teste parametrizado mede 1050×680 e 760×560, contenção, ausência de overlap/h-scrollbar e alturas coerentes. |
| FR-008 | `git diff --name-only origin/main...HEAD` e inspeção confirmam escopo sem `mouse_hub/core`/`platform`. |
| FR-009 / SC-006 | Execução RED antes do código e GREEN após o fix, com logs e contagens. |
| FR-010 / SC-007 / SC-008 | Captura dupla oficial, comparação byte a byte das 15 PNGs, dimensões e bboxes contra `origin/main`. |
| FR-011 / SC-009 / SC-010 | Focado, regressões, suíte, smoke, compileall, diff-check, pacote e três checks reais do PR final. |

## Progress Tracking

- [x] Phase 0: aprovação do desenho, worktree isolado e baseline registrados
- [ ] Phase 1: teste dedicado escrito e RED observado
- [ ] Phase 2: implementação mínima concluída
- [ ] Phase 3: GREEN, regressões e screenshots concluídos
- [ ] Phase 4: revisão, PR e CI final concluídos

## Observed Evidence

- O usuário aprovou explicitamente o desenho combinado de #85/#86 em 2026-08-30.
- Worktree isolado criado em `/home/pedro/.jcode/scratch/issue85-86-profile-cards`, branch `fix/profile-card-labels-empty-header`, baseado em `origin/main` no SHA `abad8b13877ab9b870f1bbe92c12d2d21738f569`.
- Baseline completo executado antes dos testes novos: exit 0, 544 testes aprovados. Log fora do repositório em `/home/pedro/.jcode/scratch/issue85-86-baseline-suite.log`.
- O teste dedicado passou pelo ciclo TDD: RED reproduzível com 4 pass e 4 fail, seguido de GREEN com 8 pass.
- A produção usa `_PROFILE_DISPLAY_NAMES` apenas na UI, remove `ic = QLabel(\"\")`, coloca o título no header e alterna o badge `✔ Ativo` conforme o estado confirmado. `ProfileStore`, `active_profile()`, `profile_cards` e callbacks continuam usando a identidade original.
- Regressões de Perfis/config/UI, smoke Xvfb, compileall, `git diff --check`, empacotamento Debian (7 testes) e a suíte completa (552 testes) terminaram com exit 0.
- O capturador oficial foi executado duas vezes em diretórios temporários; os 15 PNGs foram byte a byte idênticos. As dimensões oficiais foram preservadas, e contra `origin/main` somente `5_perfis.png`, `small_perfis.png` e `preview.png` mudaram nas regiões esperadas.
- O diff ainda não contém os três PNGs, pois eles foram apenas copiados para o worktree. A revisão independente, os commits finais, o PR e os checks remotos permanecem pendentes.
