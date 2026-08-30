# Quickstart de validação

No worktree da issue #94:

```bash
export QT_QPA_PLATFORM=offscreen
python3 -m pytest tests/test_issue94_preset_hierarchy.py -q -rA
python3 -m pytest tests/test_issue3_ui_integration.py tests/test_issue66_ui_craft.py -q
python3 -m compileall -q app mouse_hub tests
python3 scripts/capture_screenshots.py --out /tmp/issue94-capture
```

A captura oficial deve ser repetida em dois diretórios temporários e comparada com PIL para garantir igualdade byte a byte. A entrega só pode ser considerada pronta após a suíte completa, smoke Xvfb, pacote `.deb` e os três jobs reais do CI passarem no SHA final.
