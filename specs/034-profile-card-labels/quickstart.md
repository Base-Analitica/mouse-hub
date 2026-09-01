# Quickstart: cards de Perfis (#85/#86)

## Pré-requisitos

- Python 3.10 ou superior
- Dependências de desenvolvimento instaladas
- Execução a partir de `/home/pedro/.jcode/scratch/issue85-86-profile-cards`
- Nenhum mouse físico ou sessão X11 real necessária para os testes determinísticos

## Teste dedicado

```bash
cd /home/pedro/.jcode/scratch/issue85-86-profile-cards
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 \
  python3 -m pytest tests/test_issue85_86_profile_cards.py -q -rA
```

O teste verifica a tabela de labels oficiais, fallback de nomes customizados, identidade dos callbacks, ausência do placeholder, badge ativo/inativo e geometrias em 1050×680 e 760×560.

## Regressões

```bash
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 \
  python3 -m pytest \
  tests/test_issue6_profiles_polling.py \
  tests/test_config_profiles.py \
  tests/test_issue66_ui_craft.py \
  tests/test_issue3_ui_integration.py -q -rA
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

Execute o capturador duas vezes em diretórios temporários distintos, sem usar o diretório versionado como staging intermediário:

```bash
python3 scripts/capture_screenshots.py \
  --out /home/pedro/.jcode/scratch/issue85-86-capture-a
python3 scripts/capture_screenshots.py \
  --out /home/pedro/.jcode/scratch/issue85-86-capture-b
```

Compare os 15 PNGs por bytes e dimensões. Depois copie somente `5_perfis.png`, `small_perfis.png` e `preview.png` se o diff contra `origin/main` estiver limitado às regiões da página de Perfis.

Dimensões esperadas:

- `5_perfis.png`: 1050×680
- `small_perfis.png`: 760×560
- `preview.png`: 2130×2770

## CI e entrega

Depois de commitar e publicar a branch, abrir um PR com `Closes #85` e `Closes #86`. Confirmar no HEAD final exatamente:

- `Lint de sintaxe e testes determinísticos`
- `Smoke da UI (Xvfb)`
- `Pacote .deb`

O PR deve permanecer aberto e não merged. Testes offscreen, Xvfb e CI comprovam comportamento de software, não validação física do G403 HERO ou de sessão X11 real.
