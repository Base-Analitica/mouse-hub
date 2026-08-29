# Tasks: Labels persistentes no formulário de Perfis (issue #114)

- [x] T1 (TDD) `tests/test_issue114_profile_form_labels.py` — vermelho
  antes: constantes ausentes, sem labels, sem accessibleName.
- [x] T2 Constantes `_PROFILE_FORM_{NAME,DPI,SENS}_LABEL`.
- [x] T3 Labels acima de cada campo (linhas próprias no grid do form) +
  `setAccessibleName` correspondente.
- [x] T4 Suíte completa verde; screenshots (`5_perfis`,
  `small_perfis`, `preview`) regeneradas.
- [ ] T5 Commit + push + PR.
