# Home Assistant Integration - Mikrotik SwitchOS

Home Assistant integration for Mikrotik SwitchOS and SwitchOS Lite.

This is a maintained fork of [probert94/ha-switchos](https://github.com/probert94/ha-switchos) with RouterOS-like monitoring and control over the SwitchOS HTTP `.b` API (not SNMP).

[![Static Badge](https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge&logo=homeassistantcommunitystore&logoColor=white)](https://github.com/hacs/integration)

## HACS install

1. Go to HACS → ⋮ → Custom repositories
2. Add `https://github.com/zlatko-lakisic/hacs-switchos` as type **Integration**
3. Install **Mikrotik SwitchOS**, then restart Home Assistant

## Configuration

1. Settings → Devices & Services → Add Integration → **Mikrotik SwitchOS**
2. Enter:
   - Host: e.g. `http://192.168.1.2`
   - Username: `admin` (case sensitive; fixed on current SwitchOS)
   - Password: switch password

## Features

### Device
- Identity, model, firmware, serial, MAC
- Reboot button

### Ports
- Enable / disable each port (switch)
- Link up / down (binary sensor)
- Negotiated speed
- RX / TX rate (Mbps)
- RX / TX byte counters (disabled by default)

### PoE (when supported by hardware)
- Per-port PoE power / current / voltage sensors
- Per-port PoE on/off switch (off ↔ auto)
- PSU / total power sensors when available

### Hosts
- Device tracker entities for MACs learned on `!dhost.b`

## Compatibility

Tested with:

| Model | OS | Versions |
| - | - | - |
| CSS326-24G-2S+ | SwitchOS | 2.18 |
| CRS326-24G-2S+ | SwitchOS | 2.18 |
| CSS610-8P-2S+ | SwitchOS Lite | 2.20, 2.21 |

## Notes

- SwitchOS has no official API, CLI, or SNMP write support. This integration uses the same digest-auth HTTP endpoints as the web UI.
- Writes use read-modify-write of the full writable endpoint payload (MikroTik web UI behavior).
- Upstream sync PRs are opened automatically when `probert94/ha-switchos` advances.

## License

MIT (see `LICENSE`).
