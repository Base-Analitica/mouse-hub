#!/bin/bash
# ─── Mouse Hub Launcher ────────────────────────────────
# Inicia o Mouse Hub com as configuracoes necessarias

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🖱️  Mouse Hub - Iniciando..."
echo ""

# Verifica Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 nao encontrado!"
    exit 1
fi

# Verifica dependencias Python
python3 -c "from Xlib import display" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  python3-xlib nao encontrado. Instalando..."
    python3 -m pip install --user --break-system-packages python-xlib 2>/dev/null
fi

# Verifica acesso ao hidraw
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

# Verifica xdotool
if ! command -v xdotool &> /dev/null; then
    echo "❌ xdotool nao encontrado. Instale com: sudo apt install xdotool"
    exit 1
fi

# Verifica DISPLAY
if [ -z "$DISPLAY" ]; then
    echo "❌ DISPLAY nao definido. Execute em um terminal grafico."
    exit 1
fi

# Inicia o servidor
echo "🚀 Iniciando servidor na porta 7777..."
echo "   Abra: http://localhost:7777"
echo ""

cd "$SCRIPT_DIR"
python3 mouse_hub.py --port 7777 "$@"
