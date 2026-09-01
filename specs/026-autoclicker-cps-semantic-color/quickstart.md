# Quickstart: validar a cor semântica do CPS

Execute a partir da raiz do worktree `fix/autoclicker-cps-semantic-color`.

## Pré-requisitos

- Python 3.10+
- PyQt5 5.15.11
- dependências de desenvolvimento já usadas pelo projeto
- nenhum mouse físico ou sessão X11 necessária para os testes determinísticos

## Teste dedicado e regressões de UI

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest -q \
  tests/test_issue80_autoclicker_cps_color.py \
  tests/test_issue7_ui_caps.py \
  tests/test_issue66_ui_craft.py
```

Resultado esperado: todos os testes passam; 1, 25 e 50 CPS usam a cor normal,
o slider atualiza o texto, e o status real de permissão continua usando warning.

## Suíte completa

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

Compare os dois resultados byte a byte e confira que as diferenças contra a
baseline ficam no display numérico do Auto-Clicker em:

- `docs/screenshots/3_clicker.png` (1050×680)
- `docs/screenshots/small_clicker.png` (760×560)
- `docs/screenshots/preview.png` (2130×2770)

## Pacote

```bash
packaging/deb/build_deb.sh
```

Confira que o pacote gerado contém o launcher, a fonte subset e os arquivos do
app sem adicionar dependências.

## CI e entrega

Depois de commit e push, confirme no PR os jobs reais de lint/testes
determinísticos, pacote `.deb` e smoke Xvfb. O PR deve permanecer aberto e sem
merge.
