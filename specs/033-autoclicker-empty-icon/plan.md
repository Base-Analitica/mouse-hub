# Card do Auto-Clicker sem coluna de ícone vazia: Plano de Implementação

> **Para agentes:** executar as tarefas em ordem, mantendo o ciclo RED → GREEN e atualizando `tasks.md` somente com evidências observadas.

**Goal:** Remover a coluna estrutural causada pelo `QLabel("")` vazio do card de status do Auto-Clicker sem alterar o motor, os estados ou o gating.

**Architecture:** A `AutoClickerPage` continuará responsável somente pela projeção visual. O `QVBoxLayout` de informações (`status_title` e `status_sub`) será adicionado diretamente ao `status_frame`; o placeholder e todas as escritas nele serão removidos. Nenhum ícone substituto será criado, porque o requisito aceita a remoção do slot e a mensagem textual já representa o estado de erro.

**Tech Stack:** Python 3.10+, PyQt5 5.15.11, pytest, unittest/Xvfb, Pillow, `dpkg-deb` e scripts Spec Kit existentes.

**Spec:** [spec.md](spec.md)

## Global Constraints

- A mudança deve ficar limitada à projeção da `AutoClickerPage`, seu teste dedicado, screenshots afetadas e artefatos Spec Kit.
- Não alterar `mouse_hub/core`, `mouse_hub/platform`, persistência, capacidade, CPS, seleção de botão ou dependências.
- Não adicionar emoji, glyph dependente de fonte ou novo ícone para substituir o placeholder.
- Testes de UI devem usar `QT_QPA_PLATFORM=offscreen` e fakes determinísticos, sem mouse físico ou sessão X11 real.
- Comentários, docstrings, specs e PR ficam em pt-BR; identificadores e commits ficam em inglês.
- A branch parte de `origin/main` e a entrega permanece em PR aberto, sem merge.

## Constitution Check

| Princípio | Status inicial | Evidência exigida |
| --- | --- | --- |
| I. Correção de hardware | PASS | Nenhuma operação de hardware será adicionada. |
| II. Honestidade de estado | PASS | Títulos e subtítulos continuam projetando `AutoClickerState`; nenhum indicador falso será criado. |
| III. Fakes no CI | PASS | O teste usa fakes do motor e do serviço de foco, sem hardware. |
| IV. Regressão com teste | PASS | O teste dedicado falhou em 8 casos no baseline e passou em 8 casos após a remoção mínima. |
| V. Domínio no core | PASS | Não há regra de domínio nova; `app/` apenas reorganiza widgets. |
| VI. Menor mudança completa | PASS | A alteração de produção se limita à montagem e às referências do placeholder. |
| VII. Verificação dupla | PASS local / CI PENDING | A captura oficial foi executada duas vezes com 15/15 arquivos byte a byte idênticos; o CI remoto será confirmado no PR final. |
| VIII. UX honesta | PASS | O card deixa de reservar espaço sem significado e mantém copy de estado. |

## Project Structure

```text
app/mouse_hub_app.py                                      # AutoClickerPage._build/_toggle/_update
tests/test_issue77_autoclicker_empty_icon.py             # testes offscreen da issue 77
docs/screenshots/3_clicker.png                            # screenshot desktop afetada
docs/screenshots/small_clicker.png                        # screenshot small afetada
docs/screenshots/preview.png                              # mosaico que incorpora as telas
specs/033-autoclicker-empty-icon/{spec,plan,tasks}.md     # rastreabilidade Spec Kit
specs/033-autoclicker-empty-icon/quickstart.md            # comandos reprodutíveis
specs/033-autoclicker-empty-icon/checklists/requirements.md
```

**Structure Decision:** Manter a classe monolítica existente. O fix remove o widget morto e conecta a linha `info` diretamente ao layout horizontal já existente. O teste é dedicado para não diluir o contrato da issue em testes históricos de capacidades.

## Phase 0: Research and baseline

- Confirmar origem da branch, worktree limpo, Constituição e diff mínimo esperado.
- Executar a suíte em `origin/main` antes do teste novo. O resultado será registrado em log fora do repositório.
- Confirmar que todas as referências de produção a `status_icon` pertencem ao placeholder da issue e que os PRs #144, #145, #146 e #148 apenas criam sobreposição potencial, sem serem base desta branch.

## Phase 1: Test contract and RED

O teste dedicado terá uma fixture `QApplication`, um `FakeAc` com `state.value`, `cps`, `button`, `error`, `start()` e `stop()`, e um `FakeSvc` cujo `window_service.is_focused()` devolve um objeto com `focused=False`. Os helpers exercitarão a página real e chamarão `app.processEvents()` depois de cada mudança.

Os contratos observáveis serão:

```python
labels = page.status_frame.findChildren(QLabel)
assert [label.text() for label in labels] == [
    page.status_title.text(), page.status_sub.text()
]
assert all(label.text().strip() for label in labels)
assert page.status_title.geometry().left() <= page.status_frame.contentsRect().left() + 2
```

