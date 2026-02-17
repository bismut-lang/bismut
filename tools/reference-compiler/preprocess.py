"""
Bismut text-level preprocessor.

Runs before the lexer. Processes @-directives line-by-line and strips/includes
text based on compile-time constants.

Directives:
    @define NAME          Define a constant
    @if NAME              Include following lines if NAME is defined
    @elif NAME            Else-if branch
    @else                 Else branch
    @end                  End conditional block

Predefined constants (based on host platform):
    __LINUX__
    __MACOS__
    __WIN__
"""

import sys

_PLATFORM_NAMES = {"__LINUX__", "__MACOS__", "__WIN__"}

# Detect host platform
_PLATFORM_DEFINES: set[str] = set()
if sys.platform == "linux":
    _PLATFORM_DEFINES.add("__LINUX__")
elif sys.platform == "darwin":
    _PLATFORM_DEFINES.add("__MACOS__")
elif sys.platform == "win32":
    _PLATFORM_DEFINES.add("__WIN__")


def preprocess(source: str, file: str = "<input>", extra_defines: set[str] | None = None) -> str:
    """Preprocess source text, returning the filtered source."""
    # If user passed a platform define, suppress the auto-detected one
    if extra_defines and extra_defines & _PLATFORM_NAMES:
        defines = set()
    else:
        defines = set(_PLATFORM_DEFINES)
    if extra_defines:
        defines |= extra_defines

    out_lines: list[str] = []
    # Stack of (emitting, branch_taken) for nested @if
    # emitting: are we currently outputting lines?
    # branch_taken: has any branch in this @if/@elif/@else been taken?
    stack: list[tuple[bool, bool]] = []
    # Are we currently emitting lines? (top-level: yes)
    emitting = True

    lines = source.split("\n")
    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()

        # @define NAME
        if stripped.startswith("@define "):
            if emitting:
                name = stripped[8:].strip()
                if not name:
                    _error(file, line_no, "@define requires a name")
                defines.add(name)
            continue

        # @if NAME
        if stripped.startswith("@if "):
            name = stripped[4:].strip()
            if not name:
                _error(file, line_no, "@if requires a name")
            # Push current state
            parent_emitting = emitting
            cond = name in defines
            taken = cond
            emitting = parent_emitting and cond
            stack.append((parent_emitting, taken))
            continue

        # @elif NAME
        if stripped.startswith("@elif "):
            if not stack:
                _error(file, line_no, "@elif without matching @if")
            name = stripped[6:].strip()
            if not name:
                _error(file, line_no, "@elif requires a name")
            parent_emitting, taken = stack[-1]
            cond = name in defines
            if taken:
                # A previous branch was already taken
                emitting = False
            else:
                emitting = parent_emitting and cond
                if emitting:
                    stack[-1] = (parent_emitting, True)
            continue

        # @else
        if stripped == "@else":
            if not stack:
                _error(file, line_no, "@else without matching @if")
            parent_emitting, taken = stack[-1]
            if taken:
                emitting = False
            else:
                emitting = parent_emitting
                stack[-1] = (parent_emitting, True)
            continue

        # @end
        if stripped == "@end":
            if not stack:
                _error(file, line_no, "@end without matching @if")
            parent_emitting, _ = stack.pop()
            emitting = parent_emitting
            continue

        # Regular line — include if emitting
        if emitting:
            out_lines.append(line)

    if stack:
        _error(file, len(lines), "unterminated @if block (missing @end)")

    return "\n".join(out_lines)


def _error(file: str, line: int, msg: str):
    print(f"{file}:{line}: preprocessor error: {msg}", file=sys.stderr)
    sys.exit(1)
