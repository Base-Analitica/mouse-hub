# Quickstart: Verificar o heading CPS

Pré-requisito: ambiente de dev do repo (`uv run --with pytest --project .`).

## Verificação automática (teste de regressão)

```bash
TMPDIR=/tmp QT_QPA_PLATFORM=offscreen \
  uv run --with pytest --project . python -m pytest \
  tests/test_issue66_ui_craft.py -k cps_heading -q
```

Esperado: `1 passed` — o teste assegura que o texto do heading é exatamente
`CPS (Cliques por segundo)`.

## Verificação manual (opcional, com display)

```bash
./start.sh
```

Abrir a página **Auto-Clicker**: o heading do controle de velocidade deve ler
`CPS (Cliques por segundo)`. Reduzir a janela à largura mínima: a copy é a
mesma no layout small.

## Regenerar screenshots

Seguir o pipeline documentado em `docs/screenshots/` (prática permanente desde
a PR #76) e conferir que `3_clicker.png` e `small_clicker.png` mostram o novo
texto.
