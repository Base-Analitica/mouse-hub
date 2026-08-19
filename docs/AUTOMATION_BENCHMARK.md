# Benchmarks de automação — PR `refactor/native-core-g403`

## Ambiente

Os benchmarks foram executados no sandbox de desenvolvimento do Manus
(Ubuntu 24.04, Linux, container), **não** no IdeaPad S145 de
referência. Os números abaixo refletem o custo relativo das
implementações (hot path direto vs. modelo por subprocesso) e servem
como baseline reproduzível. A validação física no IdeaPad S145
(i5, 8 GB, Linux Mint) segue o procedimento descrito na seção final.

```
NOT PHYSICALLY VALIDATED ON TARGET HARDWARE
```

| Regime | Forma de medição | Resultado |
|---|---|---|
| Auto-clicker desligado (idle) | `/proc/self/stat`, 1 s de repouso | 0.0% de um núcleo |
| Auto-clicker 5 CPS | cliques do fake IO + CPU | 5.0 cps efetivos, 0.0% de um núcleo |
| Auto-clicker 20 CPS | idem | 20.0 cps efetivos, 0.3% de um núcleo |
| Auto-clicker 50 CPS | idem | 49.7 cps efetivos, 0.7% de um núcleo |
| Gravação de macro (10.000 eventos) | `time.monotonic` + RSS | 0.024 s (421 mil eventos/s), +1.3 MB de RSS |
| Playback (200 eventos @ 8 ms) | tempo total vs. somatório de deltas | 1.649 s, respeitando o timing |
| Cancel de macro longa | `player.cancel()` + assert | worker encerrado em < 2 s |
| RSS ao final dos benchmarks | `/proc/self/status` | 17.6 MB |

Nenhum benchmark produz cliques reais: `FakeAutomationIO` acumula
eventos em memória, e os scripts são seguros para rodar na CI.

## O que os números provam

1. **Hot path sem subprocesso.** O custo de 50 CPS é 0.7% de um
   núcleo — um modelo equivalente a `subprocess.run(["xdotool",
   "click"])` por clique custaria dezenas de vezes mais (fork/exec a
   ~1 ms por clique ≈ 5% de CPU só em overhead de processo).
2. **Foco desacoplado do clique.** `WindowFocusChecker` consulta o
   sistema apenas quando o cache TTL expira (padrão 500 ms): a 50 CPS
   isso significa no máximo 2 consultas/s, não 50.
3. **Cancelamento imediato.** O scheduler usa `threading.Event.wait`,
   que acorda em vez de girar; o player de macro encerra sob demanda.
4. **Memória proporcional.** A gravação de 10 mil eventos custa
   1.3 MB; não há estrutura fixa por dispositivo.

## Como reproduzir no IdeaPad S145

```bash
git clone https://github.com/Base-Analitica/mouse-hub.git
cd mouse-hub && git checkout refactor/native-core-g403
python3 scripts/benchmark_autoclicker.py
python3 scripts/benchmark_macros.py
```

As metas da Issue #12 para o conjunto do aplicativo
(CPU <= 1%/core em idle, RSS <= 150 MB, zero subprocessos contínuos)
permanecem como orçamento de projeto a ser validado quando a UI
adotar este core — a adoção da UI é responsabilidade de outra
instância e fica fora desta PR.
