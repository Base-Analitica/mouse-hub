# Quickstart: Card do Auto-Clicker sem coluna de ícone vazia

## Pré-requisitos

- Python 3.10 ou superior
- Dependências de desenvolvimento instaladas
- Execução a partir da raiz do repositório
- Nenhum mouse físico ou sessão X11 real necessária para os testes determinísticos

## Teste dedicado

```bash
cd "$(git rev-parse --show-toplevel)"
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 \
  python3 -m pytest tests/test_issue77_autoclicker_empty_icon.py -q -rA
```

O teste verifica a ausência do placeholder, a posição dos labels nos viewports 1050×680 e 760×560, os estados `stopped`, `running`, `blocked_by_focus` e `failed`, e as transições de iniciar/parar.

## Regressões

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 \
  python3 -m pytest \
  tests/test_issue5_autoclicker.py \
  tests/test_issue7_ui_caps.py \
  tests/test_issue66_ui_craft.py -q -rA
```

## Smoke, compilação, diff e pacote

```bash
xvfb-run -a env QT_QPA_PLATFORM=offscreen \
  python3 -m unittest tests.smoke_ui_init
python3 -m compileall -q app mouse_hub tests scripts
git diff --check
python3 -m pytest tests/test_deb_packaging.py -q -rA
```

## Suíte completa

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 \
  python3 -m pytest tests/ -q -rA
```

## Capturas oficiais

Execute o capturador oficial em duas pastas temporárias distintas, sem usar o diretório versionado como staging intermediário:

```bash
python3 scripts/capture_screenshots.py --out /tmp/issue77-capture-a
python3 scripts/capture_screenshots.py --out /tmp/issue77-capture-b
```

Compare as 15 PNGs por bytes e dimensões. Depois copie apenas `3_clicker.png`, `small_clicker.png` e `preview.png` se a comparação contra `origin/main` confirmar que somente as regiões previstas mudaram.

Dimensões esperadas:

- `3_clicker.png`: 1050×680
- `small_clicker.png`: 760×560
- `preview.png`: 2130×2770

## CI e entrega

Depois de commitar e publicar a branch, abrir um PR com `Closes #77`. Confirmar no HEAD final exatamente:

- `Lint de sintaxe e testes determinísticos`
- `Smoke da UI (Xvfb)`
- `Pacote .deb`

O PR deve permanecer aberto e não merged. Testes offscreen, Xvfb e CI comprovam comportamento de software, não validação física do G403 HERO ou de uma sessão X11 real.
