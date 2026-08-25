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
| Construção da janela (processo já iniciado) | sem regressão > 20% sobre o baseline medido | meta calibrada no ambiente de CI |

As METAS passam a ser consideradas cumpridas no S145 somente após a
execução das medições da seção 5 no equipamento.

## 2. Como medir (reproduzível)

### 2.1 Bench de fundação (construção da janela, idle, auto-clicker)

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.bench_perf -v
```

Mede, no processo real do app nativo, em uma única execução:

| Métrica | Fonte |
| --- | --- |
| `window_construction_ms` | `time.perf_counter` em torno de `MouseHubApp()`, em processo já iniciado (NÃO inclui imports do PyQt5) |
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

### 2.4 Process startup frio (cold startup)

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.bench_cold_startup -v
```

**Process startup**: novo processo Python + imports + `QApplication` +
`show()` + event loop. Diferente da construção da janela do bench de
fundaçao — que instancia `MouseHubApp()` no processo já aquecido do
teste — esta medição inclui o custo dos imports do PyQt5 e do
`QApplication` do zero. Ela mede process startup controlado: NÃO
representa primeira instalação, filesystem frio nem boot completo do
sistema.

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
`mouse_hub.py` / porta 7777). O lifecycle do `launcher.sh` é AUTOMATIZADO
e coberto por testes determinísticos (`tests/test_launchers.py`,
`LauncherLifecycleTest`, sem UI real e sem sleep longo):

1. processo inicia → marcador criado pelo PRÓPRIO processo Python do
   app (PID real + process start time, campo 22 de
   `/proc/<pid>/stat`), PID existente, cmdline do Mouse Hub, vivo e
   start time idêntico ao registrado (kernel que reutiliza PID não
   passa — start time é monotônico por encarnação);
2. processo morre na inicialização → launcher detecta, NÃO anuncia
   sucesso, marcador removido (falha nunca vira sucesso);
3. marcador stale (PID inexistente) → removido, nova execução inicia.

