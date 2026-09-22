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
# Restore the version placeholders on exit.
#
# Patching happens in place, so a local build would otherwise leave a real
# version in the working tree and it would be committed by accident. The
# release pipeline no longer commits these files back (.releaserc.yml), so
# source must always read 0.0.0 once a build finishes.
# ---------------------------------------------------------------------------
INIT_FILE="$REPO_ROOT/tessera/__init__.py"
MANIFEST_FILE="$REPO_ROOT/blender_manifest.toml"
_VERSION_BACKUP_DIR="$(mktemp -d)"
cp "$INIT_FILE" "$_VERSION_BACKUP_DIR/__init__.py"
cp "$MANIFEST_FILE" "$_VERSION_BACKUP_DIR/blender_manifest.toml"

restore_version_placeholders() {
    cp "$_VERSION_BACKUP_DIR/__init__.py" "$INIT_FILE"
    cp "$_VERSION_BACKUP_DIR/blender_manifest.toml" "$MANIFEST_FILE"
    rm -rf "$_VERSION_BACKUP_DIR"
}
trap restore_version_placeholders EXIT

# ---------------------------------------------------------------------------
# FR-027: Patch bl_info["version"] tuple in tessera/__init__.py
# ---------------------------------------------------------------------------

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
sed -i "s/^version = \".*\"/version = \"$MAJOR.$MINOR.$PATCH\"/" "$MANIFEST_FILE"
echo "Patched blender_manifest.toml version → \"$MAJOR.$MINOR.$PATCH\""

# ---------------------------------------------------------------------------
# FR-029, FR-030, FR-031: Create the .zip archive
# ---------------------------------------------------------------------------
ZIP_NAME="tessera-v${VERSION}.zip"
ZIP_PATH="$REPO_ROOT/$ZIP_NAME"
STAGE_DIR="$REPO_ROOT/.build-stage"

# Remove any previous build artifacts
rm -f "$ZIP_PATH"
rm -rf "$STAGE_DIR"

echo ""
echo "Building archive: $ZIP_NAME"

# FR-029: Blender treats the ZIP ROOT as the add-on package itself. The
# manifest and __init__.py must sit at the top level of the archive -- a
# nested "tessera/" directory makes Blender reject the install with
# 'Error, file missing from add-on: "__init__.py"'. Stage a flattened tree.
mkdir -p "$STAGE_DIR"
cp -r "$REPO_ROOT/tessera/." "$STAGE_DIR/"
cp "$MANIFEST_FILE" "$STAGE_DIR/blender_manifest.toml"
cp "$REPO_ROOT/LICENSE" "$STAGE_DIR/LICENSE"

# FR-030: Strip development-only content from the staged tree. Paths are
# relative to the package root now that the tree is flattened.
rm -rf "$STAGE_DIR/testing" "$STAGE_DIR/tests"
find "$STAGE_DIR" -name "__pycache__" -type d -prune -exec rm -rf {} +
find "$STAGE_DIR" \( -name "*.pyc" -o -name "*.pyo" \) -delete
find "$STAGE_DIR" \( -name "*.pt" -o -name "*.pth" -o -name "*.onnx" \
    -o -name "*.safetensors" -o -name "*.bin" \) -delete

# FR-031: Deterministic archive (sorted entries, no extra attributes)
cd "$STAGE_DIR"
zip -qrX "$ZIP_PATH" .
cd "$REPO_ROOT"

# ---------------------------------------------------------------------------
# FR-032: Validate archive contents
# ---------------------------------------------------------------------------
echo ""
echo "Validating archive..."

MISSING_FILES=""
ZIP_LISTING="$(unzip -Z1 "$ZIP_PATH")"

# Required files must be at the ARCHIVE ROOT, not nested in a subdirectory.
for required in blender_manifest.toml __init__.py LICENSE; do
    if ! echo "$ZIP_LISTING" | grep -qx "$required"; then
        MISSING_FILES="${MISSING_FILES}${required} "
    fi
done

if [ -n "$MISSING_FILES" ]; then
    for f in $MISSING_FILES; do
        echo "ERROR: Missing required file at archive root: $f" >&2
    done
    exit 1
fi

# Guard against the nested-package regression reappearing.
if echo "$ZIP_LISTING" | grep -qx "tessera/"; then
    echo "ERROR: Archive contains a nested 'tessera/' directory." >&2
    echo "Blender requires the add-on package at the archive root." >&2
    exit 1
fi

rm -rf "$STAGE_DIR"

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
