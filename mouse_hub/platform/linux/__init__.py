"""Implementações Linux do core: descoberta por VID/PID, HID validado e
operações de input via xinput/xdotool."""

from mouse_hub.platform.linux.device_discovery import discover_g403, find_g403_hidraw_devices
from mouse_hub.platform.linux.input import LinuxSystemInput
from mouse_hub.platform.linux.logitech import LinuxHidAccess

__all__ = [
    "LinuxHidAccess",
    "LinuxSystemInput",
    "discover_g403",
    "find_g403_hidraw_devices",
]