A matriz de estados cobrirá `stopped`, `running`, `blocked_by_focus` e `failed`, verificando títulos e subtítulos reais. Também executará `_toggle()` nos dois sentidos para detectar referências residuais ao widget removido.

## Phase 2: Minimal implementation

Depois de observar o RED, aplicar somente estas mudanças em `app/mouse_hub_app.py`:

1. Remover a criação, o estilo e o `sl.addWidget(self.status_icon)`.
2. Manter `info = QVBoxLayout()` e adicionar `sl.addLayout(info)` sem um widget anterior.
3. Remover as chamadas `self.status_icon.setText(...)` de `_toggle()` e `_update()`.
4. Não modificar textos, estilos do frame, timer, capacidade ou chamadas do motor.

Nenhum helper de produção novo é necessário.

## Phase 3: GREEN and integration

- Reexecutar o teste dedicado e as regressões `test_issue5_autoclicker.py`, `test_issue7_ui_caps.py` e `test_issue66_ui_craft.py`.
- Confirmar que a página permanece contida nos dois viewports e que o gating de `caps_hint`, slider, seleção de botão e botão de início continua igual.
- Regenerar as screenshots com `scripts/capture_screenshots.py` em duas pastas temporárias. Comparar todas as 15 PNGs por bytes e limitar o diff contra `origin/main` a `3_clicker.png`, `small_clicker.png` e `preview.png`.
- Rodar smoke Xvfb, `compileall`, `git diff --check`, pacote Debian e suíte completa.

## Phase 4: Review and delivery

- Solicitar revisão read-only comparando `origin/main...HEAD`, incluindo a matriz FR/SC, conflitos com PRs abertos e ausência de alterações no core/platform.
- Corrigir qualquer achado funcional ou lacuna de requisito antes de publicar.
- Atualizar `spec.md`, `plan.md`, `tasks.md`, `quickstart.md` e o checklist somente com resultados observados.
- Commitar em inglês, publicar a branch e abrir PR com `Closes #77`.
- Confirmar no HEAD final exatamente os três checks reais `Lint de sintaxe e testes determinísticos`, `Smoke da UI (Xvfb)` e `Pacote .deb` em `SUCCESS`. Não fazer merge.

## Requirement-to-Check Matrix

| Requisito | Check concreto |
| --- | --- |
| FR-001 / SC-001 | Teste dedicado conta somente os labels textuais no `status_frame`, rejeita texto vazio e verifica ausência de `status_icon`; captura e inspeção geométrica cobrem os dois viewports. |
| FR-002 | Teste parametrizado em 1050×680 e 760×560 verifica visibilidade, posição do texto e contenção do frame. |
| FR-003 | `grep`/AST após o fix não encontra referências a `status_icon` em produção; `_toggle()` e `_update()` são exercitados. |
| FR-004 / SC-002 | Teste dedicado executa `stopped`, `running`, `blocked_by_focus` e `failed`, verificando títulos/subtítulos e ausência de exceção. |
| FR-005 | Regressões de capacidades e UI verificam gating, CPS, botão, estilo e geometria; teste de transição cobre `_toggle()`. |
| FR-006 | `git diff --name-only origin/main...HEAD` e diff específico confirmam ausência de alterações em `mouse_hub/core` e `mouse_hub/platform`. |
| FR-007 / SC-003 | Execução RED antes da edição de produção e GREEN após o fix, com log e contagens. |
| FR-008 / SC-004 / SC-005 | Captura oficial dupla, comparação byte a byte das 15 PNGs, dimensões e bboxes contra `origin/main`. |
| FR-009 / SC-006 / SC-007 | Suíte completa, smoke Xvfb, compileall, diff-check, pacote e três checks reais do PR no HEAD final. |

## Progress Tracking

- [x] Phase 0: design e estrutura Spec Kit preparados
- [x] Phase 0: baseline em `origin/main` registrado
- [x] Phase 1: teste dedicado escrito e RED observado
- [x] Phase 2: implementação mínima concluída
- [x] Phase 3: GREEN, regressões e screenshots concluídos
- [ ] Phase 4: revisão, PR e CI final concluídos

## Observed Evidence

- Baseline em `origin/main`: exit 0, 544 testes aprovados, log em `/tmp/issue77-baseline-suite.log`.
- RED antes do código: 8 falhas no teste dedicado, encontrando o label vazio e referências `status_icon`.
- GREEN após o código: 8 testes dedicados aprovados; regressões de Auto-Clicker, capacidades e UI: 62 testes aprovados.
- Captura oficial dupla: 15/15 PNGs byte a byte idênticas. Dimensões verificadas: `3_clicker.png` 1050×680, `small_clicker.png` 760×560, `preview.png` 2130×2770. As outras 12 imagens permaneceram inalteradas.
- Smoke Xvfb: 1 teste aprovado. `compileall` e `git diff --check`: exit 0. Empacotamento Debian: 7 testes aprovados. Suíte final: exit 0, 552 testes aprovados.
- Referências `status_icon` não existem em `app/`; não houve alteração em `mouse_hub/core` ou `mouse_hub/platform`. CI remoto e revisão independente continuam pendentes.
