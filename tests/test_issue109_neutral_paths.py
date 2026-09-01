"""Issue #109: screenshots públicos NÃO incorporam caminho pessoal.

O pipeline de captura fixa XDG_CONFIG_HOME/XDG_DATA_HOME NEUTROS
(/home/user/...) antes de construir o app: duas máquinas com HOME
diferente produzem o MESMO texto em "Informações do Sistema" — artefato
reproduzível, sem username. O comportamento do usuário local é
inalterado (a página continua lendo ConfigPaths.xdg() do ambiente).
"""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_capture_module():
    spec = importlib.util.spec_from_file_location(
        "capture_screenshots", REPO / "scripts" / "capture_screenshots.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _set_neutral_xdg(monkeypatch, mod):
    for key, value in mod.NEUTRAL_XDG.items():
        monkeypatch.setenv(key, value)


def _settings_info_text_with_neutral_xdg(monkeypatch) -> str:
    """Com o XDG do pipeline aplicado, extrai o texto REAL do bloco
    Informações do Sistema lendo o QLabel da SettingsPage.

    Usa o mesmo builder da captura no processo do teste. Isso evita um
    subprocesso artificial e mantém erros de import visíveis no CI.
    """
    mod = _load_capture_module()
    _set_neutral_xdg(monkeypatch, mod)
    window, qapp, patcher = mod._build_app()
    try:
        window._switch_page(6)
        qapp.processEvents()
        for label in window.settings_page.findChildren(_label_type()):
            if "Config:" in label.text():
                return label.text()
        raise AssertionError("bloco Informações do Sistema não encontrado")
    finally:
        window.close()
        patcher.undo()


def _label_type():
    """Import tardio para manter o módulo de teste leve fora da UI."""
    from PyQt5.QtWidgets import QLabel

    return QLabel


class TestCaminhosNeutros:
    def test_xdg_fixado_e_neutro_no_pipeline(self):
        mod = _load_capture_module()
        assert mod.NEUTRAL_XDG["XDG_CONFIG_HOME"] == "/home/user/.config"
        assert mod.NEUTRAL_XDG["XDG_DATA_HOME"] == "/home/user/.local/share"

    def test_configpaths_resolvem_para_neutro_com_pipeline(self, monkeypatch):
        """Com o env do pipeline, ConfigPaths.xdg() não depende do HOME
        real — dois ambientes quaisquer resolvem os mesmos caminhos."""
        mod = _load_capture_module()
        _set_neutral_xdg(monkeypatch, mod)
        from mouse_hub.core.config import ConfigPaths

        caminhos = []
        for home in ("/home/qualquer-usuario", "/home/outro-usuario"):
            monkeypatch.setenv("HOME", home)
            paths = ConfigPaths.xdg()
            caminhos.append((str(paths.config_file), str(paths.macros_file)))

        assert caminhos == [
            (
                "/home/user/.config/mouse-hub/config.json",
                "/home/user/.local/share/mouse-hub/macros.json",
            ),
            (
                "/home/user/.config/mouse-hub/config.json",
                "/home/user/.local/share/mouse-hub/macros.json",
            ),
        ]

    def test_info_do_sistema_sem_username_real(self, monkeypatch):
        """O texto exibido no bloco Informações do Sistema não contém o
        HOME real da máquina — só os caminhos neutros fixados."""
        real_home = Path.home().as_posix()
        text = _settings_info_text_with_neutral_xdg(monkeypatch)
        assert real_home not in text, f"HOME real vazou: {real_home}"
        assert "/home/pedro" not in text
        assert "/home/user/.config/mouse-hub/config.json" in text
        assert "/home/user/.local/share/mouse-hub/macros.json" in text
