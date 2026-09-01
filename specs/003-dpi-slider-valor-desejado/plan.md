# Plan: DPI slider como "valor desejado" (issue #103)

**Branch**: `fix/dpi-slider-target-state`

## Objetivo

Tornar explícito o papel do slider de DPI como **controle de entrada**
(valor desejado a aplicar), sem que sua posição seja lida como estado
aplicado enquanto o readback físico está desconhecido. O hero permanece
reservado ao readback confirmado / estado de leitura.

## Decisões de design

- **Legenda permanente** sob o slider: `Valor desejado (aplicar ao
  hardware)` — descreve o papel do controle nos dois estados (readback
  conhecido ou desconhecido). Permanente é mais honesto: o slider nunca
  é readback, mesmo com valor confirmado.
- **Constante de módulo** `_DPI_TARGET_LABEL` para o texto (testável);
  nada de strings soltas.
- **Nenhuma mudança no comportamento físico**: preview/commit continuam
  conforme revisão PR #21 (preview visual, commit no release).

## Mudanças por arquivo

| Arquivo | Mudança |
| --- | --- |
| `app/mouse_hub_app.py` | constante `_DPI_TARGET_LABEL`; `QLabel` da legenda após o slider em `DPIPage._build` |
| `tests/test_issue103_dpi_target.py` | novo: legenda presente com readback desconhecido e confirmado; preview não promove hero a aplicado; semântica em 760×560 |
| `docs/screenshots/*` | regeneradas (`1_dpi.png`, `small_dpi.png`, `preview.png`) |

## Princípios (constituição)

| Princípio | Aplicação |
| --- | --- |
| Corretude de hardware | nenhuma operação nova; textos apenas |
| Honestidade de estado | papel do slider explícito; hero só readback |
| Menor mudança completa | 1 widget + 1 constante |
| Dupla verificação | testes novos + suíte existente verde |
