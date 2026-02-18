#!/usr/bin/env bash
#
# Build libtcc for macOS (x86_64 + arm64 universal binary).
# Run this on a macOS machine, then commit the resulting libs/tcc/macos/ directory.
#
# Prerequisites:
#   - Xcode Command Line Tools (xcode-select --install)
#   - git
#
# Usage:
#   cd libs/tcc && bash build-macos.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TCC_REPO="https://repo.or.cz/tinycc.git"
TCC_BRANCH="mob"
BUILD_DIR="$SCRIPT_DIR/_build_macos"
OUT_DIR="$SCRIPT_DIR/macos"

echo "=== Building libtcc for macOS ==="

# Clean previous build
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Clone TCC
echo "--- Cloning TCC ($TCC_BRANCH branch) ---"
git clone --depth 1 -b "$TCC_BRANCH" "$TCC_REPO" "$BUILD_DIR/tcc-src"

cd "$BUILD_DIR/tcc-src"

# Detect architecture
ARCH="$(uname -m)"
echo "--- Detected architecture: $ARCH ---"

echo "--- Configuring TCC ---"
./configure \
    --prefix="$BUILD_DIR/install" \
    --cc=cc \
    --extra-cflags="-O2"

echo "--- Building libtcc ---"
make libtcc.a -j"$(sysctl -n hw.ncpu)"

echo "--- Installing to $OUT_DIR ---"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR/include"

# Copy the static library and headers
cp libtcc.a "$OUT_DIR/libtcc.a"
cp libtcc.h "$OUT_DIR/libtcc.h"

# Copy TCC's bundled runtime headers (needed for TCC to compile C code)
cp include/*.h "$OUT_DIR/include/"

# Copy the runtime library (libtcc1.a — needed for TCC-compiled executables)
if [ -f libtcc1.a ]; then
    cp libtcc1.a "$OUT_DIR/libtcc1.a"
elif [ -f "$BUILD_DIR/install/lib/tcc/libtcc1.a" ]; then
    cp "$BUILD_DIR/install/lib/tcc/libtcc1.a" "$OUT_DIR/libtcc1.a"
else
    echo "WARNING: libtcc1.a not found — TCC may not be able to produce executables"
fi

# Clean up build directory
cd "$SCRIPT_DIR"
rm -rf "$BUILD_DIR"

echo ""
echo "=== Done ==="
echo "Output: $OUT_DIR/"
ls -la "$OUT_DIR/"
echo ""
echo "Commit the macos/ directory to the repository."
