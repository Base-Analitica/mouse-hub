#!/bin/bash
# ─── Mouse Hub Launcher ──────────────────────────────────
# Launcher para o app NATIVO (PyQt5): abre a janela em segundo plano
# sem travar o terminal. Uma instância por display — se o app já
# estiver rodando no mesmo $DISPLAY, apenas avisa e sai. O app web
# legado (mouse_hub.py, porta 7777) não é carregado neste fluxo — a
# descontinuação formal dele pertence à issue #10.
#
# Este launcher NUNCA modifica o ambiente Python do usuário
# (sem pip install automático), NÃO gerencia permissões de
# dispositivo HID (responsabilidade do hardware layer do core —
# issue #3) e NÃO deixa watcher/daemon permanente — o cleanup do
# marcador de PID é feito pelo próprio processo do app (atexit no
# Python, com fallback de trap no bash intermediário).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="/tmp/mouse_hub_native.log"
APP_PY="app/mouse_hub_app.py"

# Verifica Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 nao encontrado!" >&2
    exit 1
fi

# Verifica dependencias Python do app nativo (leitura, sem instalar)
python3 -c "from PyQt5.QtWidgets import QApplication" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Dependencia faltando: PyQt5" >&2
    echo "   sudo apt install python3-pyqt5" >&2
    echo "   ou: python3 -m pip install --user PyQt5" >&2
    exit 1
fi

python3 -c "from Xlib import display" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Dependencia faltando: python3-xlib" >&2
    echo "   sudo apt install python3-xlib" >&2
    echo "   ou: python3 -m pip install --user python-xlib" >&2
    exit 1
fi

# Verifica DISPLAY (a UI precisa de um display X)
if [ -z "$DISPLAY" ]; then
    echo "❌ DISPLAY nao definido. Execute em um terminal grafico." >&2
    exit 1
fi

# Verifica o script do app antes de tentar subir o processo
case "$APP_PY" in
    /*) APP_FILE="$APP_PY" ;;           # caminho absoluto
    *)  APP_FILE="$SCRIPT_DIR/$APP_PY" ;;
esac
if [ ! -f "$APP_FILE" ]; then
    echo "❌ Script do app nao encontrado: $APP_FILE" >&2
    exit 1
fi

# ── Uma instância por display ─────────────────────────────
# O marcador é escrito pelo PRÓPRIO processo Python do app (PID
# real) logo após o QApplication ser criado; o formato é:
#   linha 1: PID do processo real
#   linha 2: boottime do PID em /proc/$PID/stat (campo 22)
# A validação exige 4 condições simultâneas — PID existe, cmdline
# pertence ao Mouse Hub, processo vivo (kill -0) E boottime
# idêntico ao registrado. O kernel pode reutilizar um PID, mas a
# chance de reutilizar o MESMO PID com o MESMO boottime e o MESMO
# cmdline é nula na prática: boottime é monotônico por PID.
RUN_MARKER="/tmp/mouse-hub-native-${DISPLAY:-:0}.pid"

_valid_marker() {
    # $1 = arquivo do marcador; imprime PID real se válido
    [ -f "$1" ] || return 1
    local mpid mbt
    mpid=$(sed -n '1p' "$1" | tr -d '[:space:]')
    mbt=$(sed -n '2p' "$1" | tr -d '[:space:]')
    [ -n "$mpid" ] || return 1
    # PID existe e está vivo
    kill -0 "$mpid" 2>/dev/null || return 1
    # cmdline pertence ao Mouse Hub (resolve o PID real, não wrapper).
    # FAKE_APP_NAME é usada SOMENTE pelos testes de lifecycle do
    # repo (fake app sem UI) — em produção a variável não existe e o
    # nome esperado é o do app real.
    local expected_name="${FAKE_APP_NAME:-mouse_hub_app.py}"
    local cmdline
    cmdline=$(cat "/proc/$mpid/cmdline" 2>/dev/null | tr '\0' ' ')
    echo "$cmdline" | grep -q "$expected_name" || return 1
    # boottime registrado bate com o atual — anti PID-reuse
    local curbt
    curbt=$(awk '{print $22}' "/proc/$mpid/stat" 2>/dev/null)
    [ -n "$curbt" ] && [ "$curbt" = "$mbt" ] || return 1
    echo "$mpid"
    return 0
}

if RUNNING_PID=$(_valid_marker "$RUN_MARKER"); then
    echo "🖱️  Mouse Hub já está rodando (PID $RUNNING_PID em $DISPLAY)"
    exit 0
fi

# Marcador existente sem validação = stale: remover antes de iniciar
rm -f "$RUN_MARKER"

# ── Inicia o app em segundo plano ─────────────────────────
# O marcador é escrito e removido pelo PRÓPRIO processo Python
# (via atexit), que registra seu PID real + boottime. O bash
# intermediário mantém uma trap de fallback para o caso raro de
# o Python ser morto sem rodar atexit (SIGKILL). Nenhum
# watcher, daemon ou loop de monitoramento fica rodando.
# NOTA: /bin/bash explícito — 'sh' resolve para dash no
# Mint/Ubuntu, e dash NÃO roda trap EXIT quando o processo morre
# por sinal (o marcador ficaria órfão sem o fallback). bash (o
# shebang deste script) roda o trap nesses cenários.
cd "$SCRIPT_DIR"
# O path do marcador é exportado para o processo do app — assim o
# Python sabe ONDE escrever o PID real + boottime (sem precisar
# recompor a regra de nome de arquivo dentro do app).
export MOUSE_HUB_RUN_MARKER="$RUN_MARKER"
nohup /bin/bash -c "trap 'rm -f \$MOUSE_HUB_RUN_MARKER' EXIT; python3 $APP_FILE; exit" \
    > "$LOG" 2>&1 &
APP_PID=$!

# ── Verificação de sobrevivência à inicialização ──────────
# O app escreve o marcador próprio (com PID real) logo após criar
# o QApplication — antes da UI abrir. O launcher espera o marcador
# do processo real aparecer (timeout curto, sem polling agressivo):
# - marcador real no ar       → sucesso confirmado com PID real
# - wrapper (bash) morreu     → falha na inicialização (não vira sucesso)
# - wrapper vivo mas sem marker → timeout: falha (não anuncia sucesso)
WON=0
DEAD=0
for _ in 1 2 3 4 5 6; do
    sleep 0.3
    if RUNNING_PID=$(_valid_marker "$RUN_MARKER"); then
        WON=1
        break
    fi
    if ! kill -0 "$APP_PID" 2>/dev/null; then
        DEAD=1
        break
    fi
done

if [ "$WON" -ne 1 ]; then
    rm -f "$RUN_MARKER"
    echo "❌ Mouse Hub falhou ao iniciar." >&2
    sed -n '1,15p' "$LOG" >&2
    exit 1
fi

echo "🖱️  Mouse Hub iniciado (PID $RUNNING_PID, log em $LOG)"
