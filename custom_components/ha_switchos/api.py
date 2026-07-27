"""Low-level SwitchOS HTTP (.b) helpers for reads/writes beyond python-switchos."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Any
from urllib.parse import urljoin

from httpx import AsyncClient, DigestAuth, HTTPStatusError
from python_switchos.utils import hex_to_mac, str_to_json

_LOGGER = logging.getLogger(__name__)

# Writable link.b keys for SwOS / SwOS Lite (exclude link status, actual speed, etc.).
_LINK_WRITE_KEYS = (
    "en",
    "nm",
    "an",
    "spdc",
    "dpxc",
    "fctc",
    "fctr",
    "i01",
    "i0a",
    "i02",
    "i05",
    "i03",
    "i16",
    "i12",
)

# Writable poe.b keys.
_POE_WRITE_KEYS = (
    "poe",
    "prio",
    "lvl",
    "lldp",
    "i01",
    "i02",
    "i03",
    "i0a",
)

# PoE mode wire values (SwOS UI order): 0=off, 1=on, 2=auto
POE_MODE_OFF = 0
POE_MODE_ON = 1
POE_MODE_AUTO = 2

_SPEED_LABELS = ("10M", "100M", "1G", "10G", "200M", "2.5G", "5G")


@dataclass(slots=True)
class PortStats:
    """Per-port traffic statistics."""

    rx_rate_mbps: float | None = None
    tx_rate_mbps: float | None = None
    rx_bytes: int | None = None
    tx_bytes: int | None = None
    rx_packets: int | None = None
    tx_packets: int | None = None


@dataclass(slots=True)
class HostEntry:
    """MAC address learned on a switch port."""

    mac: str
    port: int
    vlan: int | None = None


def _format_hex_value(val: int) -> str:
    hex_str = f"{val:x}"
    if len(hex_str) % 2 == 1:
        hex_str = "0" + hex_str
    return f"0x{hex_str}"


def _format_post_value(val: Any) -> str:
    if isinstance(val, list):
        formatted: list[str] = []
        for item in val:
            if isinstance(item, int):
                formatted.append(f"0x{item:02x}")
            else:
                formatted.append(f"'{item}'")
        return "[" + ",".join(formatted) + "]"
    if isinstance(val, int):
        return _format_hex_value(val)
    return f"'{val}'"


def build_post_body(data: dict[str, Any]) -> str:
    """Build a SwOS text/plain POST body from a dict."""
    pairs = [f"{key}:{_format_post_value(value)}" for key, value in data.items()]
    return "{" + ",".join(pairs) + "}"


def _combine_counters(low: list[int] | None, high: list[int] | None) -> list[int] | None:
    if low is None:
        return None
    if high is None:
        return list(low)
    return [int(low[i]) + (int(high[i]) << 32) for i in range(len(low))]


def _scaled_rates(values: list[int] | None, scale: float) -> list[float] | None:
    if values is None:
        return None
    return [float(value) * scale for value in values]


def parse_stats(raw: dict[str, Any]) -> list[PortStats]:
    """Parse stats.b for SwOS or SwOS Lite into per-port stats."""
    # SwOS descriptive keys first, then SwOS Lite hex ids.
    if "rrb" in raw or "rb" in raw:
        rx_rate = _scaled_rates(raw.get("rrb"), 0.01)
        tx_rate = _scaled_rates(raw.get("trb"), 0.01)
        rx_bytes = _combine_counters(raw.get("rb"), raw.get("rbh"))
        tx_bytes = _combine_counters(raw.get("tb"), raw.get("tbh"))
        rx_packets = raw.get("rtp")
        tx_packets = raw.get("ttp")
    else:
        rx_rate = _scaled_rates(raw.get("i21"), 0.32)
        tx_rate = _scaled_rates(raw.get("i22"), 0.32)
        rx_bytes = _combine_counters(raw.get("i01"), raw.get("i02"))
        tx_bytes = _combine_counters(raw.get("i0f"), raw.get("i10"))
        rx_packets = raw.get("i23")
        tx_packets = raw.get("i24")

    length = 0
    for series in (rx_rate, tx_rate, rx_bytes, tx_bytes, rx_packets, tx_packets):
        if isinstance(series, list):
            length = max(length, len(series))

    stats: list[PortStats] = []
    for index in range(length):
        stats.append(
            PortStats(
                rx_rate_mbps=rx_rate[index] if rx_rate and index < len(rx_rate) else None,
                tx_rate_mbps=tx_rate[index] if tx_rate and index < len(tx_rate) else None,
                rx_bytes=rx_bytes[index] if rx_bytes and index < len(rx_bytes) else None,
                tx_bytes=tx_bytes[index] if tx_bytes and index < len(tx_bytes) else None,
                rx_packets=(
                    int(rx_packets[index])
                    if rx_packets and index < len(rx_packets)
                    else None
                ),
                tx_packets=(
                    int(tx_packets[index])
                    if tx_packets and index < len(tx_packets)
                    else None
                ),
            )
        )
    return stats


def parse_hosts(raw: Any) -> list[HostEntry]:
    """Parse !dhost.b / host.b dynamic or static host tables."""
    if not isinstance(raw, list):
        return []

    hosts: list[HostEntry] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        mac_hex = entry.get("adr") or entry.get("i01") or entry.get("mac")
        port = entry.get("prt")
        if port is None:
            port = entry.get("i02")
        if mac_hex is None or port is None:
            continue
        vlan = entry.get("vid", entry.get("i03"))
        try:
            mac = hex_to_mac(mac_hex) if isinstance(mac_hex, str) else str(mac_hex)
        except Exception:  # noqa: BLE001 - tolerate odd encodings
            mac = str(mac_hex)
        hosts.append(
            HostEntry(
                mac=mac.upper(),
                port=int(port),
                vlan=int(vlan) if vlan is not None else None,
            )
        )
    return hosts


def speed_label(value: int | None) -> str | None:
    """Map SwOS speed index to a label."""
    if value is None or value < 0 or value >= len(_SPEED_LABELS):
        return None
    return _SPEED_LABELS[value]


def bitmask_get(mask: int, index: int) -> bool:
    """Return whether bit index is set in a port bitmask."""
    return bool(mask & (1 << index))


def bitmask_set(mask: int, index: int, enabled: bool) -> int:
    """Set or clear bit index in a port bitmask."""
    bit = 1 << index
    return mask | bit if enabled else mask & ~bit


class SwitchOSApi:
    """Async digest-auth client for SwitchOS .b endpoints."""

    def __init__(
        self, http_client: AsyncClient, host: str, username: str, password: str
    ) -> None:
        self._http = http_client
        self._host = host.rstrip("/") + "/"
        self._auth = DigestAuth(username, password)

    def _url(self, path: str) -> str:
        return urljoin(self._host, path.lstrip("/"))

    async def get_raw(self, path: str) -> Any:
        """GET an endpoint and parse the JS-like body."""
        response = await self._http.get(
            self._url(path), auth=self._auth, follow_redirects=False
        )
        response.raise_for_status()
        text = response.text.strip()
        if not text:
            return None
        return str_to_json(text)

    async def post_raw(self, path: str, body: str) -> None:
        """POST a text/plain body to an endpoint."""
        response = await self._http.post(
            self._url(path),
            content=body,
            headers={"Content-Type": "text/plain"},
            auth=self._auth,
            follow_redirects=False,
        )
        response.raise_for_status()

    async def try_get_raw(self, path: str) -> Any | None:
        """GET an endpoint, returning None on missing/unsupported endpoints."""
        try:
            return await self.get_raw(path)
        except HTTPStatusError as err:
            if err.response.status_code in (303, 404):
                return None
            raise

    async def fetch_stats(self) -> list[PortStats]:
        """Fetch and decode port statistics."""
        raw = await self.try_get_raw("stats.b")
        if not isinstance(raw, dict):
            return []
        return parse_stats(raw)

    async def fetch_hosts(self) -> list[HostEntry]:
        """Fetch dynamic host table (!dhost.b preferred)."""
        for path in ("!dhost.b", "dhost.b", "host.b"):
            raw = await self.try_get_raw(path)
            if raw is None:
                continue
            hosts = parse_hosts(raw)
            if hosts or path == "host.b":
                return hosts
        return []

    async def set_port_enabled(self, port_index: int, enabled: bool) -> None:
        """Enable or disable a port via link.b read-modify-write."""
        raw = await self.get_raw("link.b")
        if not isinstance(raw, dict):
            raise RuntimeError("Unexpected link.b response")

        enabled_key = "en" if "en" in raw else "i01"
        if enabled_key not in raw:
            raise RuntimeError("link.b missing enabled bitmask")

        current = int(raw[enabled_key])
        raw[enabled_key] = bitmask_set(current, port_index, enabled)

        payload = {key: raw[key] for key in _LINK_WRITE_KEYS if key in raw}
        body = build_post_body(payload)
        _LOGGER.debug("Writing link.b for port %s enabled=%s", port_index, enabled)
        await self.post_raw("link.b", body)

    async def set_poe_mode(self, port_index: int, mode: int) -> None:
        """Set PoE mode for a port (0=off, 1=on, 2=auto)."""
        raw = await self.get_raw("poe.b")
        if not isinstance(raw, dict):
            raise RuntimeError("Unexpected poe.b response")

        mode_key = "poe" if "poe" in raw else "i01"
        modes = raw.get(mode_key)
        if not isinstance(modes, list) or port_index >= len(modes):
            raise RuntimeError("poe.b missing mode array or port out of range")

        modes = list(modes)
        modes[port_index] = mode
        raw[mode_key] = modes

        payload = {key: raw[key] for key in _POE_WRITE_KEYS if key in raw}
        # PoE arrays are often only the copper/PoE-capable ports.
        body = build_post_body(payload)
        _LOGGER.debug("Writing poe.b for port %s mode=%s", port_index, mode)
        await self.post_raw("poe.b", body)

    async def get_poe_modes(self) -> list[int] | None:
        """Return raw PoE mode integers per port, if PoE is available."""
        raw = await self.try_get_raw("poe.b")
        if not isinstance(raw, dict):
            return None
        modes = raw.get("poe", raw.get("i01"))
        if not isinstance(modes, list):
            return None
        return [int(value) for value in modes]

    async def reboot(self) -> None:
        """Reboot the switch."""
        await self.post_raw("reboot", "*")


def is_swos_lite_payload(raw: dict[str, Any]) -> bool:
    """Heuristic: SwOS Lite uses iXX keys; SwOS uses descriptive names."""
    has_hex = any(re.fullmatch(r"i[0-9a-f]{2}", key) for key in raw)
    has_desc = "id" in raw or "en" in raw or "brd" in raw
    return has_hex and not has_desc
