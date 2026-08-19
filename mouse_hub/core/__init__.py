"""Core de domínio do Mouse Hub: regras puras de DPI/sensibilidade,
resultado explícito de operações, configuração XDG, perfis e modelo de
capacidades."""

from mouse_hub.core.capabilities import Capability, CapabilityModel, CapabilityState
from mouse_hub.core.config import (
    ConfigPaths,
    default_config,
    load_config,
    save_config,
)
from mouse_hub.core.dpi import clamp_dpi, normalize_dpi, round_to_step
from mouse_hub.core.operation import OperationResult, OperationStatus
from mouse_hub.core.profiles import Profile, ProfileStore
from mouse_hub.core.sensitivity import accel_to_percent, percent_to_accel

__all__ = [
    "Capability",
    "CapabilityModel",
    "CapabilityState",
    "ConfigPaths",
    "OperationResult",
    "OperationStatus",
    "Profile",
    "ProfileStore",
    "accel_to_percent",
    "clamp_dpi",
    "default_config",
    "load_config",
    "normalize_dpi",
    "percent_to_accel",
    "round_to_step",
    "save_config",
]
