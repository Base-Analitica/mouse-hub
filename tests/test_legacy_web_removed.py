"""Regressões da issue #10: o produto suportado é somente o app nativo."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_web_server_and_ui_are_absent():
    assert not (ROOT / "mouse_hub.py").exists()
    assert not (ROOT / "static" / "index.html").exists()


def test_root_launchers_cannot_reintroduce_web_or_unsafe_hidraw_flow():
    forbidden = (
        "localhost:7777",
        "--port 7777",
        "/dev/hidraw0",
        "chmod 666",
        "--break-system-packages",
    )
    for relative in ("start.sh", "launcher.sh"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        executable = "\n".join(
            line for line in text.splitlines()
            if not line.lstrip().startswith("#")
        )
        for token in forbidden:
            assert token not in executable, (
                f"{relative} reintroduziu token legado/inseguro executável: {token}"
            )
        assert "app/mouse_hub_app.py" in executable
        assert "python3 mouse_hub.py" not in executable


def test_ci_no_longer_compiles_removed_web_entrypoint():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "mouse_hub.py" not in workflow
    assert "python3 -m compileall -q mouse_hub tests app" in workflow


def test_native_entrypoint_remains_present():
    entrypoint = ROOT / "app" / "run_app.sh"
    app = ROOT / "app" / "mouse_hub_app.py"
    assert entrypoint.is_file()
    assert app.is_file()
