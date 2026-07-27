"""The Mikrotik Switch class."""

from __future__ import annotations

import contextlib
from datetime import timedelta
import logging
from typing import Any

from httpx import AsyncClient, DigestAuth, HTTPStatusError, TransportError
from python_switchos.client import Client
from python_switchos.endpoints.link import LinkEndpoint
from python_switchos.endpoints.poe import PoEEndpoint
from python_switchos.endpoints.sys import SystemEndpoint
from python_switchos.http import create_httpx_client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    POE_MODE_AUTO,
    POE_MODE_OFF,
    HostEntry,
    PortStats,
    SwitchOSApi,
)
from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from .errors import AuthError, CannotConnect
from .port import Port

_LOGGER = logging.getLogger(__name__)

type MikrotikSwitchOSConfigEntry = ConfigEntry[MikrotikSwitchOSCoordinator]


class MikrotikSwitchOSData:
    """Handle all communication with the Switch."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Mikrotik Client."""
        self.hass = hass
        self.config_entry = config_entry
        self.client = _create_client(hass, config_entry.data)
        self.api = _create_api(hass, config_entry.data)
        self.device: SystemEndpoint | None = None
        self.sys: SystemEndpoint | None = None
        self.link: LinkEndpoint | None = None
        self.poe: PoEEndpoint | None = None
        self.poe_modes: list[int] | None = None
        self.stats: list[PortStats] = []
        self.hosts: list[HostEntry] = []

    async def setup(self) -> None:
        """Set up the data class by loading system information."""
        self.device = self.sys = await self.client.fetch(SystemEndpoint)
        await self.update_all()

    async def update_all(self) -> None:
        """Refresh link, health, PoE, stats, and hosts."""
        self.link = await self.client.fetch(LinkEndpoint)
        self.sys = await self.client.fetch(SystemEndpoint)

        self.poe = None
        self.poe_modes = None
        with contextlib.suppress(HTTPStatusError):
            self.poe = await self.client.fetch(PoEEndpoint)
        self.poe_modes = await self.api.get_poe_modes()

        try:
            self.stats = await self.api.fetch_stats()
        except (HTTPStatusError, ValueError, TypeError) as err:
            _LOGGER.debug("stats.b unavailable: %s", err)
            self.stats = []

        try:
            self.hosts = await self.api.fetch_hosts()
        except (HTTPStatusError, ValueError, TypeError) as err:
            _LOGGER.debug("host table unavailable: %s", err)
            self.hosts = []

    async def set_port_enabled(self, port_index: int, enabled: bool) -> None:
        """Enable or disable a switch port."""
        try:
            await self.api.set_port_enabled(port_index, enabled)
        except HTTPStatusError as err:
            raise HomeAssistantError(f"Failed to set port {port_index + 1}") from err

    async def set_poe_enabled(self, port_index: int, enabled: bool) -> None:
        """Turn PoE off or to auto for a port."""
        mode = POE_MODE_AUTO if enabled else POE_MODE_OFF
        try:
            await self.api.set_poe_mode(port_index, mode)
        except HTTPStatusError as err:
            raise HomeAssistantError(f"Failed to set PoE on port {port_index + 1}") from err

    async def reboot(self) -> None:
        """Reboot the switch."""
        try:
            await self.api.reboot()
        except HTTPStatusError as err:
            raise HomeAssistantError("Failed to reboot switch") from err

    @property
    def ports(self) -> list[Port]:
        """Return the ports of this hub."""
        assert self.link is not None
        ports: list[Port] = []
        for index, _ in enumerate(self.link.enabled):
            stats = self.stats[index] if index < len(self.stats) else None
            poe_mode = (
                self.poe_modes[index]
                if self.poe_modes is not None and index < len(self.poe_modes)
                else None
            )
            ports.append(
                Port(
                    index,
                    self.link,
                    stats=stats,
                    poe_mode=poe_mode,
                    poe=self.poe,
                )
            )
        return ports


class MikrotikSwitchOSCoordinator(DataUpdateCoordinator[None]):
    """Mikrotik SwitchOS Hub Object."""

    config_entry: MikrotikSwitchOSConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: MikrotikSwitchOSConfigEntry
    ) -> None:
        """Initialize the Mikrotik Client."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} - {config_entry.data[CONF_HOST]}",
            update_interval=timedelta(
                seconds=config_entry.data.get(
                    CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL
                )
            ),
        )
        self._mk_data = MikrotikSwitchOSData(hass, config_entry)

    @property
    def host(self) -> str:
        """Return the host of this hub."""
        return str(self.config_entry.data[CONF_HOST])

    @property
    def identity(self) -> str:
        """Return the identity (name) of the hub."""
        return self._mk_data.device.identity

    @property
    def model(self) -> str:
        """Return the model of the hub."""
        return self._mk_data.device.model

    @property
    def firmware(self) -> str:
        """Return the firmware version of the hub."""
        return self._mk_data.device.version

    @property
    def serial_num(self) -> str:
        """Return the serial number of the hub."""
        return self._mk_data.device.serial

    @property
    def mac(self) -> str:
        """Return the MAC address of the hub."""
        return self._mk_data.device.mac

    @property
    def api(self) -> MikrotikSwitchOSData:
        """Represent Mikrotik Switch data object."""
        return self._mk_data

    async def _async_setup(self) -> None:
        await self._mk_data.setup()

    async def _async_update_data(self) -> None:
        try:
            await self._mk_data.update_all()
        except HTTPStatusError as err:
            if err.response.status_code == 401:
                raise ConfigEntryAuthFailed from err
            raise UpdateFailed("Error fetching data from API") from err


async def test_connection(hass: HomeAssistant, entry: dict[str, Any]) -> None:
    """Test connection to API with given settings."""
    _LOGGER.debug("Connecting to Mikrotik SwitchOS [%s]", entry[CONF_HOST])

    client = _create_client(hass, entry)
    try:
        await client.fetch(SystemEndpoint)
    except HTTPStatusError as err:
        if err.response.status_code == 401:
            raise AuthError from err
        raise CannotConnect from err
    except (TransportError, OSError, TimeoutError) as err:
        raise CannotConnect from err


def _create_client(hass: HomeAssistant, entry: dict[str, Any]) -> Client:
    auth = DigestAuth(entry[CONF_USERNAME], entry[CONF_PASSWORD])
    http_client: AsyncClient = get_async_client(hass)
    return Client(create_httpx_client(http_client, auth), entry[CONF_HOST])


def _create_api(hass: HomeAssistant, entry: dict[str, Any]) -> SwitchOSApi:
    http_client: AsyncClient = get_async_client(hass)
    return SwitchOSApi(
        http_client,
        entry[CONF_HOST],
        entry[CONF_USERNAME],
        entry[CONF_PASSWORD],
    )
