#!/bin/bash
# ─── Mouse Hub Launcher ──────────────────────────────────
# Inicia o app NATIVO (PyQt5). O app web legado
# (mouse_hub.py, porta 7777) não é carregado neste fluxo — a
# descontinuação formal dele pertence à issue #10.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🖱️  Mouse Hub - Iniciando (app nativo)..."
echo ""

# Verifica Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 nao encontrado!"
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

# Verifica acesso ao hidraw (DPI via HID++, opcional)
HIDRAW="/dev/hidraw0"
if [ -e "$HIDRAW" ]; then
    if [ ! -w "$HIDRAW" ]; then
        echo "⚠️  Sem acesso de escrita a $HIDRAW"
        echo "    Para controle completo de DPI, rode:"
        echo "    sudo chmod 666 $HIDRAW"
        echo "    Ou crie regra udev permanente (veja README)"
        echo ""
        # Tenta com sudo se disponivel
        if sudo -n chmod 666 "$HIDRAW" 2>/dev/null; then
            echo "✅ Permissoes atualizadas automaticamente!"
        fi
    fi
fi

# Verifica DISPLAY (o app nativo precisa de um display X para a UI)
if [ -z "$DISPLAY" ]; then
    echo "❌ DISPLAY nao definido. Execute em um terminal grafico."
    exit 1
fi

echo "🚀 Abrindo a interface desktop..."
echo ""

cd "$SCRIPT_DIR"
exec python3 app/mouse_hub_app.py "$@"
