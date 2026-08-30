# Quickstart: validar a configuração Serena read-only

Execute a partir da raiz do worktree `fix/serena-read-only-config`.

## Teste dedicado

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest -q tests/test_issue63_serena_read_only.py
```

## Ponte Serena (quando instalada)

```bash
scripts/agent/semantic-code tools
scripts/agent/semantic-code overview app/mouse_hub_app.py
scripts/agent/semantic-code find SettingsPage --path app/mouse_hub_app.py
scripts/agent/semantic-code refs SettingsPage app/mouse_hub_app.py
scripts/agent/semantic-code diagnostics app/mouse_hub_app.py
```

Se `.tools/serena/venv/bin/serena` não existir, registre a execução como bloqueada e use o teste estático, sem instalar dependências no CI.

## Regressão do projeto

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q -rA
xvfb-run -a env QT_QPA_PLATFORM=offscreen python3 -m unittest tests.smoke_ui_init
python3 -m compileall -q app mouse_hub tests scripts
git diff --check
packaging/deb/build_deb.sh
```
