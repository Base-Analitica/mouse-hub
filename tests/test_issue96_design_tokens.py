"""Issue #96 — invariantes do design system contra drift visual.

A UI deve referenciar tokens para cores já nomeadas no tema e para as
exceções dimensionais repetidas (cards/status/empty state). O teste não
proíbe toda medida inline legada de uma vez: protege especificamente os
valores que o issue identificou como fonte duplicada de verdade.
"""

import re
from pathlib import Path

from app.ui import theme

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "app" / "mouse_hub_app.py"


class TestDesignTokensSemDrift:
    def test_cores_existentes_do_tema_nao_sao_repetidas_como_hex(self):
        """Cores com token nomeado não podem voltar como literal na UI."""
        src = APP.read_text(encoding="utf-8")
        for key in ("accent_lighter", "danger_light", "danger_lighter"):
            assert theme.COLORS[key] not in src, (
                f"COLORS[{key!r}] duplicada como literal em mouse_hub_app.py"
            )

    def test_medidas_excepcionais_usam_tokens_nomeados(self):
        """Cards e estados repetidos não devem depender de números mágicos."""
        src = APP.read_text(encoding="utf-8")
        for literal in (
            "border-radius: 16px",
            "padding: 20px",
            "padding: 8px 20px",
            "padding: 30px",
            "border-radius: 18px",
        ):
            assert literal not in src, f"medida sem token encontrada: {literal}"

        assert theme.RADIUS["card"] == 16
        assert theme.RADIUS["pill"] == 18
        assert theme.SPACE["card"] == 20
        assert theme.SPACE["empty_state"] == 30

    def test_hex_restante_nao_e_cor_do_tema(self):
        """Qualquer hex que permaneça precisa ser uma cor não duplicada,
        não uma cópia silenciosa de token existente."""
        src = APP.read_text(encoding="utf-8")
        hexes = set(re.findall(r"#[0-9a-fA-F]{3,8}", src))
        theme_colors = {value.lower() for value in theme.COLORS.values()}
        assert not ({value.lower() for value in hexes} & theme_colors)
