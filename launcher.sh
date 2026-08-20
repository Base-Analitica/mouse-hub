#!/bin/bash
# ─── Mouse Hub Launcher ──────────────────────────────────
# Launcher para o app NATIVO (PyQt5): abre a janela em segundo plano
# sem travar o terminal. Uma instância por display — se o app já
# estiver rodando no mesmo $DISPLAY, apenas avisa e sai. O app web
# legado (mouse_hub.py, porta 7777) não é carregado neste fluxo — a
# descontinuação formal dele pertence à issue #10.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="/tmp/mouse_hub_native.log"

# Verifica Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 nao encontrado!" >&2
    exit 1
fi

# Uma instância por display: o PID da janela é rastreado por DISPLAY
RUN_MARKER="/tmp/mouse-hub-native-${DISPLAY:-:0}.pid"
if [ -f "$RUN_MARKER" ]; then
    OLD_PID=$(cat "$RUN_MARKER" 2>/dev/null)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "🖱️  Mouse Hub já está rodando (PID $OLD_PID em $DISPLAY)"
        exit 0
    fi
    rm -f "$RUN_MARKER"
fi

# Verifica DISPLAY (a UI precisa de um display X)
if [ -z "$DISPLAY" ]; then
    echo "❌ DISPLAY nao definido. Execute em um terminal grafico." >&2
    exit 1
fi

# Verifica dependencias Python do app nativo
python3 -c "from PyQt5.QtWidgets import QApplication" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  PyQt5 nao encontrado. Instalando..."
    python3 -m pip install --user --break-system-packages PyQt5 PyQt5-sip PyQt5-Qt5 2>/dev/null
fi

python3 -c "from Xlib import display" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  python3-xlib nao encontrado. Instalando..."
    python3 -m pip install --user --break-system-packages python-xlib 2>/dev/null
fi

# Verifica permissão HID (DPI via HID++, opcional)
HIDRAW="/dev/hidraw0"
if [ -e "$HIDRAW" ] && [ ! -w "$HIDRAW" ]; then
    sudo -n chmod 666 "$HIDRAW" 2>/dev/null && echo "Permissão HID atualizada"
fi

# Inicia o app em segundo plano
cd "$SCRIPT_DIR"
nohup python3 app/mouse_hub_app.py > "$LOG" 2>&1 &
APP_PID=$!
echo "$APP_PID" > "$RUN_MARKER"

# Mantém o marcador enquanto o processo existir (cleanup simples)
(
    wait "$APP_PID"
    rm -f "$RUN_MARKER"
) >/dev/null 2>&1 &

echo "🖱️  Mouse Hub iniciado (PID $APP_PID, log em $LOG)"
