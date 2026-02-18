#!/usr/bin/env bash
# Valgrind leak check for the bootstrap: compile the self-hosted compiler
# with the Python compiler, then run it under valgrind to compile itself.
# Usage: bash test/valgrind_bootstrap.sh
set -e
cd "$(dirname "$0")/.."
ulimit -n 1024 2>/dev/null || true

TMPDIR=.tmp
mkdir -p "$TMPDIR"

echo "--- bootstrap valgrind (python compiler) ---"
if python3 tools/reference-compiler/main.py src/main.mut 2>/dev/null \
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
