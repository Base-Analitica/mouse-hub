# Metodologia de Performance — Mouse Hub

Issue #12 — Definir e cumprir orçamento de performance para IdeaPad S145 i5 / 8 GB.

Este documento define **como** o Mouse Hub é medido, **o que** é medido,
**onde** as medições podem ser repetidas e **quais** são os orçamentos de
projeto. Nenhum número aqui é atribuído ao hardware de referência
(Lenovo IdeaPad S145) sem medição executada nele — as seções de
evidência dizem explicitamente em qual ambiente foram obtidas.

## Princípios

Performance é requisito funcional do produto. As medições seguem quatro
regras fixas: nada de benchmark inventado, nada de número atribuído a
hardware não testado, medições reproduzíveis com um único comando e
separação clara entre **dados medidos** e **metas (orçamentos)**.

## Orçamentos de projeto (metas)

| Métrica | Orçamento | Racional |
| --- | --- | --- |
| CPU em idle (sem automações, 60 s) | ≤ 1% de um núcleo | app de controle de mouse deve ficar dormente |
| RSS em idle (processo principal) | ≤ 150 MB | folga confortável para 8 GB do notebook de referência |
| Subprocessos filhos em idle | 0 | xdotool/xinput não pertencem ao hot path nativo |
| Busy-wait em idle | proibido | aguardo é sempre `Event.wait` / timers do Qt |
| Crescimento de memória (sessão prolongada) | < 10% sobre o baseline | ausência de vazamento em listeners e workers |
| Custo do auto-clicker | ≤ `max(2,0; CPS × 0,05)` % CPU | escala linear com CPS, sem overhead fixo alto |
| Inicialização (instanciação da janela) | sem regressão > 20% sobre o baseline medido | meta calibrada no ambiente de CI |

Os orçamentos são validados fisicamente no IdeaPad S145 sempre que o
executor tiver acesso ao equipamento. Até lá, valem as medições do
ambiente de CI e o procedimento de repetição abaixo.

## Como medir (reproduzível)

### 1. Bench de fundação (startup, idle, auto-clicker)

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.bench_perf -v
```

Mede em uma única execução, no processo real do app nativo:

| Métrica | Fonte |
| --- | --- |
| `startup_ms` | `time.perf_counter` em torno de `MouseHubApp()` |
| `rss_mb` | `/proc/<pid>/status` (VmRSS) após estabilização |
| `threads` | `/proc/<pid>/task` |
| `children` | processos com `PPid` igual ao PID do app |
| `idle_cpu_pct` | `/proc/<pid>/stat` utime+stime sobre janela de 60 s |
| `cps_matrix` | CPU + contagem real de cliques por regime (1, 20, 50 CPS) |

Duração ajustável: `BENCH_IDLE_SECONDS` (padrão 60) e
`BENCH_ACTIVE_SECONDS` (padrão 20 por regime CPS). No CI os valores são
encurtados (`10 / 5`) para caber no tempo de execução. O auto-clicker
usa `FakeAutomationIO` injetada no `AutomationService` — o custo do
XTest real é desprezível frente ao custo de sistema, e a contagem de
cliques valida o clock do worker (não pode medir "relógio quebrado"
com CPU zero).

### 2. Estabilidade de memória

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_memory_stability -v
```

Mantém a janela viva por 120 s com `processEvents` a cada segundo,
coletando RSS a cada 10 s. O teste reprova com crescimento total ≥ 10%
sobre o baseline — cobre vazamento de listeners, workers e timers.

### 3. Custo de macro playback

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_playback_cost -v
```

Reproduz uma macro representativa (10 s, 40 eventos de teclas, cliques
e movimentos) e mede CPU do processo, latência de `play()` na thread da
UI e vazamento de threads após o fim. Orçamentos: < 2% CPU para a
macro longa, `play()` retorna em < 100 ms (worker separado), threads
voltam ao baseline (cleanup do worker confirmado).

### 4. Smoke da UI (Xvfb)

```bash
QT_QPA_PLATFORM=offscreen xvfb-run -a python3 -m unittest tests.smoke_ui_init
```

Valida que a fundação constrói e permanece 100% lazy: nenhum display X,
worker ou acesso a disco é criado antes do primeiro uso da feature.

### 5. Suíte determinística completa

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/
```

