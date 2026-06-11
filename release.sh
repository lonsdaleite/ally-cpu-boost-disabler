#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VERSION="$(node -p "require('./package.json').version")"
PLUGIN_NAME="$(node -p "require('./plugin.json').name")"
STAGING_DIR="release-staging/${PLUGIN_NAME}"
ZIP_NAME="${PLUGIN_NAME}-v${VERSION}.zip"

echo "Building ${PLUGIN_NAME} v${VERSION}..."
npm run build

rm -rf release-staging
mkdir -p "$STAGING_DIR"

cp -r dist main.py plugin.json package.json LICENSE README.md backend "$STAGING_DIR/"

rm -f "${PLUGIN_NAME}"-v*.zip
(
  cd release-staging
  zip -r "../${ZIP_NAME}" "$PLUGIN_NAME" -x "*.DS_Store"
)

echo "Created ${ZIP_NAME}"
unzip -l "${ZIP_NAME}"
