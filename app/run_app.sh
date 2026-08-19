#!/bin/bash
# ─── Mouse Hub Native App Launcher ─────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Verifica PyQt5
python3 -c "from PyQt5.QtWidgets import QApplication" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ PyQt5 não encontrado. Instalando..."
    python3 -m pip install --user --break-system-packages PyQt5 PyQt5-sip PyQt5-Qt5 2>/dev/null
fi

# Inicia o app
cd "$SCRIPT_DIR"
python3 mouse_hub_app.py &
