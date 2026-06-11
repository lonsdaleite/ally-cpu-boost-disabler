# Ally CPU Boost Disabler

Decky Loader plugin for **ASUS ROG Xbox Ally X**: disable CPU boost and optionally run a power-change workaround when boost is off.

> **Device:** this targets the **Xbox** Ally X (ROG Xbox Ally X), not the original ROG Ally or the non-Xbox ROG Ally X. The CPU cap refresh workaround was written for the amd-pstate / CPPC behavior seen on **Xbox Ally X** under SteamOS / Bazzite.

## Features

- **CPU Boost** — toggle `/sys/devices/system/cpu/cpufreq/boost` on or off
- **Refresh CPU cap on charger plug/unplug** — shown only when boost is disabled; installs a systemd/udev daemon that briefly nudges `scaling_max_freq` after AC plug/unplug (same idea as [ally-x-cpu-cap-refresh](https://github.com/lonsdaleite/ally-x-cpu-cap-refresh))

When CPU boost is turned back on, the workaround daemon is removed automatically. If boost is disabled again and the second toggle was enabled, the daemon is reinstalled.

## Install

### From GitHub Release (recommended)

1. Open [Releases](https://github.com/lonsdaleite/ally-cpu-boost-disabler/releases)
2. Download the latest `ally-cpu-boost-disabler-v*.zip` from Releases (not the Source code archive)
3. On the Xbox Ally X: **Decky Loader → Settings → Developer → Install plugin from ZIP**
4. Select the downloaded zip

Release zips must contain a top-level folder named like `plugin.json` → `"name"` (for example `Ally CPU Boost Disabler/plugin.json`). A flat zip with files in the archive root will not install via Decky.

To build a release zip locally:

```bash
npm install
./release.sh   # Linux / macOS / SteamOS
# or: pwsh ./release.ps1
```

### Build from source

```bash
git clone https://github.com/lonsdaleite/ally-cpu-boost-disabler.git
cd ally-cpu-boost-disabler
npm install
npm run build
cp -r . "$HOME/homebrew/plugins/Ally CPU Boost Disabler"
sudo systemctl restart plugin_loader
```

The plugin folder name must match `"name"` in `plugin.json`: `Ally CPU Boost Disabler`.

## Requirements

- [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader)
- **ASUS ROG Xbox Ally X** (SteamOS / Bazzite or similar Linux)
- CPU boost sysfs node: `/sys/devices/system/cpu/cpufreq/boost` (may exist on other handhelds, but the power workaround is **Xbox Ally X–specific**)
- Plugin runs with **root** flag (required for sysfs and installing the workaround daemon)

## Power refresh workaround

On **ROG Xbox Ally X**, addresses an `amd-pstate-epp` / CPPC issue where, after plugging or unplugging the charger with boost disabled, CPU frequency caps may stop being enforced.

The daemon runs on `AC0` mains power supply changes and executes:

```text
scaling_max_freq: current → current - 30 MHz → current
```

Installed files (only while the second toggle is on and boost is off):

- `/var/lib/ally-cpu-boost-disabler/refresh-cpu-cap.sh`
- `/etc/systemd/system/ally-cpu-boost-disabler-cap-refresh.service`
- `/etc/udev/rules.d/99-ally-cpu-boost-disabler-cap-refresh.rules`

Manual test:

```bash
sudo systemctl start ally-cpu-boost-disabler-cap-refresh.service
journalctl -u ally-cpu-boost-disabler-cap-refresh.service --since "2 minutes ago" --no-pager
```

## Related projects

- [ally-x-cpu-cap-refresh](https://github.com/lonsdaleite/ally-x-cpu-cap-refresh) — standalone workaround script
- [allycenter](https://github.com/PixelAddictUnlocked/allycenter) — broader ROG Ally Decky control center (also has CPU boost toggle)

## License

MIT
