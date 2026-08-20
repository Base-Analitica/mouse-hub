# Metodologia de Performance — Mouse Hub

Issue #12 — Definir e cumprir orçamento de performance para IdeaPad S145 i5 / 8 GB.

Este documento define **como** o Mouse Hub é medido, **o que** é medido e
**onde** cada medição pode ser repetida. Toda afirmação numérica abaixo
é rotulada explicitamente como uma destas três categorias:

| Rótulo | Significado |
| --- | --- |
| **META** | Orçamento de projeto — valor-alvo que ainda não foi medido neste hardware |
| **MEDIDA** | Resultado obtido em execução real, no ambiente descrito |
| **INFERÊNCIA** | Conclusão derivada de medições — declarada como tal, não como fato medido |

Nenhum número deste documento é atribuído ao Lenovo IdeaPad S145. As
medições físicas no S145 ainda não foram executadas (o executor não
teve acesso ao equipamento); a seção 5 descreve como repeti-las nele.

## 1. Metas de projeto

Os valores abaixo são orçamentos definidos pela issue #12 como meta.
São **METAS**, não medições:

| Métrica | META | Racional |
| --- | --- | --- |
| CPU em idle (sem automações, 60 s) | ≤ 1% de um núcleo | app de controle de mouse deve ficar dormente |
| RSS em idle (processo principal) | ≤ 150 MB | folga para 8 GB do notebook de referência |
| Subprocessos filhos em idle | 0 | xdotool/xinput não pertencem ao hot path nativo |
| Busy-wait em idle | proibido | aguardo é sempre `Event.wait` / timers do Qt |
| Crescimento de memória (sessão prolongada) | < 10% sobre o baseline | ausência de vazamento em listeners e workers |
| Auto-clicker | custo de CPU escalando com CPS, sem overhead fixo alto | requisito funcional da issue |
| Inicialização (instanciação da janela) | sem regressão > 20% sobre o baseline medido | meta calibrada no ambiente de CI |

As METAS passam a ser consideradas cumpridas no S145 somente após a
execução das medições da seção 5 no equipamento.

## 2. Como medir (reproduzível)

### 2.1 Bench de fundação (startup, idle, auto-clicker)

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.bench_perf -v
```

Mede, no processo real do app nativo, em uma única execução:

| Métrica | Fonte |
| --- | --- |
| `startup_ms` | `time.perf_counter` em torno de `MouseHubApp()` |
| `rss_mb` | `/proc/<pid>/status` (VmRSS) após estabilização |
| `threads` | `/proc/<pid>/task` |
| `children` | processos com `PPid` igual ao PID do app |
| `idle_cpu_pct` | `/proc/<pid>/stat` utime+stime sobre janela de 60 s |
| `cps_matrix` | CPU + contagem real de cliques por regime (1, 20, 50 CPS) |

Duração ajustável por variáveis de ambiente: `BENCH_IDLE_SECONDS`
(padrao 60) e `BENCH_ACTIVE_SECONDS` (padrao 20 por regime CPS). No CI
os valores são encurtados (`10 / 5`) para caber no tempo de execução.

O auto-clicker é executado com `FakeAutomationIO` injetada no
`AutomationService` — o emissor real de eventos (XTest) é substituído
por um fake que apenas acumula eventos. Consequência direta: a CPU
medida nestes regimes **não inclui** o custo da emissão real de
eventos X11. Esse custo não é medido por este teste e não deve ser
informado como se fosse (ver seção 4).

### 2.2 Estabilidade de memória

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_memory_stability -v
```

Mantém a janela viva por 120 s, processando o event loop a cada 10 s
(o event loop não fica parado — timers e callbacks registrados
continuam rodando), coletando RSS a cada 10 s via `VmRSS`. Há um
warm-up de 5 s antes do baseline para não contar lazy allocations
normais do Qt como leak. O guardrail do teste de CI é crescimento
< 10% — o MESMO critério da META (o esperado em offscreen é 0–2%);
se o RSS crescer de verdade, o teste deve reprovar.

### 2.3 Custo de macro playback

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_playback_cost -v
```

### 2.4 Inicialização fria (cold startup)

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.bench_cold_startup -v
```

Spawna um processo Python **novo** e mede o tempo até a janela estar
utilizável: imports do app, criação do `QApplication`, `show()` e pelo
menos uma passagem efetiva pelo event loop (marcador `READY` via
socket TCP de loopback, enviado só depois disso). Diferente do
`startup_ms` do bench de fundação — que instancia a janela no processo
já aquecido do teste — esta medição inclui o custo dos imports do
PyQt5 e do `QApplication` do zero.

