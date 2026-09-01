# Tasks: CTA do Auto-Clicker comunica armar (issue #107)

- [x] T1 (TDD) `tests/test_issue107_clicker_cta.py` — vermelho antes da
  mudança: CTA "Armar…" sem jogo, "Iniciar" com jogo, estados distintos,
  semântica em small.
- [x] T2 Constantes `_CLICKER_ARM_TEXT/_START_TEXT/_STOP_TEXT`.
- [x] T3 `_cta_text_for(state, mc_active)`; `_update` usa o helper;
  `_toggle` usa constantes.
- [x] T4 Render inicial em `_build` + guarda `svc is None`.
- [x] T5 Suíte completa verde; screenshots (`3_clicker`, `small_clicker`,
  `preview`) regeneradas.
- [ ] T6 Commit + push + PR.
