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

Não valida o comportamento de launch do app em si — o launcher abre
um processo real que depende de DISPLAY/X e foge do escopo de um
teste unitário de CI; o comportamento de lifecycle foi validado
manualmente (launch, instância única por DISPLAY, cleanup do
marcador de PID, falha rápida sem sucesso falso) e está documentado
em docs/performance/metodologia.md.

Executar: python3 -m unittest tests.test_launchers
"""
import os
import re
import unittest

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


if __name__ == "__main__":
    unittest.main()
