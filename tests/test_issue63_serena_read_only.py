"""Issue #63: a configuração Serena deve ser somente leitura.

Os testes não dependem do pacote opcional da Serena. Eles validam o contrato
versionado da configuração e da ponte semântica; o handshake real é um gate
separado quando o binário local estiver instalado.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERENA_CONFIG = ROOT / ".serena" / "project.yml"
BRIDGE = ROOT / "scripts" / "agent" / "semantic-code.py"
LAUNCHER = ROOT / "scripts" / "agent" / "semantic-code"
EXPECTED_COMMANDS = {"tools", "overview", "find", "refs", "diagnostics"}


def _parser_subcommands() -> set[str]:
    tree = ast.parse(BRIDGE.read_text(encoding="utf-8"))
    parser_functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "parser"
    ]
    assert len(parser_functions) == 1

    commands = set()
    for node in ast.walk(parser_functions[0]):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Attribute) and node.func.attr == "add_parser"):
            continue
        if node.args and isinstance(node.args[0], ast.Constant):
            commands.add(node.args[0].value)
    return commands


def test_serena_project_is_configured_as_boolean_read_only():
    text = SERENA_CONFIG.read_text(encoding="utf-8")
    values = re.findall(r"(?m)^\s*read_only:\s*([^#\s]+)\s*$", text)

    assert values == ["true"]


def test_semantic_bridge_keeps_all_read_only_query_commands():
    assert EXPECTED_COMMANDS <= _parser_subcommands()
    assert not EXPECTED_COMMANDS.intersection({"edit", "write", "replace", "delete"})


def test_semantic_bridge_launcher_still_targets_local_bridge():
    launcher = LAUNCHER.read_text(encoding="utf-8")
    bridge = BRIDGE.read_text(encoding="utf-8")

    assert "semantic-code.py" in launcher
    assert "ROOT/.tools/serena/venv/bin/python" in launcher
    assert "start-mcp-server" in bridge
    assert '"--project"' in bridge
    assert "ROOT" in bridge


def test_serena_config_keeps_tool_selection_unrestricted():
    text = SERENA_CONFIG.read_text(encoding="utf-8")

    for key in ("excluded_tools:", "included_optional_tools:", "fixed_tools:"):
        assert key in text
    assert "read_only: true" in text
