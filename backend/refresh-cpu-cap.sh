#!/bin/bash
set -eu

# Wait for late USB-C/PD/EC power events after the initial mains event.
START_DELAY_SECONDS=1

# Need a large enough step to change effective CPPC MAX.
# On Ally X: 2000000 -> 1970000 changes CPPC MAX 77 -> 76.
MAX_FREQ_STEP_KHZ=30000

LOCK_FILE="/run/ally-cpu-boost-disabler-cap-refresh.lock"
CPU_PATH="/sys/devices/system/cpu"

if [[ "${EUID}" -ne 0 ]]; then
  echo "This script must be run as root. Try: sudo $0" >&2
  exit 1
fi

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "Skipped: busy"
  exit 0
fi

sleep "$START_DELAY_SECONDS"

CPU0_MAX="$CPU_PATH/cpu0/cpufreq/scaling_max_freq"
CPU0_MIN="$CPU_PATH/cpu0/cpufreq/scaling_min_freq"

cur="$(cat "$CPU0_MAX")"
min="$(cat "$CPU0_MIN")"

tmp=$((cur - MAX_FREQ_STEP_KHZ))

if (( tmp < min )); then
  tmp="$min"
fi

if (( tmp == cur )); then
  echo "Cannot refresh CPU cap: temporary max equals current max ($cur)" >&2
  exit 1
fi

write_all_max_freq() {
  local value="$1"
  local found=0

  for f in "$CPU_PATH"/cpu[0-9]*/cpufreq/scaling_max_freq; do
    [[ -e "$f" ]] || continue
    found=1

    if [[ ! -w "$f" ]]; then
      echo "No write permission for $f. Run as root." >&2
      exit 2
    fi

    echo "$value" > "$f"
  done

  if (( found == 0 )); then
    echo "No scaling_max_freq files found." >&2
    exit 3
  fi
}

echo "Refreshing CPU cap: $cur -> $tmp -> $cur"

write_all_max_freq "$tmp"
sleep 0.2
write_all_max_freq "$cur"

echo "Done."
