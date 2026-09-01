# Quickstart: Verificar os ícones semânticos de DPI e Macros

## Pré-requisitos

- Python 3.10+.
- PyQt5 5.15.11 disponível no ambiente de testes.
- FontTools 4.x disponível somente para regenerar o subset durante o
  desenvolvimento.
- Execução a partir da raiz do checkout isolado.

## RED e GREEN focados

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest \
  tests/test_issue111_semantic_icons.py -q
```

Antes do fix, o teste deve falhar porque U+ED4C e U+EE75 não estão no subset e
as chaves ainda apontam para U+F177 e U+ED21. Depois do fix, deve passar nos
mapeamentos, na presença dos glifos, na renderização em 18/24 px e no fallback.

## Regenerar o subset

```bash
pyftsubset \
  /home/pedro/.local/lib/python3.12/site-packages/qtawesome/fonts/remixicon-2.5.0.ttf \
  --output-file=app/ui/fonts/remixicon-subset.ttf \
  --unicodes=U+EA21,U+EC0A,U+EC14,U+ED21,U+ED4C,U+EE59,U+EE75,U+EED0,U+EF7D,U+F035,U+F0E6,U+F100,U+F177,U+F264 \
  --layout-features='*' --glyph-names --symbol-cmap --legacy-cmap
```

A fonte completa local é somente insumo de desenvolvimento. A lista explícita
preserva os 12 codepoints já usados e adiciona exatamente U+ED4C e U+EE75. O
comando não instala nem adiciona FontTools às dependências do projeto.

## Regressões e integridade

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest \
  tests/test_issue66_ui_craft.py \
  tests/test_issue7_ui_caps.py -q
python3 -m compileall -q app mouse_hub tests scripts
git diff --check
```

## Screenshots oficiais

```bash
QT_QPA_PLATFORM=offscreen python3 scripts/capture_screenshots.py
```

Revisar `docs/screenshots/1_dpi.png`, `small_dpi.png`, `4_macros.png`,
`small_macros.png` e `preview.png`. As dimensões oficiais permanecem 1050×680,
760×560 e 2130×2770 no preview.

## Smoke e suíte completa

```bash
QT_QPA_PLATFORM=offscreen xvfb-run -a \
  python3 -m unittest tests.smoke_ui_init
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q -rA
```

Estas verificações são evidência de software determinístico. Não constituem
validação física do Logitech G403 nem de uma sessão X11 real.
