import {
  definePlugin,
  PanelSection,
  PanelSectionRow,
  ToggleField,
  ButtonItem,
  staticClasses,
} from "@decky/ui";
import { callable, toaster } from "@decky/api";

const { useState, useEffect } = window.SP_REACT;
type VFC<P = {}> = (props: P) => JSX.Element | null;

interface InstallStatus {
  script: boolean;
  service: boolean;
  udev: boolean;
}

interface CpuSettings {
  boost_enabled: boolean;
  boost_sysfs_enabled: boolean;
  boost_sysfs_mismatch: boolean;
  boost_available: boolean;
  power_refresh_enabled: boolean;
  power_refresh_installed: boolean;
  power_refresh_available: boolean;
  power_refresh_mismatch: boolean;
  power_refresh_last_error: string;
  power_refresh_install_status: InstallStatus;
  running_as_root: boolean;
  effective_uid: number;
  plugin_dir: string;
  backend_script_path: string;
  log_path: string;
  install_log_path: string;
  install_debug_tail: string;
  settings_path: string;
  plugin_version: string;
}

const getCpuSettings = callable<[], CpuSettings>("get_cpu_settings");
const setCpuBoostEnabled = callable<[boolean], boolean>("set_cpu_boost_enabled");
const applyPowerRefreshToggle = callable<[boolean], number>(
  "apply_power_refresh_toggle"
);

const powerRefreshMatchesIntent = (
  enabled: boolean,
  settings: CpuSettings
) => {
  if (enabled) {
    return (
      settings.power_refresh_enabled && settings.power_refresh_installed
    );
  }
  return (
    !settings.power_refresh_enabled && !settings.power_refresh_installed
  );
};

const PLUGIN_TITLE = "Ally CPU Boost Disabler";

