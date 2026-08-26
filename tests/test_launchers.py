"""Launchers — invariantes de segurança e lifecycle (issue #12).

Os testes não abrem UI real nem tocam hardware. O fake apenas representa
um processo Python vivo/morto; quem cria e valida o marcador é o próprio
launcher, exatamente como em produção.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LAUNCHERS = ["start.sh", "launcher.sh"]


def _exec_lines(path: Path):
    for raw in path.read_text().splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        yield stripped, stripped.split("#", 1)[0]


class LauncherSafetyTest(unittest.TestCase):
    def _forbidden_executed(self, patterns) -> str:
        findings = []
        for name in LAUNCHERS:
            for full, code in _exec_lines(REPO / name):
                unquoted = re.sub(r"(['\"])[^'\"]*\1", "", code)
                for pat in patterns:
                    if re.search(pat, unquoted):
                        findings.append(f"{name}: {full}")
        return "\n".join(findings)

    def test_no_pip_install_executed(self):
        self.assertEqual(
            self._forbidden_executed([r"pip\s+install", r"pip3\s+install"]), ""
        )

    def test_no_hid_permission_tampering(self):
        self.assertEqual(
            self._forbidden_executed([
                r"chmod\s+666\s*/dev/hidraw",
                r"sudo\s+-n\s+chmod",
                r"sudo\s+chmod",
            ]),
            "",
        )

    def test_no_sudo_usage(self):
        self.assertEqual(self._forbidden_executed([r"\bsudo\b"]), "")

    def test_launchers_point_to_native_app(self):
        for name in LAUNCHERS:
            src = (REPO / name).read_text()
            self.assertIn("mouse_hub_app.py", src)
            self.assertNotIn("python3 mouse_hub.py", src)
            self.assertNotIn("--port 7777", src)

    def test_no_fixed_hidraw_path(self):
        for name in LAUNCHERS:
            src = (REPO / name).read_text()
            self.assertNotIn("/dev/hidraw0", src)


_FAKE_APP = """
import os, sys, time
mode = os.environ.get('FAKE_MODE', 'alive')
if mode == 'dead_early':
    sys.exit(1)
time.sleep(60)
"""

_DISPLAY_COUNTER = [80]


def _make_launcher(fake_app_path: str, workdir: Path) -> Path:
    src = (REPO / "launcher.sh").read_text()
    src = src.replace(
        'APP_FILE="$SCRIPT_DIR/app/mouse_hub_app.py"',
        f'APP_FILE="{fake_app_path}"',
    )
    src = src.replace(
        '/tmp/mouse-hub-native-', f'{workdir}/mouse-hub-native-'
    )
    tmp = workdir / "launcher_test.sh"
    tmp.write_text(src)
    tmp.chmod(0o755)
    return tmp


def _run_launcher(path: Path, display: str, mode: str = "alive"):
    return subprocess.run(
        ["/bin/bash", str(path)],
        env={
            **os.environ,
            "DISPLAY": display,
            "FAKE_MODE": mode,
            "FAKE_APP_NAME": "fake_app.py",
        },
        capture_output=True,
        text=True,
        timeout=30,
    )


def _read_marker(path: Path):
    if not path.exists():
        return None, None
    try:
        lines = path.read_text().splitlines()
        return int(lines[0]), lines[1]
    except (ValueError, IndexError):
        return None, None


class LauncherLifecycleTest(unittest.TestCase):
    def setUp(self):
        import tempfile

        _DISPLAY_COUNTER[0] += 1
        self.display = f":{_DISPLAY_COUNTER[0]}"
        self.workdir = Path(tempfile.mkdtemp(prefix="mh_launcher_"))
        self.fake_app = self.workdir / "fake_app.py"
        self.fake_app.write_text(_FAKE_APP)
        self.marker = self.workdir / f"mouse-hub-native-{self.display}.pid"
        self.launcher = _make_launcher(str(self.fake_app), self.workdir)

    def tearDown(self):
        pid, _ = _read_marker(self.marker)
        if pid is not None:
            try:
                os.kill(pid, 9)
            except OSError:
                pass
        shutil.rmtree(self.workdir, ignore_errors=True)

    def _alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def test_process_starts_marker_represents_real_python_pid(self):
        res = _run_launcher(self.launcher, self.display)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("iniciado", res.stdout)

        pid, start = _read_marker(self.marker)
        self.assertIsNotNone(pid)
        self.assertTrue(self._alive(pid))
        self.assertTrue(start)

        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
        self.assertIn("fake_app.py", cmdline)
        current = Path(f"/proc/{pid}/stat").read_text().split()[21]
        self.assertEqual(start, current)

        again = _run_launcher(self.launcher, self.display)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("já está rodando", again.stdout)

    def test_immediate_death_never_becomes_success(self):
        res = _run_launcher(self.launcher, self.display, "dead_early")
        self.assertNotEqual(res.returncode, 0)
        self.assertNotIn("iniciado", res.stdout)
        self.assertIn("falhou", res.stderr + res.stdout)
        self.assertFalse(self.marker.exists())

    def test_stale_marker_is_replaced(self):
        self.marker.write_text("999999\n12345\n")
        res = _run_launcher(self.launcher, self.display)
        self.assertEqual(res.returncode, 0, res.stderr)
        pid, _ = _read_marker(self.marker)
        self.assertIsNotNone(pid)
        self.assertNotEqual(pid, 999999)
        self.assertTrue(self._alive(pid))


if __name__ == "__main__":
    unittest.main()
