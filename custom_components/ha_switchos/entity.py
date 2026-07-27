"""Shared entity helpers for Mikrotik SwitchOS."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from .const import ATTR_MANUFACTURER, DOMAIN
from .coordinator import MikrotikSwitchOSCoordinator


def device_info(coordinator: MikrotikSwitchOSCoordinator) -> DeviceInfo:
    """Return DeviceInfo for the switch."""
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.serial_num)},
        connections={("mac", coordinator.mac)},
        manufacturer=ATTR_MANUFACTURER,
        model=coordinator.model,
        name=coordinator.identity,
        serial_number=coordinator.serial_num,
        sw_version=coordinator.firmware,
        configuration_url=coordinator.host,
    )
