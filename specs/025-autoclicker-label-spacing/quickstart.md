# Quickstart: Espaçamento semântico dos botões do Auto-Clicker

## Pré-requisitos

- Python 3.10+
- dependências de desenvolvimento instaladas
- PyQt5 5.15.11
- Xvfb para o smoke, sem mouse físico

## Teste TDD focado

```bash
cd "$(git rev-parse --show-toplevel)"
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue79_autoclicker_label_spacing.py -q
```

O primeiro ciclo deve mostrar RED porque os textos atuais começam com dois espaços. Depois da menor alteração, o mesmo comando deve passar.

## Regressões e smoke

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest \
  tests/test_issue79_autoclicker_label_spacing.py \
  tests/test_issue7_ui_caps.py \
  tests/test_issue66_ui_craft.py -q

QT_QPA_PLATFORM=offscreen xvfb-run -a \
  python3 -m unittest tests.smoke_ui_init
```

## Capturas

```bash
QT_QPA_PLATFORM=offscreen python3 scripts/capture_screenshots.py
```

Conferir `docs/screenshots/3_clicker.png`, `small_clicker.png` e `preview.png`, repetir a captura e comparar bytes.

## Gates finais

```bash
python3 -m compileall -q app mouse_hub tests scripts
git diff --check
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q -rA
packaging/deb/build_deb.sh
```

A validação local prova comportamento de software. Ela não é medição física do G403 nem de uma sessão X11 real.
