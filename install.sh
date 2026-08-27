#!/bin/bash
# ─── Mouse Hub — Instalador para Linux Mint ─────────────
# Instala o Mouse Hub como aplicativo nativo no sistema.
#
# O que este script faz:
#   1. Verifica pré-requisitos (Python, PyQt5, python-xlib, xdotool, xinput)
#   2. Instala a regra udev para o G403 (requer sudo)
#   3. Copia o app para /opt/mouse-hub (requer sudo)
#   4. Instala o .desktop e o ícone no menu de aplicativos
#   5. Informa ao usuário como executar e como desinstalar
#
# O que este script NÃO faz:
#   - Não executa pip install --break-system-packages
#   - Não altera permissões com chmod 666
#   - Não assume /dev/hidraw0
#   - Não inicia servidor HTTP
#   - Não depende de rsync (usa cp -a + remoção de diretórios excluídos)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="/opt/mouse-hub"
DESKTOP_FILE="mouse-hub.desktop"
ICON_FILE="assets/icons/mouse-hub.svg"
UDEV_RULE="docs/udev/99-logitech-g403-hidraw.rules"

echo "🖱️  Mouse Hub — Instalador para Linux Mint"
echo "==========================================="
echo ""

# ── Verificar pré-requisitos ─────────────────────────────
echo "Verificando pré-requisitos..."

MISSING=""
python3 -c "from PyQt5.QtWidgets import QApplication" 2>/dev/null || MISSING="$MISSING python3-pyqt5"
python3 -c "from Xlib import display" 2>/dev/null || MISSING="$MISSING python3-xlib"
command -v xinput &>/dev/null || MISSING="$MISSING xinput"
command -v xdotool &>/dev/null || MISSING="$MISSING xdotool"

if [ -n "$MISSING" ]; then
    echo ""
    echo "❌ Dependências ausentes:$MISSING"
    echo ""
    echo "Instale com:"
    echo "  sudo apt install python3-pyqt5 python3-xlib xinput xdotool"
    echo ""
    read -p "Deseja instalar automaticamente? (s/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        sudo apt install -y python3-pyqt5 python3-xlib xinput xdotool
    else
        echo "Instale manualmente e execute novamente."
        exit 1
    fi
fi

echo "✅ Pré-requisitos verificados."
echo ""

# ── Instalar regra udev ──────────────────────────────────
echo "Instalando regra udev para o G403 HERO..."
if [ -f "$SCRIPT_DIR/$UDEV_RULE" ]; then
    sudo cp "$SCRIPT_DIR/$UDEV_RULE" /etc/udev/rules.d/
    sudo udevadm control --reload-rules
    sudo udevadm trigger --action=add --subsystem-match=hidraw 2>/dev/null || true
    echo "✅ Regra udev instalada."
else
    echo "⚠️  Regra udev não encontrada em $UDEV_RULE"
    echo "   O DPI físico pode não estar disponível sem permissão."
fi
echo ""

# ── Copiar app para /opt ─────────────────────────────────
echo "Instalando o Mouse Hub em $INSTALL_DIR..."
if [ -d "$INSTALL_DIR" ]; then
    echo "   Diretório anterior encontrado, atualizando..."
    sudo rm -rf "$INSTALL_DIR"
fi
sudo mkdir -p "$INSTALL_DIR"
# Copia apenas os arquivos necessários (sem .git, sem __pycache__,
# sem tests, sem .venv, sem docs de desenvolvimento). cp -a preserva
# links simbólicos e permissões; os diretórios indesejados são
# removidos em seguida.
sudo cp -a "$SCRIPT_DIR/." "$INSTALL_DIR/"
sudo rm -rf "$INSTALL_DIR/.git" "$INSTALL_DIR/__pycache__" \
    "$INSTALL_DIR/.venv" "$INSTALL_DIR/tests" \
    "$INSTALL_DIR/.pytest_cache" "$INSTALL_DIR/pytest_baseline.txt" \
    "$INSTALL_DIR/docs"
sudo chmod +x "$INSTALL_DIR/app/run_app.sh" \
    "$INSTALL_DIR/start.sh" "$INSTALL_DIR/launcher.sh"
echo "✅ App instalado em $INSTALL_DIR."
echo ""

# ── Instalar .desktop ────────────────────────────────────
echo "Instalando atalho no menu de aplicativos..."
if [ -f "$SCRIPT_DIR/$DESKTOP_FILE" ]; then
    # Atualiza o caminho do Exec com o INSTALL_DIR real
    sudo cp "$SCRIPT_DIR/$DESKTOP_FILE" /usr/share/applications/mouse-hub.desktop
    sudo sed -i "s|/opt/mouse-hub|$INSTALL_DIR|g" /usr/share/applications/mouse-hub.desktop
    echo "✅ Atalho instalado no menu de aplicativos."
else
    echo "⚠️  Arquivo .desktop não encontrado."
fi
echo ""

# ── Instalar ícone ───────────────────────────────────────
echo "Instalando ícone no tema hicolor..."
if [ -f "$SCRIPT_DIR/$ICON_FILE" ]; then
    sudo mkdir -p /usr/share/icons/hicolor/scalable/apps
    sudo cp "$SCRIPT_DIR/$ICON_FILE" /usr/share/icons/hicolor/scalable/apps/mouse-hub.svg
    sudo gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null \
        || echo "   (cache de ícones será atualizado no próximo login)"
    echo "✅ Ícone instalado."
else
    echo "⚠️  Ícone não encontrado em $ICON_FILE"
fi
echo ""

# ── Adicionar usuário ao grupo plugdev ────────────────────
if ! groups "$USER" | grep -q plugdev; then
    echo "Adicionando $USER ao grupo plugdev (para acesso HID)..."
    sudo usermod -aG plugdev "$USER"
    echo "⚠️  Você precisa relogar para que a mudança tenha efeito."
    echo ""
fi

# ── Resumo ───────────────────────────────────────────────
echo "==========================================="
echo "✅ Instalação concluída!"
echo ""
echo "Para executar:"
echo "  Opção 1: Menu de aplicativos → Mouse Hub"
echo "  Opção 2: $INSTALL_DIR/launcher.sh"
echo ""
echo "Pré-requisitos para acesso HID++ (DPI físico):"
echo "  - Usuário no grupo plugdev (configurado automaticamente)"
echo "  - Regra udev instalada (configurada automaticamente)"
echo "  - Reconecte o mouse OU execute:"
echo "    sudo udevadm trigger --action=add --subsystem-match=hidraw"
echo ""
echo "Limitações conhecidas:"
echo "  - Polling rate: não alterável pelo stack HID++ atual"
echo "  - Requer X11 (XWayland pode funcionar parcialmente)"
if [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
    echo "  - ⚠️  Sessão atual é Wayland: execute via XWayland"
    echo "    (o app detecta e informa se algum recurso não funcionar)"
fi
echo ""
echo "Para desinstalar: $SCRIPT_DIR/uninstall.sh"
echo "==========================================="
