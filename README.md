# 🖱️ Mouse Hub — Controlador de Mouse Gamer

Hub dedicada para o **Logitech G403 HERO** com controle de DPI, Sensibilidade, Macros e Auto-Clicker para Minecraft.

## 🚀 Como Usar

**App nativo (fluxo padrão):**

```bash
cd ~/mouse-hub
./start.sh
```

Abre a interface desktop PyQt5. Não há servidor HTTP no fluxo normal —
`start.sh`/`launcher.sh` da raiz lançam o app nativo.

**App web legado (porta 7777, descontinuado na issue #10):**

```bash
cd ~/mouse-hub
python3 mouse_hub.py
```

## ⚙️ Funcionalidades

### 🎯 DPI (100 - 25600)
- Slider interativo para ajuste fino
- Presets rápidos: CS:GO AWP (400), FPS Geral (800), Minecraft PvP (1200), Flick Shots (1600)
- Campo de entrada manual para valores exatos
- Ajuste via HID++ (quando tem permissão) ou sensibilidade do sistema

### 🎚️ Sensibilidade
- Controle de 0% a 100% via libinput
- Barra visual com gradiente
- Polling Rate seletor (125/250/500/1000 Hz)

### 👤 Perfis
- **Minecraft** — DPI 1200, Sens 60%
- **CS:GO** — DPI 400, Sens 30%
- **Default** — DPI 800, Sens 50%
- **Custom** — Salva suas configurações atuais

### ⚡ Auto-Clicker (Minecraft Only!)
- Funciona **APENAS** quando Minecraft ou Lunar Client está em foco
- CPS ajustável de 1 a 50
- Seleção de botão (esquerdo, meio, direito)
- Indicador visual de status com detecção em tempo real
- **Segurança**: Não clica em outras janelas!

### 🎬 Macros
- Grava teclas e cliques com timing preciso
- Salva e carrega macros automaticamente
- Reprodução com repeat (1x, 3x, etc.)
- Deleta macros desnecessárias

## 📋 Requisitos

- Linux (testado no Linux Mint 22.3)
- Python 3.12+
- python3-xlib (`pip install --user python-xlib`)
- xdotool (`sudo apt install xdotool`)

## 🔧 Permissões HID (Opcional)

Para controle completo de DPI via protocolo HID++:

```bash
# Permissão temporária
sudo chmod 666 /dev/hidraw0

# Permissão permanente (recomendado)
echo 'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="046d", ATTRS{idProduct}=="c08f", MODE="0666"' | sudo tee /etc/udev/rules.d/99-logitech-g403.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

## 🗂️ Estrutura

```
mouse-hub/
├── mouse_hub.py      # Servidor + Backend (DPI, Macros, AutoClicker)
├── static/
│   └── index.html    # Interface Web (Dark Gamer Theme)
├── start.sh          # Script de inicialização
├── config.json       # Configurações salvas
├── macros.json       # Macros gravadas
└── README.md         # Este arquivo
```

## 🎮 Dicas para Minecraft PvP

1. **CPS ideal para crystal PvP**: 12-20 CPS
2. **DPI recomendado**: 800-1200 para controle preciso
3. **Sensibilidade**: 50-70% para movimentos rápidos
4. **Auto-clicker**: Use "Esquerdo" para brigas, "Direito" para placed crystals
5. **Macro "combo"**: Grave W+A+click para strafing automático

## 🛑 Segurança

O Auto-Clicker **NÃO funciona** fora do Minecraft/Lunar Client. O detector verifica o nome da janela ativa a cada ciclo e só clica quando detecta:
- "Minecraft"
- "Lunar Client"
- "Badlion"
- "Feather"
- "Hypixel"

## 📊 Performance

Hardware de referência: **Lenovo IdeaPad S145, Intel Core i5, 8 GB RAM,
Linux Mint padrão**. Performance é requisito funcional — o app controla
um mouse, não é uma plataforma pesada. Metodologia completa em
[`docs/performance/metodologia.md`](docs/performance/metodologia.md).

**Orçamentos de projeto** (validados fisicamente no S145 quando o
executor tiver acesso ao equipamento):

| Métrica | Orçamento |
| --- | --- |
| CPU idle (60 s, sem automações) | ≤ 1% de um núcleo |
| RSS idle | ≤ 150 MB |
| Subprocessos em idle | 0 |
| Crescimento de memória (sessão prolongada) | < 10% sobre baseline |
| Auto-clicker (1–50 CPS) | ≤ `max(2,0; CPS × 0,05)` % CPU |
| Inicialização | sem regressão > 20% sobre baseline |

**Evidências medidas** (Ubuntu 24.04, Python 3.12, PyQt5 5.15.11,
display virtual Xvfb — ambiente do CI; não são medições no S145):

| Métrica | Resultado |
| --- | --- |
| Inicialização (janela) | ~174 ms |
| RSS estabilizado | ~64 MB |
| Threads / subprocessos em idle | 1 / 0 |
| CPU idle (10 s) | 0,1% |
| Auto-clicker 1 CPS | 0,0% CPU (4/3 cliques entregues) |
| Auto-clicker 20 CPS | 0,0% CPU (60/60) |
| Auto-clicker 50 CPS | 0,67% CPU (149/150) |
| Macro playback 10 s | 0,1% CPU; `play()` retorna em 0,25 ms |
| Memória em 120 s | 0,0% de crescimento |

Repetir as medições:

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest \
  tests.bench_perf tests.test_memory_stability tests.test_playback_cost -v
```