### 2.5 Custo de macro recording

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.bench_recording -v
```

`MacroRecorder` sob eventos **sintéticos** (não mede o custo físico do
listener XRecord/display — a captura real pertence à medição futura no
S145): overhead por callback (< 200 µs), CPU sob carga representativa
(~400 eventos/s por 5 s), crescimento de memória proporcional ao
volume de eventos (4.000 → 8.000 eventos; `VmRSS` cresce em páginas e
nunca decresce — por isso o teste compara o total, não deltas por
lote) e lifecycle `start()`/`stop()` sem threads/timers residuais.

### 2.6 Smoke da UI (Xvfb)

```bash
QT_QPA_PLATFORM=offscreen xvfb-run -a python3 -m unittest tests.smoke_ui_init
```

Valida que a fundação constrói e permanece 100% lazy: nenhum display X,
worker ou acesso a disco é criado antes do primeiro uso da feature.

### 2.7 Suíte determinística e invariantes dos launchers

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/
```

Inclui testes que provam, por mock, a ausência de subprocesso no hot
path (`tests/test_automation_linux.py`): clique via XTest nativo com
`subprocess.run` nunca chamado, e tick de foco do Dashboard/Auto-Clicker
sem xdotool/xinput.

Os launchers (`start.sh`/`launcher.sh`) têm invariantes de segurança
verificados por `tests/test_launchers.py` (estático, sem subprocesso):
nenhuma execução de `pip install` (instalação é única e manual, com
instruções impressas só quando falta dependência), nenhuma manipulação
de permissões de `/dev/hidraw*` ou `sudo` (responsabilidade do hardware
layer do core — issue #3) e lançamento do app nativo (nunca do legado
`mouse_hub.py` / porta 7777). O comportamento de lifecycle do
`launcher.sh` — instância única por DISPLAY com validação de que o PID
registrado é do próprio app, cleanup do marcador de PID via trap na
saída do processo (sem watcher/daemon permanente) e falha rápida sem
sucesso falso quando o app morre na inicialização — foi validado
manualmente contra o código atual e NÃO está automatizado (comando de
repetição em `tests/test_launchers.py`).

### Repetindo no IdeaPad S145 (medição futura)

Em uma instalação padrão do Linux Mint com o mouse conectado:

```bash
sudo apt install python3-pyqt5 python3-pytest xvfb -y
pip3 install --user python-xlib
git clone https://github.com/Base-Analitica/mouse-hub.git
cd mouse-hub
python3 -m pip install -e ".[dev]"
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.bench_perf tests.bench_cold_startup tests.test_memory_stability tests.test_playback_cost tests.bench_recording -v
```

Com display físico, trocar o Xvfb do smoke por `xvfb-run -a` ou rodar
`./launcher.sh` e medir com `ps`/`htop`/`pidstat -p <pid> 1 60` ao
lado. Os resultados obtidos nessa execução são a única fonte válida
para afirmar que as METAS da seção 1 foram cumpridas no S145.

## 3. Caminhos de custo identificados

| Caminho | Custo | Natureza |
| --- | --- | --- |
| App nativo em idle | 0,1% CPU; 0 subprocessos filhos (MEDIDO, seção 4) | dentro da META |
| Auto-clicker 1–50 CPS | CPU de sistema 0,0–0,7%, 1 thread, escalando com CPS (MEDIDO com emissor fake — ver seção 4) | dentro da META no CI |
| Macro playback (10 s) | CPU adicional 0,1–0,5%; `play()` retorna em < 1 ms; threads voltam ao baseline (MEDIDO com emissor mockado) | dentro da META no CI |
| `mouse_hub.py` (app web legado) | 2–3 subprocessos xdotool por clique, `print` por iteração, polling de 200 ms (INFERÊNCIA da leitura do código, confirmada qualitativamente) | não carregado pelo fluxo nativo |
| `MouseController` (xinput) | subprocesso esporádico apenas em ação do usuário (DPI/sensibilidade) (MEDIDA: `children` = 0 em idle) | aceito — operação rara |

Sobre o custo real de emissão de eventos XTest/XRecord: este
documento **não** afirma um valor numérico. A emissão real não é
medida pelos testes aqui descritos; o que está medido é o custo de
sistema (scheduler, timers, workers) do app nativo. O custo de
transporte X11 permanece uma questão em aberto, a ser respondida pela
medição no S145 (seção 5) ou por uma sessão com display real.

## 4. Evidências desta PR

Todas as medições abaixo foram executadas no mesmo ambiente:

* Ubuntu 24.04 (Linux 6.1.102 x86_64), 6 vCPU AMD EPYC, 3,8 GB RAM;
* Python 3.12.3, PyQt5 5.15.11, python-xlib, pytest 8;
* display virtual Xvfb (`QT_QPA_PLATFORM=offscreen`) — mesmo ambiente
  do CI do projeto (GitHub Actions `ubuntu-latest`);
* commit de referência desta execução: `1185630` (branch da PR) — a
  evidência inicial da PR (revisão anterior) vem do commit
  `aa58b88`, e as evidências das revisões subsequentes vêm de execuções
  locais em `1185630+`; o CI do GitHub Actions executa os mesmos
  métodos em `ubuntu-latest` em cada push da PR;
