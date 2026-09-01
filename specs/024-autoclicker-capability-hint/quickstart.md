# Quickstart: Hint de capacidade do Auto-Clicker visível

## Pré-requisitos

- Python 3.10+
- dependências de desenvolvimento do projeto instaladas
- PyQt5 5.15.11
- Xvfb para o smoke, sem mouse físico

## Teste TDD focado

```bash
cd /home/pedro/.jcode/scratch/issue78-autoclicker-capability-hint
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue78_autoclicker_capability_hint.py -q
```

O primeiro ciclo deve mostrar RED pela ausência do `caps_hint` no layout. Após a menor alteração, o mesmo comando deve passar.

## Regressões e smoke

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest \
  tests/test_issue78_autoclicker_capability_hint.py \
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

A validação local prova comportamento de software. Ela não é uma medição física do G403 nem de uma sessão X11 real.
