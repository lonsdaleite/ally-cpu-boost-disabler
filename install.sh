#!/usr/bin/env bash
set -euo pipefail

REPO="lonsdaleite/ally-cpu-boost-disabler"
PLUGIN_NAME="Ally CPU Boost Disabler"
PLUGINS_DIR="${HOME}/homebrew/plugins"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required." >&2
  exit 1
fi

if ! command -v unzip >/dev/null 2>&1; then
  echo "unzip is required." >&2
  exit 1
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

zip_path="${tmpdir}/plugin.zip"

echo "Fetching latest ${REPO} release..."
release_json="$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest")"
zip_url="$(
  printf '%s\n' "$release_json" \
    | grep -oE "https://github.com/${REPO}/releases/download/[^\"]+ally-cpu-boost-disabler-v[^\"]+\\.zip" \
    | head -n 1
)"

if [[ -z "$zip_url" ]]; then
  echo "Could not find a release zip asset." >&2
  exit 1
fi

echo "Downloading ${zip_url}"
curl -fsSL -o "$zip_path" "$zip_url"

mkdir -p "$PLUGINS_DIR"
rm -rf "${PLUGINS_DIR}/${PLUGIN_NAME}"

echo "Installing to ${PLUGINS_DIR}/${PLUGIN_NAME}"
unzip -q -o "$zip_path" -d "$PLUGINS_DIR"

if [[ ! -f "${PLUGINS_DIR}/${PLUGIN_NAME}/dist/index.js" ]]; then
  echo "Install failed: dist/index.js is missing." >&2
  exit 1
fi

echo "Restarting plugin_loader..."
if sudo systemctl restart plugin_loader; then
  echo "Installed ${PLUGIN_NAME}."
else
  echo "Plugin files are installed, but plugin_loader restart failed." >&2
  echo "Run: sudo systemctl restart plugin_loader" >&2
  exit 1
fi
