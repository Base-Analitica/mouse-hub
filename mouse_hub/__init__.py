"""mouse_hub — core de domínio do Mouse Hub.

O objetivo deste pacote é conter UMA única implementação das regras de domínio do
Mouse Hub: estado, perfis, configuração, descoberta, controle de hardware suportado
e automação local de entrada. A direção arquitetural inclui mouse, teclado, timing
e sequências como primitivas do Input Engine, enquanto recursos proprietários de
hardware entram apenas por adapters/capabilities explícitos.

O Logitech G403 HERO permanece como o primeiro hardware concreto suportado, não
como o limite conceitual do produto. Regras de domínio não devem existir na UI nem
em módulos de plataforma/legados paralelos.
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
