# Plano: remover a barra decorativa de Sensibilidade

**Branch:** `fix/remove-sensitivity-decorative-bar`  
**Spec:** [spec.md](spec.md)  
**Criado:** 2026-08-30

## Resumo

Remover o `QFrame#speedBar` estático da função `_build` de `SensitivityPage`,
adicionar regressão offscreen para provar a ausência do indicador e preservar o
slider, o estado do sistema, o gating e o polling. Regenerar as capturas oficiais
e validar a entrega em branch e PR independentes.

## Contexto técnico

- **Linguagem:** Python 3.10+
- **UI:** PyQt5 5.15.11 no CI
- **Arquivos de produção:** `app/mouse_hub_app.py`, somente o bloco do `speedBar`
- **Teste novo:** `tests/test_issue91_sensitivity_bar.py`
- **Dependências:** nenhuma nova
- **Persistência/hardware:** sem alteração
- **Ambientes:** `QT_QPA_PLATFORM=offscreen` para testes e Xvfb para smoke
- **Capturas:** `python3 scripts/capture_screenshots.py`

## Checagem da Constituição

| Princípio | Aplicação | Verificação |
|---|---|---|
| I. Correção de hardware | Nenhuma operação HID ou sistema é modificada. | Diff de produção e testes de estado. |
| II. Honestidade de estado | Remove indicador que aparenta representar estado sem representar. | Teste de ausência e preservação do estado/slider. |
| III. Fakes no CI | A página é construída com fakes e sem mouse físico. | Teste offscreen e CI determinístico. |
| IV. Regressão com teste | O teste deve falhar antes da remoção. | Execução RED e GREEN registradas. |
| V. Domínio no core | Nenhuma regra de sensibilidade é criada na UI. | Diff limitado ao widget visual. |
| VI. Menor mudança completa | Um bloco decorativo, teste, capturas e documentação. | `git diff --stat` e revisão. |
| VII. Verificação dupla | Claims ficam limitadas ao software e ao ambiente CI. | Suíte, smoke, pacote e CI reportados separadamente. |
| VIII. UX honesta | Um único controle comunica a sensibilidade, sem metáfora enganosa. | Inspeção visual e capturas oficiais. |

## Estrutura e fluxo de dados

`SensitivityPage.slider` continua recebendo o valor inicial confirmado e os
callbacks já existentes. `_on_slider_preview` atualiza a prévia e
`_commit_slider` aplica o valor pelo controller. O `speedBar` não participa desse
fluxo e será removido. `caps_hint`, `sens_value`, `sens_state` e a seção de
polling permanecem nos mesmos contratos.

## Estratégia de execução

1. Confirmar branch isolada e árvore limpa.
2. Executar a suíte baseline antes do teste novo.
3. Criar o teste dedicado com a expectativa de ausência do `speedBar` e preservação dos elementos essenciais.
4. Executar o teste e registrar RED causado pelo widget existente.
5. Remover somente a construção e adição do `speedBar`.
6. Executar GREEN e regressões focadas, incluindo os estados de capacidade.
7. Capturar as telas oficiais duas vezes e conferir bytes, dimensões e regiões.
8. Executar suíte completa, smoke Xvfb, `compileall`, `git diff --check` e pacote Debian.
9. Fazer revisão independente read-only, resolver achados e atualizar tasks/checklist.
10. Commitar, publicar branch, abrir PR com `Closes #91` e confirmar os três jobs reais no HEAD final.

## Matriz de rastreabilidade

| Requisito | Evidência | Resultado inicial |
|---|---|---|
| FR-001 / SC-001 | Teste de ausência de `QFrame#speedBar` e inspeção do diff. | Pendente |
| FR-002 / SC-002 | Teste de orientação, faixa 0–100, sinais e gating do slider. | Pendente |
| FR-003 / SC-003 | Teste de labels, valor/estado, `caps_hint` e polling em desktop/small. | Pendente |
| FR-004 / SC-003 | Regressões de polling e construção da página. | Pendente |
| FR-005 / SC-004 | `git diff` sem alterações em core/platform. | Pendente |
| FR-006 / SC-005 | Execução RED antes da remoção e GREEN depois. | Pendente |
| FR-007 / SC-006 | Dupla captura oficial com dimensões e regiões esperadas. | Pendente |
| FR-008 / SC-007 | Suíte, smoke, compileall, diff-check, pacote e CI remoto. | Pendente |
| SC-008 | PR, `gh pr checks` e estado aberto/não merged. | Pendente |

## Riscos e contenções

- PRs de ícones e de estado da Sensibilidade podem tocar `app/mouse_hub_app.py`
  e `2_sens.png`. A branch parte de `origin/main` e o diff será auditado para
  não incorporar alterações de PRs concorrentes.
- A remoção altera a altura vertical da página. O teste deve verificar que os
  elementos seguintes continuam dentro dos dois viewports, e as capturas devem
  confirmar que só a região da barra foi removida.
- A validação não prova hardware físico. Nenhum claim físico será feito.

## Gates de entrega

- [ ] Implementação e testes GREEN
- [ ] Capturas oficiais reproduzíveis
- [ ] Suíte, smoke, compilação, diff-check e pacote locais
- [ ] Revisão independente sem achado sem tratamento
- [ ] PR aberto com `Closes #91`
- [ ] Três checks reais verdes no HEAD final
