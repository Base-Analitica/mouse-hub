# Tasks: DPI slider como "valor desejado" (issue #103)

## T1 — Testes primeiro (TDD)

- [ ] T1.1 `tests/test_issue103_dpi_target.py`:
  - legenda `_DPI_TARGET_LABEL` presente sob o slider com readback
    **desconhecido** (estado inicial);
  - legenda presente com readback **confirmado** (após aplicar 1200);
  - durante preview (valueChanged sem commit) o sub-rótulo do hero
    permanece "AGUARDANDO LEITURA DO HARDWARE" quando não há confirmação;
  - janela 760×560 (small) mantém a mesma legenda visível.

## T2 — Implementação

- [ ] T2.1 constante `_DPI_TARGET_LABEL` em `app/mouse_hub_app.py`.
- [ ] T2.2 `QLabel` da legenda adicionado após o slider em `DPIPage._build`.

## T3 — Verificação

- [ ] T3.1 suíte completa verde.
- [ ] T3.2 screenshots regeneradas (`1_dpi.png`, `small_dpi.png`,
  `preview.png`).
- [ ] T3.3 commit convencional + push + PR (português, fecha #103 a
  critério do mantenedor).
