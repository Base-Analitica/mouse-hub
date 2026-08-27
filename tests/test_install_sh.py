"""Testes determinísticos dos scripts de instalação/desinstalação (issue #8).

Garante invariantes críticas SEM executar alterações reais no sistema:
1. install.sh verifica dependências ANTES da primeira mutação.
2. Nenhum chmod 666 nem /dev/hidraw0 fixo.
3. Sem rsync (cópia via cp -a + exclusões).
4. O ícone declarado no .desktop existe no repositório e é instalado.
5. uninstall.sh remove tudo que install.sh instala e preserva dados XDG.
"""

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_INSTALL_SH = _REPO_ROOT / "install.sh"
_UNINSTALL_SH = _REPO_ROOT / "uninstall.sh"
_DESKTOP = _REPO_ROOT / "mouse-hub.desktop"


def _code_lines(path: Path) -> str:
    lines = [
        line for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return "\n".join(lines)


# ── install.sh ────────────────────────────────────────────

def test_install_checks_precede_mutations():
    """Toda verificação de dependência antecede qualquer mutação do sistema."""
    check_positions, mutation_positions = [], []
    for i, line in enumerate(_INSTALL_SH.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.search(r"command -v \w+", stripped) or re.search(r"python3 -c\s", stripped):
            check_positions.append(i)
        if re.search(r"\bsudo\b", stripped) and not stripped.startswith("echo"):
            mutation_positions.append(i)

    assert check_positions, "install.sh não contém verificações de dependência"
    assert mutation_positions, "install.sh não contém mutações do sistema"
    assert max(check_positions) < min(mutation_positions), (
        "mutação do sistema ocorre antes da última verificação de dependência"
    )


def test_install_no_chmod_666():
    assert "chmod 666" not in _code_lines(_INSTALL_SH)


def test_install_no_fixed_hidraw():
    assert "/dev/hidraw0" not in _code_lines(_INSTALL_SH)


def test_install_no_rsync_dependency():
    assert "rsync" not in _code_lines(_INSTALL_SH)


def test_install_uses_cp_a_with_exclusions():
    content = _code_lines(_INSTALL_SH)
    assert "cp -a" in content
    for dirname in [".git", "tests", ".venv", "__pycache__"]:
        assert dirname in content, f"install.sh deve excluir {dirname} da cópia"


def test_install_udev_rule_references_existing_file():
    match = re.search(r'UDEV_RULE="(docs/udev/[^"]+)"', _INSTALL_SH.read_text(encoding="utf-8"))
    assert match, "install.sh não define UDEV_RULE"
    assert (_REPO_ROOT / match.group(1)).exists(), "regra udev referenciada não existe"


def test_install_installs_icon_file():
    """O ícone instalado existe no repo e o install.sh o copia."""
    content = _code_lines(_INSTALL_SH)
    icon_ref = re.search(r'ICON_FILE="([^"]+)"', content)
    assert icon_ref, "install.sh não define ICON_FILE"
    icon_path = _REPO_ROOT / icon_ref.group(1)
    assert icon_path.exists(), "ícone referenciado pelo install.sh não existe"
    assert "hicolor" in content, "install.sh deve instalar o ícone no tema hicolor"


def test_install_warns_about_wayland_session():
    """Resumo da instalação informa a limitação de sessão Wayland."""
    content = _INSTALL_SH.read_text(encoding="utf-8")
    assert "XDG_SESSION_TYPE" in content
    assert "wayland" in content.lower()


# ── mouse-hub.desktop ─────────────────────────────────────

def test_desktop_declares_existing_icon():
    content = _DESKTOP.read_text(encoding="utf-8")
    match = re.search(r"^Icon=(.+)$", content, re.MULTILINE)
    assert match, ".desktop não declara Icon="
    icon_name = match.group(1).strip()
    assert (_REPO_ROOT / "assets" / "icons" / f"{icon_name}.svg").exists(), (
        "Icon declarado no .desktop não existe em assets/icons/"
    )


def test_desktop_points_to_installed_launcher():
    content = _DESKTOP.read_text(encoding="utf-8")
    assert "launcher.sh" in content or "run_app.sh" in content
    assert "7777" not in content, ".desktop não pode referenciar o fluxo web legado"


# ── uninstall.sh ──────────────────────────────────────────

def test_uninstall_exists_and_removes_install_targets():
    assert _UNINSTALL_SH.exists(), "uninstall.sh não existe"
    content = _code_lines(_UNINSTALL_SH)
    for target in ["/opt/mouse-hub", "mouse-hub.desktop", "hicolor", "99-logitech-g403-hidraw.rules"]:
        assert target in content, f"uninstall.sh deve remover {target}"


def test_uninstall_preserves_user_data():
    """uninstall.sh não remove dados do usuário em XDG."""
    content = _code_lines(_UNINSTALL_SH)
    assert ".config/mouse-hub" in content or ".config$HOME" in content or "mouse-hub/" in content
    # proibido rm -rf nos caminhos XDG do usuário
    assert not re.search(r"rm\s+-rf\s+.*\.config/mouse-hub", content)
    assert not re.search(r"rm\s+-rf\s+.*\.local/share/mouse-hub", content)


def test_uninstall_no_pip_and_no_chmod_666():
    content = _code_lines(_UNINSTALL_SH)
    assert "pip install" not in content
    assert "chmod 666" not in content
