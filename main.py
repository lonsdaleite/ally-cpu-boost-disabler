"""
ally-cpu-boost-disabler - Decky Loader Plugin Backend
CPU boost control and power-change CPU cap refresh workaround for ROG Ally X.
"""

import json
import os
import shutil
import subprocess

import decky

BOOST_PATH = "/sys/devices/system/cpu/cpufreq/boost"

SCRIPT_DST_DIR = "/var/lib/ally-cpu-boost-disabler"
SCRIPT_DST = f"{SCRIPT_DST_DIR}/refresh-cpu-cap.sh"
SERVICE_DST = "/etc/systemd/system/ally-cpu-boost-disabler-cap-refresh.service"
UDEV_DST = "/etc/udev/rules.d/99-ally-cpu-boost-disabler-cap-refresh.rules"
LOCK_FILE = "/run/ally-cpu-boost-disabler-cap-refresh.lock"

BACKEND_DIR = "backend"
SCRIPT_SRC = "refresh-cpu-cap.sh"
SERVICE_SRC = "ally-cpu-boost-disabler-cap-refresh.service"
UDEV_SRC = "99-ally-cpu-boost-disabler-cap-refresh.rules"


class Plugin:
    settings_path: str = ""
    settings: dict = {}

    def _backend_path(self, filename: str) -> str:
        return os.path.join(decky.DECKY_PLUGIN_DIR, BACKEND_DIR, filename)

    async def _main(self):
        self.settings_path = os.path.join(
            decky.DECKY_PLUGIN_SETTINGS_DIR, "settings.json"
        )
        await self.load_settings()
        await self._apply_settings()
        decky.logger.info("ally-cpu-boost-disabler initialized")

    async def _unload(self):
        decky.logger.info("ally-cpu-boost-disabler unloaded")

    async def _migration(self):
        pass

    async def load_settings(self):
        defaults = {
            "cpu_boost_enabled": True,
            "power_refresh_enabled": False,
        }
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self.settings = {**defaults, **loaded}
            else:
                self.settings = defaults.copy()
                await self.save_settings()
        except Exception as e:
            decky.logger.error(f"Failed to load settings: {e}")
            self.settings = defaults.copy()
        return self.settings

    async def save_settings(self):
        try:
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            decky.logger.error(f"Failed to save settings: {e}")

    def _is_power_refresh_installed(self) -> bool:
        return (
            os.path.exists(SCRIPT_DST)
            and os.path.exists(SERVICE_DST)
            and os.path.exists(UDEV_DST)
        )

    def _run_systemctl(self, *args: str) -> bool:
        try:
            result = subprocess.run(
                ["systemctl", *args],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                decky.logger.error(
                    f"systemctl {' '.join(args)} failed: {result.stderr.strip()}"
                )
                return False
            return True
        except Exception as e:
            decky.logger.error(f"systemctl {' '.join(args)} error: {e}")
            return False

    def _reload_systemd_udev(self) -> bool:
        ok = self._run_systemctl("daemon-reload")
        try:
            result = subprocess.run(
                ["udevadm", "control", "--reload-rules"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                decky.logger.error(
                    f"udevadm reload failed: {result.stderr.strip()}"
                )
                ok = False
        except Exception as e:
            decky.logger.error(f"udevadm reload error: {e}")
            ok = False
        return ok

    async def install_power_refresh(self) -> bool:
        try:
            script_src = self._backend_path(SCRIPT_SRC)
            service_src = self._backend_path(SERVICE_SRC)
            udev_src = self._backend_path(UDEV_SRC)

            for path in (script_src, service_src, udev_src):
                if not os.path.exists(path):
                    decky.logger.error(f"Missing backend file: {path}")
                    return False

            os.makedirs(SCRIPT_DST_DIR, exist_ok=True)
            shutil.copy2(script_src, SCRIPT_DST)
            os.chmod(SCRIPT_DST, 0o755)
            shutil.copy2(service_src, SERVICE_DST)
            shutil.copy2(udev_src, UDEV_DST)

            if not self._reload_systemd_udev():
                return False

            decky.logger.info("Installed power refresh workaround")
            return True
        except PermissionError:
            decky.logger.error(
                "Permission denied installing power refresh - requires root"
            )
            return False
        except Exception as e:
            decky.logger.error(f"Failed to install power refresh: {e}")
            return False

    async def uninstall_power_refresh(self) -> bool:
        try:
            for path in (SCRIPT_DST, SERVICE_DST, UDEV_DST):
                if os.path.exists(path):
                    os.remove(path)

            if os.path.isdir(SCRIPT_DST_DIR) and not os.listdir(SCRIPT_DST_DIR):
                os.rmdir(SCRIPT_DST_DIR)

            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)

            self._reload_systemd_udev()
            decky.logger.info("Uninstalled power refresh workaround")
            return True
        except PermissionError:
            decky.logger.error(
                "Permission denied uninstalling power refresh - requires root"
            )
            return False
        except Exception as e:
            decky.logger.error(f"Failed to uninstall power refresh: {e}")
            return False

    async def _sync_power_refresh(self) -> bool:
        boost_enabled = self.settings.get("cpu_boost_enabled", True)
        want_refresh = (
            not boost_enabled and self.settings.get("power_refresh_enabled", False)
        )
        installed = self._is_power_refresh_installed()

        if want_refresh and not installed:
            return await self.install_power_refresh()
        if not want_refresh and installed:
            return await self.uninstall_power_refresh()
        return True

    async def _apply_settings(self):
        if "cpu_boost_enabled" in self.settings:
            await self.set_cpu_boost_enabled(self.settings["cpu_boost_enabled"])
        await self._sync_power_refresh()
        decky.logger.info("Applied saved settings")

    async def get_cpu_settings(self) -> dict:
        result = {
            "boost_enabled": True,
            "boost_available": os.path.exists(BOOST_PATH),
            "power_refresh_enabled": self.settings.get(
                "power_refresh_enabled", False
            ),
            "power_refresh_installed": self._is_power_refresh_installed(),
            "power_refresh_available": os.path.exists(
                self._backend_path(SCRIPT_SRC)
            ),
        }

        try:
            if os.path.exists(BOOST_PATH):
                with open(BOOST_PATH, "r", encoding="utf-8") as f:
                    result["boost_enabled"] = f.read().strip() == "1"
        except Exception as e:
            decky.logger.error(f"Failed to read CPU boost state: {e}")

        return result

    async def set_cpu_boost_enabled(self, enabled: bool) -> bool:
        try:
            if not os.path.exists(BOOST_PATH):
                decky.logger.warning("CPU boost control not available")
                return False

            with open(BOOST_PATH, "w", encoding="utf-8") as f:
                f.write("1" if enabled else "0")

            self.settings["cpu_boost_enabled"] = enabled
            await self.save_settings()
            await self._sync_power_refresh()

            decky.logger.info(f"CPU boost {'enabled' if enabled else 'disabled'}")
            return True
        except PermissionError:
            decky.logger.error("Permission denied setting CPU boost - requires root")
            return False
        except Exception as e:
            decky.logger.error(f"Failed to set CPU boost: {e}")
            return False

    async def set_power_refresh_enabled(self, enabled: bool) -> bool:
        if self.settings.get("cpu_boost_enabled", True):
            decky.logger.warning(
                "Power refresh is only applicable when CPU boost is disabled"
            )
            return False

        self.settings["power_refresh_enabled"] = enabled
        await self.save_settings()

        if enabled:
            success = await self.install_power_refresh()
        else:
            success = await self.uninstall_power_refresh()

        if success:
            decky.logger.info(
                f"Power refresh workaround {'enabled' if enabled else 'disabled'}"
            )
        return success
