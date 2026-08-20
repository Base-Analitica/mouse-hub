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

Performance é requisito funcional — o app controla um mouse, não é uma
plataforma pesada. Orçamentos de projeto (CPU idle ≤ 1%, RSS ≤ 150 MB,
0 subprocessos em idle, memória sem vazamento) e o procedimento
reproduzível de medição estão em
[`docs/performance/metodologia.md`](docs/performance/metodologia.md).

**Resumo das medições no ambiente do CI** (Ubuntu 24.04, Python 3.12,
PyQt5 5.15.11, display virtual Xvfb — **não** é o IdeaPad S145; a
validação no notebook de referência é descrita na metodologia):

| Métrica | Medido no CI |
| --- | --- |
| Inicialização | ~164–174 ms |
| RSS idle | ~62–64 MB |
| Threads / subprocessos em idle | 1 / 0 |
| CPU idle | 0,1% |
| Auto-clicker 1–50 CPS | 0,0–0,7% CPU, dentro do esperado |
| Memória em 120 s | 0,0% de crescimento |
| Cold startup (processo novo) | ~926–988 ms (guardrail CI < 4.000 ms) |
| Macro recording | < 0,002 ms/callback; memória linear com nº de eventos |

Repetir as medições:

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest \
  tests.bench_perf tests.bench_cold_startup tests.test_memory_stability \
  tests.test_playback_cost tests.bench_recording -v
```
