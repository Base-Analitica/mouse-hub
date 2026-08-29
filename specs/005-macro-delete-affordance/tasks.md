# Tasks: Botão de excluir macro com affordance (issue #88)

- [x] T1 (TDD) `tests/test_issue88_delete_affordance.py` — vermelho
  antes: constantes ausentes, botão vazio, sem tooltip/acessibilidade.
- [x] T2 Constantes `_MACRO_DELETE_LABEL` / `_MACRO_DELETE_TOOLTIP`.
- [x] T3 Botão rotulado 80×32 com tooltip, accessibleName/Description,
  hover/focus vermelhos.
- [x] T4 Estado de QA no pipeline de screenshots (`qa_macros.png`,
  `small_qa_macros.png`) com engine fake de macros gravadas.
- [x] T5 Suíte completa verde.
- [ ] T6 Commit + push + PR.
