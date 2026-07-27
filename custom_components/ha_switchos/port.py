"""Network port class."""

from __future__ import annotations

from python_switchos.endpoints.link import LinkEndpoint
from python_switchos.endpoints.poe import PoEEndpoint

from .api import PortStats, speed_label


class Port:
    """Represents a network port of the switch."""

    def __init__(
        self,
        num: int,
        link_info: LinkEndpoint,
        stats: PortStats | None = None,
        poe_mode: int | None = None,
        poe: PoEEndpoint | None = None,
    ) -> None:
        """Initialize the network port."""
        self.num = num
        self.link_info = link_info
        self.stats = stats
        self.poe_mode = poe_mode
        self.poe = poe

    @property
    def enabled(self) -> bool:
        """Return if the port is administratively enabled."""
        return bool(self.link_info.enabled[self.num])

    @property
    def name(self) -> str:
        """Return the port name."""
        name = self.link_info.name[self.num]
        return name if name else f"Port{self.num + 1}"

    @property
    def link_up(self) -> bool | None:
        """Return whether the port has link."""
        if self.link_info.link_state is None:
            return None
        return bool(self.link_info.link_state[self.num])

    @property
    def full_duplex(self) -> bool | None:
        """Return whether the port is full duplex."""
        if self.link_info.full_duplex is None:
            return None
        return bool(self.link_info.full_duplex[self.num])

    @property
    def speed(self) -> str | None:
        """Return negotiated/current link speed label."""
        # On SwOS, spd is actual speed (man_speed in python-switchos).
        # On SwOS Lite, i08 is closer to operational speed (speed field).
        candidates = (
            getattr(self.link_info, "man_speed", None),
            getattr(self.link_info, "speed", None),
        )
        for series in candidates:
            if series is None or self.num >= len(series):
                continue
            value = series[self.num]
            if isinstance(value, str):
                return value
            if isinstance(value, int):
                return speed_label(value)
        return None

    @property
    def poe_enabled(self) -> bool | None:
        """Return whether PoE output is not off."""
        if self.poe_mode is None:
            return None
        return self.poe_mode != 0

    @property
    def has_poe(self) -> bool:
        """Return whether this port has PoE capability data."""
        return self.poe_mode is not None