O marcador é escrito/removido pelo processo Python real (atexit, com
fallback de trap no bash intermediário — dash não roda trap EXIT sob
sinal, então o wrapper usa bash explícito); nenhum watcher, daemon ou
loop de monitoramento fica rodando. Para reproduzir:

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_launchers -v
```

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
| App nativo em idle | 0,1–0,5% CPU; 0 subprocessos filhos (MEDIDO, seção 4) | dentro da META |
| Auto-clicker 1–50 CPS | CPU de sistema 0,0–1,0%, 1 thread, escalando com CPS (MEDIDO com emissor fake — ver seção 4) | dentro da META no CI |
| Macro playback (10 s) | CPU adicional 0,1%; `play()` retorna em 2,6 ms; threads voltam ao baseline (MEDIDO com emissor mockado) | dentro da META no CI |
| `mouse_hub.py` (app web legado) | 2–3 subprocessos xdotool por clique, `print` por iteração, polling de 200 ms (INFERÊNCIA da leitura do código, confirmada qualitativamente) | não carregado pelo fluxo nativo |
| `MouseController` (xinput) | subprocesso esporádico apenas em ação do usuário (DPI/sensibilidade) (MEDIDA: `children` = 0 em idle) | aceito — operação rara |

Sobre o custo real de emissão de eventos XTest/XRecord: este
documento **não** afirma um valor numérico. A emissão real não é
medida pelos testes aqui descritos; o que está medido é o custo de
sistema (scheduler, timers, workers) do app nativo. O custo de
transporte X11 permanece uma questão em aberto, a ser respondida pela
medição no S145 (seção 5) ou por uma sessão com display real.

## 4. Evidências desta PR (head final)

As medições abaixo foram **reexecutadas no head final da PR**, depois
da reconciliação com a `main` (que incorporou a correção do busy-loop
da issue #23 / PR #51). Nenhum número da PR antiga foi reutilizado sem
ser reexecutado. Ambiente real da re-execução:

* Linux Mint 22.3 (Zena), kernel 7.0.0-30-generic x86_64, Intel Core
  i5-1235U, 12 threads, 32 GB RAM — **NÃO é o hardware de referência**
  (IdeaPad S145 i5 / 8 GB): é a máquina de desenvolvimento do executor;
* Python 3.12.3, PyQt5 5.15.11, python-xlib 0.33, pytest 9;
* `QT_QPA_PLATFORM=offscreen` — sem display físico (Xvfb disponível
  para o smoke da UI);
* head da PR na re-execução: `1a6392d` (que contém o merge
  `eb67422` de `main` + correção #23). O CI (GitHub Actions
  `ubuntu-latest`) reexecuta os mesmos métodos em cada push — as
  faixas abaixo são deste ambiente, os guardrails de CI são os mesmos
  métodos com os mesmos limites;
* os valores voláteis (CPU, tempo, RSS exato) variam entre execuções
  do mesmo ambiente — reportamos faixas, não pontos únicos, e os
  testes usam guardrails com folga deliberada em vez de thresholds
  colados no medido.

**Nenhuma medição abaixo foi feita no S145.** Automações (clicker,
playback, recording) foram exercitadas com `FakeAutomationIO` /
eventos sintéticos — o custo real de emissão XTest/XRecord não é
medido por estes testes (ver seção 5):

| Métrica | MEDIDA (re-execução no head, máquina do executor) | META correspondente (seção 1) |
| --- | --- | --- |
| Construção da janela (processo já iniciado) | 96,5–647,7 ms (3 execuções; a maior inclui o 1º import do PyQt5 no processo) | sem regressão > 20% sobre baseline |
| Process startup (processo novo + imports + show + 1ª passagem do loop) | 636–2.085 ms (4 execuções; 3 de 4 entre 636–940 ms; guardrail CI < 4.000 ms) | — |
| RSS estabilizado | 60,6 MB (3 execuções idênticas) | ≤ 150 MB |
| Threads / subprocessos em idle | 1 / 0 | 0 filhos |
| CPU idle (10 s) | 0,1–0,5% (3 execuções) | ≤ 1% |
| Auto-clicker 1 CPS | 0,0–0,4% CPU (6/5 cliques entregues) | — |
| Auto-clicker 20 CPS | 0,4–0,6% CPU (100/100 cliques) | — |
| Auto-clicker 50 CPS | 0,4–1,0% CPU (247–249/250 cliques) | — |
| Macro playback 10 s | CPU adicional 0,0–0,1%; `play()` 0,4–2,6 ms; 70 eventos; threads no baseline | zero busy-wait |
| Memória em 120 s (UI viva) | 0,2% de crescimento (62.248 → 62.372 KB) | < 10% |
| Recording: 2.000 callbacks | 1,3–6,9 µs/evento (4 execuções; a mais lenta é a 1ª, com import frio) | < 200 µs/evento |
| Recording: crescimento de memória 4k→8k eventos | bytes/evento constante (109,0–109,7 → idem); RSS 256–304 → 820–876 KB (4 execuções) | O(n) |
| Lifecycle do launcher | fake app determinístico: 3 casos (início com PID real + process start time, morte imediata sem sucesso falso, marker stale removido) | uma instância por display |

**Regressão #23 não reapareceu:** o `tests/test_playback_cost`
(re-executado no head) mede **0,0–0,1%** de CPU adicional durante
10 s de playback — contra ~98% da falha original — e o
`AutomationScheduler.wait_next()` dorme em `Event.wait` com
`_notify.clear()` atômico sob o mesmo lock da versão (correção da
PR #51). Os testes determinísticos `tests/test_scheduler_regression.py`
(9 casos: mudança de intervalo, espera bloqueante, stop, reset,
concorrência) passam sem alteração.

Os valores de cold startup variam com o estado do cache de módulos: a
primeira execução (import do PyQt5 ainda não mapeado) é a mais lenta
(2.085 ms; as demais ficaram em 636–940 ms). O guardrail de CI é
4.000 ms justamente por isso; os valores deste ambiente e os do CI
são medidos no mesmo método, em máquinas diferentes — não são
comparáveis entre si e não representam cache frio do S145 (primeira
instalação).

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
