"""mouse_hub — core de domínio do Mouse Hub.

O objetivo deste pacote é conter UMA única implementação das regras de
domínio do Mouse Hub (DPI, sensibilidade, perfis, configuração, descoberta
do Logitech G403 HERO), consumida tanto pelo aplicativo nativo quanto por
outras superfícies. Regras de domínio não devem existir na UI nem em
módulos legados paralelos.
"""

from mouse_hub.core.constants import (
    G403_VID,
    G403_PID,
    G403_NAME,
    DPI_MIN,
    DPI_MAX,
    DPI_STEP,
    DPI_DEFAULT,
    DPI_PRESETS,
    SENSITIVITY_MIN,
    SENSITIVITY_MAX,
    SENSITIVITY_DEFAULT,
    POLLING_RATES,
)

__all__ = [
    "G403_VID",
    "G403_PID",
    "G403_NAME",
    "DPI_MIN",
    "DPI_MAX",
    "DPI_STEP",
    "DPI_DEFAULT",
    "DPI_PRESETS",
    "SENSITIVITY_MIN",
    "SENSITIVITY_MAX",
    "SENSITIVITY_DEFAULT",
    "POLLING_RATES",
]