* os valores voláteis (CPU, tempo, RSS exato) variam entre execuções
  do mesmo ambiente — reportamos faixas, não pontos únicos, e os
  testes de CI usam guardrails com folga deliberada em vez de
  thresholds colados no medido.

| Métrica | MEDIDA | Categoria da META correspondente |
| --- | --- | --- |
| Inicialização (instanciação da janela) | 174,2 ms (164,5 ms em segunda execução; commit `aa58b88`) | ≤ baseline + 20% |
| Cold startup (processo novo + imports + show + 1 passagem do loop) | 926–988 ms (2 execuções em cache quente; commit `1185630+`; guardrail CI < 4.000 ms) | — |
| RSS estabilizado | 64,1 MB (62,5 MB na segunda execução) | ≤ 150 MB |
| Threads / subprocessos em idle | 1 / 0 | 0 filhos |
| CPU idle (10 s / 20 s) | 0,1% | ≤ 1% |
| Auto-clicker 1 CPS | 0,0% CPU do sistema (4/3 cliques entregues) | — |
| Auto-clicker 20 CPS | 0,0–0,2% CPU do sistema (60/100 cliques) | — |
| Auto-clicker 50 CPS | 0,4–0,7% CPU do sistema (149–249/150–250 cliques) | — |
| Macro playback 10 s | CPU adicional 0,0–0,1%; `play()` 0,18–0,36 ms; threads no baseline | — |
| Memória em 120 s (UI viva) | 0,0% de crescimento (64204–65120 KB; pico usado como referência) | < 10% |
| Recording: 2.000 callbacks | 2,3–3,9 ms totais (< 0,002 ms/evento); threads no baseline | — |
| Recording: crescimento de memória 4k→8k eventos | 264 KB → 528 KB (proporcional; `VmRSS` por página) | — |

Os valores de cold startup variam fortemente com o estado do cache de
módulos: com o PyQt5 já importado na máquina a janela abre em
~950 ms; na primeira execução do CI (sem cache pré-carregado) o mesmo
método tende a ser mais lento — por isso o guardrail do CI é de
4.000 ms, não um valor fixo. As duas execuções reportadas são do mesmo
método em cache quente e não devem ser confundidas com o caso de
cache frio do S145.

## 5. Validação pendente no IdeaPad S145

Esta é a lista de pendências para completar a issue #12 no hardware de
referência:

1. executar `tests.bench_perf` no S145 e comparar cada métrica com a
   META da seção 1;
2. executar `tests.test_memory_stability` e `tests.test_playback_cost`
   no S145;
3. medir responsividade da UI com display real (os valores de RSS em
   offscreen tendem a ser menores que com display físico, pois nada é
   rasterizado — a META de 150 MB foi definida com essa margem);
4. medir o custo real da emissão XTest/XRecord sob display real, que
   não é capturado pelos testes com emissor mockado;
5. medir `bench_cold_startup` com cache frio (primeira execução,
   sem dependências pré-carregadas) — no CI o mesmo teste inclui o
   custo do primeiro import do PyQt5;
6. repetir o benchmark de recording (`bench_recording`) sob o
   listener XRecord real — o custo atual é medido com eventos
   sintéticos.

Enquanto as etapas 1–4 não forem executadas, todas as afirmações sobre
o S145 neste repositório são inválidas e devem ser ignoradas.

## 6. Mudanças desta PR

1. `launcher.sh` e `start.sh` da raiz passam a lançar o app nativo
   (`app/mouse_hub_app.py`) — sem servidor HTTP no fluxo normal; o
   app web legado permanece no repo (descontinuação na issue #10).
2. `docs/performance/metodologia.md` — este documento.
3. `tests/test_memory_stability.py` — regressão de crescimento de
   memória em sessão prolongada (warm-up, event loop vivo, guardrail
   < 10%).
4. `tests/test_playback_cost.py` — regressão de CPU/latência/cleanup
   do macro playback (thread específica, idle descontado).
5. `tests/bench_cold_startup.py` — inicialização fria com processo
   novo (subprocesso + marcador READY via socket TCP).
6. `tests/bench_recording.py` — custo de macro recording (overhead,
   CPU, memória linear, lifecycle) com eventos sintéticos.
7. `tests/test_launchers.py` — invariantes de segurança dos launchers
   (sem `pip install`/`sudo`/`chmod hidraw` executados; app nativo).
8. `launcher.sh`/`start.sh` reescritos: sem pip automático, sem
   manipulação de HID (`/dev/hidraw0`/`chmod 666`/`sudo`), lifecycle
   correto do marcador de PID (trap na saída, sem watcher; validação
   de que o PID registrado é do app; falha rápida sem sucesso falso).
9. Seção `Performance` no README com resumo de performance.
