#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${DECKY_PLUGIN_RUNTIME_DIR:-/tmp}/install.log"

log() {
  echo "$(date -Iseconds) $*" | tee -a "$LOG_FILE"
}

if [[ "${EUID}" -ne 0 ]]; then
  log "install-daemon.sh: must run as root (euid=${EUID})"
  exit 1
fi

SCRIPT_DST_DIR="/var/lib/ally-cpu-boost-disabler"
SCRIPT_DST="${SCRIPT_DST_DIR}/refresh-cpu-cap.sh"
SERVICE_DST="/etc/systemd/system/ally-cpu-boost-disabler-cap-refresh.service"
UDEV_DST="/etc/udev/rules.d/99-ally-cpu-boost-disabler-cap-refresh.rules"

log "install-daemon.sh: start from ${SCRIPT_DIR}"

mkdir -p "${SCRIPT_DST_DIR}"
install -m 755 "${SCRIPT_DIR}/refresh-cpu-cap.sh" "${SCRIPT_DST}"
install -m 644 "${SCRIPT_DIR}/ally-cpu-boost-disabler-cap-refresh.service" "${SERVICE_DST}"
install -m 644 "${SCRIPT_DIR}/99-ally-cpu-boost-disabler-cap-refresh.rules" "${UDEV_DST}"

systemctl daemon-reload
udevadm control --reload-rules

log "install-daemon.sh: done"
