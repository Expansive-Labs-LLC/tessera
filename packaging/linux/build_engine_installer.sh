#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Builds the Linux x64 engine installer (SPEC-TS-0023 FR-030).
#
# The artifact is a self-contained tarball plus an install script. It carries
# its own virtual environment, PyTorch, and TRELLIS's compiled extensions, so
# the user needs no Python, no compiler and no CUDA toolkit — which is the
# whole point: the audience is artists, and ADR-0001 D2 says installation has
# to stay inside what they will tolerate.
#
# The extensions are the reason this is a build job and not a packaging step.
# PyTorch ships a published cu128 wheel; TRELLIS's extensions have none for
# current architectures and compile against a toolkit that knows the target
# compute capability (ADR-0001 premise verification). Whatever architectures
# this build machine's toolkit supports are the architectures the artifact
# serves — CUDA_ARCH_LIST below is the contract, not a hint.
#
# Usage: build_engine_installer.sh <version> [output-dir]

set -euo pipefail

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
    echo "Usage: $0 <version> [output-dir]" >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${2:-$REPO_ROOT/dist}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

# Compute capabilities this artifact is built for. sm_120 is Blackwell
# (RTX 50-series); 8.6 and 8.9 cover Ampere and Ada. A GPU outside this list
# gets a clear refusal at startup rather than a kernel that does not launch.
CUDA_ARCH_LIST="${CUDA_ARCH_LIST:-8.6;8.9;12.0}"
TORCH_INDEX="${TORCH_INDEX:-https://download.pytorch.org/whl/cu128}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

# Prefer the project-local toolchain from provision_toolchain.sh. The distro
# toolkit is frequently too old for current architectures — this workstation
# ships 12.0, which cannot target sm_120 at all — so falling through to
# whatever nvcc happens to be on PATH produces a confusing failure rather
# than a clear one.
if [[ -z "${CUDA_HOME:-}" && -x "$REPO_ROOT/.cuda-toolchain/bin/nvcc" ]]; then
    CUDA_HOME="$REPO_ROOT/.cuda-toolchain"
fi
if [[ -n "${CUDA_HOME:-}" ]]; then
    export CUDA_HOME
    export PATH="$CUDA_HOME/bin:$PATH"
fi

echo "=== Tessera engine installer ${VERSION} (linux-x64) ==="
echo "Target architectures: ${CUDA_ARCH_LIST}"

# --- verify the toolchain can actually serve those architectures -----------
# Failing here is far better than shipping an artifact whose kernels refuse
# to launch on the GPU it was built for.
if ! command -v nvcc >/dev/null 2>&1; then
    echo "ERROR: nvcc not found. TRELLIS's extensions build from source and" >&2
    echo "       need a CUDA toolkit." >&2
    echo "       Run: packaging/linux/provision_toolchain.sh" >&2
    exit 2
