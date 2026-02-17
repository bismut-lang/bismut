#!/usr/bin/env bash
# Valgrind leak check using the self-hosted Bismut compiler.
# Usage: bash test/valgrind_selfhost.sh
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

pass=0
fail=0
errors=""

for f in test/positive/*.mut; do
    name=$(basename "$f")
    if ! $COMPILER build "$f" --compiler-dir "$COMPILER_DIR" 2>/dev/null; then
        echo "  FAIL  $name (compile error)"
        fail=$((fail + 1))
        errors="$errors  $name (compile error)\n"
        rm -f out.c
        continue
    fi
    mv -f out.c "$TMPDIR/out.c" 2>/dev/null || true
    if ! gcc -O0 -g -std=c99 -Irt -o "$TMPDIR/mut_valgrind" "$TMPDIR/out.c" -lm 2>/dev/null; then
        echo "  FAIL  $name (gcc error)"
        fail=$((fail + 1))
        errors="$errors  $name (gcc error)\n"
        continue
    fi
    if valgrind --leak-check=full --error-exitcode=1 "$TMPDIR/mut_valgrind" >/dev/null 2>&1; then
        echo "  CLEAN $name"
        pass=$((pass + 1))
    else
        echo "  LEAK  $name"
        fail=$((fail + 1))
        errors="$errors  $name\n"
    fi
done

rm -f "$TMPDIR/mut_valgrind" "$TMPDIR/out.c"

echo ""
echo "$pass clean, $fail leaked"
if [ $fail -gt 0 ]; then
    echo -e "Leaks:\n$errors"
    exit 1
fi
