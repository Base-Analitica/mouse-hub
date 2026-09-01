# Quickstart: Validar o empty state de Macros

**Feature**: [spec.md](./spec.md)
**Issue**: #105

## Pré-requisitos

- Python >= 3.10 com dependências de desenvolvimento instaladas.
- PyQt5 5.15.11 disponível no ambiente de testes.
- Nenhum mouse físico ou sessão X11 real é necessário para os testes
  determinísticos.

## Cenário focado

Execute o teste dedicado com Qt offscreen:

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest \
  tests/test_issue105_macro_empty_state.py -q
```

Resultado esperado: todos os casos passam, cobrindo estado vazio e preenchido,
transição sem widgets residuais, CTA único e os tamanhos 1050×680 e 760×560.

## Suíte de regressão

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q
```

Resultado esperado: zero falhas. O benchmark de playback pode depender da carga
da máquina; se houver flutuação, registrar o resultado separadamente sem
relaxar o threshold.

## Smoke da UI

```bash
QT_QPA_PLATFORM=offscreen xvfb-run -a \
  python3 -m unittest tests.smoke_ui_init
```

Resultado esperado: a janela principal inicializa e fecha sem exceção.

## Screenshots

```bash
QT_QPA_PLATFORM=offscreen python3 scripts/capture_screenshots.py
```

Verifique as imagens geradas em `docs/screenshots/`:

- `4_macros.png`
- `small_macros.png`
- `preview.png`

Nas duas telas de Macros, `Macros Salvas` deve ficar visualmente unido à
mensagem de estado vazio, sem grande área vazia intermediária.

## Checks finais

```bash
python3 -m compileall -q app mouse_hub tests scripts
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_issue105_macro_empty_state.py -q
git diff --check
```

A validação acima prova comportamento de software em ambiente fake/offscreen.
Ela não constitui medição física no Logitech G403 nem validação de uma sessão
X11 real.
