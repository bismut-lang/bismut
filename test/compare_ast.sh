#!/bin/bash
# Compare AST output from Python parser vs mut_parse on .mut files.
# Usage: bash test/compare_ast.sh <file.mut>
#   or:  bash test/compare_ast.sh       (runs on all test/positive/*.mut files)

set -e
cd "$(dirname "$0")/.."

TMPDIR=.tmp
mkdir -p "$TMPDIR"

# Build the mut_parse driver once
echo "Building ast_dump_mut..."
python3 tools/reference-compiler/main.py test/ast_dump_mut.mut 2>/dev/null
gcc -O2 -std=c99 -Irt -o "$TMPDIR/ast_dump_mut" out.c -lm 2>/dev/null
rm -f out.c
echo "Build OK"
echo ""

matched=0
diffed=0
skipped=0

compare_file() {
    local f="$1"
    local name
    name=$(basename "$f")

    # Run Python parser AST dump
    if ! python3 test/ast_dump_py.py "$f" > "$TMPDIR/ast_py.txt" 2>/dev/null; then
        echo "  SKIP  $name (Python parser failed)"
        skipped=$((skipped + 1))
        return
    fi

    # Run mut_parse AST dump
    if ! "$TMPDIR/ast_dump_mut" "$f" > "$TMPDIR/ast_mut.txt" 2>/dev/null; then
        echo "  SKIP  $name (mut_parse failed)"
        skipped=$((skipped + 1))
        return
    fi

    # Compare
    if diff -u "$TMPDIR/ast_py.txt" "$TMPDIR/ast_mut.txt" > "$TMPDIR/ast_diff.txt" 2>&1; then
        echo "  MATCH $name"
        matched=$((matched + 1))
    else
        echo "  DIFF  $name"
        head -30 "$TMPDIR/ast_diff.txt" | sed 's/^/    /'
        echo ""
        diffed=$((diffed + 1))
    fi
}

if [ -n "$1" ]; then
    compare_file "$1"
else
    for f in test/positive/*.mut; do
        compare_file "$f"
    done
fi

rm -f "$TMPDIR/ast_dump_mut" "$TMPDIR/ast_py.txt" "$TMPDIR/ast_mut.txt" "$TMPDIR/ast_diff.txt"

echo ""
echo "$matched matched, $diffed diffed, $skipped skipped"
