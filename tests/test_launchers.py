"""Launchers (start.sh / launcher.sh) — invariantes de segurança
(Issue #12).

O launcher NUNCA deve modificar o ambiente Python do usuário nem o
sistema de arquivos sensível. Este teste codifica os invariantes
aceitos na revisão do mantenedor:

* nenhuma invocação de `pip install` (instalação é única, manual,
  instruções impressas só quando falta dependência);
* nenhuma manipulação de permissões de `/dev/hidraw*` ou chamadas a
  `chmod 666` (responsabilidade do hardware layer do core — issue #3);
* nenhuma chamada a `sudo` (sem privilégio escalado a partir de um
  launcher de usuário comum).

Os testes de lifecycle abaixo são determinísticos e usam um FAKE do
app (subprocesso controlado) em um DISPLAY exclusivo por teste —
nenhuma UI real é aberta, nenhum sleep longo ou polling agressivo.

Executar: python3 -m unittest tests.test_launchers
"""
import os
import re
import shutil
import subprocess
import time
import unittest
from pathlib import Path

REPO = os.path.join(os.path.dirname(__file__), "..")
LAUNCHERS = ["start.sh", "launcher.sh"]

# expressões de comando EXECUTADO no shell — excluímos linhas de
# comentário e blocos de mensagem de erro (echo "..." pip install)
EXEC_LINE = re.compile(
    r"^\s*(?!#)\s*"           # linha não-comentada (com tolerância)
    r"(?!\s*#\s).*"           # não começa com '#' (após espaços)
)


def _exec_lines(path: str):
    with open(path) as f:
        for raw in f:
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # trechos após '#' na linha (comentário inline)
            code = stripped.split("#")[0]
            yield stripped, code


class LauncherSafetyTest(unittest.TestCase):
    def _forbidden_executed(self, patterns) -> str:
        findings = []
        for name in LAUNCHERS:
            path = os.path.join(REPO, name)
            for full, code in _exec_lines(path):
                # remover partes dentro de aspas duplas/simples:
                # comandos proibidos dentro de echo '...' são
                # instruções impressas ao usuário, não execução
                unquoted = re.sub(r"(['\"])[^'\"]*\1", "", code)
                for pat in patterns:
                    if re.search(pat, unquoted):
                        findings.append(f"{name}: {full}")
        return "\n".join(findings)

    def test_no_pip_install_executed(self) -> None:
        # pip install pode aparecer como INSTRUÇÃO em mensagens de
        # erro (echo '...python3 -m pip install...') — isso é aceito.
        # O que é proibido é a EXECUÇÃO: python3 -m pip install ou
        # pip install no caminho do código.
        bad = self._forbidden_executed([
            r"pip\s+install",
            r"pip3\s+install",
        ])
        self.assertEqual(bad, "",
                         f"pip install executado no launcher:\n{bad}")

    def test_no_hid_permission_tampering(self) -> None:
        bad = self._forbidden_executed([
            r"chmod\s+666\s*/dev/hidraw",
            r"sudo\s+-n\s+chmod",
            r"sudo\s+chmod",
        ])
        self.assertEqual(bad, "",
                         f"manipulação de permissões HID no launcher:\n{bad}")

    def test_no_sudo_usage(self) -> None:
        bad = self._forbidden_executed([r"\bsudo\b"])
        self.assertEqual(bad, "",
                         f"sudo usado no launcher:\n{bad}")

    def test_launchers_point_to_native_app(self) -> None:
        """Os launchers abrem o app nativo (mouse_hub_app.py), não o
        app web legado (mouse_hub.py)."""
        for name in LAUNCHERS:
            path = os.path.join(REPO, name)
            with open(path) as f:
                src = f.read()
            self.assertIn("mouse_hub_app.py", src,
                          f"{name} não referencia o app nativo")
            # legado: nenhuma invocação de mouse_hub.py como comando
            self.assertNotIn(
                "python3 mouse_hub.py", src,
                f"{name} ainda lança o app web legado")
            self.assertNotIn(
                "--port 7777", src,
                f"{name} ainda referencia a porta do app legado")


# ─────────────────────────────────────────────────────────────
# Lifecycle do launcher.sh — casos determinísticos com FAKE app.
# Cada teste usa um DISPLAY exclusivo e um marcador em diretório
# temporário próprio, então nenhum par de testes interage.
# ─────────────────────────────────────────────────────────────

# FAKE APP: escreve o marker no MESMO formato do app real
# (PID real + boottime) para provar o protocolo; a lógica de
# validação testada é a do launcher.sh.
_FAKE_APP = """
import os, sys, atexit, time

def _cleanup():
    marker = os.environ.get("MOUSE_HUB_RUN_MARKER", "")
    if marker:
        try:
            os.unlink(marker)
        except OSError:
            pass

def main():
    mode = os.environ.get("FAKE_MODE", "alive")
    if mode == "dead_early":
        # morre SEM escrever marker — simula ImportError, DISPLAY
        # inválido etc. (caso de falha-na-inicialização)
        sys.exit(1)
    # escrever marker no formato do app real
    marker = os.environ.get("MOUSE_HUB_RUN_MARKER", "")
    if not marker:
        sys.exit(2)
    _stat = open("/proc/self/stat", "rb").read().decode("ascii")
    _last = _stat.rfind(")")
    _bt = _stat[_last + 2:].split()[19]
    with open(marker, "w") as fh:
        fh.write(f"{os.getpid()}\\n{_bt}\\n")
    os.environ["MOUSE_HUB_RUN_MARKER"] = marker
    atexit.register(_cleanup)
    if mode == "alive":
        time.sleep(60)

if __name__ == "__main__":
    main()
"""

