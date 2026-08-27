<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/mouse-gaymer-banner-dark.webp">
    <source media="(prefers-color-scheme: light)" srcset="assets/mouse-gaymer-banner-light.webp">
    <img src="assets/mouse-gaymer-banner-light.webp" alt="Mouse Gaymer — Auto-click e macros no Linux" width="100%">
  </picture>
</p>

<h1 align="center">Mouse Hub</h1>

<p align="center">
  Aplicativo desktop nativo para o <strong>Logitech G403 HERO</strong> no Linux Mint.
</p>

<p align="center">
  <a href="https://github.com/Base-Analitica/mouse-hub/actions/workflows/ci.yml"><img src="https://github.com/Base-Analitica/mouse-hub/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Linux-X11-FCC624?logo=linux&logoColor=111111" alt="Linux X11">
  <img src="https://img.shields.io/badge/UI-PyQt5-41CD52?logo=qt&logoColor=white" alt="PyQt5">
</p>

## Estado do projeto

O produto principal é a aplicação PyQt5 em `app/`. O foco atual é exclusivamente o Logitech G403 HERO (VID `046d`, PID `c08f`) no Linux Mint; o projeto não tenta ser uma suíte universal de periféricos.

O core diferencia dispositivo detectado, acesso HID, DPI físico, sensibilidade do sistema e demais capabilities. Operações de hardware só são consideradas bem-sucedidas quando há evidência do protocolo; falha não é convertida em sucesso visual ou persistido.

A suíte automatizada usa fakes/adapters e não substitui validação física. O caminho HID++ de DPI está implementado e testado deterministicamente, mas ainda não deve ser descrito como fisicamente validado no G403 até o teste ser executado no hardware real.

O antigo servidor HTTP e a interface web foram removidos após a consolidação do fluxo nativo. O Mouse Hub não precisa de navegador ou porta local para funcionar.

## Capacidades atuais

| Área | Estado | Dependência | Observação |
| --- | --- | --- | --- |
| **Detecção do G403** | Implementada | — | Identidade do dispositivo é validada; não depende de `/dev/hidraw0` nem da ordem de enumeração. |
| **DPI físico** | Implementado no software | Acesso HID (regra udev, grupo `plugdev`) | HID++ com validação de identidade/feature e tratamento separado de timeout, erro de protocolo, permissão e remoção; validação física ainda pendente. Sem a regra udev, a UI informa "acesso negado" em vez de falhar em silêncio. |
| **Sensibilidade** | Implementada | Sessão X11 (libinput) | É independente do DPI físico. |
| **Perfis e presets** | Implementados | — | Fonte de verdade no core; aplicação de DPI e sensibilidade ocorre como operações independentes. |
| **Polling rate** | Indisponível no stack atual | — | A UI não simula sucesso nem marca frequência ativa sem capacidade confirmada. |
| **Auto-clicker** | Funcional, em hardening | Sessão X11 (XTest + leitura de foco) | 1–50 CPS, três botões e restrição por janela em foco; CPS/botão persistem no config XDG. Sem X11, os controles ficam desabilitados com a causa visível. |
| **Macros — persistência/playback** | Implementados | Sessão X11 (XTest) | Modelo, armazenamento e reprodução existem no core; timing usa o clock do servidor X na captura e relógio monotônico na reprodução. |
| **Macros — captura** | Implementada no software | Sessão X11 (extensão XRecord) | Backend XRecord captura teclado/cliques com handshake, cancelamento durante a inicialização e lifecycle testado deterministicamente; validação end-to-end em sessão X11 real ainda deve ser tratada como evidência separada. |

## Requisitos

- Linux, com foco em Linux Mint;
- **sessão X11** — auto-clicker, macros e leitura de janela em foco usam XTest/XRecord/leitura direta X11; em sessões Wayland essas automações ficam indisponíveis e a UI exibe o motivo em vez de simular funcionamento (DPI físico via HID++ e detecção do dispositivo continuam funcionando);
- Python 3.10+;
- PyQt5 5.15+;
- `python-xlib`.

As dependências Python estão declaradas em [`pyproject.toml`](pyproject.toml).

## Instalação nativa (Linux Mint)

O formato oficial de distribuição é o **instalador `install.sh`**: ele verifica dependências via `apt`, instala a regra udev do G403, copia o app para `/opt/mouse-hub`, registra o atalho e o ícone no menu de aplicativos e adiciona o usuário ao grupo `plugdev`. Um `.deb`/AppImage não é necessário neste estágio; essa decisão vale até que o volume de usuários justifique empacotamento formal.

```bash
git clone https://github.com/Base-Analitica/mouse-hub.git
cd mouse-hub
./install.sh
```

Depois, execute pelo menu de aplicativos (**Mouse Hub**) ou por `/opt/mouse-hub/launcher.sh`.

Para remover (preserva seus dados em `~/.config/mouse-hub/` e `~/.local/share/mouse-hub/`):

```bash
./uninstall.sh
```

## Instalação para desenvolvimento/uso a partir do repositório

Use um ambiente virtual; o aplicativo não precisa alterar os pacotes Python do sistema:

