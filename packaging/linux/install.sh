#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Installs the Tessera engine for the current user (SPEC-TS-0023 FR-030/031).
#
# Per-user, no root. The engine binds a loopback port and reads a weight cache
# the add-on owns; nothing it does needs system-wide privilege, and asking for
# it would be asking the user to trust more than the job requires.
#
# Writes the installation marker the add-on discovers the engine by. The
# marker's presence is the definition of "installed" — probing the port cannot
# answer that, because nothing listening means stopped or absent and those want
# opposite advice (FR-031, EC-001).

set -euo pipefail

PREFIX="${TESSERA_ENGINE_PREFIX:-${XDG_DATA_HOME:-$HOME/.local/share}/tessera/engine}"
MARKER_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/tessera/engine"
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing the Tessera engine to ${PREFIX}"

if [[ -d "$PREFIX/venv" ]]; then
    echo "Replacing the existing installation..."
    rm -rf "$PREFIX/venv" "$PREFIX/tessera_engine"
fi
mkdir -p "$PREFIX"
cp -r "$SOURCE/venv" "$PREFIX/venv"
cp -r "$SOURCE/tessera_engine" "$PREFIX/tessera_engine"
cp "$SOURCE/LICENSE" "$PREFIX/LICENSE"
cp "$SOURCE/build-info.json" "$PREFIX/build-info.json"

# The venv's shebangs point at wherever it was built. Re-point them, or the
# engine runs against the build machine's paths and fails somewhere confusing.
"$PREFIX/venv/bin/python" - <<'PY'
import pathlib, sys, sysconfig
# venv relocation: rewrite the config so the interpreter resolves in place.
cfg = pathlib.Path(sys.prefix) / "pyvenv.cfg"
if cfg.exists():
    lines = []
    for line in cfg.read_text().splitlines():
        if line.startswith("home ="):
            line = f"home = {pathlib.Path(sys.base_prefix) / 'bin'}"
        lines.append(line)
    cfg.write_text("\n".join(lines) + "\n")
PY

LAUNCHER="$PREFIX/bin/tessera-engine"
mkdir -p "$PREFIX/bin"
cat > "$LAUNCHER" <<LAUNCH
#!/usr/bin/env bash
# Launcher for the Tessera engine. The add-on invokes this with the cache
# root it governs; the engine never resolves weights itself (FR-033).
exec "${PREFIX}/venv/bin/python" -m tessera_engine "\$@"
LAUNCH
chmod +x "$LAUNCHER"
# PYTHONPATH so the copied package is importable without a wheel install.
sed -i "2i export PYTHONPATH=\"${PREFIX}:\${PYTHONPATH:-}\"" "$LAUNCHER"

ENGINE_VERSION="$("$PREFIX/venv/bin/python" -c "
import json,pathlib
print(json.loads(pathlib.Path('$PREFIX/build-info.json').read_text())['engine_version'])")"
PROTOCOL_VERSIONS="$(PYTHONPATH="$PREFIX" "$PREFIX/venv/bin/python" -c "
import json
from tessera_engine import PROTOCOL_VERSIONS
print(json.dumps(sorted(PROTOCOL_VERSIONS)))")"

mkdir -p "$MARKER_DIR"
cat > "$MARKER_DIR/install.json" <<MARKER
{
  "engine_version": "${ENGINE_VERSION}",
  "protocol_versions": ${PROTOCOL_VERSIONS},
  "executable": "${LAUNCHER}"
}
MARKER

echo
echo "Installed engine ${ENGINE_VERSION}"
echo "  executable: ${LAUNCHER}"
echo "  marker:     ${MARKER_DIR}/install.json"
echo
echo "Tessera will find it automatically. Nothing else to do."
