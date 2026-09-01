# AGENTS.md — Convenções para agentes de código

Diretrizes para agentes de código trabalharem neste repositório. O agente
responsável pelo projeto é o **Jcode** (configuração em `.jcode/`).

**Idioma**: pt-BR para comentários, docstrings, issues e PRs; identificadores de código em inglês.

## O que é este projeto

Aplicativo desktop nativo (PyQt5) e motor local de **controle e automação de entrada** para Linux (alvo: Linux Mint). Mouse e teclado fazem parte do domínio de input; configuração proprietária de hardware é capability separada e entra somente por adapters explicitamente suportados.

O Logitech G403 HERO é o primeiro hardware concreto do projeto e continua sendo o dispositivo atualmente suportado para DPI físico/HID++, mas **não define mais o limite conceitual do produto**. A direção arquitetural está documentada em `docs/ARCHITECTURE.md`.

O produto suportado é o app desktop nativo (`start.sh`, `launcher.sh`, `app/run_app.sh` ou `app/mouse_hub_app.py`). O servidor/UI web legado foi removido na issue #10 e não deve ser recriado.

## Arquitetura

| Caminho | Papel |
|---|---|
| `mouse_hub/core/` | Regras de domínio, estado, perfis e automações. Deve concentrar a evolução do Input Engine para mouse, teclado, timing e sequências. **Única** implementação permitida dessas regras. |
| `mouse_hub/platform/` | Camada de plataforma: protocolo HID++ (`protocol.py`, `hidpp.py`), backend Linux (`platform/linux/`) e backends de input/hardware. |
| `app/mouse_hub_app.py` | UI nativa PyQt5. Não contém regras de domínio. |
| `tests/` | Suíte determinística **sem hardware** + benchmarks (`bench_*`) + smoke de UI. |

**Regra de ouro** (declarada no próprio `mouse_hub/__init__.py`): regras de domínio vivem somente no `core`. Lógica de DPI/perfil/sensibilidade/automação na UI ou duplicada na platform é bug de arquitetura.

### Direção do Input Engine

A arquitetura deve convergir, conforme necessidades reais surgirem, para primitivas tipadas equivalentes a movimento/botões/scroll de mouse, key down/up de teclado, espera, sequência, repetição e agendamento controlado.

Auto-clicker, macros, hotkeys e outras features devem **compor essas primitivas**, não criar emissores paralelos quando o engine já representar a operação.

Não faça uma reescrita especulativa nem crie um framework universal de dispositivos sem caso concreto. A migração deve ser incremental, guiada por issues e testes.

### Fronteiras obrigatórias

1. **Input genérico ≠ gerenciamento universal de periféricos.** Suporte a teclado no engine não autoriza implementar RGB, firmware, polling ou recursos proprietários de qualquer teclado sem adapter/capability explícito.
2. **Emissão ≠ automação semântica.** Mouse Hub executa ações de input; reconhecimento de tela, interpretação de intenção e decisão sobre “o que clicar” pertencem a outra camada.
3. **Captura explícita ≠ keylogger.** Captura de teclado/cliques só existe em modos explícitos, observáveis e com lifecycle claro. Não introduza monitoramento global contínuo do que o usuário digita.
4. **Hardware real é autoridade.** Capability não confirmada não produz estado fictício de sucesso.
5. **Standalone continua obrigatório.** O Mouse Hub deve permanecer útil sem Katherine, Ouroboros ou qualquer outro módulo da Anakyklos.

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

