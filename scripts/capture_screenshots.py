#!/usr/bin/env python3
"""Captura screenshots de TODAS as telas do Mouse Hub.

Uso:
    python3 scripts/capture_screenshots.py [--out docs/screenshots] [--small]

Padrão do projeto (decisão do mantenedor): os screenshots em
docs/screenshots/ devem estar SEMPRE atualizados com a main — são
usados para avaliação de design por agentes externos e para o README.
Ao mudar a UI, rode este script e commit as imagens no MESMO PR.

Ambiente: QT_QPA_PLATFORM=offscreen + fakes determinísticos
(hardware real NUNCA é necessário — a captura é reproduzível em CI).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

PAGES = [
    ("dashboard", "Dashboard"),
    ("dpi", "Controle de DPI"),
    ("sens", "Sensibilidade"),
    ("clicker", "Auto-Clicker"),
    ("macros", "Macros"),
    ("perfis", "Perfis"),
    ("settings", "Configurações"),
]


def _build_app():
    """App real com fakes determinísticos (sem hardware)."""
    from app import mouse_hub_app as app_module
    from tests.fakes import FakeHidAccess, FakeSystemInput, fake_g403_device
    from mouse_hub.core.mouse_controller import MouseController
    from mouse_hub.core.dpi_persistence import NeverDpiPersister

    class DummyMonitor:
        def __init__(self, out):
            pass

        def start(self):
            return True

        def stop(self):
            pass

    mp = pytest.MonkeyPatch()
    mp.setattr(app_module, "UdevHidrawMonitor", DummyMonitor)
    mp.setattr(app_module, "discover_candidates",
               lambda: [fake_g403_device()])

    def make_state():
        core = MouseController(hid=FakeHidAccess(),
                               system_input=FakeSystemInput(),
                               dpi_persister=NeverDpiPersister())
        return app_module.MouseCoreState(core)

    mp.setattr(app_module, "build_mouse_state", make_state)

    from PyQt5.QtWidgets import QApplication
    qapp = QApplication.instance() or QApplication(
        ["mouse-hub", "-platform", "offscreen"])
    qapp.setStyleSheet(app_module.STYLESHEET)
    window = app_module.MouseHubApp()
    return window, qapp, mp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/screenshots")
    ap.add_argument("--width", type=int, default=1050)
    ap.add_argument("--height", type=int, default=680)
    args = ap.parse_args()

    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    window, qapp, mp = _build_app()
    window.resize(args.width, args.height)
    window.show()
    qapp.processEvents()

    written = []
    for i, (slug, label) in enumerate(PAGES):
        window._switch_page(i)
        qapp.processEvents()
        target = out_dir / f"{i}_{slug}.png"
        window.grab().save(str(target))
        written.append((target, label))

    # variante estreita (prova de responsividade, issue #66)
    window.resize(760, 560)
    qapp.processEvents()
    for i, (slug, label) in enumerate(PAGES):
        window._switch_page(i)
        qapp.processEvents()
        target = out_dir / f"small_{slug}.png"
        window.grab().save(str(target))
    window.close()
    mp.undo()

    # mosaico de preview (hero do README)
    from PIL import Image, ImageDraw
    imgs = [Image.open(p) for p, _ in written]
    cw = max(im.width for im in imgs)
    ch = max(im.height for im in imgs)
    sheet = Image.new("RGB", (2 * cw + 30, 4 * ch + 50), "#0b0b14")
    draw = ImageDraw.Draw(sheet)
    for idx, (im, (_, label)) in enumerate(zip(imgs, written)):
        x = (idx % 2) * (cw + 10) + 10
        y = (idx // 2) * (ch + 10) + 10
        sheet.paste(im, (x, y))
        draw.text((x + 6, y + 4), label, fill="#a78bfa")
    sheet.save(out_dir / "preview.png")

    print(f"{len(written)} telas + variantes small + preview.png em {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
