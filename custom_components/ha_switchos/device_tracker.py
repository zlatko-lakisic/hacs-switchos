"""Device tracker for hosts learned by Mikrotik SwitchOS."""

from __future__ import annotations

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MikrotikSwitchOSConfigEntry, MikrotikSwitchOSCoordinator
from .entity import device_info


async def async_setup_entry(
    _: HomeAssistant,
    config_entry: MikrotikSwitchOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchOS device trackers."""
    coordinator = config_entry.runtime_data
    known: set[str] = set()

    def _async_add_new_hosts() -> None:
        new_entities: list[MikrotikHostTracker] = []
        for host in coordinator.api.hosts:
            if host.mac in known:
                continue
            known.add(host.mac)
            new_entities.append(
                MikrotikHostTracker(coordinator, device_info(coordinator), host.mac)
            )
        if new_entities:
            async_add_entities(new_entities)

    _async_add_new_hosts()
    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_add_new_hosts)
    )


class MikrotikHostTracker(
    CoordinatorEntity[MikrotikSwitchOSCoordinator], ScannerEntity
):
    """Track a MAC address seen on the switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "host"

    def __init__(
        self,
        coordinator: MikrotikSwitchOSCoordinator,
        device: dict,
        mac: str,
    ) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = f"{coordinator.serial_num}_{mac}"
        self._attr_device_info = device
        self._attr_name = mac

    @property
    def mac_address(self) -> str:
        """Return the MAC address."""
        return self._mac

    @property
    def hostname(self) -> str | None:
        """Hostname is not provided by SwOS host tables."""
        return None

    @property
    def is_connected(self) -> bool:
        """Return true if the host is currently in the switch table."""
        return any(host.mac == self._mac for host in self.coordinator.api.hosts)

    @property
    def extra_state_attributes(self) -> dict[str, int | str | None]:
        """Return host attributes."""
        for host in self.coordinator.api.hosts:
            if host.mac == self._mac:
                port = (
                    self.coordinator.api.ports[host.port]
                    if host.port < len(self.coordinator.api.ports)
                    else None
                )
                return {
                    "port": host.port + 1,
                    "port_name": port.name if port else None,
                    "vlan": host.vlan,
                }
        return {}
