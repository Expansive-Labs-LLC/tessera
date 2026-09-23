#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Provisions a user-local CUDA toolchain for building the engine.
#
# Why this exists: TRELLIS's extensions compile from source, Blackwell
# (sm_120) needs CUDA >= 12.8, and the distro toolkit is frequently older —
# this workstation shipped 12.0, which rejects sm_120 outright.
#
# Why not pip: NVIDIA's `nvidia-cuda-nvcc-cu12` wheel contains only `ptxas`,
# at both 12.8.93 and 12.9.86. There is no nvcc driver and no cicc in it, so
# a pure-pip environment cannot compile an extension offline. Verified, not
# assumed.
#
# Why not the distro package: it needs root, and it installs system-wide for
# a build dependency that belongs to one project.
#
# So: conda-forge/nvidia channels via micromamba, into a directory beside the
# engine venv. ~400 MB, no root, removable with rm -rf.
#
# The version is pinned to match what PyTorch was built against. A toolkit
# newer than torch's CUDA can compile extensions that then fail to load
# against torch's runtime, and that failure surfaces at import rather than at
# build.
#
# Usage: provision_toolchain.sh [cuda-version]   (default: match torch)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOOLCHAIN="${TESSERA_CUDA_TOOLCHAIN:-$REPO_ROOT/.cuda-toolchain}"
VENV="${TESSERA_ENGINE_VENV:-$REPO_ROOT/.venv-engine}"
CUDA_VERSION="${1:-}"

# Match the toolkit to torch's CUDA build unless told otherwise.
if [[ -z "$CUDA_VERSION" ]]; then
    if [[ -x "$VENV/bin/python" ]]; then
        CUDA_VERSION="$("$VENV/bin/python" -c \
            'import torch; print(torch.version.cuda or "")' 2>/dev/null || true)"
    fi
    CUDA_VERSION="${CUDA_VERSION:-12.8}"
fi
echo "Provisioning CUDA ${CUDA_VERSION} toolchain at ${TOOLCHAIN}"

if [[ -x "$TOOLCHAIN/bin/nvcc" ]]; then
    have="$("$TOOLCHAIN/bin/nvcc" --version | sed -n 's/.*release \([0-9.]*\).*/\1/p')"
    if [[ "$have" == "$CUDA_VERSION"* ]]; then
        echo "Already provisioned: nvcc ${have}"
        exit 0
    fi
    echo "Replacing nvcc ${have} with ${CUDA_VERSION}"
    rm -rf "$TOOLCHAIN"
fi

MM="${TESSERA_MICROMAMBA:-$TOOLCHAIN/../.micromamba/bin/micromamba}"
if [[ ! -x "$MM" ]]; then
    echo "Fetching micromamba..."
    mkdir -p "$(dirname "$MM")"
    curl -sSL https://micro.mamba.pm/api/micromamba/linux-64/latest \
        | tar -xjO bin/micromamba > "$MM"
    chmod +x "$MM"
fi

export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$(dirname "$MM")/root}"
"$MM" create -y -q -p "$TOOLCHAIN" -c nvidia -c conda-forge \
    "cuda-nvcc=${CUDA_VERSION}" \
    "cuda-cudart-dev=${CUDA_VERSION}" \
    "cuda-crt=${CUDA_VERSION}" \
    "cuda-nvrtc-dev=${CUDA_VERSION}"

# ninja is what torch's extension builder shells out to. It is a venv
# console script, so the venv's bin has to be on PATH at build time — being
# able to import torch is not enough, and the error when it is missing names
# ninja rather than PATH.
if [[ -x "$VENV/bin/pip" ]]; then
    "$VENV/bin/pip" install --quiet ninja
fi

echo
"$TOOLCHAIN/bin/nvcc" --version | tail -2
echo
echo "Architectures this toolchain can target:"
"$TOOLCHAIN/bin/nvcc" --list-gpu-arch | tr '\n' ' '
echo
echo
echo "Use it with:"
echo "  export CUDA_HOME=${TOOLCHAIN}"
echo "  export PATH=\"${VENV}/bin:${TOOLCHAIN}/bin:\$PATH\""
