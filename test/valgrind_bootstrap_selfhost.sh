#!/usr/bin/env bash
# Valgrind leak check for the bootstrap: the self-hosted compiler compiles
# itself under valgrind.
# Usage: bash test/valgrind_bootstrap_selfhost.sh
set -e
cd "$(dirname "$0")/.."
ulimit -n 1024 2>/dev/null || true

COMPILER="./bismut"
COMPILER_DIR="."
TMPDIR=.tmp
mkdir -p "$TMPDIR"

if [ ! -f "$COMPILER" ]; then
    echo "error: self-hosted compiler binary '$COMPILER' not found"
    echo "Build it first: python3 tools/reference-compiler/main.py src/main.mut && gcc -O2 -std=c99 -Irt -o bismut out.c -lm"
    exit 1
fi

echo "--- bootstrap valgrind (self-hosted compiler) ---"
if $COMPILER build src/main.mut --compiler-dir "$COMPILER_DIR" 2>/dev/null \
   && mv -f out.c "$TMPDIR/out.c" \
   && gcc -O0 -g -std=c99 -Irt -o "$TMPDIR/mut_bootstrap" "$TMPDIR/out.c" -lm -ltcc -ldl 2>/dev/null; then
    if valgrind --leak-check=full --error-exitcode=1 \
       "$TMPDIR/mut_bootstrap" build src/main.mut --compiler-dir . >/dev/null 2>&1; then
        echo "  CLEAN bootstrap"
    else
        echo "  LEAK  bootstrap"
        rm -f "$TMPDIR/mut_bootstrap" "$TMPDIR/out.c"
        exit 1
    fi
else
    echo "  FAIL  bootstrap (stage1 compile failed)"
    rm -f "$TMPDIR/mut_bootstrap" "$TMPDIR/out.c"
    exit 1
fi
rm -f "$TMPDIR/mut_bootstrap" "$TMPDIR/out.c"
