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
# marcador de PID é feito na saída do próprio processo (trap).

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
# O marcador registra o PID esperado E o display que o registrou.
# Antes de considerar "já rodando", validamos que o PID ainda
# existe E é o nosso processo (cmdline contém o script do app) —
# PID reutilizado pelo kernel não passa nessa checagem.
RUN_MARKER="/tmp/mouse-hub-native-${DISPLAY:-:0}.pid"
if [ -f "$RUN_MARKER" ]; then
    OLD_PID=$(cat "$RUN_MARKER" 2>/dev/null)
    STALE=1
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        CMDLINE=$(cat "/proc/$OLD_PID/cmdline" 2>/dev/null | tr '\0' ' ')
        if echo "$CMDLINE" | grep -q "mouse_hub_app.py"; then
            STALE=0
        fi
    fi
    if [ "$STALE" -eq 1 ]; then
        rm -f "$RUN_MARKER"
    else
        echo "🖱️  Mouse Hub já está rodando (PID $OLD_PID em $DISPLAY)"
        exit 0
    fi
fi

# ── Inicia o app em segundo plano ─────────────────────────
# O cleanup do marcador é agendado por trap no PRÓPRIO processo
# do app — assim o marcador nunca fica órfão e não há watcher
# permanente. Se o processo morrer na inicialização, a função
# de trap ainda roda (EXIT) e o marcador é removido; mas,
# importante: o anúncio de sucesso só acontece APÓS a verificação
# de que o processo sobreviveu à inicialização.
cd "$SCRIPT_DIR"

# O marcador é limpo pelo processo do próprio app (trap EXIT do bash
# que executa o Python): nenhum watcher, daemon ou subshell do
# launcher fica aguardando o PID — o subshell de 'wait $PID' do design
# antigo nunca funcionou porque o PID não é filho daquele subshell.
# NOTA: invocar /bin/bash explicitamente — 'sh' resolve para dash no
# Mint/Ubuntu, e dash NÃO roda trap EXIT quando o processo morre por
# sinal (o marcador ficaria órfão). bash (shebang deste script) roda
# o trap corretamente nesses cenários.
# NOTA: o python3 NÃO usa 'exec' aqui — após o exec o shell morre e o
# trap EXIT nunca rodaria, deixando o marcador órfão; o bash espera o
# python3 naturalmente.
nohup /bin/bash -c "trap 'rm -f $RUN_MARKER' EXIT; python3 $APP_FILE; exit" \
    > "$LOG" 2>&1 &
APP_PID=$!
echo "$APP_PID" > "$RUN_MARKER"

# O PID registrado é do sh -c que executa o Python. Como o launcher
# não pode saber o instante exato em que o Python assumiu o trabalho
# sem watcher permanente (proibido por design), valida-se que o
# subprocesso sobreviveu à fase de spawn: se o Python morreu antes de
# iniciar (script faltando, ImportError, display ausente), o sh -c
# sai quase de imediato e as verificações abaixo detectam o caso mais
# comum de falha na inicialização — sem polling contínuo.
DEATHS=0
for _ in 1 2 3; do
    sleep 0.3
    if ! kill -0 "$APP_PID" 2>/dev/null; then
        DEATHS=1
        break
    fi
done

if [ "$DEATHS" -eq 1 ]; then
    rm -f "$RUN_MARKER"
    echo "❌ Mouse Hub falhou ao iniciar. Log:" >&2
    sed -n '1,15p' "$LOG" >&2
    exit 1
fi

echo "🖱️  Mouse Hub iniciado (PID $APP_PID, log em $LOG)"
