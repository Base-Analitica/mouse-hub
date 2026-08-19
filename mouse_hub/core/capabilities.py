"""Modelo granular de capacidades do ambiente.

A UI original apresentava um único estado binário (`online`/`connected`),
que contradizia a realidade: o mouse podia estar detectado mas sem
acesso HID, ou a sensibilidade disponível mesmo sem o mouse ser
localizado via hidraw. Este módulo expõe cada capacidade de forma
independente, para que a UI indique com precisão o que está disponível,
o que falhou e o que está indisponível — sem declarar o produto inteiro
como "desconectado" por causa de um recurso.

O modelo é testável de ponta a ponta: `CapabilityModel` recebe
detectores injetáveis e não toca em `/sys`, `/dev` nem subprocess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


# Nomes de capacidades do produto. A lista é fixa por design: novas
# capacidades precisam de revisão explícita, para evitar que o modelo
# vire um saco de booleanos soltos.
CAPABILITY_NAMES = [
    "mouse_detected",
    "hid_available",
    "hardware_dpi_available",
    "sensitivity_available",
    "polling_rate_available",
    "macro_capture_available",
    "autoclick_available",
    "active_window_detection_available",
]


@dataclass
class Capability:
    """Estado de uma capacidade individual."""

    name: str
    available: bool
    reason: str = ""


@dataclass(frozen=True)
class CapabilityState:
    """Resultado imutável de uma avaliação de capacidades."""

    capabilities: Dict[str, Capability]

    def get(self, name: str) -> Capability:
        return self.capabilities.get(
            name, Capability(name=name, available=False, reason="capacidade desconhecida")
        )

    def is_available(self, name: str) -> bool:
        return self.get(name).available

    def __getitem__(self, name: str) -> bool:
        return self.is_available(name)


Detector = Callable[[], bool]


@dataclass
class CapabilityModel:
    """Avalia capacidades do ambiente a partir de detectores injetáveis.

    Cada detector retorna True se a capacidade correspondente está
    disponível neste momento. A avaliação é feita de uma vez e o
    resultado é imutável até a próxima avaliação, evitando race
    conditions entre a leitura de vários detectores.
    """

    mouse_detected: Detector = field(default=lambda: False)
    hid_available: Detector = field(default=lambda: False)
    hardware_dpi_available: Detector = field(default=lambda: False)
    sensitivity_available: Detector = field(default=lambda: False)
    polling_rate_available: Detector = field(default=lambda: False)
    macro_capture_available: Detector = field(default=lambda: False)
    autoclick_available: Detector = field(default=lambda: False)
    active_window_detection_available: Detector = field(default=lambda: False)

    def _detector_for(self, name: str) -> Optional[Detector]:
        return {
            "mouse_detected": self.mouse_detected,
            "hid_available": self.hid_available,
            "hardware_dpi_available": self.hardware_dpi_available,
            "sensitivity_available": self.sensitivity_available,
            "polling_rate_available": self.polling_rate_available,
            "macro_capture_available": self.macro_capture_available,
            "autoclick_available": self.autoclick_available,
            "active_window_detection_available": self.active_window_detection_available,
        }.get(name)

    def evaluate(self) -> CapabilityState:
        """Avalia todas as capacidades e retorna o estado imutável."""
        capabilities: Dict[str, Capability] = {}
        for name in CAPABILITY_NAMES:
            detector = self._detector_for(name)
            if detector is None:
                continue
            try:
                available = bool(detector())
            except Exception as exc:  # detector nunca quebra a avaliação
                available = False
                reason = f"erro no detector: {exc}"
            else:
                reason = ""
            capabilities[name] = Capability(name=name, available=available, reason=reason)
        return CapabilityState(capabilities=capabilities)

    @staticmethod
    def unavailable() -> "CapabilityModel":
        """Estado em que nenhuma capacidade está disponível (fallback)."""
        return CapabilityModel()