const AllyCpuBoostContent: VFC = () => {
  const [cpuSettings, setCpuSettings] = useState<CpuSettings | null>(null);
  const [boostEnabled, setBoostEnabled] = useState(true);
  const [powerRefreshEnabled, setPowerRefreshEnabled] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [loading, setLoading] = useState(true);

  const refreshSettings = async () => {
    try {
      const data = await getCpuSettings();
      setCpuSettings(data);
      setBoostEnabled(data.boost_enabled);
      setPowerRefreshEnabled(data.power_refresh_enabled);
      setErrorMessage(data.power_refresh_last_error || "");
    } catch (e) {
      console.error("Failed to get CPU settings:", e);
    }
  };

  useEffect(() => {
    const load = async () => {
      await refreshSettings();
      setLoading(false);
    };
    load();
  }, []);

  const handleBoostToggle = async (enabled: boolean) => {
    setBoostEnabled(enabled);
    const success = await setCpuBoostEnabled(enabled);
    if (success) {
      await refreshSettings();
      toaster.toast({
        title: PLUGIN_TITLE,
        body: `CPU Boost ${enabled ? "enabled" : "disabled"}`,
      });
    } else {
      setBoostEnabled(!enabled);
      toaster.toast({
        title: PLUGIN_TITLE,
        body: "Failed to change CPU Boost setting",
      });
    }
  };

  const runPowerRefreshAction = async (enabled: boolean) => {
    setPowerRefreshEnabled(enabled);
    setErrorMessage("");

    try {
      await applyPowerRefreshToggle(enabled);
    } catch (e) {
      console.error("apply_power_refresh_toggle:", e);
    }

    let settings: CpuSettings;
    try {
      settings = await getCpuSettings();
    } catch (e) {
      setPowerRefreshEnabled(!enabled);
      setErrorMessage(`get_cpu_settings failed: ${String(e)}`);
      return;
    }

    setCpuSettings(settings);
    setBoostEnabled(settings.boost_enabled);
    setPowerRefreshEnabled(settings.power_refresh_enabled);

    if (powerRefreshMatchesIntent(enabled, settings)) {
      setErrorMessage("");
      toaster.toast({
        title: PLUGIN_TITLE,
        body: enabled
          ? "Power refresh workaround enabled."
          : "Power refresh workaround disabled.",
      });
      return;
    }

    const parts = [
      settings.power_refresh_last_error,
      settings.install_debug_tail,
    ].filter((part) => part && part.length > 0);
    setErrorMessage(
      parts.join("\n") || "Failed to change power refresh setting."
    );
  };

  const handlePowerRefreshToggle = async (enabled: boolean) => {
    await runPowerRefreshAction(enabled);
  };

  const handleRetryInstall = async () => {
    await runPowerRefreshAction(true);
  };

  if (loading) {
    return (
      <PanelSection title="CPU">
        <PanelSectionRow>
          <div style={{ color: "#8b929a" }}>Loading...</div>
        </PanelSectionRow>
      </PanelSection>
    );
  }

  if (!cpuSettings?.boost_available) {
    return (
      <PanelSection title="CPU">
        <PanelSectionRow>
          <div style={{ color: "#8b929a" }}>
            CPU boost control is not available on this device.
          </div>
        </PanelSectionRow>
      </PanelSection>
    );
  }

  return (
    <PanelSection title="CPU">
      <PanelSectionRow>
        <ToggleField
          label="CPU Boost"
          description="Disable to reduce heat and power usage"
          checked={boostEnabled}
          onChange={handleBoostToggle}
        />
      </PanelSectionRow>

      {!boostEnabled && (
        <PanelSectionRow>
          <ToggleField
            label="Refresh CPU cap on charger plug/unplug"
            description="Workaround for amd-pstate cap not being enforced after AC/DC switch when boost is off"
            checked={powerRefreshEnabled}
            onChange={handlePowerRefreshToggle}
          />
        </PanelSectionRow>
      )}

      {cpuSettings?.boost_sysfs_mismatch && (
        <PanelSectionRow>
          <div style={{ color: "#b8860b", fontSize: "12px" }}>
            Saved CPU boost setting could not be applied to hardware (sysfs
            mismatch). Ensure Decky runs as root.
          </div>
        </PanelSectionRow>
      )}

      {!boostEnabled && cpuSettings && !cpuSettings.running_as_root && (
        <PanelSectionRow>
          <div style={{ color: "#b8860b", fontSize: "12px" }}>
            Power refresh needs Decky backend as root. Run: sudo systemctl
            restart plugin_loader
          </div>
        </PanelSectionRow>
      )}

      {!boostEnabled && !cpuSettings?.power_refresh_available && (
        <PanelSectionRow>
          <div style={{ color: "#b8860b", fontSize: "12px" }}>
            Backend scripts missing in plugin install. Reinstall from the release
            zip (v1.0.1+).
          </div>
        </PanelSectionRow>
      )}

      {!boostEnabled && powerRefreshEnabled && cpuSettings && (
        <PanelSectionRow>
          <div style={{ color: "#8b929a", fontSize: "12px" }}>
            {cpuSettings.power_refresh_installed
              ? "Daemon active: refreshes scaling_max_freq after power changes"
              : "Daemon not installed"}
          </div>
        </PanelSectionRow>
      )}

      {!boostEnabled && cpuSettings?.power_refresh_mismatch && (
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={handleRetryInstall}>
            Retry daemon install
          </ButtonItem>
        </PanelSectionRow>
      )}

      {errorMessage && (
        <PanelSectionRow>
          <div
            style={{
              color: "#ff6b6b",
              fontSize: "12px",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}
          >
            {errorMessage}
          </div>
        </PanelSectionRow>
      )}

      {!boostEnabled && cpuSettings && (
        <PanelSectionRow>
          <div style={{ color: "#8b929a", fontSize: "11px" }}>
            v{cpuSettings.plugin_version} | uid={cpuSettings.effective_uid} |
            root={cpuSettings.running_as_root ? "yes" : "no"} | sysfs=
            {cpuSettings.boost_sysfs_enabled ? "on" : "off"} | backend=
            {cpuSettings.power_refresh_available ? "ok" : "missing"} | files=
            {cpuSettings.power_refresh_install_status.script ? "S" : "-"}
            {cpuSettings.power_refresh_install_status.service ? "s" : "-"}
            {cpuSettings.power_refresh_install_status.udev ? "u" : "-"}
          </div>
        </PanelSectionRow>
      )}
    </PanelSection>
  );
};

const AllyCpuBoostIcon: VFC = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" width="1em" height="1em">
    <path d="M13 2.05v2.02c3.95.49 7 3.85 7 7.93 0 1.62-.49 3.12-1.33 4.37l1.46 1.46A9.96 9.96 0 0 0 22 12c0-5.52-4.48-10-10-9.95zM12 4c-4.42 0-8 3.58-8 8 0 1.85.63 3.55 1.69 4.9l1.45-1.45A5.94 5.94 0 0 1 6 12c0-3.31 2.69-6 6-6 1.01 0 1.97.25 2.8.7l1.45-1.45A7.93 7.93 0 0 0 12 4zm-1 6v6h2V10h-2zm-4.24 9.66 1.41 1.41L18.36 3.34 16.95 1.93 6.76 12.12z" />
  </svg>
);

export default definePlugin(() => {
  return {
    name: PLUGIN_TITLE,
    title: <div className={staticClasses.Title}>{PLUGIN_TITLE}</div>,
    content: <AllyCpuBoostContent />,
    icon: <AllyCpuBoostIcon />,
  };
});
