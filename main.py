"""
ally-cpu-boost-disabler - Decky Loader Plugin Backend
CPU boost control and power-change CPU cap refresh workaround for ROG Ally X.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import decky

SYSTEMCTL = shutil.which("systemctl") or "/usr/bin/systemctl"
UDEVADM = shutil.which("udevadm") or "/usr/bin/udevadm"

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
INSTALL_SCRIPT_SRC = "install-daemon.sh"

class Plugin:
    settings_path: str = ""
    settings: dict = {}
    last_error: str = ""

    def _backend_path(self, filename: str) -> str:
        return os.path.join(decky.DECKY_PLUGIN_DIR, BACKEND_DIR, filename)

    def _refresh_script_path(self) -> str | None:
        if os.path.exists(SCRIPT_DST):
            return SCRIPT_DST
        bundled = self._backend_path(SCRIPT_SRC)
        if os.path.exists(bundled):
            return bundled
        return None

    def _set_error(self, message: str) -> str:
        self.last_error = message
        decky.logger.error(message)
        return message

    def _read_boost_enabled(self) -> bool:
        try:
            if not os.path.exists(BOOST_PATH):
                return True
            with open(BOOST_PATH, "r", encoding="utf-8") as f:
                return f.read().strip() == "1"
        except Exception as e:
            decky.logger.error(f"Failed to read CPU boost state: {e}")
            return self.settings.get("cpu_boost_enabled", True)

    def _boost_enabled_from_settings(self) -> bool:
        return bool(self.settings.get("cpu_boost_enabled", True))

    async def _main(self):
        self.settings_path = os.path.join(
            decky.DECKY_PLUGIN_SETTINGS_DIR, "settings.json"
        )
        await self.load_settings()
        decky.logger.info(
            "ally-cpu-boost-disabler initialized (euid=%s, plugin_dir=%s)",
            os.geteuid(),
            decky.DECKY_PLUGIN_DIR,
        )
        await self._apply_settings()

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

    def _install_log_path(self) -> str:
        return os.path.join(decky.DECKY_PLUGIN_RUNTIME_DIR, "install.log")

    def _install_log(self, message: str):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
        decky.logger.info(line)
        try:
            os.makedirs(decky.DECKY_PLUGIN_RUNTIME_DIR, exist_ok=True)
            with open(self._install_log_path(), "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            decky.logger.error(f"Failed to write install log: {e}")

    def _read_install_log_tail(self, lines: int = 12) -> str:
        path = self._install_log_path()
        try:
            if not os.path.exists(path):
                return ""
            with open(path, "r", encoding="utf-8") as f:
                content = f.readlines()
            return "".join(content[-lines:]).strip()
        except Exception as e:
            return f"Could not read install log: {e}"

    def _record_power_refresh_error(self, message: str):
        self._set_error(message)
        self.settings["power_refresh_last_error"] = message
        self._install_log(f"ERROR: {message}")
        return message

    def _clear_power_refresh_error(self):
        self.last_error = ""
        self.settings.pop("power_refresh_last_error", None)

    def _read_lf_bytes(self, src: str) -> bytes:
        with open(src, "rb") as f:
            return f.read().replace(b"\r\n", b"\n").replace(b"\r", b"\n")

    def _system_command_env(self) -> dict:
        """Clean env for system binaries.

        Decky's PyInstaller runtime sets LD_LIBRARY_PATH to bundled OpenSSL,
        which breaks systemctl/udevadm linked against the host libcrypto.
        """
        env = {
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }
        for key in ("HOME", "USER", "LOGNAME", "SHELL"):
            if key in os.environ:
                env[key] = os.environ[key]
        return env

    def _stage_backend_lf(self) -> str:
        staging_dir = tempfile.mkdtemp(prefix="ally-cpu-boost-install-")
        for name in (SCRIPT_SRC, SERVICE_SRC, UDEV_SRC, INSTALL_SCRIPT_SRC):
            src = self._backend_path(name)
            dst = os.path.join(staging_dir, name)
            with open(dst, "wb") as f:
                f.write(self._read_lf_bytes(src))
            if name.endswith(".sh"):
                os.chmod(dst, 0o755)
        return staging_dir

    def _power_refresh_install_status(self) -> dict:
        return {
            "script": os.path.exists(SCRIPT_DST),
            "service": os.path.exists(SERVICE_DST),
            "udev": os.path.exists(UDEV_DST),
        }

    def _is_power_refresh_installed(self) -> bool:
        return (
            os.path.exists(SCRIPT_DST)
            and os.path.exists(SERVICE_DST)
            and os.path.exists(UDEV_DST)
        )

    def _run_command(self, args: list[str], *, record_error: bool = True) -> bool:
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                check=False,
                env=self._system_command_env(),
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "").strip()
                message = (
                    f"{' '.join(args)} failed"
                    + (f": {detail}" if detail else "")
                )
                if record_error:
                    self._set_error(message)
                else:
                    self._install_log(f"WARNING: {message}")
                return False
            return True
        except Exception as e:
            message = f"{' '.join(args)} error: {e}"
            if record_error:
                self._set_error(message)
            else:
                self._install_log(f"WARNING: {message}")
            return False

    def _reload_systemd_udev(self) -> bool:
        if not self._run_command([SYSTEMCTL, "daemon-reload"]):
            return False
        return self._run_command([UDEVADM, "control", "--reload-rules"])

    def _require_root_for_system_install(self) -> bool:
        if os.geteuid() == 0:
            return True
        self._record_power_refresh_error(
            "Power refresh install needs root. Ensure Decky runs as root "
            "(sudo systemctl restart plugin_loader) and the plugin has the root flag."
        )
        return False

    async def install_power_refresh(self) -> bool:
        self.last_error = ""
        self._install_log("install_power_refresh: start")
        try:
            if not self._require_root_for_system_install():
                await self.save_settings()
                return False

            install_script = self._backend_path(INSTALL_SCRIPT_SRC)
            if not os.path.exists(install_script):
                self._record_power_refresh_error(
                    f"Missing install script: {install_script}"
                )
                await self.save_settings()
                return False

            staging_dir = self._stage_backend_lf()
            try:
                staged_install = os.path.join(staging_dir, INSTALL_SCRIPT_SRC)
                env = self._system_command_env()
                env["DECKY_PLUGIN_RUNTIME_DIR"] = decky.DECKY_PLUGIN_RUNTIME_DIR
                self._install_log(f"Running install-daemon.sh from {staging_dir}")
                result = subprocess.run(
                    ["/usr/bin/bash", staged_install],
                    capture_output=True,
                    text=True,
                    check=False,
                    env=env,
                )
                if result.stdout.strip():
                    self._install_log(result.stdout.strip())
                if result.returncode != 0:
                    detail = (result.stderr or result.stdout or "").strip()
                    self._record_power_refresh_error(
                        f"install-daemon.sh failed (code {result.returncode})"
                        + (f": {detail}" if detail else "")
                    )
                    await self.save_settings()
                    return False
            finally:
                shutil.rmtree(staging_dir, ignore_errors=True)

            self._clear_power_refresh_error()
            await self.save_settings()
            self._install_log("install_power_refresh: success")
            return True
        except PermissionError:
            self._record_power_refresh_error(
                "Permission denied writing to /var/lib or /etc. "
                "Decky plugin backend must run as root."
            )
            await self.save_settings()
            return False
        except Exception as e:
            self._record_power_refresh_error(f"Failed to install power refresh: {e}")
            await self.save_settings()
            return False

    async def uninstall_power_refresh(self) -> bool:
        self.last_error = ""
        try:
            if not self._require_root_for_system_install():
                return False

            for target in (SCRIPT_DST, SERVICE_DST, UDEV_DST):
                if os.path.exists(target):
                    os.remove(target)

            if os.path.isdir(SCRIPT_DST_DIR) and not os.listdir(SCRIPT_DST_DIR):
                os.rmdir(SCRIPT_DST_DIR)

            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)

            self._reload_systemd_udev()
            decky.logger.info("Uninstalled power refresh workaround")
            return True
        except PermissionError:
            self._set_error(
                "Permission denied removing system files. "
                "Decky plugin backend must run as root."
            )
            return False
        except Exception as e:
            self._set_error(f"Failed to uninstall power refresh: {e}")
            return False

    async def _sync_power_refresh(self) -> bool:
        boost_enabled = self._boost_enabled_from_settings()
        want_refresh = (
            not boost_enabled and self.settings.get("power_refresh_enabled", False)
        )
        installed = self._is_power_refresh_installed()

        if want_refresh and not installed:
            ok = await self.install_power_refresh()
            if not ok:
                decky.logger.error(
                    "Power refresh auto-install failed on startup: %s",
                    self.last_error,
                )
            return ok
        if not want_refresh and installed:
            return await self.uninstall_power_refresh()
        return True

    async def _apply_settings(self):
        if "cpu_boost_enabled" in self.settings:
            await self.set_cpu_boost_enabled(self.settings["cpu_boost_enabled"])
        await self._sync_power_refresh()
        decky.logger.info("Applied saved settings")

    def _read_plugin_version(self) -> str:
        try:
            package_json = Path(decky.DECKY_PLUGIN_DIR) / "package.json"
            if package_json.exists():
                with open(package_json, "r", encoding="utf-8") as f:
                    return json.load(f).get("version", "unknown")
        except Exception as e:
            decky.logger.error(f"Failed to read plugin version: {e}")
        return "unknown"

    def _coerce_bool(self, value) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)

    async def get_cpu_settings(self) -> dict:
        boost_enabled = self._boost_enabled_from_settings()
        boost_sysfs = self._read_boost_enabled()
        backend_script = self._backend_path(SCRIPT_SRC)

        power_refresh_installed = self._is_power_refresh_installed()
        power_refresh_enabled = bool(
            self.settings.get("power_refresh_enabled", False)
        )

        return {
            "boost_enabled": boost_enabled,
            "boost_sysfs_enabled": boost_sysfs,
            "boost_sysfs_mismatch": boost_enabled != boost_sysfs,
            "boost_available": os.path.exists(BOOST_PATH),
            "power_refresh_enabled": power_refresh_enabled,
            "power_refresh_installed": power_refresh_installed,
            "power_refresh_available": os.path.exists(backend_script),
            "power_refresh_mismatch": power_refresh_enabled and not power_refresh_installed,
            "power_refresh_last_error": self.settings.get(
                "power_refresh_last_error", self.last_error
            ),
            "power_refresh_install_status": self._power_refresh_install_status(),
            "running_as_root": os.geteuid() == 0,
            "effective_uid": os.geteuid(),
            "plugin_dir": decky.DECKY_PLUGIN_DIR,
            "backend_script_path": backend_script,
            "log_path": decky.DECKY_PLUGIN_LOG,
            "install_log_path": self._install_log_path(),
            "install_debug_tail": self._read_install_log_tail(),
            "settings_path": self.settings_path,
            "plugin_version": self._read_plugin_version(),
        }

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

    async def apply_power_refresh_toggle(self, enabled) -> int:
        """Fire-and-forget style action. Frontend must call get_cpu_settings() after."""
        enabled = self._coerce_bool(enabled)
        self.last_error = ""
        self._install_log(
            f"apply_power_refresh_toggle({enabled}) euid={os.geteuid()} "
            f"boost={self._read_boost_enabled()} plugin_dir={decky.DECKY_PLUGIN_DIR}"
        )

        if enabled and self._boost_enabled_from_settings():
            self._record_power_refresh_error(
                "Disable CPU boost before enabling power refresh."
            )
            await self.save_settings()
            return 0

        backend_script = self._backend_path(SCRIPT_SRC)
        if enabled and not os.path.exists(backend_script):
            self._record_power_refresh_error(
                f"Plugin backend files missing at {backend_script}. "
                "Reinstall the plugin zip and restart Decky."
            )
            await self.save_settings()
            return 0

        if enabled:
            success = await self.install_power_refresh()
        else:
            success = await self.uninstall_power_refresh()

        if success:
            self.settings["power_refresh_enabled"] = enabled
            if not enabled:
                self._clear_power_refresh_error()
            await self.save_settings()
            self._install_log(
                f"apply_power_refresh_toggle: success enabled={enabled}"
            )
            return 1

        error = self.last_error or "Failed to change power refresh setting."
        self.settings["power_refresh_last_error"] = error
        await self.save_settings()
        self._install_log(f"apply_power_refresh_toggle: failed: {error}")
        return 0

    async def manual_refresh_cpu_cap(self) -> dict:
        if self._boost_enabled_from_settings():
            return {
                "success": False,
                "message": "Disable CPU boost before manual refresh.",
            }

        if os.geteuid() != 0:
            return {
                "success": False,
                "message": (
                    "Manual refresh needs root. Run: sudo systemctl restart "
                    "plugin_loader"
                ),
            }

        script_path = self._refresh_script_path()
        if not script_path:
            return {
                "success": False,
                "message": (
                    "refresh-cpu-cap.sh not found. Reinstall the plugin zip "
                    "and restart Decky."
                ),
            }

        self._install_log(f"manual_refresh_cpu_cap: running {script_path}")
        try:
            result = subprocess.run(
                ["/usr/bin/bash", script_path],
                capture_output=True,
                text=True,
                check=False,
                env=self._system_command_env(),
            )
            output = (result.stdout or "").strip()
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "").strip()
                message = (
                    f"Manual refresh failed (code {result.returncode})"
                    + (f": {detail}" if detail else "")
                )
                decky.logger.error(message)
                self._install_log(f"manual_refresh_cpu_cap: {message}")
                return {"success": False, "message": message}

            message = output or "CPU cap refreshed."
            decky.logger.info("Manual refresh: %s", message)
            self._install_log(f"manual_refresh_cpu_cap: success: {message}")
            return {"success": True, "message": message}
        except Exception as e:
            message = f"Manual refresh error: {e}"
            decky.logger.error(message)
            self._install_log(f"manual_refresh_cpu_cap: {message}")
            return {"success": False, "message": message}