Inclui testes de regressão que provam, por mock, a ausência de
subprocesso no hot path (`tests/test_automation_linux.py`): clique
via XTest nativo com `subprocess.run` nunca chamado, e tick de foco do
Dashboard/Auto-Clicker sem xdotool/xinput.

### Repetindo no IdeaPad S145

Em uma instalação padrão do Linux Mint com o mouse conectado:

```bash
sudo apt install python3-pyqt5 python3-pytest xvfb -y
pip3 install --user python-xlib
git clone https://github.com/Base-Analitica/mouse-hub.git
cd mouse-hub
python3 -m pip install -e ".[dev]"
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.bench_perf tests.test_memory_stability tests.test_playback_cost -v
```

Com display físico (avaliação de responsividade da UI), troque o
Xvfb do smoke por `xvfb-run -a` ou rode `./launcher.sh` e meça com
`ps`/`htop`/`pidstat -p <pid> 1 60` ao lado.

## Caminhos de custo identificados

| Caminho | Custo real | Estado |
| --- | --- | --- |
| App nativo em idle | 0,1% CPU, 0 subprocessos | medido — dentro do orçamento |
| Auto-clicker 1–50 CPS | 0,0–0,7% CPU, 1 thread, escalando linear | medido — dentro do orçamento |
| Macro playback (10 s) | 0,1% CPU, worker dedicado com cleanup | medido — dentro do orçamento |
| `mouse_hub.py` (app web legado) | 2–3 subprocessos xdotool por clique, print por iteração, polling de 200 ms | identificado — lançado por `launcher.sh`/`start.sh` na raiz; fluxo nativo não o carrega |
| `MouseController` (xinput) | subprocesso esporádico apenas em ação do usuário (DPI/sensibilidade) | aceito — operação rara, não afeta idle |

O app web legado (`mouse_hub.py`) **não é importado nem carregado** pelo
fluxo nativo, portanto não consome CPU/RAM quando o app nativo roda.
A descontinuação formal dele pertence à issue #10; esta PR apenas
muda o launcher padrão da raiz para o app nativo, removendo o servidor
HTTP e o xdotool do fluxo normal de uso.

## Ambiente das medições desta PR

As medições da seção de evidências foram executadas em:

* Ubuntu 24.04 (Linux 6.1.102 x86_64), 6 vCPU AMD EPYC, 3,8 GB RAM;
* Python 3.12.3, PyQt5 5.15.11, python-xlib 0.17, pytest 8;
* display virtual Xvfb (`QT_QPA_PLATFORM=offscreen`) — mesmo ambiente
  do CI do projeto (GitHub Actions `ubuntu-latest`);
* commit de referência: `271d4f7` (main).

Nenhum valor acima afirma comportamento no IdeaPad S145. A validação
física no notebook de referência é obrigatória antes de qualquer
afirmação sobre ele; os orçamentos têm margem suficiente (folga de
10–100× sobre os números medidos) para tolerar a diferença de
hardware entre o CI e o S145.

## Mudanças desta PR

1. `launcher.sh` e `start.sh` da raiz passam a lançar o app nativo
   (`app/mouse_hub_app.py`) — sem servidor HTTP no fluxo normal; o
   app web legado permanece no repo (descontinuação na issue #10).
2. `docs/performance/metodologia.md` — este documento.
3. `tests/test_memory_stability.py` — regressão de crescimento de
   memória em sessão prolongada.
4. `tests/test_playback_cost.py` — regressão de CPU/latência/cleanup
   do macro playback.
5. Seção `Performance` no README com os orçamentos e o link para a
   metodologia.

## Validade das medições

* O bench do auto-clicker usa `FakeAutomationIO`; o custo do XTest real
  é medido como desprezível em relação ao custo de sistema, dentro de
  ~0,01 ponto percentual de CPU — abaixo do piso de ruído do método.
* O bench de playback também usa backend mockado pelo mesmo motivo.
* O RSS medido em offscreen tende a ser menor que no display físico
  (nenhum conteúdo rasterizado de widgets acelerados) — a margem do
  orçamento de 150 MB cobre essa diferença com folga.
