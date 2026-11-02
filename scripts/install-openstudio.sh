#!/usr/bin/env bash
# Install the pinned residential engine on Ubuntu 24.04 x86_64.
# OpenStudio 3.11.0 (241b8abb4d) + OpenStudio-HPXML v1.12.0 (EnergyPlus 25.2.0).
set -euo pipefail

OS_URL="https://github.com/NatLabRockies/OpenStudio/releases/download/v3.11.0/OpenStudio-3.11.0%2B241b8abb4d-Ubuntu-24.04-x86_64.tar.gz"
HPXML_URL="https://github.com/NatLabRockies/OpenStudio-HPXML/releases/download/v1.12.0/OpenStudio-HPXML-v1.12.0.zip"
PREFIX_OS="${OPENSTUDIO_PREFIX:-/usr/local/openstudio-3.11.0}"
PREFIX_HPXML="${OPENSTUDIO_HPXML_DIR:-/opt/OpenStudio-HPXML-1.12.0}"
WORKDIR="${TMPDIR:-/tmp}/hems-openstudio-install"

mkdir -p "$WORKDIR"
curl -fL --retry 4 --retry-delay 4 -o "$WORKDIR/openstudio.tar.gz" "$OS_URL"
curl -fL --retry 4 --retry-delay 4 -o "$WORKDIR/oshpxml.zip" "$HPXML_URL"

sudo mkdir -p /usr/local /opt
rm -rf "$WORKDIR/os-extract"
mkdir -p "$WORKDIR/os-extract"
tar -xzf "$WORKDIR/openstudio.tar.gz" -C "$WORKDIR/os-extract"
# Tarball contains usr/local/openstudio-3.11.0
EXTRACTED="$(find "$WORKDIR/os-extract" -type f -name openstudio -path '*/bin/openstudio' | head -1)"
if [[ -z "$EXTRACTED" ]]; then
  echo "openstudio binary not found in tarball" >&2
  exit 1
fi
SRC_ROOT="$(cd "$(dirname "$EXTRACTED")/.." && pwd)"
sudo rm -rf "$PREFIX_OS"
sudo mkdir -p "$(dirname "$PREFIX_OS")"
sudo mv "$SRC_ROOT" "$PREFIX_OS"

rm -rf "$WORKDIR/hpxml-extract"
mkdir -p "$WORKDIR/hpxml-extract"
python3 - <<PY
import zipfile
zipfile.ZipFile("$WORKDIR/oshpxml.zip").extractall("$WORKDIR/hpxml-extract")
PY
HPXML_SRC="$(find "$WORKDIR/hpxml-extract" -name run_simulation.rb | head -1)"
sudo rm -rf "$PREFIX_HPXML"
sudo mv "$(dirname "$(dirname "$HPXML_SRC")")" "$PREFIX_HPXML"

"$PREFIX_OS/bin/openstudio" --version
test -f "$PREFIX_HPXML/workflow/run_simulation.rb"
test -f "$PREFIX_HPXML/weather/USA_CO_Denver.Intl.AP.725650_TMY3.epw"
echo "Installed:"
echo "  OPENSTUDIO_CLI=$PREFIX_OS/bin/openstudio"
echo "  OPENSTUDIO_HPXML_DIR=$PREFIX_HPXML"
echo "Weather: OS-HPXML 1.12.0 ships selected TMY3 files, including Denver Intl AP."
