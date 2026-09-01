# Quickstart: validar a microcopy de segurança do Auto-Clicker

Execute a partir da raiz do worktree `fix/autoclicker-security-copy`.

## Pré-requisitos

- Python 3.10+
- PyQt5 5.15.11
- dependências de desenvolvimento já usadas pelo projeto
- nenhum hardware físico ou sessão X11 real necessária para testes determinísticos

## Teste dedicado e regressões

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest -q \
  tests/test_issue82_83_security_copy.py \
  tests/test_issue5_autoclicker.py \
  tests/test_issue7_ui_caps.py \
  tests/test_automation_linux.py
```

Resultado esperado: copy neutra, sem X11/TTL/cache, com foco e bloqueio fora do jogo; motor e capabilities permanecem intactos.

## Suíte e integração local

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q -rA
xvfb-run -a env QT_QPA_PLATFORM=offscreen \
  python3 -m unittest tests.smoke_ui_init
python3 -m compileall -q app mouse_hub tests scripts
git diff --check
```

## Screenshots determinísticas

```bash
python3 scripts/capture_screenshots.py
python3 scripts/capture_screenshots.py
```

Compare bytes e dimensões de `6_settings.png`, `small_settings.png` e `preview.png`; as mudanças esperadas ficam no grupo de segurança do Auto-Clicker.

## Pacote e CI

```bash
packaging/deb/build_deb.sh
```

Depois do commit e push, confirme no PR os jobs reais de lint/testes determinísticos, pacote `.deb` e smoke Xvfb. O PR deve permanecer aberto e sem merge.