fi
for arch in ${CUDA_ARCH_LIST//;/ }; do
    sm="sm_${arch/./}"
    if ! nvcc -arch="$sm" -o /dev/null -x cu - <<<'int main(){return 0;}' 2>/dev/null; then
        echo "ERROR: this CUDA toolkit cannot target ${sm}." >&2
        echo "       $(nvcc --version | tail -1)" >&2
        echo "       Blackwell (sm_120) needs CUDA >= 12.8." >&2
        exit 2
    fi
done
echo "Toolchain check passed: $(nvcc --version | grep release)"

# --- build the engine environment ------------------------------------------
PAYLOAD="$STAGE/tessera-engine"
mkdir -p "$PAYLOAD"
"$PYTHON_BIN" -m venv "$PAYLOAD/venv"
"$PAYLOAD/venv/bin/pip" install --quiet --upgrade pip

echo "Installing PyTorch (published cu128 wheel, no build)..."
"$PAYLOAD/venv/bin/pip" install --quiet torch --index-url "$TORCH_INDEX"

# ninja is a venv console script, and torch's extension builder shells out to
# it by name. Importing torch is not enough — without the venv's bin on PATH
# the build dies reporting that ninja is missing, having just installed it.
"$PAYLOAD/venv/bin/pip" install --quiet ninja

echo "Building TRELLIS extensions from source for ${CUDA_ARCH_LIST}..."
PATH="$PAYLOAD/venv/bin:$PATH" \
TORCH_CUDA_ARCH_LIST="$CUDA_ARCH_LIST" \
    "$PAYLOAD/venv/bin/pip" install --quiet -r "$REPO_ROOT/packaging/linux/requirements-engine.txt"

# The engine itself. Copied, not pip-installed: it is our code, it has no
# build step, and a wheel would add a layer with nothing in it.
cp -r "$REPO_ROOT/tessera_engine" "$PAYLOAD/tessera_engine"
cp "$REPO_ROOT/LICENSE" "$PAYLOAD/LICENSE"
find "$PAYLOAD" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true

# Record what this artifact can actually run, so the engine can refuse a GPU
# it was not built for instead of failing inside a kernel launch.
cat > "$PAYLOAD/build-info.json" <<JSON
{
  "engine_version": "${VERSION}",
  "platform": "linux-x64",
  "cuda_arch_list": "${CUDA_ARCH_LIST}",
  "torch_index": "${TORCH_INDEX}",
  "built": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON

cp "$REPO_ROOT/packaging/linux/install.sh" "$PAYLOAD/install.sh"
chmod +x "$PAYLOAD/install.sh"

# --- trim ------------------------------------------------------------------
# An untrimmed payload does not fit a GitHub release asset. See the script for
# what comes out and why, and for what was tried and rejected.
bash "$REPO_ROOT/packaging/linux/trim_payload.sh" "$PAYLOAD/venv"

# Prove the trim did not remove something the engine needs. Cheaper to find
# here than in a user's install.
echo "Verifying the trimmed environment..."
PATH="$PAYLOAD/venv/bin:$PATH" "$PAYLOAD/venv/bin/python" - <<'SMOKE'
import torch
a = torch.randn(256, 256, device="cuda"); (a @ a.T).sum().item()
c = torch.nn.Conv2d(3, 8, 3).to("cuda"); c(torch.randn(1, 3, 32, 32, device="cuda")).sum().item()
torch.linalg.svd(torch.randn(4, 4, device="cuda"))
torch.fft.fft(torch.randn(32, device="cuda"))
torch.cuda.synchronize()
print("  trimmed environment passes the op smoke test")
SMOKE

# --- package ---------------------------------------------------------------
# xz over gzip: measured 41% of raw against gzip's 65% on this payload, which
# is the difference between fitting a release asset and not. It costs build
# time, not install time.
mkdir -p "$OUT_DIR"
TARBALL="$OUT_DIR/tessera-engine-${VERSION}-linux-x64.tar.xz"
tar -c -C "$STAGE" tessera-engine | xz -9 -T0 > "$TARBALL"
sha256sum "$TARBALL" | awk '{print $1}' > "${TARBALL}.sha256"

# A release asset has a hard ceiling; failing the build is better than
# discovering it at upload.
ASSET_LIMIT=$((2 * 1024 * 1024 * 1024))
ACTUAL=$(stat -c%s "$TARBALL")
if (( ACTUAL > ASSET_LIMIT )); then
    echo "ERROR: artifact is $((ACTUAL/1048576)) MB, over the $((ASSET_LIMIT/1048576)) MB" >&2
    echo "       release-asset ceiling. Trim further or split the artifact." >&2
    exit 4
fi

# --- sign (FR-042) ---------------------------------------------------------
# Detached OpenPGP signature. The add-on's own integrity gate is the pinned
# SHA256 (FR-041), which works without the user having imported anything;
# this is for people who want to verify the distribution independently.
if [[ -n "${TESSERA_SIGNING_KEY:-}" ]]; then
    gpg --batch --yes --local-user "$TESSERA_SIGNING_KEY" \
        --detach-sign --armor --output "${TARBALL}.asc" "$TARBALL"
    echo "Signed with ${TESSERA_SIGNING_KEY}"
else
    echo "WARNING: TESSERA_SIGNING_KEY not set — artifact is UNSIGNED." >&2
    echo "         A release build must set it (FR-042)." >&2
fi

echo
echo "=== Build Summary ==="
echo "Artifact: $(basename "$TARBALL")"
echo "Size:     $(du -h "$TARBALL" | cut -f1)"
echo "SHA256:   $(cat "${TARBALL}.sha256")"
[[ -f "${TARBALL}.asc" ]] && echo "Signature: $(basename "${TARBALL}.asc")"
echo "====================="
