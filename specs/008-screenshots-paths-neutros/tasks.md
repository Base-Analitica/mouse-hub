# Tasks: Screenshots públicos com caminhos neutros (issue #109)

## 1. Fixture de captura

- [x] T001 `scripts/capture_screenshots.py`: aplicar `NEUTRAL_XDG`
  (`/home/user/.config`, `/home/user/.local/share`) em `main()`, ANTES
  de `_build_app()` (imports resolvem caminhos depois do env).
- [x] T002 Sem escrita nesses caminhos: captura é leitura-apenas
  (defaults determinísticos); configuração real do usuário intocada.

## 2. Testes de regressão (CI, sem hardware)

- [x] T003 `tests/test_issue109_neutral_paths.py`:
  - `test_xdg_fixado_e_neutro_no_pipeline` — constantes do pipeline.
  - `test_configpaths_resolvem_para_neutro_com_pipeline` — `HOME`
    arbitrário + env do pipeline → caminhos `/home/user/...`.
  - `test_info_do_sistema_sem_username_real` — texto REAL do QLabel
    (subprocesso com env do pipeline) não contém `$HOME` real e contém
    os caminhos neutros.

## 3. Artefatos

- [x] T004 Regenerar `docs/screenshots/*` com o pipeline corrigido
  (`6_settings`, `small_settings`, `preview` sem `/home/pedro`).

## Verificação

- [x] `pytest tests/test_issue109_neutral_paths.py` — 3 passed.
- [x] Suíte completa + lint antes do PR (gate de CI local).
