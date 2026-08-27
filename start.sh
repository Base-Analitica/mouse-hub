#!/bin/bash
# ─── Mouse Hub Launcher ──────────────────────────────────
# Inicia o app NATIVO (PyQt5). O app web legado
# (mouse_hub.py, porta 7777) não é carregado neste fluxo — a
# descontinuação formal dele pertence à issue #10.
#
# Este launcher NUNCA modifica o ambiente Python do usuário
# (sem pip install automático) e NÃO gerencia permissões de
# dispositivo HID — a descoberta e o acesso ao mouse correto
# pertencem ao hardware layer do core (issue #3).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🖱️  Mouse Hub - Iniciando (app nativo)..."
echo ""

# Verifica Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 nao encontrado!" >&2
    exit 1
fi

# Verifica dependencias Python do app nativo (leitura, sem instalar)
MISSING=0

python3 -c "from PyQt5.QtWidgets import QApplication" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Dependencia faltando: PyQt5" >&2
    echo "   Instale com (uma unica vez):" >&2
    echo "   sudo apt install python3-pyqt5" >&2
    echo "   Ou: python3 -m pip install --user PyQt5" >&2
    MISSING=1
fi

python3 -c "from Xlib import display" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Dependencia faltando: python3-xlib" >&2
    echo "   Instale com (uma unica vez):" >&2
    echo "   sudo apt install python3-xlib" >&2
    echo "   Ou: python3 -m pip install --user python-xlib" >&2
    MISSING=1
fi

if [ "$MISSING" -ne 0 ]; then
    exit 1
fi

# Verifica DISPLAY (o app nativo precisa de um display X para a UI)
if [ -z "$DISPLAY" ]; then
    echo "❌ DISPLAY nao definido. Execute em um terminal grafico." >&2
    if [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
        echo "   Sessao Wayland detectada: o app requer XWayland." >&2
    fi
    exit 1
fi

echo "🚀 Abrindo a interface desktop..."
echo ""

cd "$SCRIPT_DIR"
exec python3 app/mouse_hub_app.py "$@"
