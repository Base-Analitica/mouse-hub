# Quickstart: Verificar o label do nome da macro

## Pré-requisitos

- Python 3.10+
- dependências do projeto instaladas, incluindo PyQt5 5.15.11
- execução a partir da raiz do checkout

## Teste focado

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest \
  tests/test_issue104_macro_label.py -q
```

O teste confirma a transparência do label, a existência de um único campo de
nome e a ordem geométrica nos viewports 1050×680 e 760×560.

## Regressões

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest \
  tests/test_issue4_macro_recording.py \
  tests/test_issue7_ui_caps.py -q
```

## Screenshots e integridade

```bash
QT_QPA_PLATFORM=offscreen python3 scripts/capture_screenshots.py
python3 -m compileall -q app mouse_hub tests scripts
git diff --check
```

Revisar `docs/screenshots/4_macros.png`,
`docs/screenshots/small_macros.png` e `docs/screenshots/preview.png`.

## Smoke e suíte completa

```bash
QT_QPA_PLATFORM=offscreen xvfb-run -a \
  python3 -m unittest tests.smoke_ui_init
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q -rA
```

Estas verificações são evidência de software determinístico. Não constituem
validação física do Logitech G403 nem de uma sessão X11 real.
