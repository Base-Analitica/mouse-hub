# Quickstart: validar a microcopy de permissões HID

Execute a partir da raiz do worktree `fix/hid-permission-microcopy`.

## Pré-requisitos

- Python 3.10+
- PyQt5 5.15.11
- dependências de desenvolvimento já usadas pelo projeto
- nenhum mouse físico ou sessão X11 real necessária para testes determinísticos

## Teste dedicado e regressões

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest -q \
  tests/test_issue81_hid_permission_microcopy.py \
  tests/test_issue7_ui_caps.py \
  tests/test_hid_permission_helper.py
```

Resultado esperado: a copy explica o DPI físico, autorização administrativa e
instalação da regra; não pede terminal nem alteração manual; estados reais do
botão permanecem intactos.

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

Compare bytes e dimensões de `6_settings.png`, `small_settings.png` e
`preview.png`; as mudanças esperadas ficam na seção de permissões HID.

## Pacote e CI

```bash
packaging/deb/build_deb.sh
```

Depois do commit e push, confirme no PR os jobs reais de lint/testes
  determinísticos, pacote `.deb` e smoke Xvfb. O PR deve permanecer aberto e sem
  merge.
