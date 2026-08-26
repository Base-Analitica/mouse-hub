#!/bin/bash
# ─── Mouse Hub Native Launcher ────────────────────────────
# Inicia o app PyQt5 em segundo plano, sem servidor HTTP, sem instalar
# dependencias, sem sudo/chmod e sem assumir qualquer /dev/hidrawX.
# Uma instância por DISPLAY é controlada por PID + process start time.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_FILE="$SCRIPT_DIR/app/mouse_hub_app.py"
LOG="/tmp/mouse_hub_native.log"
RUN_MARKER="/tmp/mouse-hub-native-${DISPLAY:-:0}.pid"

if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Python3 nao encontrado!" >&2
    exit 1
fi

if ! python3 -c "from PyQt5.QtWidgets import QApplication" 2>/dev/null; then
    echo "❌ Dependencia faltando: PyQt5" >&2
    echo "   Instale uma unica vez pelo gerenciador de pacotes ou em ambiente virtual." >&2
    exit 1
fi

if ! python3 -c "from Xlib import display" 2>/dev/null; then
    echo "❌ Dependencia faltando: python-xlib" >&2
    echo "   Instale uma unica vez pelo gerenciador de pacotes ou em ambiente virtual." >&2
    exit 1
fi

if [ -z "$DISPLAY" ]; then
    echo "❌ DISPLAY nao definido. Execute em uma sessao X11." >&2
    exit 1
fi

if [ ! -f "$APP_FILE" ]; then
    echo "❌ Script do app nao encontrado: $APP_FILE" >&2
    exit 1
fi

_process_starttime() {
    awk '{print $22}' "/proc/$1/stat" 2>/dev/null
}

_valid_marker() {
    [ -f "$1" ] || return 1
    local mpid mstart current expected_name cmdline
    mpid=$(sed -n '1p' "$1" | tr -d '[:space:]')
    mstart=$(sed -n '2p' "$1" | tr -d '[:space:]')
    [ -n "$mpid" ] && [ -n "$mstart" ] || return 1
    kill -0 "$mpid" 2>/dev/null || return 1
    expected_name="${FAKE_APP_NAME:-mouse_hub_app.py}"
    cmdline=$(tr '\0' ' ' < "/proc/$mpid/cmdline" 2>/dev/null)
    echo "$cmdline" | grep -q "$expected_name" || return 1
    current=$(_process_starttime "$mpid")
    [ -n "$current" ] && [ "$current" = "$mstart" ] || return 1
    echo "$mpid"
}

if RUNNING_PID=$(_valid_marker "$RUN_MARKER"); then
    echo "🖱️  Mouse Hub já está rodando (PID $RUNNING_PID em $DISPLAY)"
    exit 0
fi
rm -f "$RUN_MARKER"

cd "$SCRIPT_DIR"
nohup python3 "$APP_FILE" >"$LOG" 2>&1 &
APP_PID=$!

# $! é o PID real do processo Python lançado diretamente. Registrar o
# starttime impede que um PID reutilizado seja aceito como a mesma instância.
STARTTIME=$(_process_starttime "$APP_PID")
if [ -n "$STARTTIME" ]; then
    printf '%s\n%s\n' "$APP_PID" "$STARTTIME" > "$RUN_MARKER"
fi

# Confirma sobrevivência à inicialização. O loop é curto (máx. 1,8 s),
# iniciado por ação explícita do usuário; não existe polling em idle.
STARTED=0
for _ in 1 2 3 4 5 6; do
    sleep 0.3
    if RUNNING_PID=$(_valid_marker "$RUN_MARKER"); then
        STARTED=1
        break
    fi
    if ! kill -0 "$APP_PID" 2>/dev/null; then
        break
    fi
done

if [ "$STARTED" -ne 1 ]; then
    rm -f "$RUN_MARKER"
    echo "❌ Mouse Hub falhou ao iniciar." >&2
    sed -n '1,15p' "$LOG" >&2
    exit 1
fi

echo "🖱️  Mouse Hub iniciado (PID $RUNNING_PID, log em $LOG)"
