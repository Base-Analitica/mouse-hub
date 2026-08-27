#!/bin/bash
# ─── Mouse Hub Native App Launcher ─────────────────────
# Verifica dependências e inicia o app. NUNCA instala nada
# automaticamente (sem pip --break-system-packages) — a
# instalação de dependências é responsabilidade do usuário
# ou do install.sh (issue #8).
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Verifica PyQt5
if ! python3 -c "from PyQt5.QtWidgets import QApplication" 2>/dev/null; then
    echo "❌ PyQt5 não encontrado." >&2
    echo "   Instale uma única vez:" >&2
    echo "     sudo apt install python3-pyqt5" >&2
    echo "   Ou use um ambiente virtual (ver README)." >&2
    exit 1
fi

# Verifica python-xlib
if ! python3 -c "from Xlib import display" 2>/dev/null; then
    echo "❌ python-xlib não encontrado." >&2
    echo "   Instale uma única vez:" >&2
    echo "     sudo apt install python3-xlib" >&2
    echo "   Ou use um ambiente virtual (ver README)." >&2
    exit 1
fi

# Verifica display (o app nativo precisa de X11/XWayland)
if [ -z "$DISPLAY" ]; then
    echo "❌ DISPLAY não definido." >&2
    if [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
        echo "   Sessão Wayland detectada: o app requer XWayland." >&2
        echo "   Verifique se o pacote xwayland está instalado." >&2
    fi
    exit 1
fi

cd "$SCRIPT_DIR"
exec python3 app/mouse_hub_app.py "$@"
