# Mikrotik SwitchOS (Home Assistant)

Maintained fork of [probert94/ha-switchos](https://github.com/probert94/ha-switchos) with RouterOS-like monitoring and control for MikroTik **SwitchOS** and **SwitchOS Lite**.

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge&logo=homeassistantcommunitystore&logoColor=white)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/zlatko-lakisic/hacs-switchos?style=for-the-badge)](https://github.com/zlatko-lakisic/hacs-switchos/releases)

Uses the SwitchOS web UI HTTP `.b` API (digest auth) — **not SNMP**. SwitchOS has no official CLI, REST, or RouterOS API.

## Why this fork

Upstream focuses on PoE / health sensors. This fork adds:

| Area | Upstream | This fork |
| --- | --- | --- |
| Port enable / disable | — | Switch entities |
| Link up / down | — | Binary sensors |
| Negotiated speed | — | Sensors |
| RX / TX rate & bytes | — | Sensors (`stats.b`) |
| PoE on / off | Read-only power | Switches (off ↔ auto) + sensors |
| Host MAC table | — | Device trackers (`!dhost.b`) |
| Reboot | — | Button |
| Upstream sync | — | Daily GitHub Action |

Current version: **0.1.1**

## Features

### Device
- Identity, model, firmware, serial number, MAC
- CPU temperature (when exposed by the switch)
- Reboot button

### Ports
- **Switch** — administratively enable / disable each port
- **Binary sensor** — link up / down (with speed, duplex, enabled attributes)
- **Sensor** — negotiated link speed
- **Sensor** — RX / TX rate (Mbit/s)
- **Sensor** — RX / TX byte counters (disabled by default in the entity registry)

### PoE (hardware-dependent)
- Per-port power, current, and voltage sensors
- Per-port PoE switch (off ↔ auto)
- PSU / total power sensors when available

### Hosts
- Device tracker entities for MACs learned from `!dhost.b` (port + VLAN attributes)

## HACS install

1. HACS → ⋮ → **Custom repositories**
2. Add `https://github.com/zlatko-lakisic/hacs-switchos` as type **Integration**
3. Install **Mikrotik SwitchOS**, then **restart Home Assistant**

If you previously used `probert94/ha-switchos`, replace that custom repo with this fork (same integration domain: `mikrotik_switchos`).

## Configuration

1. Settings → Devices & Services → **Add Integration** → Mikrotik SwitchOS
2. Enter:
   - **Host** — e.g. `http://192.168.88.1` or `http://10.0.10.2/`
   - **Username** — `admin` (case sensitive; fixed on current SwitchOS builds)
   - **Password** — switch password
   - **Scan interval** — optional (default 10 seconds)

## Compatibility

| Model | OS | Versions tested |
| --- | --- | --- |
| CSS326-24G-2S+ | SwitchOS | 2.18 |
| CRS326-24G-2S+ | SwitchOS | 2.18 |
| CSS610-8P-2S+ | SwitchOS Lite | 2.20, 2.21 |

Other SwitchOS / SwitchOS Lite models should work; field names differ slightly between SwOS and SwOS Lite and are handled by the client layer.

## How it talks to the switch

- **Read:** `sys.b`, `link.b`, `stats.b`, `poe.b` (if present), `!dhost.b`
- **Write:** `link.b` (port enable), `poe.b` (PoE mode), `reboot`
- Auth: HTTP Digest over plain HTTP (same as the web UI — use a management VLAN / trusted network)
- Writes use read-modify-write of the full writable endpoint payload (MikroTik web UI behavior)

SNMP on SwitchOS is read-only and is **not** used by this integration.

## Development

- Integration path: `custom_components/ha_switchos/`
- Extended HTTP helpers: `api.py` (beyond `python-switchos` read-only endpoints)
- Dependency: `python-switchos==0.0.10`
- Upstream remote: `probert94/ha-switchos` (synced via `.github/workflows/sync-upstream.yml`)

## License

MIT (see `LICENSE`).
