#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Shrinks the engine payload so a release asset fits where it has to go.
#
# An untrimmed payload is 6.8 GB on disk and 3.7 GiB gzipped. GitHub documents
# a 2 GiB per-asset limit on releases, and hosting elsewhere was rejected — so
# the artifact has to get smaller rather than move.
#
# Every removal below was established by deleting it and running an op smoke
# test, not by reading a dependency list. What that exercise showed is that
# most CUDA libraries cannot simply be deleted: libtorch_cuda.so has them as
# DT_NEEDED entries, so ld.so refuses to load torch at all if one is missing,
# even when nothing ever calls into it. Hence the stub approach for the
# libraries that are linked but unreachable.
#
# What was tried and rejected:
#   nvprune  — only accepts relocatable objects, not linked .so files, so the
#              prebuilt wheels cannot be pruned to our architecture list.
#   deleting cusparseLt — its stub aborted immediately, so torch really does
#              call into it during initialisation. Left alone.
#
# Usage: trim_payload.sh <payload-venv-dir>

set -euo pipefail

VENV="${1:-}"
if [[ -z "$VENV" || ! -d "$VENV" ]]; then
    echo "Usage: $0 <payload-venv-dir>" >&2
    exit 1
fi

SP="$(echo "$VENV"/lib/python3.*/site-packages)"
[[ -d "$SP" ]] || { echo "ERROR: no site-packages under $VENV" >&2; exit 1; }

before_kb=$(du -sk "$VENV" | cut -f1)
echo "Trimming payload (${before_kb} KB before)"

# --- 1. build-time only -----------------------------------------------------
# Headers, static archives and packaging tools are needed to *build* an
# extension, never to run one. The artifact ships a built environment.
find "$SP/nvidia" -maxdepth 2 -type d -name include -prune -exec rm -rf {} + 2>/dev/null || true
find "$SP" -name '*.a' -delete 2>/dev/null || true
find "$SP" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$SP" -name '*.pyc' -delete 2>/dev/null || true
rm -rf "$SP/pip" "$SP/setuptools" "$SP"/pip-*.dist-info "$SP"/setuptools-*.dist-info 2>/dev/null || true
rm -rf "$SP/torchgen" 2>/dev/null || true

# --- 2. Triton --------------------------------------------------------------
# 641 MB, and only reachable through torch.compile or hand-written Triton
# kernels. The engine runs adapters in eager mode. Set TESSERA_KEEP_TRITON=1
# if an adapter turns out to need it — the smoke test after this script is
# what should catch that, not a guess here.
if [[ "${TESSERA_KEEP_TRITON:-0}" != "1" ]]; then
    rm -rf "$SP/triton" "$SP"/triton-*.dist-info 2>/dev/null || true
fi

# --- 3. stub the linked-but-unreachable libraries ---------------------------
# NCCL is multi-GPU collectives. v1 runs one inference on one GPU
# (SPEC-TS-0023 section 8 excludes multi-GPU), so nothing reaches these
# symbols — but torch will not load without the soname present. A stub that
# aborts with an explanation is both smaller and more honest than shipping
# 383 MB of unreachable kernels.
stub_library () {
    local lib="$1" soname="$2" reason="$3"
    [[ -f "$lib" ]] || return 0
    command -v gcc >/dev/null 2>&1 || { echo "  gcc absent — keeping $soname"; return 0; }
    local work; work="$(mktemp -d)"
    nm -D --defined-only "$lib" 2>/dev/null \
        | awk '$2=="T"||$2=="W"{print $3}' | grep -E '^[A-Za-z_][A-Za-z0-9_]*$' | sort -u > "$work/syms"
    # Versioned symbols (name@@VER) are skipped by the filter above; if that
    # leaves us with nothing, the library is not safely stubbable.
    [[ -s "$work/syms" ]] || { rm -rf "$work"; echo "  $soname not stubbable — keeping"; return 0; }
    {
        echo '#include <stdio.h>'
        echo '#include <stdlib.h>'
        echo 'static void unsupported(const char* s){'
        printf '  fprintf(stderr, "Tessera engine: %%s is unavailable in this build (%s).\\n", s);\n' "$reason"
        echo '  abort();'
        echo '}'
        while read -r sym; do echo "void $sym(void){ unsupported(\"$sym\"); }"; done < "$work/syms"
    } > "$work/stub.c"
    if gcc -shared -fPIC -Wl,-soname,"$soname" -o "$work/$soname" "$work/stub.c" 2>/dev/null; then
        local was; was=$(stat -c%s "$lib")
        cp "$work/$soname" "$lib"
        echo "  stubbed $soname: $((was/1048576)) MB -> $(( $(stat -c%s "$lib")/1024 )) KB"
    else
        echo "  could not build a stub for $soname — keeping"
    fi
    rm -rf "$work"
}

stub_library "$SP/nvidia/nccl/lib/libnccl.so.2" "libnccl.so.2" \
    "this build is single-GPU"

# --- report -----------------------------------------------------------------
after_kb=$(du -sk "$VENV" | cut -f1)
echo "Trimmed: $((before_kb/1024)) MB -> $((after_kb/1024)) MB (-$(( (before_kb-after_kb)*100/before_kb ))%)"
