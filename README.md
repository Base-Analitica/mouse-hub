<p align="center">
  <img src="assets/mouse-gaymer-banner.webp" alt="Mouse Gamer — Mouse Hub para Linux" width="100%">
</p>

<h1 align="center">Mouse Hub</h1>

<p align="center">
  Aplicativo nativo para controlar o <strong>Logitech G403 HERO</strong> no Linux.
  <br>
  DPI, sensibilidade, perfis, macros e auto-clicker com foco em uma experiência desktop integrada.
</p>

<p align="center">
  <a href="https://github.com/Base-Analitica/mouse-hub/actions/workflows/ci.yml"><img src="https://github.com/Base-Analitica/mouse-hub/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10 ou superior">
  <img src="https://img.shields.io/badge/Linux-X11-FCC624?logo=linux&logoColor=111111" alt="Linux com X11">
  <img src="https://img.shields.io/badge/UI-PyQt5-41CD52?logo=qt&logoColor=white" alt="Interface PyQt5">
</p>

> **Estado do projeto:** o aplicativo desktop em `app/` é o caminho principal. O servidor web na raiz (`mouse_hub.py`) e seus launchers permanecem no repositório por compatibilidade, mas estão em processo de descontinuação e não devem receber novas funcionalidades.[^1]

## Visão geral

O Mouse Hub é um controlador nativo para Linux direcionado ao Logitech G403 HERO. A aplicação separa as regras de domínio, o acesso ao protocolo HID++ e a interface PyQt5, permitindo testar a maior parte do comportamento sem depender de um mouse físico conectado. O controle de DPI físico usa HID++ quando o dispositivo e as permissões estão disponíveis; a sensibilidade do sistema é tratada como uma configuração independente.[^1] [^2]

O projeto foi pensado para uso em ambientes Linux com X11, especialmente Linux Mint. A automação de cliques e macros é inicializada sob demanda e possui uma verificação centralizada de foco, evitando emitir cliques quando a janela ativa não pertence ao contexto reconhecido pelo aplicativo.[^1]

## Funcionalidades

| Área | O que está disponível | Observações de escopo |
| --- | --- | --- |
| **DPI** | Ajuste de 100 a 25.600 DPI em passos de 50, presets para FPS, Minecraft PvP e flick shots. | O ajuste físico depende do acesso ao endpoint HID++ do G403 HERO. |
| **Sensibilidade** | Controle da sensibilidade do ponteiro do sistema de 0% a 100%. | É independente do DPI físico do mouse. |
| **Perfis** | Perfis para Minecraft PvP, CS:GO e configurações personalizadas. | As configurações são persistidas pelo aplicativo. |
| **Auto-clicker** | CPS configurável, seleção do botão e estados visíveis na interface. | O motor bloqueia a emissão quando o foco não está em uma janela reconhecida. |
| **Macros** | Gravação, armazenamento e reprodução de eventos de teclado e mouse. | A automação usa a camada nativa de input do Linux/X11. |
| **Interface** | Dashboard e páginas dedicadas para DPI, sensibilidade, auto-clicker, macros, perfis e configurações. | Interface desktop construída com PyQt5. |

> **Limitação conhecida:** a interface apresenta opções de *polling rate* de 125, 250, 500 e 1.000 Hz, mas o modelo de capacidades atual não declara o ajuste de polling rate como disponível no hardware. Portanto, essa opção não deve ser interpretada como uma garantia de alteração física do dispositivo.[^1] [^2]

## Requisitos

O caminho principal exige:

| Requisito | Versão ou condição |
| --- | --- |
| Sistema operacional | Linux com sessão gráfica X11 |
| Python | 3.10 ou superior |
| Interface | PyQt5 5.15 ou superior |
| Input e foco | `python-xlib` 0.17 ou superior |
| Hardware suportado | Logitech G403 HERO USB, VID `046d` e PID `c08f` |

As dependências de execução e de desenvolvimento estão declaradas em [`pyproject.toml`](pyproject.toml).[^2]

## Instalação

A instalação em um ambiente virtual evita conflitos com o gerenciador de pacotes da distribuição:

```bash
git clone https://github.com/Base-Analitica/mouse-hub.git
cd mouse-hub

python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -e .
```

Se `venv` não estiver disponível na distribuição, instale o pacote correspondente ao Python antes de repetir os comandos acima. O aplicativo também precisa ser executado dentro de uma sessão gráfica X11 com acesso ao display atual.

## Execução

Com o ambiente virtual ativado, inicie a aplicação nativa pela raiz do repositório:

```bash
./app/run_app.sh
```

O launcher verifica a presença do PyQt5 e inicia `app/mouse_hub_app.py`. Para executar diretamente, use:

```bash
python3 app/mouse_hub_app.py
```

Os arquivos de configuração e os dados de macros são armazenados em `~/mouse-hub/`, conforme a configuração atual do aplicativo.[^1]

## Permissão para ajustar o DPI físico

Sem uma regra udev adequada, o Mouse Hub pode executar sem acesso de escrita ao dispositivo HID e não conseguirá aplicar o DPI físico via HID++. A configuração versionada em [`docs/udev/99-logitech-g403-hidraw.rules`](docs/udev/99-logitech-g403-hidraw.rules) concede acesso ao grupo `plugdev` sem abrir o dispositivo para todos os usuários.

Instale a regra uma única vez:

```bash
sudo cp docs/udev/99-logitech-g403-hidraw.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger --action=add --subsystem-match=hidraw
sudo usermod -aG plugdev "$USER"
```

Depois, encerre e inicie novamente a sessão do usuário para que a associação ao grupo tenha efeito. A regra usa permissões `0660`; não é necessário nem recomendado executar `chmod 666` no dispositivo `hidraw`.[^3]

Para confirmar a descoberta do dispositivo, substitua `hidrawN` pelo endpoint identificado no seu sistema:

```bash
udevadm info /dev/hidrawN | grep -i logitech
ls -l /dev/hidrawN
```

## Arquitetura

A separação de responsabilidades atual é a seguinte:

| Caminho | Responsabilidade |
| --- | --- |
| [`app/`](app/) | Interface desktop PyQt5 e composição das páginas da aplicação. |
| [`mouse_hub/core/`](mouse_hub/core/) | Regras de domínio: DPI, sensibilidade, perfis, configuração, descoberta e automação. |
| [`mouse_hub/platform/`](mouse_hub/platform/) | Protocolo HID++ e integração com o backend Linux/X11. |
| [`tests/`](tests/) | Testes determinísticos, fakes de hardware, benchmark e smoke test da UI. |
| [`docs/udev/`](docs/udev/) | Regra udev específica para o Logitech G403 HERO. |
| `mouse_hub.py`, `static/`, `start.sh` e `launcher.sh` | Caminho web legado, mantido congelado enquanto a migração para o app nativo é concluída. |

A regra arquitetural central é que a lógica de domínio deve permanecer em `mouse_hub/core/`; a interface e a camada de plataforma não devem duplicar regras de DPI, sensibilidade ou perfis.[^1]

## Testes e desenvolvimento

A suíte é executada sem hardware físico por meio de fakes e cobre o core, o protocolo HID++, a descoberta do dispositivo, a persistência, a automação Linux e a inicialização da UI. Para reproduzir localmente o ambiente de CI:

```bash
python3 -m pip install -e ".[dev]" PyQt5==5.15.11

python3 -m compileall -q mouse_hub tests mouse_hub.py app
python3 -c "import mouse_hub.core, mouse_hub.platform.linux"
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/
QT_QPA_PLATFORM=offscreen BENCH_IDLE_SECONDS=10 BENCH_ACTIVE_SECONDS=5 \
  python3 -m unittest tests.bench_perf -v
QT_QPA_PLATFORM=offscreen xvfb-run -a \
  python3 -m unittest tests.smoke_ui_init
```

O workflow [`ci.yml`](.github/workflows/ci.yml) executa os testes determinísticos e o smoke test da UI com Python 3.12.[^4]

## Contribuição

Antes de abrir uma alteração, leia [`AGENTS.md`](AGENTS.md). O fluxo esperado é criar uma branch `feat/<tema>` ou `fix/<tema>`, manter o escopo da mudança restrito, incluir testes para correções de comportamento e abrir um pull request para revisão do mantenedor. Commits seguem o padrão convencional em inglês, como `docs: improve project README`.[^1]

## Referências

[^1]: [AGENTS.md — convenções de arquitetura, execução e contribuição](AGENTS.md)
[^2]: [`pyproject.toml` — metadados, dependências e limites de compatibilidade](pyproject.toml)
[^3]: [`docs/udev/99-logitech-g403-hidraw.rules` — regra de permissões do Logitech G403 HERO](docs/udev/99-logitech-g403-hidraw.rules)
[^4]: [`.github/workflows/ci.yml` — jobs de testes e smoke test da interface](.github/workflows/ci.yml)
