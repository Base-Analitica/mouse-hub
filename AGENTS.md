# AGENTS.md — Convenções para agentes de código

Diretrizes para qualquer agente (Hermes, OpenCode, etc.) trabalhar neste repositório.

**Idioma**: pt-BR para comentários, docstrings, issues e PRs; identificadores de código em inglês.

## O que é este projeto

Controlador nativo (PyQt5) do mouse **Logitech G403 HERO** para Linux (alvo: Linux Mint): DPI, sensibilidade, perfis, macros e auto-clicker. Python ≥ 3.10. O produto suportado é o app desktop nativo (`start.sh`, `launcher.sh`, `app/run_app.sh` ou `app/mouse_hub_app.py`). O servidor/UI web legado foi removido na issue #10 e não deve ser recriado.

## Arquitetura

| Caminho | Papel |
|---|---|
| `mouse_hub/core/` | Regras de domínio (DPI, sensibilidade, perfis, config, descoberta). **Única** implementação permitida dessas regras |
| `mouse_hub/platform/` | Camada de plataforma: protocolo HID++ (`protocol.py`, `hidpp.py`) e backend Linux (`platform/linux/`) |
| `app/mouse_hub_app.py` | UI nativa PyQt5. Não contém regras de domínio |
| `tests/` | Suíte determinística **sem hardware** + benchmarks (`bench_*`) + smoke de UI |

**Regra de ouro** (declarada no próprio `mouse_hub/__init__.py`): regras de domínio vivem somente no `core`. Lógica de DPI/perfil/sensibilidade na UI ou na platform é bug de arquitetura.

## Comandos

```bash
# Testes locais (não exige instalar o pacote — tests/conftest.py ajusta sys.path)
python3 -m pytest tests/

# Réplica do job `test` do CI:
pip install -e ".[dev]" PyQt5==5.15.11
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/

# Benchmark encurtado (mesma forma do CI)
QT_QPA_PLATFORM=offscreen BENCH_IDLE_SECONDS=10 BENCH_ACTIVE_SECONDS=5 \
  python3 -m unittest tests.bench_perf -v

# Smoke de UI com display virtual (job `ui_smoke`)
xvfb-run -a QT_QPA_PLATFORM=offscreen python3 -m unittest tests.smoke_ui_init

# Iniciar o produto nativo
./start.sh
# ou
./app/run_app.sh
```

O CI (`.github/workflows/ci.yml`) roda em Python 3.12 com 2 jobs: `test` (compileall + imports + pytest + benchmarks) e `ui_smoke` (Xvfb). Um PR só está pronto quando **ambos** passam — e o estado reportado deve vir das checks reais, nunca presumido.

## Regras para agentes

1. **Hardware não existe no CI.** Tudo que depende do mouse físico (HID++, udev, XTest/XRecord) deve ser testável via fakes (`tests/fakes.py`). Código novo que toque hardware precisa de caminho fakeável + teste determinístico correspondente.
2. **Teste de regressão junto do fix.** Toda correção de bug chega com teste que falha sem a mudança e passa com ela.
3. **Menor mudança completa.** Cada linha rastreia até uma issue. Sem refatoração drive-by nem reformatação de código alheio.
4. **Branch + PR, sempre.** Nunca pushar direto na `main`. Branches: `fix/<tema>` ou `feat/<tema>`; commits convencionais em inglês (`feat:`, `fix:`, `docs:`, `test:`).
5. **PR vinculado à issue**: corpo com problema, abordagem, testes executados e riscos; fechar com `Closes #N`.
6. **UI**: PyQt5 fixado em `5.15.11` no CI — não atualizar versão sem discussão prévia. Mudanças de UI se verificam com `QT_QPA_PLATFORM=offscreen`.
7. **Constantes de domínio**: respeite `mouse_hub/core/constants.py` (`DPI_MIN/MAX/STEP`, `DPI_PRESETS`, `SENSITIVITY_*`, `POLLING_RATES`). Nada de limites hardcoded em outro lugar.
8. **Prioridades das issues**: P0 = bloqueia uso; P1 = importante; P2 = melhoria. Use a prioridade para calibrar escopo do PR.
9. **Fluxo de dupla**: quem implementa entrega PR e NÃO faz merge — revisão e merge são do mantenedor (@mantenedor / Pedro). Requests de mudança do revisor têm prioridade máxima.
10. **Web legado não volta.** Não recrie servidor HTTP, `static/index.html`, `mouse_hub.py` raiz ou lógica de domínio paralela para navegador.

## Armadilhas conhecidas

- O pacote **não está instalado** em runtime na máquina de desenvolvimento: os testes importam o core direto do repo (`tests/conftest.py`). Não "conserte" isso alterando o layout.
- Permissões de udev para HID++ pertencem à máquina do usuário (ver `docs/udev/`). Em ambiente sem permissão, a descoberta do device deve degradar com elegância, nunca crashar.
- `python-xlib` e `PyQt5` são dependências de produção; não adicione dependências pesadas sem necessidade.
- Separar DPI físico (HID++) de sensibilidade do sistema (libinput) é decisão de design central — ver issues #3, #6 e #7 antes de mexer nesse eixo.
- `start.sh` e `launcher.sh` são entrypoints nativos de compatibilidade; não os transforme novamente em launchers de servidor web e não introduza `/dev/hidraw0`, `chmod 666` ou instalação silenciosa de dependências.
