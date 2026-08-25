"""Cold startup real (Issue #12 — MAJOR 1).

**Process startup** (novo processo Python + imports + QApplication +
show + event loop). Mede o tempo desde o spawn de um processo Python
NOVO até a janela estar utilizável:

Este benchmark mede process startup controlado: o código e o bytecode
já estão em cache no runner na segunda execução. Ele NÃO representa
primeira instalação, filesystem frio nem boot completo do sistema —
essas condições só são afirmáveis medidas nelas.

1. processo Python novo (spawn);
2. imports do app (PyQt5, mouse_hub_app);
3. criação do QApplication;
4. criação e show da janela;
5. pelo menos uma passagem efetiva pelo event loop antes do
   marcador READY.

Método: o processo de benchmark abre um socket TCP em 127.0.0.1 e o
subprocesso envia o marcador READY SOMENTE depois de `show()` + uma
iteração do event loop (`QTimer.singleShot`). Socket TCP de loopback
em vez de datagrama Unix: `sendto()` para um socket de datagrama
`AF_UNIX` não-criado falha com `ENOENT` em kernels Linux (o path de
destino precisa existir como socket bindado), adicionando fragilidade
desnecessária. Precisão declarada: milissegundos de
`time.perf_counter` — o método NÃO garante precisão de microssegundos
e não deve ser tratado como tal.

Guardrail do CI: cold startup < 4.000 ms em ubuntu-latest (valor
observado: ~1.500–2.500 ms, incluindo instalação de dependências e
primeiro import do PyQt5, que é o pior caso de máquina fria).
Re-execução no head final desta PR (máquina do executor, Linux Mint
22.3, offscreen): 637–776 ms (3 execuções). Este é um guardrail de
CI, não uma medição no S145 — a validação física pertence à medição
futura descrita na metodologia.

Executar: QT_QPA_PLATFORM=offscreen python3 -m unittest tests.bench_cold_startup
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest

APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")
READY_TIMEOUT_S = 60

# O placeholder {SOCK_HOST}:{SOCK_PORT} é substituído pelo endereço
# do servidor; {REPO_APP_DIR} pelo diretório do app no repo.
TARGET_CODE = '''
import socket
import sys
import os

sys.path.insert(0, "{REPO_APP_DIR}")

# 1/2. imports do app (PyQt5 + mouse_hub_app) — cronômetro já corre no
# processo pai desde o spawn.
from PyQt5.QtWidgets import QApplication
import mouse_hub_app

qt = QApplication.instance() or QApplication(sys.argv)

# 3/4. criação e show da janela.
window = mouse_hub_app.MouseHubApp()
window.show()

# 5. marcador READY somente após pelo menos uma passagem efetiva pelo
# event loop.
from PyQt5.QtCore import QTimer
def _ready():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("{SOCK_HOST}", {SOCK_PORT}))
    sock.sendall(b"READY")
    sock.close()
QTimer.singleShot(0, _ready)

sys.exit(qt.exec_())
'''


def _cold_startup_ms() -> float:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    host, port = srv.getsockname()
    srv.listen(1)
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w",
                                     delete=False) as f:
        f.write(TARGET_CODE.replace("{SOCK_HOST}", host)
                        .replace("{SOCK_PORT}", str(port))
                        .replace("{REPO_APP_DIR}", os.path.abspath(APP_DIR)))
        script = f.name
    try:
        env = dict(os.environ)
        env["QT_QPA_PLATFORM"] = env.get("QT_QPA_PLATFORM", "offscreen")
        t0 = time.perf_counter()
        proc = subprocess.Popen([sys.executable, script],
                                env=env,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        # aguardar marcador READY no socket
        srv.settimeout(READY_TIMEOUT_S)
        try:
            conn, _ = srv.accept()
            data = conn.recv(16)
            conn.close()
        except socket.timeout:
            proc.kill()
            raise AssertionError(
                f"subprocesso não emitiu READY em {READY_TIMEOUT_S} s "
                f"(deadlines de cold startup devem reprovar)")
        finally:
            srv.close()
        if data != b"READY":
            proc.kill()
            raise AssertionError(
                f"marcador inesperado: {data!r}")
        elapsed_ms = (time.perf_counter() - t0) * 1000
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        return elapsed_ms
    finally:
        os.unlink(script)


class ColdStartupTest(unittest.TestCase):
    def test_cold_startup(self) -> None:
        ms = _cold_startup_ms()
        results = {"cold_startup_ms": round(ms, 1)}
        with open("/tmp/cold_startup_results.json", "w") as f:
            import json
            json.dump(results, f, indent=2)
        print("COLD_STARTUP:", results)
        # guardrail de CI: processo novo + imports + QApplication +
        # show + 1ª passagem do event loop abaixo de 4 s. O número
        # observado no CI (commit aa58b88) foi ~1.500–2.500 ms; a
        # folga cobre máquina fria e primeiro import do PyQt5.
        self.assertLess(ms, 4000,
                        f"cold startup de {ms:.0f} ms excedeu o "
                        f"guardrail de 4.000 ms")


if __name__ == "__main__":
    unittest.main()
