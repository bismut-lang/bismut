#!/usr/bin/env bash
# Run the test suite using the self-hosted Bismut compiler binary.
# Usage: bash test/run_selfhost.sh
set -e
cd "$(dirname "$0")/.."

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

# ── Positive tests: must compile, link, and run ──
for f in test/positive/*.mut; do
    name=$(basename "$f")
    if $COMPILER build "$f" -o "$TMPDIR/mut_test" --compiler-dir "$COMPILER_DIR" 2>/dev/null \
       && "$TMPDIR/mut_test" >/dev/null 2>&1; then
        echo "  PASS  $name"
        pass=$((pass + 1))
    else
        echo "  FAIL  $name"
        fail=$((fail + 1))
        errors="$errors  $name\n"
    fi
done

# ── Negative tests: must be rejected by the compiler ──
for f in test/negative/*.mut; do
    name=$(basename "$f")
    if $COMPILER build "$f" -o "$TMPDIR/mut_test" --compiler-dir "$COMPILER_DIR" 2>/dev/null; then
        echo "  FAIL  $name (should have been rejected)"
        fail=$((fail + 1))
        errors="$errors  $name\n"
    else
        echo "  PASS  $name (correctly rejected)"
        pass=$((pass + 1))
    fi
done

# ── Runtime panic tests: must compile but crash at runtime ──
for f in test/runtime_errors/*.mut; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    if ! $COMPILER build "$f" -o "$TMPDIR/mut_test" --compiler-dir "$COMPILER_DIR" 2>/dev/null; then
        echo "  FAIL  $name (should have compiled)"
        fail=$((fail + 1))
        errors="$errors  $name\n"
    elif "$TMPDIR/mut_test" >/dev/null 2>&1; then
        echo "  FAIL  $name (should have panicked)"
        fail=$((fail + 1))
        errors="$errors  $name\n"
    else
        echo "  PASS  $name (panicked as expected)"
        pass=$((pass + 1))
    fi
done

rm -f "$TMPDIR/mut_test" out.c

# ── Bootstrap test: self-hosted compiler compiles itself ──
echo ""
echo "--- bootstrap test ---"
if $COMPILER build src/main.mut -o "$TMPDIR/mut_bootstrap" --compiler-dir "$COMPILER_DIR" 2>/dev/null; then
    if "$TMPDIR/mut_bootstrap" build src/main.mut -o "$TMPDIR/mut_bootstrap2" --compiler-dir . 2>/dev/null; then
        echo "  PASS  bootstrap (self-hosted compiler compiles itself)"
        pass=$((pass + 1))
    else
        echo "  FAIL  bootstrap (stage2 compile failed)"
        fail=$((fail + 1))
        errors="$errors  bootstrap (stage2)\n"
    fi
else
    echo "  FAIL  bootstrap (stage1 compile failed)"
    fail=$((fail + 1))
    errors="$errors  bootstrap (stage1)\n"
fi
rm -f "$TMPDIR/mut_bootstrap" "$TMPDIR/mut_bootstrap2" out.c

echo ""
echo "$pass passed, $fail failed"
if [ $fail -gt 0 ]; then
    echo -e "Failures:\n$errors"
    exit 1
fi
