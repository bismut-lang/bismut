#!/usr/bin/env bash
# Generate src/version.mut from VERSION file.
# Run before compiling the self-hosted compiler.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VER="$(tr -d '[:space:]' < "$ROOT/VERSION")"
echo "const VERSION: str = \"${VER}\"" > "$ROOT/src/version.mut"