_DISPLAY_COUNTER = [70]


def _make_launcher(fake_app_path: str, marker_dir: str) -> str:
    """Copia launcher.sh reparametrizado (APP_PY e RUN_MARKER) para
    um diretório temporário e retorna o caminho do script."""
    src = os.path.join(REPO, "launcher.sh")
    tmp = Path(marker_dir) / "launcher_test.sh"
    tmp.write_text(Path(src).read_text()
                   .replace('APP_PY="app/mouse_hub_app.py"',
                            f'APP_PY="{fake_app_path}"')
                   .replace('/tmp/mouse-hub-native-',
                            f'{marker_dir}/mouse-hub-native-'))
    tmp.chmod(0o755)
    return str(tmp)


def _run_launcher(launcher_path: str, display: str):
    return subprocess.run(
        ["/bin/bash", launcher_path],
        env={**os.environ, "DISPLAY": display,
             "FAKE_APP_NAME": "fake_app.py"},
        capture_output=True, text=True, timeout=30,
    )


def _marker(pid_file: str):
    if not os.path.exists(pid_file):
        return None, None
    try:
        lines = Path(pid_file).read_text().splitlines()
        return int(lines[0]), lines[1] if len(lines) > 1 else None
    except (ValueError, IndexError):
        return None, None


class LauncherLifecycleTest(unittest.TestCase):
    """Casos determinísticos do lifecycle do launcher.sh com fake app.

    O fake app reproduz o protocolo do app real (marker com PID real
    + boottime) — os testes provam o comportamento do launcher, não
    a UI (que depende de DISPLAY/X completo).
    """

    def setUp(self):
        _DISPLAY_COUNTER[0] += 1
        self.display = f":{_DISPLAY_COUNTER[0]}"
        self.workdir = Path(__import__("tempfile").mkdtemp(
            prefix="mh_launcher_"))
        self.fake_app = str(self.workdir / "fake_app.py")
        Path(self.fake_app).write_text(_FAKE_APP)
        self.marker_file = str(self.workdir / "mouse-hub-native-"
                               f"{self.display}.pid")
        self.launcher = _make_launcher(self.fake_app, str(self.workdir))
        if os.path.exists(self.marker_file):
            os.unlink(self.marker_file)

    def tearDown(self):
        # encerrar qualquer fake app remanescente deste teste
        pid, _ = _marker(self.marker_file)
        if pid is not None:
            try:
                os.kill(pid, 9)
            except OSError:
                pass
        shutil.rmtree(self.workdir, ignore_errors=True)

    def _wait_alive(self, pid: int, timeout_s: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                time.sleep(0.05)
        return False

    # Caso 1 — processo inicia: marker criado, PID válido,
    # processo reconhecido como do Mouse Hub
    def test_case1_process_starts(self):
        res = _run_launcher(self.launcher, self.display)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("iniciado", res.stdout)

        pid, bt = _marker(self.marker_file)
        self.assertIsNotNone(pid, "marker nao criado")
        self.assertIsNotNone(bt, "boottime ausente no marker")

        # PID existe, é o python do fake app e está vivo
        self.assertTrue(self._wait_alive(pid),
                        "processo do marker morreu")
        with open(f"/proc/{pid}/cmdline", "rb") as _cl:
            cmdline = _cl.read().decode("ascii", "replace")\
                .replace("\x00", " ")
        self.assertIn("fake_app.py", cmdline,
                      "processo nao e o app registrado")

        # boottime registrado == atual — anti PID-reuse
        with open(f"/proc/{pid}/stat", "rb") as _st:
            stat = _st.read().decode("ascii")
        curbt = stat[stat.rfind(")") + 2:].split()[19]
        self.assertEqual(bt, curbt,
                         "boottime diverge — marker nao representa "
                         "o processo real")

        # segunda execução não inicia nova instância
        res2 = _run_launcher(self.launcher, self.display)
        self.assertEqual(res2.returncode, 0, res2.stderr)
        self.assertIn("já está rodando", res2.stdout)

    # Caso 2 — processo morre imediatamente: launcher detecta
    # falha, NÃO anuncia sucesso, marker removido
    def test_case2_immediate_death(self):
        res = subprocess.run(
            ["/bin/bash", self.launcher],
            env={**os.environ, "DISPLAY": self.display,
                 "FAKE_MODE": "dead_early",
                 "FAKE_APP_NAME": "fake_app.py"},
            capture_output=True, text=True, timeout=30,
        )
        self.assertNotEqual(res.returncode, 0,
                            "falha virou sucesso")
        self.assertIn("falhou", res.stderr + res.stdout)
        # nada anunciou início
        self.assertNotIn("iniciado", res.stdout)
        self.assertFalse(os.path.exists(self.marker_file),
                         "marker ficou apos falha")

    # Caso 3 — marker antigo: PID inexistente é removido e nova
    # execução inicia normalmente
    def test_case3_stale_marker(self):
        # simular PID morto (kernel não reutiliza PIDs tão altos)
        Path(self.marker_file).write_text("999999\n12345\n")
        res = _run_launcher(self.launcher, self.display)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("iniciado", res.stdout)

        pid, _ = _marker(self.marker_file)
        self.assertIsNotNone(pid)
        self.assertNotEqual(pid, 999999,
                            "launcher reusou marker stale")
        self.assertTrue(self._wait_alive(pid),
                        "nova instancia nao subiu")


if __name__ == "__main__":
    unittest.main()
