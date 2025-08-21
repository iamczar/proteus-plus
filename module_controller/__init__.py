"""Proteus Module Controller package.

Manages multiple Alpha module connections via serial + MQTT.
"""

from .module_controller import ModuleController
from .module_handler import ModuleHandler

__all__ = ["ModuleController", "ModuleHandler"]


