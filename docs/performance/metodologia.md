# Metodologia de Performance — Mouse Hub

Issue #12 — orçamento de performance para o Lenovo IdeaPad S145 i5 / 8 GB.

Este documento separa explicitamente três categorias:

- **META**: orçamento do projeto;
- **MEDIDA**: valor observado no ambiente informado;
- **INFERÊNCIA**: conclusão derivada, não medição direta.

Nenhum número abaixo deve ser atribuído ao IdeaPad S145 enquanto a medição física nesse equipamento não tiver sido executada.

## 1. Metas do projeto

| Métrica | META |
| --- | --- |
| CPU idle, sem automações | ≤ 1% de um núcleo em média |
| RSS idle | ≤ 150 MB |
| Subprocessos filhos do app em idle | 0 |
| Busy-wait | proibido |
| Crescimento contínuo de memória | proibido; guardrail prolongado < 10% |
| Servidor HTTP no fluxo nativo | 0 |
| Subprocessos recorrentes em hot path | 0 |

A UI deve permanecer responsiva durante captura/reprodução e auto-clicker.

## 2. Benchmarks reproduzíveis

### Fundação: startup da janela, RSS, threads, filhos, CPU idle e CPS

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.bench_perf -v
```

No CI a duração pode ser reduzida por:

```bash
BENCH_IDLE_SECONDS=10 BENCH_ACTIVE_SECONDS=5
```

O auto-clicker usa `FakeAutomationIO`, portanto mede scheduler/serviço e não o custo físico de emissão XTest.

### Process startup

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.bench_cold_startup -v
```

Mede um processo Python novo, imports, `QApplication`, `show()` e primeira passagem do loop. Não equivale a primeira instalação ou filesystem realmente frio.

### Estabilidade de memória

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_memory_stability -v
```

Mantém a UI viva e coleta RSS periodicamente. O objetivo é detectar crescimento contínuo, não exigir um valor exato de memória entre máquinas.

### Macro playback

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_playback_cost -v
```

Protege contra busy-loop e verifica retorno rápido do `play()`, CPU adicional baixa e cleanup das threads do scheduler.

### Macro recording

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.bench_recording -v
```

Usa eventos sintéticos. Mede overhead de callback e crescimento de memória do modelo, não o custo físico do listener XRecord.

### Scheduler regression

```bash
python3 -m pytest tests/test_scheduler_regression.py
```

Este gate existe por causa da regressão da issue #23, em que uma mudança de intervalo deixava `Event.wait()` retornando imediatamente e levava o playback a aproximadamente 98% de CPU. O teste não deve ser enfraquecido para esconder regressões.

### Smoke da UI

```bash
QT_QPA_PLATFORM=offscreen xvfb-run -a python3 -m unittest tests.smoke_ui_init
```

### Launchers

```bash
python3 -m unittest tests.test_launchers -v
```

Os testes garantem:

- nenhum `pip install` executado pelo launcher;
- nenhum `sudo`, `chmod 666` ou `/dev/hidraw0` no fluxo normal;
- app nativo em vez do servidor web;
- falha de startup não vira sucesso;
- uma instância por `DISPLAY` por marcador com PID real + process start time;
- marcador stale não é confundido com processo vivo.

O `launcher.sh` inicia diretamente `python3 app/mouse_hub_app.py` em segundo plano. O PID retornado por `$!` é o processo Python real, e o launcher registra PID + campo 22 de `/proc/<pid>/stat`. Não existe watcher ou daemon permanente. Um marcador deixado após encerramento é inofensivo: na próxima execução ele só é aceito se PID, cmdline e process start time ainda corresponderem; caso contrário é removido antes do novo startup.

## 3. Ambiente das medições existentes

As medições associadas a esta PR foram obtidas em:

- Linux Mint 22.3;
- Intel Core i5-1235U;
- 32 GB RAM;
- Python 3.12.3;
- PyQt5 5.15.11;
- python-xlib 0.33;
- execução offscreen/Xvfb quando aplicável.

**Este ambiente não é o IdeaPad S145 de referência.**

Resultados observados antes da sincronização final com a `main`, usados apenas como evidência do método e revalidados pelos guardrails de CI quando aplicável:

| Métrica | MEDIDA no ambiente do executor |
| --- | --- |
| CPU idle | aproximadamente 0,1–0,5% |
| RSS idle | aproximadamente 60,6 MB |
| Threads / filhos em idle | 1 / 0 |
| Macro playback | aproximadamente 0,0–0,1% de CPU adicional com emissor fake |
| Memória por 120 s | crescimento observado de aproximadamente 0,2% |
| Auto-clicker | exercitado em 1, 20 e 50 CPS com emissor fake |

Valores voláteis variam entre execuções e máquinas. O CI deve ser tratado como guardrail, não como benchmark do S145.

## 4. Limitações das medições automatizadas

Os testes automatizados **não medem**:

- custo físico real de XTest/XRecord em uma sessão X11 real;
- latência HID física do G403;
- consumo no IdeaPad S145;
- primeira instalação/filesystem frio;
- impacto de outros aplicativos normalmente abertos pelo usuário.

Não transformar fakes em prova de hardware real.

## 5. Repetição no IdeaPad S145

No notebook de referência, com Linux Mint e ambiente Python preparado, executar pelo menos:

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.bench_perf -v
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.bench_cold_startup -v
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_memory_stability -v
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_playback_cost -v
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.bench_recording -v
QT_QPA_PLATFORM=offscreen xvfb-run -a python3 -m unittest tests.smoke_ui_init
```

Depois, repetir os cenários de auto-clicker e macro com display X11 real para medir o custo de emissão de input e observar responsividade da UI.

Registrar:

- CPU média em 60 s de idle;
- RSS estabilizado;
- threads e processos;
- cold startup;
- estabilidade de memória;
- auto-clicker em CPS baixo e alto;
- macro recording/playback;
- qualquer diferença relevante entre offscreen e display real.

Somente essa execução física autoriza afirmar que as metas foram cumpridas no S145.

## 6. Regra de evolução

Qualquer PR que altere scheduler, timers, startup, input capture, auto-clicker, macro playback ou lifecycle deve informar:

1. o que foi alterado;
2. o que foi medido;
3. ambiente da medição;
4. antes/depois quando houver baseline comparável;
5. validação física ainda pendente.

Não remover features nem trocar framework sob alegação genérica de performance sem evidência.
