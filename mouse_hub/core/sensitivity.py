"""Sensibilidade do ponteiro do sistema (libinput), independente do DPI.

O projeto original misturava dois conceitos distintos:

* DPI físico: resolução do sensor, gravada no hardware do G403;
* sensibilidade: curva de aceleração do ponteiro aplicada pelo
  sistema operacional (propriedade "libinput Accel Speed", faixa
  -1.0 a 1.0).

Este módulo trata exclusivamente da segunda. Ele não tem ciência de
hardware: apenas mapeia a escala percentual usada pela UI (0-100%) para
a escala do libinput e vice-versa. Uma mudança de DPI físico NUNCA deve
alterar a sensibilidade automaticamente; se a UI quiser ajustar as
duas, chama as duas operações explicitamente.
"""

from __future__ import annotations

from mouse_hub.core.constants import SENSITIVITY_MAX, SENSITIVITY_MIN


def clamp_sensitivity(value: int) -> int:
    """Restringe um percentual de sensibilidade a 0-100."""
    return max(SENSITIVITY_MIN, min(SENSITIVITY_MAX, int(value)))


def percent_to_accel(value: int) -> float:
    """Converte sensibilidade 0-100% para "libinput Accel Speed" (-1.0..1.0).

    0%  -> -1.0  (mínima aceleração / desaceleração máxima)
    50% ->  0.0  (aceleração padrão do libinput desativada)
    100% -> +1.0 (aceleração máxima)
    """
    clamped = clamp_sensitivity(value)
    return (clamped / 100.0) * 2.0 - 1.0


def accel_to_percent(accel: float) -> int:
    """Converte "libinput Accel Speed" para sensibilidade 0-100%.

    Valores fora da faixa são saturados nos limites da escala.
    """
    accel = max(-1.0, min(1.0, float(accel)))
    return int(round((accel + 1.0) / 2.0 * 100))


def normalize_sensitivity(value: int) -> tuple[int, bool]:
    """Normaliza uma sensibilidade solicitada, retornando (efetiva, foi_clampada)."""
    clamped = clamp_sensitivity(value)
    return clamped, clamped != value
