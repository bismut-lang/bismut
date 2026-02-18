#!/usr/bin/env bash
# Generate src/version.mut from VERSION file.
# Set BISMUT_DEV_BUILD=1 to append -dev+<commit> suffix.
# Run before compiling the self-hosted compiler.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VER="$(tr -d '[:space:]' < "$ROOT/VERSION")"
if [ "${BISMUT_DEV_BUILD:-}" = "1" ] && command -v git >/dev/null 2>&1; then
    SHORT_HASH="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown")"
    VER="${VER}-dev+${SHORT_HASH}"
fi
echo "const VERSION: str = \"${VER}\"" > "$ROOT/src/version.mut"
