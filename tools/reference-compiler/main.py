from codegen import generate_c
from import_resolver import parse_file, resolve_imports, resolve_externs
from typecheck import typecheck

import sys
import os


if len(sys.argv) < 2:
    print("usage: python3 tools/reference-compiler/main.py <file.mut> [--define NAME ...] [--no-debug-leaks]", file=sys.stderr)
    sys.exit(1)

src_file = sys.argv[1]

# Parse flags
extra_defines: set[str] = set()
no_debug_leaks = False
i = 2
while i < len(sys.argv):
    if sys.argv[i] == "--define" and i + 1 < len(sys.argv):
        extra_defines.add(sys.argv[i + 1])
        i += 2
    elif sys.argv[i] == "--no-debug-leaks":
        no_debug_leaks = True
        i += 1
    else:
        i += 1

# Determine target platform (for mutlib flag resolution)
target_platform = None
for d in extra_defines:
    if d == "__WIN__":
        target_platform = "win"
    elif d == "__MACOS__":
        target_platform = "macos"
    elif d == "__LINUX__":
        target_platform = "linux"

prog = parse_file(src_file, extra_defines=extra_defines or None)
base_dir = os.path.dirname(os.path.abspath(src_file))
compiler_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
prog = resolve_imports(prog, base_dir, {os.path.abspath(src_file)}, compiler_dir, extra_defines=extra_defines or None, target_platform=target_platform)
prog = resolve_externs(prog, src_file, compiler_dir, target_platform=target_platform)
typecheck(prog)
# Debug leaks on by default (reference compiler always does debug builds)
debug_leaks = not no_debug_leaks
c = generate_c(prog, debug_leaks=debug_leaks)
open("out.c", "w", encoding="utf-8").write(c)

# Print build flags for extern libraries (if any)
if prog.extern_cflags or prog.extern_ldflags:
    flags = " ".join(prog.extern_cflags + prog.extern_ldflags)
    print(f"EXTERN_FLAGS: {flags}", file=sys.stderr)
