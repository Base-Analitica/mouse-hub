"""Issue #64 — empacotamento .deb determinístico.

Valida a árvore de staging do pacote sem sudo, sem dpkg e sem tocar
no sistema: o script build_deb.sh --stage monta a árvore e os testes
afirmam o contrato de instalação (mesmas convenções do install.sh).
O build real com dpkg-deb roda em CI quando disponível.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BUILD = REPO / "packaging" / "deb" / "build_deb.sh"


@pytest.fixture(scope="module")
def stage(tmp_path_factory):
    out = tmp_path_factory.mktemp("deb")
    result = subprocess.run(
        [str(BUILD), "--stage", str(out)],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return out


def test_control_fields(stage):
    control = (stage / "DEBIAN" / "control").read_text()
    assert "Package: mouse-hub" in control
    assert "Architecture: all" in control
    assert "python3-pyqt5" in control
    assert "python3-xlib" in control
    # versão injetada (placeholder nunca sobra no pacote)
    assert "__VERSION__" not in control
    version_line = next(l for l in control.splitlines() if l.startswith("Version:"))
    version = version_line.split(":", 1)[1].strip()
    assert version and version != ""


def test_maintainer_scripts_contract(stage):
    postinst = stage / "DEBIAN" / "postinst"
    prerm = stage / "DEBIAN" / "prerm"
    postrm = stage / "DEBIAN" / "postrm"
    for s in (postinst, prerm, postrm):
        assert s.exists(), f"{s} ausente"
        mode = s.stat().st_mode
        assert mode & stat.S_IXUSR, f"{s} não executável"

    text = postinst.read_text()
    assert "udevadm control --reload-rules" in text
    assert "udevadm trigger" in text
    assert "plugdev" in text  # grupo exigido pelo acesso HID
    # proibições do projeto: o postinst NUNCA instala dependências
    # (nem via pip --break-system-packages, nem via apt)
    assert "pip install" not in text
    assert "apt-get" not in text
    assert "apt install" not in text


def test_app_tree_in_opt(stage):
    opt = stage / "opt" / "mouse-hub"
    assert (opt / "app" / "mouse_hub_app.py").is_file()
    assert (opt / "mouse_hub" / "core" / "mouse_controller.py").is_file()
    assert (opt / "launcher.sh").is_file()
    assert (opt / "start.sh").is_file()
    for s in ("launcher.sh", "start.sh", "app/run_app.sh"):
        assert (opt / s).stat().st_mode & stat.S_IXUSR, f"{s} não executável"
    # sem ruído de desenvolvimento
    assert not (opt / ".git").exists()
    assert not (opt / "tests").exists()
    assert not list(opt.rglob("__pycache__"))


def test_directories_are_traversable(stage):
    """mktemp -d cria 0700 — a árvore instalada precisa ser legível
    por usuários comuns, senão o app não abre para ninguém."""
    for d in stage.rglob("*"):
        if d.is_dir():
            mode = d.stat().st_mode & 0o777
            assert mode & stat.S_IROTH and mode & stat.S_IXOTH, \
                f"diretório não travessável: {d} ({oct(mode)})"


def test_desktop_and_icon(stage):
    desktop = stage / "usr" / "share" / "applications" / "mouse-hub.desktop"
    text = desktop.read_text()
    assert "Exec=/usr/bin/mouse-hub" in text
    icon = stage / "usr" / "share" / "icons" / "hicolor" / "scalable" / "apps" / "mouse-hub.svg"
    assert icon.is_file()

    wrapper = stage / "usr" / "bin" / "mouse-hub"
    assert wrapper.stat().st_mode & stat.S_IXUSR
    assert "/opt/mouse-hub/launcher.sh" in wrapper.read_text()


def test_udev_rule_matches_source(stage):
    packaged = stage / "etc" / "udev" / "rules.d" / "99-logitech-g403-hidraw.rules"
    source = REPO / "docs" / "udev" / "99-logitech-g403-hidraw.rules"
    assert packaged.read_text() == source.read_text()


@pytest.mark.skipif(shutil.which("dpkg-deb") is None, reason="dpkg-deb ausente")
def test_dpkg_build_produces_valid_package(tmp_path):
    """Build real do pacote (sem instalação) e inspeção com dpkg-deb."""
    out = tmp_path / "dist"
    out.mkdir()
    result = subprocess.run(
        [str(BUILD)], capture_output=True, text=True, timeout=300,
        env={**__import__("os").environ, "MOUSE_HUB_VERSION": "9.9.9-test"},
    )
    assert result.returncode == 0, result.stderr
    deb = REPO / "dist" / "mouse-hub_9.9.9-test_all.deb"
    assert deb.is_file()
    info = subprocess.run(["dpkg-deb", "--info", str(deb)],
                          capture_output=True, text=True)
    assert info.returncode == 0
    assert "Package: mouse-hub" in info.stdout
    assert "Version: 9.9.9-test" in info.stdout
    # limpa o artefato do repositório — nada gerado fica commitado
    deb.unlink()
