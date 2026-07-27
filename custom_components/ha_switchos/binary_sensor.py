"""Binary sensor platform for Mikrotik SwitchOS."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MikrotikSwitchOSConfigEntry, MikrotikSwitchOSCoordinator
from .entity import device_info
from .port import Port

PORT_BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="link",
        translation_key="link",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)


async def async_setup_entry(
    _: HomeAssistant,
    config_entry: MikrotikSwitchOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchOS binary sensors."""
    coordinator = config_entry.runtime_data
    info = device_info(coordinator)
    async_add_entities(
        MikrotikPortBinarySensor(coordinator, info, description, port)
        for description in PORT_BINARY_SENSORS
        for port in coordinator.api.ports
        if port.link_up is not None
    )


class MikrotikPortBinarySensor(
    CoordinatorEntity[MikrotikSwitchOSCoordinator], BinarySensorEntity
):
    """Binary sensor for a switch port."""

    _attr_has_entity_name = True
    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: MikrotikSwitchOSCoordinator,
        device: dict,
        description: BinarySensorEntityDescription,
        port: Port,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.port_num = port.num
        self._attr_translation_placeholders = {
            "port_num": f"{(port.num + 1):02d}",
            "port_name": port.name,
        }
        self._attr_unique_id = (
            f"{coordinator.serial_num}_{port.num}_{description.key}"
        )
        self._attr_device_info = device

    @property
    def _port(self) -> Port:
        return self.coordinator.api.ports[self.port_num]

    @property
    def is_on(self) -> bool:
        """Return true if the port has link."""
        return bool(self._port.link_up)

    @property
    def extra_state_attributes(self) -> dict[str, str | bool | None]:
        """Return link attributes."""
        port = self._port
        return {
            "port": port.num + 1,
            "port_name": port.name,
            "speed": port.speed,
            "full_duplex": port.full_duplex,
            "enabled": port.enabled,
        }
