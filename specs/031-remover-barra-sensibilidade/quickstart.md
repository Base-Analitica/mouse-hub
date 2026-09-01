# Quickstart: remover a barra decorativa de Sensibilidade

Execute os comandos a partir da raiz do repositório.

## Teste dedicado

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 \
  python3 -m pytest -q tests/test_issue91_sensitivity_bar.py
```

Esperado: todos os testes passam e comprovam que `QFrame#speedBar` não existe,
enquanto slider, labels, estado e polling continuam presentes.

## Regressões

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 \
  python3 -m pytest -q tests/test_issue3_ui_integration.py \
  tests/test_issue7_ui_caps.py tests/test_dpi_sensitivity.py
```

## Suíte e smoke

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 \
  python3 -m pytest tests/ -q -rA
xvfb-run -a env QT_QPA_PLATFORM=offscreen \
  python3 -m unittest tests.smoke_ui_init -v
python3 -m compileall -q app mouse_hub tests scripts
```

## Capturas

```bash
python3 scripts/capture_screenshots.py
```

Conferir `2_sens.png`, `small_sens.png` e `preview.png` contra as dimensões
oficiais e executar o capturador duas vezes para provar reprodutibilidade.

## Pacote

```bash
bash packaging/deb/build_deb.sh
dpkg-deb --info dist/mouse-hub_0.1.0_all.deb
dpkg-deb --contents dist/mouse-hub_0.1.0_all.deb
```

## Limpeza e diff

```bash
git diff --check
git status --short --branch
```
