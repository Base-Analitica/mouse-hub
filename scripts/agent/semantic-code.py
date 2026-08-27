#!/usr/bin/env python3
"""Small, read-only Serena MCP bridge for Prime Agent project skills."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / ".tools" / "serena"
SERENA_BIN = TOOLS / "venv" / "bin" / "serena"
LOG_PATH = TOOLS / "state" / "bridge.log"


def clipped(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n[truncated; full Serena log: {LOG_PATH}]"


def runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    env["SERENA_HOME"] = str(TOOLS / "home")
    npm_cache = ROOT / ".cache" / "agent-tools" / "npm"
    npm_cache.mkdir(parents=True, exist_ok=True)
    env["npm_config_cache"] = str(npm_cache)
    env["NPM_CONFIG_CACHE"] = str(npm_cache)
    env["npm_config_audit"] = "false"
    env["npm_config_fund"] = "false"
    env["npm_config_update_notifier"] = "false"
    return env


def server_params() -> StdioServerParameters:
    return StdioServerParameters(
        command=str(SERENA_BIN),
        args=[
            "start-mcp-server",
            "--transport",
            "stdio",
            "--context",
            "oaicompat-agent",
            "--project",
            str(ROOT),
            "--enable-web-dashboard=false",
            "--enable-gui-log-window=false",
            "--open-web-dashboard=false",
            "--log-level",
            "WARNING",
        ],
        env=runtime_env(),
        cwd=str(ROOT),
    )


def result_text(result: Any) -> str:
    parts = [getattr(item, "text", "") for item in getattr(result, "content", [])]
    text = "".join(part for part in parts if part)
    if getattr(result, "isError", False):
        raise RuntimeError(text or "Serena returned an error")
    return text


async def call_tool(name: str, arguments: dict[str, Any]) -> str:
    if not SERENA_BIN.exists():
        raise RuntimeError("Serena is not installed; run scripts/agent/bootstrap-serena")
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as errlog:
        async with stdio_client(server_params(), errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return result_text(await session.call_tool(name, arguments))


async def list_semantic_tools() -> str:
    if not SERENA_BIN.exists():
        raise RuntimeError("Serena is not installed; run scripts/agent/bootstrap-serena")
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as errlog:
        async with stdio_client(server_params(), errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                names = sorted(
                    tool.name
                    for tool in result.tools
                    if tool.name
                    in {
                        "get_symbols_overview",
                        "find_symbol",
                        "find_referencing_symbols",
                        "find_implementations",
                        "find_declaration",
                        "get_diagnostics_for_file",
                    }
                )
                return json.dumps({"status": "ok", "tools": names}, separators=(",", ":"))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Read-only semantic queries through local Serena.")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("tools", help="handshake and list semantic tools")
    o = sub.add_parser("overview", help="list symbols in one source file")
    o.add_argument("path")
    o.add_argument("--depth", type=int, default=0)
    o.add_argument("--max-chars", type=int, default=5000)
    f = sub.add_parser("find", help="find a symbol, optionally returning its body")
    f.add_argument("pattern")
    f.add_argument("--path", default="")
    f.add_argument("--body", action="store_true")
    f.add_argument("--info", action="store_true")
    f.add_argument("--max-matches", type=int, default=5)
    f.add_argument("--max-chars", type=int, default=8000)
    r = sub.add_parser("refs", help="find references to a symbol")
    r.add_argument("name")
    r.add_argument("path")
    r.add_argument("--max-chars", type=int, default=6000)
    d = sub.add_parser("diagnostics", help="get language-server diagnostics")
    d.add_argument("path")
    d.add_argument("--max-chars", type=int, default=6000)
    return p


async def run(args: argparse.Namespace) -> str:
    if args.command == "tools":
        return await list_semantic_tools()
    if args.command == "overview":
        return await call_tool(
            "get_symbols_overview",
            {"relative_path": args.path, "depth": args.depth, "max_answer_chars": args.max_chars},
        )
    if args.command == "find":
        return await call_tool(
            "find_symbol",
            {
                "name_path_pattern": args.pattern,
                "relative_path": args.path,
                "include_body": args.body,
                "include_info": args.info,
                "max_matches": args.max_matches,
                "max_answer_chars": args.max_chars,
            },
        )
    if args.command == "refs":
        return await call_tool(
            "find_referencing_symbols",
            {"name_path": args.name, "relative_path": args.path, "max_answer_chars": args.max_chars},
        )
    if args.command == "diagnostics":
        return await call_tool(
            "get_diagnostics_for_file",
            {"relative_path": args.path, "max_answer_chars": args.max_chars},
        )
    raise AssertionError(args.command)


def main() -> int:
    args = parser().parse_args()
    try:
        print(clipped(asyncio.run(run(args)), getattr(args, "max_chars", 12000)))
        return 0
    except Exception as exc:  # keep failures short; details remain in the local log
        print(f"semantic-code: {exc} (Serena log: {LOG_PATH})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
