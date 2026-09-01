# Plano: copy acentuada na página de Perfis

## Resumo

Aplicar uma correção mínima nos quatro pontos de copy visível de `ProfilesPage`, atualizar os testes que comparam essas mensagens e acrescentar cobertura para os estados de aplicação e persistência. A branch parte de `origin/main` (`abad8b1`) para não incorporar mudanças de PRs concorrentes de Perfis.

## Arquivos previstos

- `app/mouse_hub_app.py`: somente literais exibidos por `config_hint` e `apply_hint`.
- `tests/test_issue6_profiles_polling.py`: atualizar assertions exatas das mensagens de leitura e salvamento.
- `tests/test_issue97_profile_copy.py`: regressão para todos os estados de copy, usando os serviços/fakes existentes.
- `docs/screenshots/5_perfis.png`, `docs/screenshots/small_perfis.png`, `docs/screenshots/preview.png`: capturas oficiais afetadas.
- `specs/030-profile-copy-accents/`: especificação, plano, tasks, checklist e quickstart.
- `.specify/feature.json`: apontar para a feature ativa.

## Estratégia

1. Confirmar a árvore limpa e executar a suíte baseline em `origin/main`.
2. Escrever testes de comportamento que exigem as formas acentuadas. Executar os testes para observar RED antes de tocar na produção.
3. Alterar somente os literais de feedback visível, preservando placeholders, pontuação semântica, resultados e fluxo.
4. Executar GREEN focado e regressões de Perfis.
5. Capturar as telas oficiais duas vezes e comparar bytes, dimensões e regiões esperadas.
6. Executar suíte completa, smoke Xvfb, `compileall`, `git diff --check` e pacote `.deb`.
7. Fazer revisão independente read-only, registrar a matriz de requisitos, commitar, publicar PR e confirmar os três jobs reais.

## Fluxo de dados preservado

`ProfileStore` e os serviços do estado continuam determinando os resultados. A UI apenas renderiza os mesmos resultados com copy acentuada. Não há alteração em entrada, persistência, chamadas HID, sensibilidade, DPI ou lógica de habilitação do formulário.

## Matriz da Constituição

| Princípio | Aplicação nesta issue | Verificação |
|---|---|---|
| I. Correção de hardware | Nenhuma operação de hardware é alterada. | Diff de produção e regressões de aplicação. |
| II. Honestidade de estado | Erros, estados parciais e sucesso mantêm seus significados. | Testes de `_render_apply_feedback` e persistência. |
| III. Fakes no CI | Aplicação usa os fakes já existentes, sem hardware físico. | Testes focados e CI determinístico. |
| IV. Regressão com teste | Assertions antigas e testes novos falham antes da troca. | Log RED e GREEN. |
| V. Domínio no core | Nenhuma regra de domínio é introduzida na UI. | Diff limitado a literais. |
| VI. Menor mudança completa | Quatro literais, assertions, regressão e capturas necessárias. | `git diff --stat` e revisão. |
| VII. Verificação dupla | Software será validado localmente e no CI. Não haverá claim de hardware físico. | Suíte, smoke, pacote e checks remotos. |
| VIII. UX consistente | Copy pt-BR recebe diacríticos e concordância consistentes. | Testes de strings e inspeção visual. |

## Matriz de rastreabilidade

| Requisito | Evidência planejada | Resultado |
|---|---|---|
| FR-001 / SC-001 | `test_read_error_copy_is_accented_and_form_remains_blocked`; grep do app sem forma antiga | GREEN local |
| FR-002 / SC-002 | Mesmo teste: mensagem de integridade, arquivo byte a byte intacto e botão desabilitado | GREEN local |
| FR-003 / SC-003 | `test_total_apply_failure_copy_is_accented_and_causes_remain_visible` e `test_partial_apply_keeps_explicit_state_copy` com fakes | GREEN local |
| FR-004 / SC-004 | `test_save_failure_copy_is_accented_and_does_not_claim_success` com falha determinística de escrita | GREEN local |
| FR-005 / SC-004 | `test_save_success_copy_is_accented_and_profile_is_persisted` com `ProfileStore` real | GREEN local |
| FR-006 / SC-003 | Regressões de aplicação parcial/falha preservam detalhes e ausência de sucesso falso | GREEN local |
| FR-007 / SC-007 | Diff de produção restrito a literais; gates restantes em T010–T012 | Parcial, gates pendentes |
| FR-008 / SC-005 | 25 testes focados GREEN; suíte completa em T012 | Parcial, regressão completa pendente |
| SC-006 | Dupla captura e comparação byte a byte | Pendente |
| SC-008 | PR e `gh pr checks` | Pendente |

## Riscos e contenções

- PRs #126, #134, #135 e #139 também alteram `app/mouse_hub_app.py` ou screenshots de Perfis. A branch fica baseada em `origin/main` e o diff é mantido somente no escopo #97.
- A troca de copy pode alterar pixels e reflow textual nas três capturas. A comparação deve aceitar somente as regiões de texto previstas e confirmar dimensões oficiais.
- A execução local não prova hardware físico. Nenhuma validação física será alegada.