```bash
git clone https://github.com/Base-Analitica/mouse-hub.git
cd mouse-hub
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

Execute pelo entrypoint nativo:

```bash
./start.sh
```

ou diretamente:

```bash
./app/run_app.sh
# ou
python3 app/mouse_hub_app.py
```

`start.sh` e `launcher.sh` são launchers nativos de compatibilidade. Nenhum deles inicia servidor HTTP, abre navegador ou seleciona `/dev/hidraw0`.

## Dados e configuração

O core usa diretórios XDG:

- configuração: `${XDG_CONFIG_HOME:-~/.config}/mouse-hub/`;
- dados: `${XDG_DATA_HOME:-~/.local/share}/mouse-hub/`.

Existe migração não destrutiva do layout legado em `~/mouse-hub/`. Configuração existente porém ilegível/corrompida não deve ser sobrescrita silenciosamente.

## Permissão HID do G403 HERO

A regra versionada em [`docs/udev/99-logitech-g403-hidraw.rules`](docs/udev/99-logitech-g403-hidraw.rules) concede acesso ao grupo `plugdev` com `MODE="0660"`, sem abrir o dispositivo para todos os usuários.

```bash
sudo cp docs/udev/99-logitech-g403-hidraw.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger --action=add --subsystem-match=hidraw
sudo usermod -aG plugdev "$USER"
```

Depois de adicionar o usuário ao grupo, encerre e inicie a sessão novamente. Não use `chmod 666` em `/dev/hidrawX` como fluxo normal.

A descoberta do endpoint é feita pelo aplicativo; não escolha manualmente `/dev/hidraw0`.

## Arquitetura

| Caminho | Responsabilidade |
| --- | --- |
| [`app/`](app/) | UI desktop PyQt5 e composição das páginas. |
| [`mouse_hub/core/`](mouse_hub/core/) | Estado, DPI, sensibilidade, perfis, configuração e automações. |
| [`mouse_hub/platform/`](mouse_hub/platform/) | HID++ e integrações de plataforma. |
| [`tests/`](tests/) | Regressões determinísticas, fakes, benchmarks e smoke da UI. |
| [`docs/`](docs/) | Documentação técnica, regras udev e metodologia de performance. |

A UI projeta o estado do core; não é fonte de verdade sobre o hardware.

## Performance

O hardware de referência do projeto é um Lenovo IdeaPad S145, Intel Core i5, 8 GB RAM, Linux Mint. As metas iniciais incluem CPU idle próxima de zero (alvo ≤ 1% de um núcleo), RSS ≤ 150 MB, nenhum busy-wait e nenhum subprocesso recorrente em idle.

Resultados obtidos em outras máquinas devem ser identificados como medições daquele ambiente e não como resultados do S145. A metodologia reproduzível fica em [`docs/performance/metodologia.md`](docs/performance/metodologia.md).

**Resumo das medições reexecutadas no head final da PR #19** (Linux Mint 22.3, Python 3.12.3, PyQt5 5.15.11, `QT_QPA_PLATFORM=offscreen`, máquina do executor — Intel i5-1235U / 32 GB RAM). O CI executa os mesmos métodos em cada push à branch da PR. Cada número foi obtido nesse ambiente — **não** é resultado no IdeaPad S145; a validação no notebook de referência é descrita na metodologia e só é afirmada após medição física nele:

| Métrica | Medido (head final, máquina do executor) |
| --- | --- |
| Construção da janela (processo já iniciado) | ~97–648 ms (3 execuções; a maior inclui o 1º import do PyQt5) |
| RSS idle | ~60,6 MB (3 execuções) |
| Threads / subprocessos em idle | 1 / 0 |
| CPU idle (10 s) | 0,1–0,5% |
| Auto-clicker 1–50 CPS | 1 CPS → 0,0–0,4%; 20 → 0,4–0,6%; 50 → 0,4–1,0% (emissor fake) |
| Macro playback (10 s) | 0,0–0,1% CPU adicional — regressão #23 (busy-loop) não reapareceu |
| Memória em 120 s | 0,2% de crescimento (62.248 → 62.372 KB) |
| Cold startup — processo Python novo + imports + QApplication + show + event loop | 636–2.085 ms (4 execuções; 3 de 4 entre 636–940 ms, a mais lenta é o 1º import do PyQt5) |
| Macro recording (eventos sintéticos) | 1,3–6,9 µs/callback; bytes/evento constante → O(n) |

O cold startup acima é um **process startup** controlado: novo processo Python com as dependências já instaladas e o código/bytecode já em cache. Ele **não representa** primeira instalação, filesystem frio ou boot completo do sistema — medições nessas condições só valem feitas nelas.

Repetir as medições:

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest \
  tests.bench_perf tests.bench_cold_startup tests.test_memory_stability \
  tests.test_playback_cost tests.bench_recording -v
```

A regressão conhecida de busy-loop do scheduler possui teste dedicado e não deve ser mascarada por thresholds enfraquecidos.

## Testes

O CI executa sintaxe/imports, suíte determinística, benchmark mínimo, benchmarks complementares e smoke da UI:

```bash
python3 -m compileall -q mouse_hub tests app
python3 -c "import mouse_hub.core, mouse_hub.platform.linux"
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/
QT_QPA_PLATFORM=offscreen BENCH_IDLE_SECONDS=10 BENCH_ACTIVE_SECONDS=5 \
  python3 -m unittest tests.bench_perf -v
QT_QPA_PLATFORM=offscreen python3 -m unittest \
  tests.bench_cold_startup tests.bench_recording -v
QT_QPA_PLATFORM=offscreen xvfb-run -a \
  python3 -m unittest tests.smoke_ui_init
```

Testes com fakes provam comportamento do software; não são evidência de validação física do G403 nem substituem uma sessão X11 real quando esse detalhe é relevante.

## Contribuição

Leia [`AGENTS.md`](AGENTS.md) antes de alterar o projeto. Mudanças devem preservar, nesta ordem: correção de hardware, segurança, comportamento verificável, simplicidade e performance.
