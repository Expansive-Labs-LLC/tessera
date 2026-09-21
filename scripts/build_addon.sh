#!/usr/bin/env bash
# =============================================================================
# Tessera Add-on Build Script
# Spec: SPEC-TS-0014 (FR-024 – FR-034)
#
# Produces a Blender-compatible .zip from the repository source tree.
# Accepts a semantic version string, patches bl_info and blender_manifest.toml,
# then creates a deterministic archive.
#
# Usage: build_addon.sh <version>
#   e.g.: build_addon.sh 1.2.3
#         build_addon.sh 0.0.0-ci
# =============================================================================

# FR-025: Exit on error, undefined variable, or pipe failure
set -euo pipefail

# FR-024: Require a version argument
if [ $# -lt 1 ]; then
    echo "Usage: build_addon.sh <version>" >&2
    exit 1
fi

VERSION="$1"

# FR-026: Parse version into major.minor.patch, stripping pre-release suffix
MAJOR="$(echo "$VERSION" | cut -d. -f1)"
MINOR="$(echo "$VERSION" | cut -d. -f2)"
# Strip any pre-release suffix (e.g., "0-ci" → "0")
PATCH_RAW="$(echo "$VERSION" | cut -d. -f3)"
PATCH="$(echo "$PATCH_RAW" | cut -d- -f1)"

# Resolve the repository root relative to this script's location
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Tessera Build Script ==="
echo "Version:  $VERSION"
echo "Tuple:    ($MAJOR, $MINOR, $PATCH)"
echo "Repo:     $REPO_ROOT"
echo ""

# ---------------------------------------------------------------------------
# FR-027: Patch bl_info["version"] tuple in tessera/__init__.py
# ---------------------------------------------------------------------------
INIT_FILE="$REPO_ROOT/tessera/__init__.py"

if ! grep -q '"version": ([0-9]*, [0-9]*, [0-9]*),' "$INIT_FILE"; then
    echo "ERROR: Could not find version tuple in $INIT_FILE" >&2
    echo "Expected pattern: \"version\": (<digits>, <digits>, <digits>)," >&2
    exit 1
fi

sed -i "s/\"version\": ([0-9]*, [0-9]*, [0-9]*),/\"version\": ($MAJOR, $MINOR, $PATCH),/" "$INIT_FILE"
echo "Patched bl_info[\"version\"] → ($MAJOR, $MINOR, $PATCH)"

# ---------------------------------------------------------------------------
# FR-028: Patch version field in blender_manifest.toml
# ---------------------------------------------------------------------------
MANIFEST_FILE="$REPO_ROOT/blender_manifest.toml"

sed -i "s/^version = \".*\"/version = \"$MAJOR.$MINOR.$PATCH\"/" "$MANIFEST_FILE"
echo "Patched blender_manifest.toml version → \"$MAJOR.$MINOR.$PATCH\""

# ---------------------------------------------------------------------------
# FR-029, FR-030, FR-031: Create the .zip archive
# ---------------------------------------------------------------------------
ZIP_NAME="tessera-v${VERSION}.zip"
ZIP_PATH="$REPO_ROOT/$ZIP_NAME"

# Remove any previous build artifact
rm -f "$ZIP_PATH"

echo ""
echo "Building archive: $ZIP_NAME"

cd "$REPO_ROOT"

zip -r "$ZIP_PATH" \
    tessera/ \
    blender_manifest.toml \
    LICENSE \
    -x "tests/*" \
       "tessera/tests/*" \
       "tessera/testing/*" \
       "tessera/__pycache__/*" \
       "tessera/**/__pycache__/*" \
       "tessera/.git/*" \
       ".git/*" \
       ".venv/*" \
       "specs/*" \
       "tasks/*" \
       ".agent/*" \
       ".pytest_cache/*" \
       ".mypy_cache/*" \
       "scripts/*" \
       "docs/*" \
       ".github/*" \
       "*.pyc" \
       "*.pyo" \
       "*.pt" \
       "*.pth" \
       "*.onnx" \
       "*.safetensors" \
       "*.bin" \
       ".gitignore" \
       ".releaserc.yml" \
       "CONTRIBUTING.md" \
       "CODE_OF_CONDUCT.md" \
       "SECURITY.md" \
       "FUNDING.yml" \
       "PRD-001_Tessera.md" \
       "TASK-INDEX.md" \
       "README.md" \
       "CHANGELOG.md" \
       "commitlint.config.js"

# ---------------------------------------------------------------------------
# FR-032: Validate archive contents
# ---------------------------------------------------------------------------
echo ""
echo "Validating archive..."

MISSING_FILES=""
ZIP_LISTING="$(unzip -l "$ZIP_PATH")"

if ! echo "$ZIP_LISTING" | grep -q "blender_manifest.toml"; then
    MISSING_FILES="${MISSING_FILES}blender_manifest.toml "
fi

if ! echo "$ZIP_LISTING" | grep -q "tessera/__init__.py"; then
    MISSING_FILES="${MISSING_FILES}tessera/__init__.py "
fi

if ! echo "$ZIP_LISTING" | grep -q "LICENSE"; then
    MISSING_FILES="${MISSING_FILES}LICENSE "
fi

if [ -n "$MISSING_FILES" ]; then
    for f in $MISSING_FILES; do
        echo "ERROR: Missing required file in zip: $f" >&2
    done
    exit 1
fi

echo "Validation passed: all required files present."

# ---------------------------------------------------------------------------
# FR-033: Print build summary
# ---------------------------------------------------------------------------
FILE_SIZE="$(stat -c%s "$ZIP_PATH")"
FILE_COUNT="$(unzip -l "$ZIP_PATH" | tail -1 | awk '{print $2}')"

echo ""
echo "=== Build Summary ==="
echo "Archive:    $ZIP_NAME"
echo "Size:       $FILE_SIZE bytes"
echo "Files:      $FILE_COUNT"
echo "===================="
