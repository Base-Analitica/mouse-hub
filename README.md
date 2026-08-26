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

O core já diferencia dispositivo detectado, acesso HID, DPI físico, sensibilidade do sistema e demais capabilities. Operações de hardware só são consideradas bem-sucedidas quando há evidência do protocolo; falha não é convertida em sucesso visual ou persistido.

A suíte automatizada usa fakes/adapters e não substitui validação física. O caminho HID++ de DPI está implementado e testado deterministicamente, mas ainda não deve ser descrito como fisicamente validado no G403 até o teste ser executado no hardware real.

## Capacidades atuais

| Área | Estado | Observação |
| --- | --- | --- |
| **Detecção do G403** | Implementada | Identidade do dispositivo é validada; não depende de `/dev/hidraw0` nem da ordem de enumeração. |
| **DPI físico** | Implementado no software | HID++ com validação de identidade/feature e tratamento separado de timeout, erro de protocolo, permissão e remoção; validação física ainda pendente. |
| **Sensibilidade** | Implementada | É independente do DPI físico. |
| **Perfis e presets** | Implementados | Fonte de verdade no core; aplicação de DPI e sensibilidade ocorre como operações independentes. |
| **Polling rate** | Indisponível no stack atual | A UI não simula sucesso nem marca frequência ativa sem capacidade confirmada. |
| **Auto-clicker** | Funcional, em hardening | 1–50 CPS, três botões e restrição por janela em foco; a consolidação final permanece acompanhada pela issue correspondente. |
| **Macros — persistência/playback** | Implementados | Modelo, armazenamento e reprodução existem no core. |
| **Macros — captura real** | Ainda incompleta | A gravação real de teclado/mouse no app nativo ainda é trabalho pendente; não é apresentada aqui como feature concluída. |

## Requisitos

- Linux, com foco em Linux Mint;
- sessão X11 para as integrações nativas atuais de input/foco;
- Python 3.10+;
- PyQt5 5.15+;
- `python-xlib`.

As dependências Python estão declaradas em [`pyproject.toml`](pyproject.toml).

## Instalação para desenvolvimento/uso a partir do repositório

Use um ambiente virtual; o aplicativo não precisa alterar os pacotes Python do sistema:

```bash
git clone https://github.com/Base-Analitica/mouse-hub.git
cd mouse-hub
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

Execute diretamente o aplicativo nativo:

```bash
python3 app/mouse_hub_app.py
```

Os launchers legados ainda existentes no repositório estão sendo eliminados/ajustados durante a consolidação do produto nativo. O fluxo suportado não depende de servidor HTTP.

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

Resultados obtidos em outras máquinas devem ser identificados como medições daquele ambiente e não como resultados do S145. A metodologia reproduzível fica em [`docs/performance/metodologia.md`](docs/performance/metodologia.md) quando presente na `main`.

A regressão conhecida de busy-loop do scheduler possui teste dedicado e não deve ser mascarada por thresholds enfraquecidos.

## Testes

O CI executa sintaxe/imports, suíte determinística, benchmark mínimo e smoke da UI:

```bash
python3 -m compileall -q mouse_hub tests mouse_hub.py app
python3 -c "import mouse_hub.core, mouse_hub.platform.linux"
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/
QT_QPA_PLATFORM=offscreen BENCH_IDLE_SECONDS=10 BENCH_ACTIVE_SECONDS=5 \
  python3 -m unittest tests.bench_perf -v
QT_QPA_PLATFORM=offscreen xvfb-run -a \
  python3 -m unittest tests.smoke_ui_init
```

Testes com fakes provam comportamento do software; não são evidência de validação física do G403.

## Contribuição

Leia [`AGENTS.md`](AGENTS.md) antes de alterar o projeto. Mudanças devem preservar, nesta ordem: correção de hardware, segurança, comportamento verificável, simplicidade e performance.
