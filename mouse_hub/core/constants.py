APP_VERSION = "1.4.0"

"""Parâmetros de domínio fixos do Logitech G403 HERO.

Este módulo centraliza os limites e presets que hoje estão duplicados
entre `mouse_hub.py` e `app/mouse_hub_app.py`. Qualquer ajuste de faixa
de DPI, step ou preset passa por aqui, e nunca mais é reescrito na UI.
"""

# Identidade de hardware do Logitech G403 HERO (USB)
G403_VID = 0x046D
G403_PID = 0xC08F
G403_NAME = "Logitech G403 HERO Gaming Mouse"

# Faixa de DPI suportada pelo sensor HERO
DPI_MIN = 100
DPI_MAX = 25600
DPI_STEP = 50
DPI_DEFAULT = 800

# Presets de DPI usados na UI (mantidos como produto)
DPI_PRESETS = {
    "Low (CS:GO AWP)": 400,
    "Medium (FPS Geral)": 800,
    "High (Minecraft PvP)": 1200,
    "Ultra (Flick Shots)": 1600,
    "Max Speed": 25600,
}

# Sensibilidade do ponteiro do sistema (libinput), em percentual 0-100
SENSITIVITY_MIN = 0
SENSITIVITY_MAX = 100
SENSITIVITY_DEFAULT = 50

# Polling rates suportados pelo G403
POLLING_RATES = [125, 250, 500, 1000]
