"""
Bismut extern library support.
Parses .mutlib manifest files for native C library integration.

Manifest format (.mutlib):
    [types]
    BismutName = c_type

    [functions]
    bismut_name(p1: type, p2: type) -> ret_type = c_function_name
    destructor(obj: BismutName) [dtor] = c_destructor_func

    [constants]
    BISMUT_NAME: type = c_expression

    [flags]
    cflags = -I.
    ldflags = -lm
    cflags_linux = -DLINUX
    ldflags_macos = -framework Cocoa
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple
import os
import platform


@dataclass
class ExternFunc:
    bismut_name: str
    params: List[Tuple[str, str]]  # [(name, type), ...]
    ret_type: str
    c_name: str
    is_dtor: bool = False  # True if tagged [dtor] — first param's type uses this as destructor
    doc: str = ""           # doc comment from preceding # lines
    line: int = 0           # 1-based line number in the .mutlib file


@dataclass
class ExternConst:
    bismut_name: str
    ty: str
    c_expr: str  # C expression or literal
    doc: str = ""           # doc comment from preceding # lines
    line: int = 0           # 1-based line number in the .mutlib file


@dataclass
class ExternType:
    bismut_name: str
    c_type: str           # C struct/typedef name (used as pointer: c_type*)
    c_dtor: Optional[str] = None  # C function called on the raw pointer when refcount drops to 0
    doc: str = ""           # doc comment from preceding # lines
    line: int = 0           # 1-based line number in the .mutlib file


@dataclass
class LibManifest:
    name: str
    lib_dir: str               # absolute path to the lib folder
    types: List[ExternType]
    funcs: List[ExternFunc]
    consts: List[ExternConst]
    c_source: Optional[str]    # absolute path to C source file (if exists)
    cflags: List[str]
    ldflags: List[str]


def _current_platform() -> str:
    s = platform.system().lower()
    if s == "linux":
        return "linux"
    if s == "darwin":
        return "macos"
    if s == "windows" or s.startswith("mingw") or s.startswith("msys"):
        return "win"
    return s


def parse_mutlib(path: str, lib_name: str, lib_dir: str, target_platform: str | None = None) -> LibManifest:
    """Parse a .mutlib manifest file."""
    types: List[ExternType] = []
    funcs: List[ExternFunc] = []
    consts: List[ExternConst] = []
    flag_entries: dict = {}
    section = None
    doc_lines: list[str] = []

    def _strip_comment(line: str) -> str:
        """Strip leading '# ' or '#' from a comment line."""
        if len(line) > 1 and line[1] == ' ':
            return line[2:]
        return line[1:]

    def _flush_doc() -> str:
        """Join accumulated doc lines into a single string and clear."""
        nonlocal doc_lines
        if not doc_lines:
            return ""
        result = "\n".join(doc_lines)
        doc_lines = []
        return result

    with open(path, encoding="utf-8") as f:
        for line_no, raw in enumerate(f, 1):
            line = raw.strip()
            if not line:
                doc_lines = []
                continue
            if line.startswith("#"):
                doc_lines.append(_strip_comment(line))
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip().lower()
                doc_lines = []
                continue

            doc = _flush_doc()

            if section == "types":
                t = _parse_type_line(line, path, line_no)
                t.doc = doc
                t.line = line_no
                types.append(t)
            elif section == "functions":
                fn = _parse_func_line(line, path, line_no)
                fn.doc = doc
                fn.line = line_no
                funcs.append(fn)
            elif section == "constants":
                c = _parse_const_line(line, path, line_no)
                c.doc = doc
                c.line = line_no
                consts.append(c)
            elif section == "flags":
                if "=" in line:
                    key, val = line.split("=", 1)
                    flag_entries[key.strip()] = val.strip()
            else:
                raise RuntimeError(f"{path}:{line_no}: unknown section or orphan line: {line!r}")

    # Look for C source
    c_source = os.path.join(lib_dir, f"{lib_name}.c")
    if not os.path.isfile(c_source):
        c_source = None

    # Resolve flags for current platform
    cflags, ldflags = _resolve_flags(flag_entries, target_platform=target_platform)

    # Substitute {LIB_DIR} in flag values
    cflags = [f.replace("{LIB_DIR}", lib_dir) for f in cflags]
    ldflags = [f.replace("{LIB_DIR}", lib_dir) for f in ldflags]

    # Link [dtor] functions to their types
    type_by_name = {t.bismut_name: t for t in types}
    for fn in funcs:
        if fn.is_dtor:
            if not fn.params:
                raise RuntimeError(f"{path}: [dtor] function '{fn.bismut_name}' must have at least one parameter")
            first_param_type = fn.params[0][1]
            if first_param_type not in type_by_name:
                raise RuntimeError(f"{path}: [dtor] function '{fn.bismut_name}' first parameter type "
                                   f"'{first_param_type}' is not a declared [types] entry")
            type_by_name[first_param_type].c_dtor = fn.c_name

    return LibManifest(name=lib_name, lib_dir=lib_dir, types=types, funcs=funcs,
                       consts=consts, c_source=c_source, cflags=cflags, ldflags=ldflags)


def _parse_type_line(line: str, path: str, line_no: int) -> ExternType:
    """Parse: BismutName = c_type"""
    if "=" not in line:
        raise RuntimeError(f"{path}:{line_no}: type line must have '= c_type': {line!r}")
    bismut_name, c_type = line.split("=", 1)
    return ExternType(bismut_name=bismut_name.strip(), c_type=c_type.strip())


def _parse_func_line(line: str, path: str, line_no: int) -> ExternFunc:
    """Parse: bismut_name(p1: type, p2: type) -> ret_type = c_name"""
    # Split on '='
    if "=" not in line:
        raise RuntimeError(f"{path}:{line_no}: function line must have '= c_name': {line!r}")
    sig_part, c_name = line.rsplit("=", 1)
    sig_part = sig_part.strip()
    c_name = c_name.strip()

    # Extract name and params
    paren_open = sig_part.index("(")
    bismut_name = sig_part[:paren_open].strip()
    rest = sig_part[paren_open + 1:]

    # Find closing paren
    paren_close = rest.index(")")
    params_str = rest[:paren_close].strip()
    after_paren = rest[paren_close + 1:].strip()

    # Parse params
    params: List[Tuple[str, str]] = []
    if params_str:
        for p in params_str.split(","):
            p = p.strip()
            if ":" not in p:
                raise RuntimeError(f"{path}:{line_no}: param must have 'name: type': {p!r}")
            pname, pty = p.split(":", 1)
            params.append((pname.strip(), pty.strip()))

    # Check for [dtor] tag and parse return type
    is_dtor = False
    if "[dtor]" in after_paren:
        is_dtor = True
        after_paren = after_paren.replace("[dtor]", "").strip()

    ret_type = "void"
    if after_paren.startswith("->"):
        ret_type = after_paren[2:].strip()

    return ExternFunc(bismut_name=bismut_name, params=params, ret_type=ret_type,
                      c_name=c_name, is_dtor=is_dtor)


def _parse_const_line(line: str, path: str, line_no: int) -> ExternConst:
    """Parse: BISMUT_NAME: type = c_expression"""
    if "=" not in line:
        raise RuntimeError(f"{path}:{line_no}: constant line must have '= value': {line!r}")
    decl_part, c_expr = line.split("=", 1)
    decl_part = decl_part.strip()
    c_expr = c_expr.strip()

    if ":" not in decl_part:
        raise RuntimeError(f"{path}:{line_no}: constant must have 'NAME: type': {decl_part!r}")
    name, ty = decl_part.split(":", 1)
    return ExternConst(bismut_name=name.strip(), ty=ty.strip(), c_expr=c_expr)


def _resolve_flags(entries: dict, target_platform: str | None = None) -> Tuple[List[str], List[str]]:
    """Resolve cflags/ldflags from a [flags] section dict for the current platform."""
    plat = target_platform if target_platform else _current_platform()
    cflags: List[str] = []
    ldflags: List[str] = []

    if entries.get("cflags"):
        cflags.extend(entries["cflags"].split())
    if entries.get("ldflags"):
        ldflags.extend(entries["ldflags"].split())

    plat_cflags = entries.get(f"cflags_{plat}", "")
    plat_ldflags = entries.get(f"ldflags_{plat}", "")
    if plat_cflags:
        cflags.extend(plat_cflags.split())
    if plat_ldflags:
        ldflags.extend(plat_ldflags.split())

    return (cflags, ldflags)


def find_lib(lib_name: str, src_file: str, compiler_dir: str) -> Optional[str]:
    """Find a library directory. Resolution order:
    1. libs/ relative to the source file
    2. libs/ relative to the compiler binary
    Returns absolute path to lib dir, or None.
    """
    src_dir = os.path.dirname(os.path.abspath(src_file))
    candidates = [
        os.path.join(src_dir, "libs", lib_name),
        os.path.join(compiler_dir, "libs", lib_name),
    ]
    for d in candidates:
        pxlib = os.path.join(d, f"{lib_name}.mutlib")
        if os.path.isfile(pxlib):
            return os.path.abspath(d)
    return None