1. **Hardware não existe no CI.** Tudo que depende do mouse físico (HID++, udev, XTest/XRecord) ou de backends de input deve ser testável via fakes (`tests/fakes.py`). Código novo que toque hardware/input precisa de caminho fakeável + teste determinístico correspondente.
2. **Teste de regressão junto do fix.** Toda correção de bug chega com teste que falha sem a mudança e passa com ela.
3. **Menor mudança completa.** Cada linha rastreia até uma issue. Sem refatoração drive-by nem reformatação de código alheio.
4. **Branch + PR, sempre.** Nunca pushar direto na `main`. Branches: `fix/<tema>` ou `feat/<tema>`; commits convencionais em inglês (`feat:`, `fix:`, `docs:`, `test:`).
5. **PR vinculado à issue**: corpo com problema, abordagem, testes executados e riscos; fechar com `Closes #N` quando houver issue correspondente.
6. **UI**: PyQt5 fixado em `5.15.11` no CI — não atualizar versão sem discussão prévia. Mudanças de UI se verificam com `QT_QPA_PLATFORM=offscreen`.
7. **Constantes de domínio**: respeite `mouse_hub/core/constants.py` (`DPI_MIN/MAX/STEP`, `DPI_PRESETS`, `SENSITIVITY_*`, `POLLING_RATES`). Nada de limites hardcoded em outro lugar.
8. **Prioridades das issues**: P0 = bloqueia uso; P1 = importante; P2 = melhoria. Use a prioridade para calibrar escopo do PR.
9. **Fluxo de dupla**: quem implementa entrega PR e NÃO faz merge — revisão e merge são do mantenedor (@mantenedor / Pedro). Requests de mudança do revisor têm prioridade máxima.
10. **Web legado não volta.** Não recrie servidor HTTP, `static/index.html`, `mouse_hub.py` raiz ou lógica de domínio paralela para navegador.
11. **Sem keylogging contínuo.** Não introduza captura global persistente/oculta de teclado. Gravação deve ser feature explícita, delimitada e cancelável.
12. **Sem RPA semântico no core.** OCR, visão computacional, interpretação de UI e tomada autônoma de decisão sobre aplicações não pertencem ao Mouse Hub.

## Eficiência de tokens (agentes)

<!-- BEGIN TOKEN-EFFICIENCY LAYER -->

**Código mínimo (estilo ponytail)**: entenda o fluxo real antes de editar; reutilize implementação existente; prefira stdlib e dependências já presentes; sem abstração/helper para uso único; sem dependência nova para problema trivial; menor mudança correta; sem refactor adjacente; sem duplicar lógica existente. Legibilidade e testes valem mais que economia.

**Comunicação enxuta (profissional, não "caveman speak")**: respostas curtas por padrão; não repetir a solicitação; não narrar ações óbvias; não explicar código que fala por si; não despejar logs completos (citá-los só quando a precisão exigir); conclusões com resultado, validação, arquivos e bloqueios reais. Código, comandos, erros e dados técnicos permanecem exatos.

**Shell comprimido**: use `scripts/agent/rtk` para saídas verbosas (`git status/diff/log`, `rg/grep`, `pytest`, `find`, `ls`). Saída bruta para diffs exatos, dados byte-sensíveis ou resultados pequenos. Em falhas, inspecione o tee antes de reexecutar. Setup: `scripts/agent/bootstrap-rtk` (uma vez por checkout). Ver `.jcode/skills/token-efficient-shell/`.

**Navegação semântica**: prefira `scripts/agent/semantic-code` (overview/find/refs) antes de ler arquivos grandes; fallback: `rg` + leitura de trechos. Nunca comece lendo o repositório inteiro: estrutura → símbolos candidatos → referências → ler só as regiões relevantes. Arquivo já compreendido e inalterado: reutilize o conhecimento. Ver `.jcode/skills/semantic-code/`.

**Compaction**: em tarefas longas, consulte o uso de contexto em limites naturais e compacte quando houver material resolvido e trabalho substancial restante, preservando no resumo: objetivo, decisões, invariantes, arquivos modificados, testes, erros abertos e próximo passo. Não compacte compulsivamente a cada turno.

**Subagentes**: apenas com os modelos autorizados pelo mantenedor (`openai-codex/gpt-5.6-luna` ou `opencode-go/deepseek-v4-flash`). O agente principal roda no modelo do próprio provedor. Nenhum outro modelo.

**Decisões registradas**: EcoTokens descartado (sobrepõe RTK); Tokscale descartado (telemetria nativa do agente basta). Detalhes e benchmark: `.token-efficiency/REPORT.md`.

<!-- END TOKEN-EFFICIENCY LAYER -->

## Armadilhas conhecidas

- O pacote **não está instalado** em runtime na máquina de desenvolvimento: os testes importam o core direto do repo (`tests/conftest.py`). Não "conserte" isso alterando o layout.
- Permissões de udev para HID++ pertencem à máquina do usuário (ver `docs/udev/`). Em ambiente sem permissão, a descoberta do device deve degradar com elegância, nunca crashar.
- `python-xlib` e `PyQt5` são dependências de produção; não adicione dependências pesadas sem necessidade.
- Separar DPI físico (HID++) de sensibilidade do sistema (libinput) é decisão de design central — ver issues #3, #6 e #7 antes de mexer nesse eixo.
- `start.sh` e `launcher.sh` são entrypoints nativos de compatibilidade; não os transforme novamente em launchers de servidor web e não introduza `/dev/hidraw0`, `chmod 666` ou instalação silenciosa de dependências.