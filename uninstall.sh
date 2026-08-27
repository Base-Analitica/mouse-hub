#!/bin/bash
# ─── Mouse Hub — Desinstalador para Linux Mint ───────────
# Remove a instalação nativa feita por install.sh:
#   - /opt/mouse-hub
#   - atalho .desktop do menu
#   - ícone do tema hicolor
#   - regra udev do G403
#
# NÃO remove dados do usuário (XDG):
#   - ~/.config/mouse-hub/  (config.json)
#   - ~/.local/share/mouse-hub/  (macros.json)
#   Remova manualmente se desejar.
set -euo pipefail

INSTALL_DIR="/opt/mouse-hub"
UDEV_RULE="/etc/udev/rules.d/99-logitech-g403-hidraw.rules"

echo "🖱️  Mouse Hub — Desinstalador"
echo "============================="
echo ""

# ── Encerrar instância em execução (se houver) ───────────
for MARKER in /tmp/mouse-hub-native-*.pid; do
    [ -f "$MARKER" ] || continue
    MPID=$(sed -n '1p' "$MARKER" | tr -d '[:space:]')
    if [ -n "$MPID" ] && kill -0 "$MPID" 2>/dev/null; then
        echo "Encerrando Mouse Hub em execução (PID $MPID)..."
        kill "$MPID" 2>/dev/null || true
    fi
    rm -f "$MARKER"
done
echo ""

# ── Remover diretórios e arquivos do sistema ─────────────
if [ -d "$INSTALL_DIR" ]; then
    sudo rm -rf "$INSTALL_DIR"
    echo "✅ Removido: $INSTALL_DIR"
else
    echo "ℹ️  Não encontrado: $INSTALL_DIR"
fi

if [ -f /usr/share/applications/mouse-hub.desktop ]; then
    sudo rm -f /usr/share/applications/mouse-hub.desktop
    echo "✅ Removido: atalho do menu de aplicativos"
else
    echo "ℹ️  Atalho do menu não encontrado"
fi

if [ -f /usr/share/icons/hicolor/scalable/apps/mouse-hub.svg ]; then
    sudo rm -f /usr/share/icons/hicolor/scalable/apps/mouse-hub.svg
    sudo gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
    echo "✅ Removido: ícone"
else
    echo "ℹ️  Ícone não encontrado"
fi

if [ -f "$UDEV_RULE" ]; then
    sudo rm -f "$UDEV_RULE"
    sudo udevadm control --reload-rules
    echo "✅ Removida: regra udev do G403"
else
    echo "ℹ️  Regra udev não encontrada"
fi

echo ""
echo "✅ Mouse Hub desinstalado."
echo ""
echo "Dados do usuário preservados (remova manualmente se desejar):"
echo "  ~/.config/mouse-hub/"
echo "  ~/.local/share/mouse-hub/"
