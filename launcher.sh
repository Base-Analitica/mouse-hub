#!/bin/bash
# ─── Mouse Hub Launcher ────────────────────────────────
# Launcher便捷 para o Mouse Hub

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=7777
LOG="/tmp/mouse_hub.log"

# Verifica se já está rodando
if ss -tlnp | grep -q ":${PORT}"; then
    xdg-open "http://localhost:${PORT}" 2>/dev/null &
    exit 0
fi

# Mata processos antigos
pkill -f "mouse_hub.py" 2>/dev/null
sleep 1

# Verifica permissão HID
HIDRAW="/dev/hidraw0"
if [ -e "$HIDRAW" ] && [ ! -w "$HIDRAW" ]; then
    if sudo -n chmod 666 "$HIDRAW" 2>/dev/null; then
        echo "Permissão HID atualizada"
    fi
fi

# Inicia o servidor
cd "$SCRIPT_DIR"
python3 mouse_hub.py --port "$PORT" > "$LOG" 2>&1 &
SERVER_PID=$!

# Espera o servidor iniciar
for i in {1..10}; do
    if ss -tlnp | grep -q ":${PORT}"; then
        break
    fi
    sleep 0.5
done

# Abre o navegador
sleep 1
xdg-open "http://localhost:${PORT}" 2>/dev/null &
