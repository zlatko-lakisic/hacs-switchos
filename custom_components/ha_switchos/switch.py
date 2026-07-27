"""Switch platform for Mikrotik SwitchOS."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MikrotikSwitchOSConfigEntry, MikrotikSwitchOSCoordinator
from .entity import device_info
from .port import Port


async def async_setup_entry(
    _: HomeAssistant,
    config_entry: MikrotikSwitchOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchOS switches."""
    coordinator = config_entry.runtime_data
    info = device_info(coordinator)

    entities: list[SwitchEntity] = [
        MikrotikPortSwitch(coordinator, info, port) for port in coordinator.api.ports
    ]
    entities.extend(
        MikrotikPoESwitch(coordinator, info, port)
        for port in coordinator.api.ports
        if port.has_poe
    )
    async_add_entities(entities)


class MikrotikPortSwitch(
    CoordinatorEntity[MikrotikSwitchOSCoordinator], SwitchEntity
):
    """Administrative enable/disable switch for a port."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MikrotikSwitchOSCoordinator,
        device: dict,
        port: Port,
    ) -> None:
        """Initialize the port switch."""
        super().__init__(coordinator)
        self.port_num = port.num
        self.entity_description = SwitchEntityDescription(
            key="port_enabled",
            translation_key="port_enabled",
            translation_placeholders={
                "port_num": f"{(port.num + 1):02d}",
                "port_name": port.name,
            },
        )
        self._attr_unique_id = f"{coordinator.serial_num}_{port.num}_port_enabled"
        self._attr_device_info = device
        self._attr_icon = "mdi:ethernet"

    @property
    def _port(self) -> Port:
        return self.coordinator.api.ports[self.port_num]

    @property
    def is_on(self) -> bool:
        """Return true if the port is enabled."""
        return self._port.enabled

    @property
    def extra_state_attributes(self) -> dict[str, str | bool | None]:
        """Return port attributes."""
        port = self._port
        return {
            "port": port.num + 1,
            "port_name": port.name,
            "link_up": port.link_up,
            "speed": port.speed,
        }

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the port."""
        await self.coordinator.api.set_port_enabled(self.port_num, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the port."""
        await self.coordinator.api.set_port_enabled(self.port_num, False)
        await self.coordinator.async_request_refresh()


class MikrotikPoESwitch(CoordinatorEntity[MikrotikSwitchOSCoordinator], SwitchEntity):
    """PoE output switch for a port (off <-> auto)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MikrotikSwitchOSCoordinator,
        device: dict,
        port: Port,
    ) -> None:
        """Initialize the PoE switch."""
        super().__init__(coordinator)
        self.port_num = port.num
        self.entity_description = SwitchEntityDescription(
            key="poe_enabled",
            translation_key="poe_enabled",
            translation_placeholders={
                "port_num": f"{(port.num + 1):02d}",
                "port_name": port.name,
            },
        )
        self._attr_unique_id = f"{coordinator.serial_num}_{port.num}_poe_enabled"
        self._attr_device_info = device
        self._attr_icon = "mdi:power-plug"

    @property
    def _port(self) -> Port:
        return self.coordinator.api.ports[self.port_num]

    @property
    def is_on(self) -> bool:
        """Return true if PoE is not off."""
        return bool(self._port.poe_enabled)

    async def async_turn_on(self, **kwargs) -> None:
        """Enable PoE (auto)."""
        await self.coordinator.api.set_poe_enabled(self.port_num, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable PoE."""
        await self.coordinator.api.set_poe_enabled(self.port_num, False)
        await self.coordinator.async_request_refresh()
