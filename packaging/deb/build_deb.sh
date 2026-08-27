#!/bin/bash
# ─── Mouse Hub — empacotamento .deb (issue #64) ────────────────
# Build determinístico: monta a árvore de staging e empacota com
# dpkg-deb. NÃO instala nada no sistema, NÃO usa sudo, NÃO roda apt.
#
# Uso:
#   packaging/deb/build_deb.sh                 # gera dist/mouse-hub_<versão>_all.deb
#   packaging/deb/build_deb.sh --stage DIR     # só monta a árvore (testes)
#   MOUSE_HUB_VERSION=1.2.3 packaging/deb/build_deb.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

STAGE_MODE=""
STAGE_DIR=""
if [ "${1:-}" = "--stage" ]; then
    STAGE_MODE="1"
    STAGE_DIR="${2:?--stage requer um diretório}"
fi

VERSION="${MOUSE_HUB_VERSION:-$(cd "$ROOT" && (git describe --tags 2>/dev/null || echo "0.1.0") | sed 's/^v//')}"

if [ -n "$STAGE_MODE" ]; then
    STAGE="$STAGE_DIR"
else
    STAGE="$(mktemp -d /tmp/mouse-hub-deb.XXXXXX)"
fi

OPT="$STAGE/opt/mouse-hub"
BIN="$STAGE/usr/bin"
APPS="$STAGE/usr/share/applications"
ICONS="$STAGE/usr/share/icons/hicolor/scalable/apps"
UDEV="$STAGE/etc/udev/rules.d"

mkdir -p "$OPT" "$BIN" "$APPS" "$ICONS" "$UDEV" "$STAGE/DEBIAN"

# ── Aplicativo em /opt (mesma árvore do install.sh, sem ruído) ──
cp -a "$ROOT/app" "$ROOT/mouse_hub" "$ROOT/assets" "$OPT/"
cp -a "$ROOT/start.sh" "$ROOT/launcher.sh" "$OPT/"
for f in pyproject.toml README.md; do
    [ -f "$ROOT/$f" ] && cp -a "$ROOT/$f" "$OPT/"
done
rm -rf "$OPT/__pycache__" "$OPT/app/__pycache__" "$OPT/mouse_hub/__pycache__" \
       $(find "$OPT" -type d -name __pycache__ 2>/dev/null) 2>/dev/null || true
chmod +x "$OPT/app/run_app.sh" "$OPT/start.sh" "$OPT/launcher.sh"

# ── Wrapper em /usr/bin ──────────────────────────────────────────
cat > "$BIN/mouse-hub" <<'WRAPPER'
#!/bin/bash
# Mouse Hub — entrypoint do pacote .deb
exec /bin/bash /opt/mouse-hub/launcher.sh
WRAPPER
chmod 755 "$BIN/mouse-hub"

# ── Atalho no menu (aponta para o wrapper) ──────────────────────
sed 's|^Exec=.*|Exec=/usr/bin/mouse-hub|' "$ROOT/mouse-hub.desktop" \
    > "$APPS/mouse-hub.desktop"
chmod 644 "$APPS/mouse-hub.desktop"

# ── Ícone hicolor ────────────────────────────────────────────────
cp "$ROOT/assets/icons/mouse-hub.svg" "$ICONS/mouse-hub.svg"
chmod 644 "$ICONS/mouse-hub.svg"

# ── Regra udev (conffile — dpkg preserva em upgrade) ─────────────
cp "$ROOT/docs/udev/99-logitech-g403-hidraw.rules" \
   "$UDEV/99-logitech-g403-hidraw.rules"
chmod 644 "$UDEV/99-logitech-g403-hidraw.rules"

# ── Permissões: diretórios precisam ser travessáveis (mktemp -d
# cria com 0700 — sem isto, o app ficaria inacessível após instalar).
find "$STAGE" -type d -exec chmod 755 {} +

# ── Metadados do pacote ──────────────────────────────────────────
sed "s/__VERSION__/$VERSION/" "$SCRIPT_DIR/control" > "$STAGE/DEBIAN/control"
chmod 644 "$STAGE/DEBIAN/control"
for s in postinst prerm postrm; do
    cp "$SCRIPT_DIR/$s" "$STAGE/DEBIAN/$s"
    chmod 755 "$STAGE/DEBIAN/$s"
done

if [ -n "$STAGE_MODE" ]; then
    echo "$STAGE"
    exit 0
fi

mkdir -p "$ROOT/dist"
OUT="$ROOT/dist/mouse-hub_${VERSION}_all.deb"
dpkg-deb --root-owner-group --build "$STAGE" "$OUT"
rm -rf "$STAGE"
echo "Pacote gerado: $OUT"
