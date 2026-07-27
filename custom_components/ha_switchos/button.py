"""Button platform for Mikrotik SwitchOS."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MikrotikSwitchOSConfigEntry, MikrotikSwitchOSCoordinator
from .entity import device_info

REBOOT_BUTTON = ButtonEntityDescription(
    key="reboot",
    translation_key="reboot",
    icon="mdi:restart",
)


async def async_setup_entry(
    _: HomeAssistant,
    config_entry: MikrotikSwitchOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchOS buttons."""
    coordinator = config_entry.runtime_data
    async_add_entities([MikrotikRebootButton(coordinator, device_info(coordinator))])


class MikrotikRebootButton(
    CoordinatorEntity[MikrotikSwitchOSCoordinator], ButtonEntity
):
    """Reboot the switch."""

    _attr_has_entity_name = True
    entity_description = REBOOT_BUTTON

    def __init__(
        self,
        coordinator: MikrotikSwitchOSCoordinator,
        device: dict,
    ) -> None:
        """Initialize the reboot button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.serial_num}_reboot"
        self._attr_device_info = device

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.api.reboot()
