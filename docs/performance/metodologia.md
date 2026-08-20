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

Mantém a janela viva por 120 s com `processEvents` a cada segundo,
coletando RSS a cada 10 s. Reprova com crescimento total ≥ 10% sobre o
baseline — cobre vazamento de listeners, workers e timers.

### 2.3 Custo de macro playback

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_playback_cost -v
```

Reproduz uma macro representativa (10 s, 40 eventos de teclas, cliques
e movimentos) com backend mockado e mede:

* CPU **adicional** do processo sobre o fundo do mesmo processo
  (janela de idle de 2 s antes do playback é descontada);
* latência de `play()` na thread da UI;
* threads após o fim do playback, comparadas ao snapshot da mesma
  execução (cleanup do worker).

### 2.4 Smoke da UI (Xvfb)

```bash
QT_QPA_PLATFORM=offscreen xvfb-run -a python3 -m unittest tests.smoke_ui_init
```

Valida que a fundação constrói e permanece 100% lazy: nenhum display X,
worker ou acesso a disco é criado antes do primeiro uso da feature.

### 2.5 Suíte determinística completa

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/
```

Inclui testes que provam, por mock, a ausência de subprocesso no hot
path (`tests/test_automation_linux.py`): clique via XTest nativo com
`subprocess.run` nunca chamado, e tick de foco do Dashboard/Auto-Clicker
sem xdotool/xinput.

### Repetindo no IdeaPad S145 (medição futura)

Em uma instalação padrão do Linux Mint com o mouse conectado:

```bash
sudo apt install python3-pyqt5 python3-pytest xvfb -y
pip3 install --user python-xlib
git clone https://github.com/Base-Analitica/mouse-hub.git
cd mouse-hub
python3 -m pip install -e ".[dev]"
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.bench_perf tests.test_memory_stability tests.test_playback_cost -v
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
* commit de referência: `271d4f7` (main).

| Métrica | MEDIDA | Categoria da META correspondente |
| --- | --- | --- |
| Inicialização (instanciação da janela) | 174,2 ms (164,5 ms em segunda execução) | ≤ baseline + 20% |
| RSS estabilizado | 64,1 MB (62,5 MB na segunda execução) | ≤ 150 MB |
| Threads / subprocessos em idle | 1 / 0 | 0 filhos |
| CPU idle (10 s / 20 s) | 0,1% | ≤ 1% |
| Auto-clicker 1 CPS | 0,0% CPU do sistema (4/3 cliques entregues) | — |
| Auto-clicker 20 CPS | 0,0–0,2% CPU do sistema (60/100 cliques) | — |
| Auto-clicker 50 CPS | 0,4–0,7% CPU do sistema (149–249/150–250 cliques) | — |
| Macro playback 10 s | CPU adicional 0,1–0,5%; `play()` 0,18–0,35 ms; threads no baseline | — |
| Memória em 120 s (UI viva) | 0,0% de crescimento (64204 KB constante) | < 10% |

Na segunda execução (janela do processo já aquecida) os valores de
startup e RSS caíram para 36,7 ms e 55,5 MB no runner de CI — a
diferença entre as duas execuções é apresentada sem escolher uma como
"o" valor oficial; ambas são evidência do mesmo método.

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
   não é capturado pelos testes com emissor mockado.

Enquanto as etapas 1–4 não forem executadas, todas as afirmações sobre
o S145 neste repositório são inválidas e devem ser ignoradas.

## 6. Mudanças desta PR

1. `launcher.sh` e `start.sh` da raiz passam a lançar o app nativo
   (`app/mouse_hub_app.py`) — sem servidor HTTP no fluxo normal; o
   app web legado permanece no repo (descontinuação na issue #10).
2. `docs/performance/metodologia.md` — este documento.
3. `tests/test_memory_stability.py` — regressão de crescimento de
   memória em sessão prolongada.
4. `tests/test_playback_cost.py` — regressão de CPU/latência/cleanup
   do macro playback.
5. Seção `Performance` no README com resumo de performance.
