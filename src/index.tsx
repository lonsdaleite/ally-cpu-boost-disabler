import {
  definePlugin,
  PanelSection,
  PanelSectionRow,
  ToggleField,
  staticClasses,
} from "@decky/ui";
import { callable, toaster } from "@decky/api";

const { useState, useEffect } = window.SP_REACT;
type VFC<P = {}> = (props: P) => JSX.Element | null;

interface CpuSettings {
  boost_enabled: boolean;
  boost_available: boolean;
  power_refresh_enabled: boolean;
  power_refresh_installed: boolean;
  power_refresh_available: boolean;
}

const getCpuSettings = callable<[], CpuSettings>("get_cpu_settings");
const setCpuBoostEnabled = callable<[boolean], boolean>("set_cpu_boost_enabled");
const setPowerRefreshEnabled = callable<[boolean], boolean>(
  "set_power_refresh_enabled"
);

const PLUGIN_TITLE = "ally-cpu-boost-disabler";

const AllyCpuBoostContent: VFC = () => {
  const [cpuSettings, setCpuSettings] = useState<CpuSettings | null>(null);
  const [boostEnabled, setBoostEnabled] = useState(true);
  const [powerRefreshEnabled, setPowerRefreshEnabled] = useState(false);
  const [loading, setLoading] = useState(true);

  const refreshSettings = async () => {
    try {
      const data = await getCpuSettings();
      setCpuSettings(data);
      setBoostEnabled(data.boost_enabled);
      setPowerRefreshEnabled(data.power_refresh_enabled);
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

  const handlePowerRefreshToggle = async (enabled: boolean) => {
    setPowerRefreshEnabled(enabled);
    const success = await setPowerRefreshEnabled(enabled);
    if (success) {
      await refreshSettings();
      toaster.toast({
        title: PLUGIN_TITLE,
        body: enabled
          ? "Power refresh workaround enabled"
          : "Power refresh workaround disabled",
      });
    } else {
      setPowerRefreshEnabled(!enabled);
      toaster.toast({
        title: PLUGIN_TITLE,
        body: "Failed to change power refresh setting",
      });
    }
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

      {!boostEnabled && powerRefreshEnabled && cpuSettings && (
        <PanelSectionRow>
          <div style={{ color: "#8b929a", fontSize: "12px" }}>
            {cpuSettings.power_refresh_installed
              ? "Daemon active: refreshes scaling_max_freq after power changes"
              : "Daemon not installed — toggle again or check plugin logs"}
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
