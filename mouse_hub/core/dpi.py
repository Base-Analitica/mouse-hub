"""Regras puras de DPI do sensor HERO.

DPI físico é a resolução do sensor, configurada no hardware do mouse.
Este módulo contém apenas matemática de domínio: clamp e alinhamento
ao step suportado pelo G403. Não há nenhuma chamada de sistema aqui.
"""

from __future__ import annotations

from mouse_hub.core.constants import DPI_MAX, DPI_MIN, DPI_STEP


def clamp_dpi(value: int) -> int:
    """Restringe um valor à faixa suportada pelo G403 HERO.

    Valores fora da faixa são truncados para os limites.
    """
    return max(DPI_MIN, min(DPI_MAX, int(value)))


def round_to_step(value: int, step: int = DPI_STEP) -> int:
    """Alinha um DPI ao step suportado pelo hardware (múltiplo de 50).

    O alinhamento é feito para o múltiplo mais próximo; empates exatos
    (825, 875, ...) resolvem para cima.
    """
    clamped = clamp_dpi(value)
    base = (clamped // step) * step
    # Múltiplo mais próximo; empates (825, 875, ...) resolvem para cima
    # na metade superior, como na aritmética do firmware HID++.
    return base + step if clamped - base >= step // 2 else base


def next_dpi(value: int, step: int = DPI_STEP) -> int:
    """Próximo DPI válido acima de `value` (para botões step up).

    Valores já alinhados ao step também avançam (pressionar step-up em
    800 leva a 850), como nos botões físicos de DPI.
    """
    clamped = clamp_dpi(value)
    stepped = ((clamped + step) // step) * step
    return clamp_dpi(stepped)


def previous_dpi(value: int, step: int = DPI_STEP) -> int:
    """DPI válido anterior abaixo de `value` (para botões step down)."""
    clamped = clamp_dpi(value)
    stepped = ((clamped - 1) // step) * step
    return clamp_dpi(stepped)


def normalize_dpi(value: int, step: int = DPI_STEP) -> tuple[int, bool]:
    """Normaliza um DPI solicitado, retornando (valor_efetivo, foi_arredondado).

    Útil para informar à UI quando o valor aplicado difere do solicitado
    (APPLIED_PARTIAL em vez de APPLIED).
    """
    clamped = clamp_dpi(value)
    stepped = round_to_step(clamped, step)
    return stepped, stepped != value
