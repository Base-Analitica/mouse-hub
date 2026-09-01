# Quickstart de validação

Execute a partir da raiz do repositório.

```bash
export QT_QPA_PLATFORM=offscreen
python3 -m pytest -q tests/test_issue97_profile_copy.py tests/test_issue6_profiles_polling.py
python3 -m pytest -q tests/test_issue6_profiles_polling.py tests/test_issue3_ui_integration.py tests/test_issue7_ui_caps.py
python3 -m pytest -q tests/
xvfb-run -a env QT_QPA_PLATFORM=offscreen python3 -m unittest tests.smoke_ui_init -v
python3 -m compileall -q app mouse_hub tests scripts
git diff --check
python3 scripts/capture_screenshots.py
```

A validação local é evidência de software. A validação física do mouse G403 não faz parte desta issue.
