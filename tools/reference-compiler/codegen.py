from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from parser import (
    Program, FuncDecl, ClassDecl, StructDecl, InterfaceDecl, MethodSig, EnumDecl,
    Stmt, SVarDecl, SAssign, SMemberAssign, SIndexAssign, SExpr, SReturn, SBreak, SContinue, SIf, SWhile, SFor, SBlock,
    Expr, EInt, EFloat, EString, EChar, EBool, ENone, EVar, EUnary, EBinary, ECall, EMemberAccess, EIndex, EIs, EAs,
    ETuple, STupleDestructure, EListLit, EDictLit,
)

# -------------------------
# Helpers: type mapping
# -------------------------

PRIM_C = {
    "i8": "int8_t",
    "i16": "int16_t",
    "i32": "int32_t",
    "i64": "int64_t",
    "u8": "uint8_t",
    "u16": "uint16_t",
    "u32": "uint32_t",
    "u64": "uint64_t",
    "f32": "float",
    "f64": "double",
    "bool": "bool",
    "str": "__lang_rt_Str*",
    "void": "void",
}

CAST_TYPES = {"i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64", "f32", "f64"}

# ---- generic container type helpers ----
_PRIM_TAG = {
    "i8": "I8", "i16": "I16", "i32": "I32", "i64": "I64",
    "u8": "U8", "u16": "U16", "u32": "U32", "u64": "U64",
    "f32": "F32", "f64": "F64",
    "bool": "BOOL", "str": "STR",
}

def _is_list_type(ty: str) -> bool:
    return ty.startswith("List[") and ty.endswith("]")

def _list_elem(ty: str) -> str:
    """List[i64] -> i64, List[Person] -> Person"""
    return ty[5:-1]

def _is_dict_type(ty: str) -> bool:
    return ty.startswith("Dict[") and ty.endswith("]")

def _split_dict_inner(inner: str):
    """Split 'K,V' into (K, V), handling nested types."""
    depth = 0
    for i, ch in enumerate(inner):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "," and depth == 0:
            return inner[:i], inner[i+1:]
    raise ValueError(f"invalid dict inner: {inner}")

def _dict_key(ty: str) -> str:
    """Dict[str,i64] -> str"""
    k, _ = _split_dict_inner(ty[5:-1])
    return k

def _dict_val(ty: str) -> str:
    """Dict[str,i64] -> i64"""
    _, v = _split_dict_inner(ty[5:-1])
    return v

def _dict_combined_tag(ty: str) -> str:
    """Dict[str,i64] -> STR_I64"""
    k = _dict_key(ty)
    v = _dict_val(ty)
    return f"{_elem_tag(k)}_{_elem_tag(v)}"

def _split_dict_tag(combined: str):
    """Split combined dict tag 'KTAG_VTAG' into (key_tag, val_tag).
    Key tags are always single words (no underscores)."""
    i = combined.index("_")
    return combined[:i], combined[i+1:]

def _is_fn_type(ty: str) -> bool:
    return ty.startswith("Fn(") and ")->" in ty

def _is_tuple_type(ty: str) -> bool:
    return len(ty) >= 5 and ty[0] == "(" and ty[-1] == ")"

def _tuple_elem_types(ty: str) -> List[str]:
    """(i64,str,bool) -> ['i64', 'str', 'bool']"""
    inner = ty[1:-1]
    parts: List[str] = []
    depth = 0
    start = 0
    for i, ch in enumerate(inner):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(inner[start:i])
            start = i + 1
    parts.append(inner[start:])
    return parts

def _tuple_struct_name(ty: str) -> str:
    elems = _tuple_elem_types(ty)
    tags = [_elem_tag(e) for e in elems]
    return "__lang_rt_Tuple_" + "_".join(tags)

def _fn_param_types(ty: str) -> List[str]:
    """Fn(i64,str)->bool -> ['i64', 'str']"""
    inner = ty[3:ty.index(")->")]
    if not inner:
        return []
    parts: List[str] = []
    depth = 0
    start = 0
    for i, ch in enumerate(inner):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == ',' and depth == 0:
            parts.append(inner[start:i])
            start = i + 1
    parts.append(inner[start:])
    return parts

def _fn_ret_type(ty: str) -> str:
    """Fn(i64,str)->bool -> 'bool'"""
    return ty[ty.index(")->") + 3:]

def _elem_tag(elem_ty: str) -> str:
    """i64 -> I64, str -> STR, Person -> Person, List[i64] -> List_I64, Dict[str,i64] -> Dict_STR_I64"""
    if elem_ty in _PRIM_TAG:
        return _PRIM_TAG[elem_ty]
    if _is_list_type(elem_ty):
        return f"List_{_elem_tag(_list_elem(elem_ty))}"
    if _is_dict_type(elem_ty):
        return f"Dict_{_dict_combined_tag(elem_ty)}"
    if _is_fn_type(elem_ty):
        return _fn_typedef_name(elem_ty)
    if _is_tuple_type(elem_ty):
        inner_tags = [_elem_tag(et) for et in _tuple_elem_types(elem_ty)]
        return "Tuple_" + "_".join(inner_tags)
    return elem_ty

def _elem_c_type(elem_ty: str) -> str:
    if elem_ty in PRIM_C:
        return PRIM_C[elem_ty]
    if elem_ty in STRUCT_NAMES:
        return f"__lang_rt_Struct_{elem_ty}"
    if _is_list_type(elem_ty):
        tag = _elem_tag(_list_elem(elem_ty))
        return f"__lang_rt_List_{tag}*"
    if _is_dict_type(elem_ty):
        combined = _dict_combined_tag(elem_ty)
        return f"__lang_rt_Dict_{combined}*"
    if _is_fn_type(elem_ty):
        return _fn_typedef_name(elem_ty)
    if _is_tuple_type(elem_ty):
        return _tuple_struct_name(elem_ty)
    if elem_ty in IFACE_NAMES:
        return f"__lang_rt_Iface_{elem_ty}"
    return f"__lang_rt_Class_{elem_ty}*"

REF_TYPES: set = {"str"}  # extended at generate() for class types
IFACE_NAMES: set = set()  # interface names, extended at generate()
ENUM_NAMES: set = set()   # enum type names, extended at generate()
STRUCT_NAMES: set = set() # struct type names, extended at generate()


def _ci(name: str) -> str:
    """Mangle a user identifier for safe C emission.
    Appends a trailing underscore so no Bismut name can ever collide
    with a C keyword (short, long, int, double, register, auto, …).
    Applied to: field names, parameter names, member accesses, vtable slots."""
    return name + "_"


def is_ref_type(tname: str) -> bool:
    if tname in REF_TYPES:
        return True
    if tname in IFACE_NAMES:
        return True
    if _is_list_type(tname) or _is_dict_type(tname):
        return True
    if _is_fn_type(tname):
        return False  # function pointers are value types
    if _is_tuple_type(tname):
        return any(is_ref_type(et) for et in _tuple_elem_types(tname))
    return False


def _fn_typedef_name(ty: str) -> str:
    """Generate a C typedef name for a function pointer type.
    Fn(i64,str)->bool -> __lang_rt_Fn_I64_STR__BOOL"""
    params = _fn_param_types(ty)
    ret = _fn_ret_type(ty)
    parts = [_elem_tag(p) for p in params]
    ret_tag = _elem_tag(ret) if ret != "void" else "VOID"
    if parts:
        return f"__lang_rt_Fn_{'_'.join(parts)}__{ret_tag}"
    return f"__lang_rt_Fn_VOID__{ret_tag}"


def c_type(tname: str) -> str:
    if tname in PRIM_C:
        return PRIM_C[tname]
    if tname in ENUM_NAMES:
        return "int64_t"
    if tname in STRUCT_NAMES:
        return f"__lang_rt_Struct_{tname}"
    if _is_list_type(tname):
        tag = _elem_tag(_list_elem(tname))
        return f"__lang_rt_List_{tag}*"
    if _is_dict_type(tname):
        combined = _dict_combined_tag(tname)
        return f"__lang_rt_Dict_{combined}*"
    if tname in IFACE_NAMES:
        return f"__lang_rt_Iface_{tname}"
    if _is_fn_type(tname):
        return _fn_typedef_name(tname)
    if _is_tuple_type(tname):
        return _tuple_struct_name(tname)
    # Assume it's a class type (struct pointer)
    return f"__lang_rt_Class_{tname}*"


# Builtin function name -> (param_types, return_type)
BUILTIN_SIGS: Dict[str, Tuple[List[str], str]] = {}

# (print is overloaded, handled specially in _emit_call)
# (list/dict container ops are handled via generic codegen, not BUILTIN_SIGS)


# -------------------------
# String literal encoding
# -------------------------

def _unescape___lang_rt_string(raw: str) -> bytes:
    # Triple-quoted strings: """...""" or '''...'''
    if len(raw) >= 6 and raw[:3] in ('"""', "'''") and raw[-3:] == raw[:3]:
        s = raw[3:-3]
    elif len(raw) < 2 or raw[0] not in "\"'" or raw[-1] != raw[0]:
        raise ValueError(f"invalid string literal {raw!r}")
    else:
        s = raw[1:-1]
    out = bytearray()
    i = 0
    while i < len(s):
        ch = s[i]
        if ch != "\\":
            out.append(ord(ch))
            i += 1
            continue
        if i + 1 >= len(s):
            raise ValueError("dangling backslash")
        esc = s[i + 1]
        if esc == "n":
            out.append(10)
        elif esc == "t":
            out.append(9)
        elif esc == "\\":
            out.append(92)
        elif esc == '"':
            out.append(34)
        elif esc == "'":
            out.append(39)
        elif esc == "r":
            out.append(13)
        else:
            raise ValueError(f"unknown escape \\{esc}")
        i += 2
    return bytes(out)


def _c_escape_bytes(data: bytes) -> str:
    parts = ['"']
    for b in data:
        if b == 34:
            parts.append(r"\"")
        elif b == 92:
            parts.append(r"\\")
        elif b == 10:
            parts.append(r"\n")
        elif b == 9:
            parts.append(r"\t")
        elif b == 13:
            parts.append(r"\r")
        elif 32 <= b <= 126:
            parts.append(chr(b))
        else:
            parts.append(r"\x%02X" % b)
    parts.append('"')
    return "".join(parts)


def _unescape_char_literal(raw: str) -> int:
    """Convert a char literal like 'A' or '\\n' to its integer value."""
    s = raw[1:-1]  # strip surrounding quotes
    if len(s) == 1:
        return ord(s)
    if len(s) == 2 and s[0] == '\\':
        esc = s[1]
        if esc == 'n': return 10
        if esc == 't': return 9
        if esc == '\\': return 92
        if esc == "'": return 39
        if esc == '"': return 34
        if esc == '0': return 0
        if esc == 'r': return 13
    raise ValueError(f"invalid char literal {raw!r}")


def _src(loc) -> str:
    file_c = _c_escape_bytes(loc.file.encode("utf-8"))
    return f"__LANG_RT_SRC({file_c}, {loc.line}, {loc.col})"


# -------------------------
# Codegen state
# -------------------------

@dataclass
class VarInfo:
    c_name: str
    ty: str  # type name in language (e.g. i64, str, ListI64, DictStrI64)
    is_static: bool = False


class CodeGen:
    def __init__(self, debug_leaks: bool = False):
        self.out: List[str] = []
        self.ind = 0
        self.tmp = 0
        self.debug_leaks = debug_leaks

        self.env: List[Dict[str, VarInfo]] = []
        self.scope_vars: List[List[VarInfo]] = []

        self.used_list_tags: Set[str] = set()
        self.used_dict_tags: Set[str] = set()
        self.used_fn_types: Set[str] = set()  # Fn(...)->... type strings
        self.used_tuple_types: Set[str] = set()  # tuple type strings like "(i64,str)"

        self.func_sigs: Dict[str, Tuple[List[str], str]] = {}  # name -> ([param types], ret type)
        self.cur_fn_ret: Optional[str] = None
        # Temporary owned refs from call arguments that need releasing after the statement
        self._pending_releases: List[VarInfo] = []

        # Class info for codegen
        self.class_defs: Dict[str, ClassDecl] = {}  # class_name -> ClassDecl
        # Struct info for codegen
        self.struct_defs: Dict[str, StructDecl] = {}  # struct_name -> StructDecl
        # Interface info for codegen
        self.iface_defs: Dict[str, InterfaceDecl] = {}  # iface_name -> InterfaceDecl
        self.class_implements: Dict[str, List[str]] = {}  # class_name -> [iface_names]
        self.extern_type_info: Dict[str, tuple] = {}  # mangled_name -> (c_type, c_dtor)
        self.enum_variants: Dict[str, Dict[str, int]] = {}  # enum_name -> {variant_name -> value}
        self.extern_constants: Dict[str, tuple] = {}  # mangled_name -> (c_expr, bismut_type)
        self._global_scope_depth = 0  # scope_vars depth below which _release_all_scopes won't go
        self._loop_scope_depth: List[int] = []  # stack of scope_vars depths at loop entry (for break/continue cleanup)

        # String literal interning: escaped C string -> static variable name
        self._string_lits: Dict[str, str] = {}  # c_escaped_bytes -> ___lang_rt_lit_N
        self._string_lit_idx = 0
        self._string_lit_inse__lang_rt_pos = 0  # index in self.out to splice __LANG_RT_STR_LIT lines

    def w(self, s: str = "") -> None:
        self.out.append("  " * self.ind + s)

    def new_tmp(self) -> str:
        self.tmp += 1
        return f"_t{self.tmp}"

    def push_scope(self) -> None:
        self.env.append({})
        self.scope_vars.append([])

    def pop_scope(self, src_expr: str) -> None:
        vars_ = self.scope_vars.pop()
        # release in reverse (skip static vars — they persist)
        for v in reversed(vars_):
            if is_ref_type(v.ty) and not v.is_static:
                self._emit_release(v, src_expr)
        self.env.pop()

    def declare_var(self, name: str, ty: str) -> VarInfo:
        # mangle for shadowing
        self.tmp += 1
        c_name = f"{name}_{self.tmp}"
        vi = VarInfo(c_name=c_name, ty=ty)
        self.env[-1][name] = vi
        self.scope_vars[-1].append(vi)
        return vi

    def lookup(self, name: str, loc) -> VarInfo:
        for scope in reversed(self.env):
            if name in scope:
                return scope[name]
        raise RuntimeError(f"{loc.file}:{loc.line}:{loc.col}: undefined variable '{name}'")

    # -------------------------
    # Refcount helpers
    # -------------------------

    def _emit_release(self, v: VarInfo, src_expr: str) -> None:
        # Dispatch by type
        if v.ty == "str":
            self.w(f"__lang_rt_str_release({v.c_name}); (void){src_expr};")
        elif _is_list_type(v.ty):
            tag = _elem_tag(_list_elem(v.ty))
            self.w(f"__lang_rt_list_{tag}_release({v.c_name}); (void){src_expr};")
        elif _is_dict_type(v.ty):
            combined = _dict_combined_tag(v.ty)
            self.w(f"__lang_rt_dict_{combined}_release({v.c_name}); (void){src_expr};")
        elif v.ty in self.iface_defs:
            self.w(f"if ({v.c_name}.obj) {v.c_name}.vtbl->release({v.c_name}.obj); (void){src_expr};")
        elif v.ty in self.class_defs:
            self.w(f"if ({v.c_name}) __lang_rt_class_{v.ty}_release({v.c_name}); (void){src_expr};")
        elif _is_tuple_type(v.ty):
            for i, et in enumerate(_tuple_elem_types(v.ty)):
                if is_ref_type(et):
                    self._emit_release(VarInfo(c_name=f"{v.c_name}.f{i}", ty=et), src_expr)
        else:
            # primitives: no-op
            pass

    def _emit_retain_value(self, ty: str, expr: str, src_expr: str) -> None:
        if ty == "str":
            self.w(f"if ({expr}) __lang_rt_str_retain({expr}); (void){src_expr};")
        elif _is_list_type(ty):
            tag = _elem_tag(_list_elem(ty))
            self.w(f"if ({expr}) __lang_rt_list_{tag}_retain({expr}); (void){src_expr};")
        elif _is_dict_type(ty):
            combined = _dict_combined_tag(ty)
            self.w(f"if ({expr}) __lang_rt_dict_{combined}_retain({expr}); (void){src_expr};")
        elif ty in self.iface_defs:
            self.w(f"if ({expr}.obj) {expr}.vtbl->retain({expr}.obj); (void){src_expr};")
        elif ty in self.class_defs:
            self.w(f"if ({expr}) __lang_rt_class_{ty}_retain({expr}); (void){src_expr};")
        elif _is_tuple_type(ty):
            for i, et in enumerate(_tuple_elem_types(ty)):
                if is_ref_type(et):
                    self._emit_retain_value(et, f"{expr}.f{i}", src_expr)
        else:
            # primitives: nothing
            pass

    # -------------------------
    # Collect container instantiations
    # -------------------------

    def _maybe_wrap_iface(self, expr_c: str, src_ty: str, dst_ty: str) -> str:
        """If src_ty is a class and dst_ty is an interface it implements, wrap into fat pointer."""
        if dst_ty in self.iface_defs and src_ty in self.class_defs:
            return f"(__lang_rt_Iface_{dst_ty}){{.obj = {expr_c}, .vtbl = &__lang_rt_vtbl_{src_ty}_as_{dst_ty}}}"
        if dst_ty in self.iface_defs and src_ty == "none":
            return f"(__lang_rt_Iface_{dst_ty}){{.obj = NULL, .vtbl = NULL}}"
        return expr_c

    def _mark_type_use(self, tname: str) -> None:
        if _is_list_type(tname):
            elem = _list_elem(tname)
            tag = _elem_tag(elem)
            self.used_list_tags.add(tag)
            self._mark_type_use(elem)   # recurse for nested containers
        if _is_dict_type(tname):
            combined = _dict_combined_tag(tname)
            self.used_dict_tags.add(combined)
            self._mark_type_use(_dict_key(tname))  # recurse for key type
            self._mark_type_use(_dict_val(tname))   # recurse for nested containers
        if _is_fn_type(tname):
            self.used_fn_types.add(tname)
        if _is_tuple_type(tname):
            self.used_tuple_types.add(tname)
            for et in _tuple_elem_types(tname):
                self._mark_type_use(et)

    # -------------------------
    # Entry
    # -------------------------

    def generate(self, prog: Program) -> str:
        # Register extern type info
        self.extern_type_info = prog.extern_type_info

        # Register extern constants
        self.extern_constants = prog.extern_constants

        # Register interfaces
        IFACE_NAMES.clear()
        for iface in prog.interfaces:
            self.iface_defs[iface.name] = iface
            IFACE_NAMES.add(iface.name)

        # Register enums
        ENUM_NAMES.clear()
        for enum in prog.enums:
            ENUM_NAMES.add(enum.name)
            variants: Dict[str, int] = {}
            for v in enum.variants:
                variants[v.name] = v.value
            self.enum_variants[enum.name] = variants

        # Register classes
        for cls in prog.classes:
            self.class_defs[cls.name] = cls
            REF_TYPES.add(cls.name)
            self.class_implements[cls.name] = cls.implements

        # Register structs
        STRUCT_NAMES.clear()
        for st in prog.structs:
            self.struct_defs[st.name] = st
            STRUCT_NAMES.add(st.name)

        # Build function signature table
        for f in prog.funcs:
            if f.type_params:
                continue  # skip generic templates
            self.func_sigs[f.name] = ([p.ty.name for p in f.params], f.ret.name)

        # Collect type uses from decls (cheap pass)
        for f in prog.funcs:
            if f.type_params:
                continue  # skip generic templates
            self._mark_type_use(f.ret.name)
            for p in f.params:
                self._mark_type_use(p.ty.name)
            self._collect_stmt_types(f.body)
        for cls in prog.classes:
            for fd in cls.fields:
                self._mark_type_use(fd.ty.name)
            for m in cls.methods:
                self._mark_type_use(m.ret.name)
                for p in m.params:
                    if p.name != "self":
                        self._mark_type_use(p.ty.name)
                self._collect_stmt_types(m.body)
        for st_ in prog.structs:
            for fd in st_.fields:
                self._mark_type_use(fd.ty.name)
            for m in st_.methods:
                self._mark_type_use(m.ret.name)
                for p in m.params:
                    if p.name != "self":
                        self._mark_type_use(p.ty.name)
                self._collect_stmt_types(m.body)
        for st in prog.stmts:
            self._collect_stmt_types(st)

        # Emit C
        self._emit_prelude()
        self.w("")
        # Reserve position for string literal statics (filled in at the end)
        self._string_lit_inse__lang_rt_pos = len(self.out)

        # Include extern library C source files
        for inc_path in prog.extern_includes:
            self.w(f'#include "{inc_path}"')
        if prog.extern_includes:
            self.w("")

        self._emit_fn_typedefs()

        # Class forward typedefs (enables self-referential and cross-class fields)
        for cls in prog.classes:
            self.w(f"typedef struct __lang_rt_Class_{cls.name} __lang_rt_Class_{cls.name};")
        self.w("")

        # Interface vtable structs and fat pointer types (before containers, which may use them)
        for iface in prog.interfaces:
            self._emit_iface_types(iface)
        self.w("")

        # Struct typedefs (value types, no __lang_rt_Rc) — before containers so sizeof is available
        for st_ in prog.structs:
            self._emit_struct_typedef(st_)
        if prog.structs:
            self.w("")

        self._emit_container_instantiations()
        self.w("")

        # Tuple struct typedefs
        self._emit_tuple_typedefs()

        # Class struct definitions + forward declarations
        for cls in prog.classes:
            self._emit_class_struct(cls)
        self.w("")

        # prototypes for functions
        for f in prog.funcs:
            if f.type_params:
                continue
            self.w(self._fn_proto(f) + ";")
        self.w("")

        # Global variables: emit file-scope C declarations
        self._emit_global_vars(prog)
        # Mark global scope depth so functions don't release globals
        self._global_scope_depth = len(self.scope_vars)

        # Class methods (constructor, destructor, retain/release, user methods)
        for cls in prog.classes:
            self._emit_class_methods(cls)
        self.w("")

        # Struct methods
        for st_ in prog.structs:
            for m in st_.methods:
                self._emit_struct_method(st_, m)
        if prog.structs:
            self.w("")

        # Interface vtable instances (one per class-interface pair)
        for cls in prog.classes:
            for iname in cls.implements:
                self._emit_vtable_instance(cls, self.iface_defs[iname])
        self.w("")

        # function bodies
        for f in prog.funcs:
            if f.type_params:
                continue
            if f.extern_c_name:
                self._emit_extern_wrapper(f)
            else:
                self._emit_function(f)
            self.w("")

        # program() + main()
        self._emit_program(prog)
        self.w("")

        # Pop global scope (env only, globals freed in __lang_rt_program)
        self.env.pop()
        self.scope_vars.pop()
        self._emit_main(prog)
        # Splice interned string literal statics at the reserved position
        if self._string_lits:
            lit_lines = []
            for c_escaped, var_name in self._string_lits.items():
                # Recover original byte length from the escaped string
                lit_lines.append(f"__LANG_RT_STR_LIT({var_name}, {c_escaped});")
            lit_lines.append("")
            for i, line in enumerate(lit_lines):
                self.out.insert(self._string_lit_inse__lang_rt_pos + i, line)
        return "\n".join(self.out)

    def _collect_stmt_types(self, st: Stmt) -> None:
        # mark types from var decls and nested statements
        if isinstance(st, SVarDecl):
            if st.ty is not None:
                self._mark_type_use(st.ty.name)
            self._collect_expr_types(st.value)
        elif isinstance(st, SAssign):
            self._collect_expr_types(st.value)
        elif isinstance(st, SMemberAssign):
            self._collect_expr_types(st.obj)
            self._collect_expr_types(st.value)
        elif isinstance(st, SIndexAssign):
            self._collect_expr_types(st.obj)
            self._collect_expr_types(st.index)
            self._collect_expr_types(st.value)
        elif isinstance(st, SExpr):
            self._collect_expr_types(st.expr)
        elif isinstance(st, SReturn):
            if st.value: self._collect_expr_types(st.value)
        elif isinstance(st, SIf):
            for arm in st.arms:
                if arm.cond: self._collect_expr_types(arm.cond)
                for s2 in arm.block.stmts:
                    self._collect_stmt_types(s2)
        elif isinstance(st, SWhile):
            self._collect_expr_types(st.cond)
            for s2 in st.body.stmts:
                self._collect_stmt_types(s2)
        elif isinstance(st, SFor):
            self._mark_type_use(st.var_ty.name)  # register annotated element type container
            self._collect_expr_types(st.iterable)
            for s2 in st.body.stmts:
                self._collect_stmt_types(s2)
        elif isinstance(st, SBlock):
            for s2 in st.stmts:
                self._collect_stmt_types(s2)
        elif isinstance(st, STupleDestructure):
            self._collect_expr_types(st.value)
        else:
            pass

    def _collect_expr_types(self, e: Expr) -> None:
        if isinstance(e, (EInt, EFloat, EString, EChar, EBool, EVar, ENone)):
            return
        if isinstance(e, EIs):
            self._collect_expr_types(e.expr)
            return
        if isinstance(e, EAs):
            self._collect_expr_types(e.expr)
            return
        if isinstance(e, EUnary):
            self._collect_expr_types(e.rhs)
            return
        if isinstance(e, EBinary):
            self._collect_expr_types(e.lhs)
            self._collect_expr_types(e.rhs)
            return
        if isinstance(e, EMemberAccess):
            # Check for enum variant access: EnumName.VARIANT
            if isinstance(e.obj, EVar) and e.obj.name in ENUM_NAMES:
                pass  # no sub-expressions to collect
            else:
                self._collect_expr_types(e.obj)
            return
        if isinstance(e, EIndex):
            self._collect_expr_types(e.obj)
            self._collect_expr_types(e.index)
            return
        if isinstance(e, ECall):
            # Detect range/keys calls to pre-register container tags
            if isinstance(e.callee, EVar):
                if e.callee.name == "range":
                    self.used_list_tags.add("I64")
            # Generic container ops: register tag from type_param
            _LIST_OPS = {"List", "append", "get", "set", "pop", "remove"}
            _DICT_OPS = {"Dict", "put", "lookup", "has"}
            if e.type_param is not None:
                if isinstance(e.callee, EVar):
                    nm = e.callee.name
                    if nm in _LIST_OPS:
                        tag = _elem_tag(e.type_param)
                        self.used_list_tags.add(tag)
                    elif nm in _DICT_OPS:
                        # type_param is "K,V" for dict ops
                        k, v = _split_dict_inner(e.type_param)
                        combined = f"{_elem_tag(k)}_{_elem_tag(v)}"
                        self.used_dict_tags.add(combined)
                    else:
                        # User-defined generic function — no container registration needed
                        pass
                # Recursively register nested container element types
                if isinstance(e.callee, EVar) and e.callee.name in _DICT_OPS:
                    # type_param is "K,V" — mark as Dict type
                    self._mark_type_use(f"Dict[{e.type_param}]")
                else:
                    self._mark_type_use(e.type_param)
            self._collect_expr_types(e.callee)
            for a in e.args:
                self._collect_expr_types(a)
            return
        if isinstance(e, ETuple):
            for elem in e.elems:
                self._collect_expr_types(elem)
            return
        if isinstance(e, EListLit):
            tag = _elem_tag(e.elem_type)
            self.used_list_tags.add(tag)
            self._mark_type_use(e.elem_type)
            for elem in e.elems:
                self._collect_expr_types(elem)
            return
        if isinstance(e, EDictLit):
            combined = f"{_elem_tag(e.key_type)}_{_elem_tag(e.val_type)}"
            self.used_dict_tags.add(combined)
            self._mark_type_use(f"Dict[{e.key_type},{e.val_type}]")
            for k in e.keys:
                self._collect_expr_types(k)
            for v in e.vals:
                self._collect_expr_types(v)
            return

    # -------------------------
    # Prelude + containers
    # -------------------------

    def _emit_prelude(self) -> None:
        if self.debug_leaks:
            self.w('#define __LANG_RT_DEBUG_LEAKS')
        self.w('#if !defined(_WIN32) && !defined(__APPLE__)')
        self.w('  #define _POSIX_C_SOURCE 199309L')
        self.w('#endif')
        self.w('#include <stdint.h>')
        self.w('#include <stdbool.h>')
        self.w('#include "rt_runtime.h"')
        self.w("")
        self.w("#define __LANG_RT_SRC(file, line, col) __lang_rt_src((file), (line), (col))")
        self.w("")
        # Global argc/argv for extern libs (os lib) to access
        self.w("int __lang_rt_argc_ = 0;")
        self.w("char** __lang_rt_argv_ = NULL;")

    def _emit_tuple_typedefs(self) -> None:
        # Emit in dependency order: inner tuples before outer ones
        emitted: set = set()
        def _emit_one(ty: str) -> None:
            if ty in emitted:
                return
            for et in _tuple_elem_types(ty):
                if _is_tuple_type(et) and et in self.used_tuple_types:
                    _emit_one(et)
            struct_name = _tuple_struct_name(ty)
            elem_types = _tuple_elem_types(ty)
            fields = "; ".join(f"{c_type(et)} f{i}" for i, et in enumerate(elem_types))
            self.w(f"typedef struct {{ {fields}; }} {struct_name};")
            emitted.add(ty)
        for ty in sorted(self.used_tuple_types):
            _emit_one(ty)
        if self.used_tuple_types:
            self.w("")

    def _emit_container_instantiations(self) -> None:
        _PRIM = {
            "I8": ("int8_t", False), "I16": ("int16_t", False),
            "I32": ("int32_t", False), "I64": ("int64_t", False),
            "U8": ("uint8_t", False), "U16": ("uint16_t", False),
            "U32": ("uint32_t", False), "U64": ("uint64_t", False),
            "F32": ("float", False), "F64": ("double", False),
            "BOOL": ("bool", False), "STR": ("__lang_rt_Str*", True),
        }

        def _tag_cat(tag):
            """Classify a tag: 'prim', 'list', 'dict', 'fn', 'iface', 'struct', or 'class'."""
            if tag in _PRIM:
                return 'prim'
            if tag.startswith("List_"):
                return 'list'
            if tag.startswith("Dict_"):
                return 'dict'
            if tag.startswith("__lang_rt_Fn_"):
                return 'fn'
            if tag in IFACE_NAMES:
                return 'iface'
            if tag in STRUCT_NAMES:
                return 'struct'
            return 'class'

        # ---- Forward-declare class types used in containers ----
        class_tags = set()
        # For list tags, check the tag directly
        for tag in self.used_list_tags:
            cat = _tag_cat(tag)
            if cat == 'class':
                class_tags.add(tag)
        # For dict tags (combined KTAG_VTAG), check the val tag
        for combined in self.used_dict_tags:
            _, val_tag = _split_dict_tag(combined)
            cat = _tag_cat(val_tag)
            if cat == 'class':
                class_tags.add(val_tag)
        if class_tags:
            self.w("// ---- forward declarations for class types in containers ----")
            for tag in sorted(class_tags):
                self.w(f"typedef struct __lang_rt_Class_{tag} __lang_rt_Class_{tag};")
                self.w(f"static void __lang_rt_class_{tag}_retain(__lang_rt_Class_{tag}* o);")
                self.w(f"static void __lang_rt_class_{tag}_release(__lang_rt_Class_{tag}* o);")
            self.w("")

        # ---- Ensure List[K] exists for every Dict[K,V] (keys() support) ----
        for combined in self.used_dict_tags:
            key_tag, _ = _split_dict_tag(combined)
            self.used_list_tags.add(key_tag)

        # ---- Topological sort: inner containers before outer ----
        all_entries = [('list', t) for t in self.used_list_tags] + \
                      [('dict', t) for t in self.used_dict_tags]
        visited: set = set()
        ordered: list = []

        def visit(kind, tag):
            key = (kind, tag)
            if key in visited:
                return
            visited.add(key)
            if kind == 'list':
                cat = _tag_cat(tag)
                if cat == 'list':
                    visit('list', tag[5:])
                elif cat == 'dict':
                    visit('dict', tag[5:])  # strips "Dict_" to get combined tag
            elif kind == 'dict':
                # tag is combined "KTAG_VTAG"
                _, val_tag = _split_dict_tag(tag)
                cat = _tag_cat(val_tag)
                if cat == 'list':
                    visit('list', val_tag[5:])
                elif cat == 'dict':
                    visit('dict', val_tag[5:])
            ordered.append(key)

        for kind, tag in all_entries:
            visit(kind, tag)

        # ---- Helper: compute C type + drop/clone for an element tag ----
        def _drop_clone(tag, vprefix="", name_tag=None):
            """Return (c_type, drop_macro, clone_macro) for an element tag.
            name_tag overrides the macro name suffix (used for dict value macros)."""
            nt = name_tag if name_tag else tag
            dp = vprefix
            cat = _tag_cat(tag)
            if cat == 'prim':
                ct, is_ref = _PRIM[tag]
                if is_ref:
                    drop = f"#define __LANG_RT_{dp}DROP_{nt}(x) do {{ __lang_rt_str_release((x)); }} while(0)"
                    clone = f"#define __LANG_RT_{dp}CLONE_{nt}(dst, src) do {{ (dst) = (src); __lang_rt_str_retain((src)); }} while(0)"
                else:
                    drop = f"#define __LANG_RT_{dp}DROP_{nt}(x) ((void)(x))"
                    clone = f"#define __LANG_RT_{dp}CLONE_{nt}(dst, src) do {{ (dst) = (src); }} while(0)"
                return ct, drop, clone
            elif cat == 'list':
                inner_tag = tag[5:]
                ct = f"__lang_rt_List_{inner_tag}*"
                drop = f"#define __LANG_RT_{dp}DROP_{nt}(x) do {{ if ((x)) __lang_rt_list_{inner_tag}_release((x)); }} while(0)"
                clone = f"#define __LANG_RT_{dp}CLONE_{nt}(dst, src) do {{ (dst) = (src); if ((src)) __lang_rt_list_{inner_tag}_retain((src)); }} while(0)"
                return ct, drop, clone
            elif cat == 'dict':
                inner_tag = tag[5:]  # strips "Dict_" prefix to get combined tag
                ct = f"__lang_rt_Dict_{inner_tag}*"
                drop = f"#define __LANG_RT_{dp}DROP_{nt}(x) do {{ if ((x)) __lang_rt_dict_{inner_tag}_release((x)); }} while(0)"
                clone = f"#define __LANG_RT_{dp}CLONE_{nt}(dst, src) do {{ (dst) = (src); if ((src)) __lang_rt_dict_{inner_tag}_retain((src)); }} while(0)"
                return ct, drop, clone
            elif cat == 'fn':
                ct = tag
                drop = f"#define __LANG_RT_{dp}DROP_{nt}(x) ((void)(x))"
                clone = f"#define __LANG_RT_{dp}CLONE_{nt}(dst, src) do {{ (dst) = (src); }} while(0)"
                return ct, drop, clone
            elif cat == 'iface':
                ct = f"__lang_rt_Iface_{tag}"
                drop = f"#define __LANG_RT_{dp}DROP_{nt}(x) do {{ if ((x).obj) (x).vtbl->release((x).obj); }} while(0)"
                clone = f"#define __LANG_RT_{dp}CLONE_{nt}(dst, src) do {{ (dst) = (src); if ((src).obj) (src).vtbl->retain((src).obj); }} while(0)"
                return ct, drop, clone
            elif cat == 'struct':
                ct = f"__lang_rt_Struct_{tag}"
                drop = f"#define __LANG_RT_{dp}DROP_{nt}(x) ((void)(x))"
                clone = f"#define __LANG_RT_{dp}CLONE_{nt}(dst, src) do {{ (dst) = (src); }} while(0)"
                return ct, drop, clone
            else:
                ct = f"__lang_rt_Class_{tag}*"
                drop = f"#define __LANG_RT_{dp}DROP_{nt}(x) do {{ if ((x)) __lang_rt_class_{tag}_release((x)); }} while(0)"
                clone = f"#define __LANG_RT_{dp}CLONE_{nt}(dst, src) do {{ (dst) = (src); if ((src)) __lang_rt_class_{tag}_retain((src)); }} while(0)"
                return ct, drop, clone

        # ---- Emit container definitions in dependency order ----
        if ordered:
            self.w("// ---- container instantiations ----")
        for kind, tag in ordered:
            if kind == 'list':
                ct, drop, clone = _drop_clone(tag, "")
                self.w(drop)
                self.w(clone)
                self.w(f"__LANG_RT_LIST_DEFINE({tag}, {ct}, __LANG_RT_DROP_{tag}, __LANG_RT_CLONE_{tag})")
                self.w("")
            else:  # dict — tag is combined "KTAG_VTAG"
                key_tag, val_tag = _split_dict_tag(tag)
                # Value type drop/clone (named with combined tag to avoid collisions)
                vct, vdrop, vclone = _drop_clone(val_tag, "V", name_tag=tag)
                self.w(vdrop)
                self.w(vclone)
                # Key type macros
                if key_tag == "STR":
                    kct = "__lang_rt_Str*"
                    khash = "__LANG_RT_KHASH_STR"
                    keq = "__LANG_RT_KEQ_STR"
                    kclone = "__LANG_RT_KCLONE_STR"
                    kdrop = "__LANG_RT_KDROP_STR"
                    knull = "__LANG_RT_KNULL_STR"
                else:
                    kct = _PRIM.get(key_tag, ("int64_t", False))[0]
                    khash = "__LANG_RT_KHASH_INT"
                    keq = "__LANG_RT_KEQ_INT"
                    kclone = "__LANG_RT_KCLONE_INT"
                    kdrop = "__LANG_RT_KDROP_INT"
                    knull = "__LANG_RT_KNULL_INT"
                self.w(f"__LANG_RT_DICT_DEFINE({tag}, {kct}, {vct}, {khash}, {keq}, {kclone}, {kdrop}, {knull}, __LANG_RT_VCLONE_{tag}, __LANG_RT_VDROP_{tag})")
                self.w("")

        # range() helper — needs __lang_rt_List_I64 to exist
        if "I64" in self.used_list_tags:
            self.w('#include "rt_range.h"')
            self.w("")

        # keys() helpers — emit after all container instantiations
        if self.used_dict_tags:
            for combined in sorted(self.used_dict_tags):
                key_tag, _ = _split_dict_tag(combined)
                self.w(f"__LANG_RT_DICT_KEYS_DEFINE({combined}, {key_tag})")
            self.w("")

    # -------------------------
    # Function pointer typedefs
    # -------------------------

    def _emit_fn_typedefs(self) -> None:
        if not self.used_fn_types:
            return
        self.w("// ---- function pointer typedefs ----")
        for fn_ty in sorted(self.used_fn_types):
            params = _fn_param_types(fn_ty)
            ret = _fn_ret_type(fn_ty)
            td_name = _fn_typedef_name(fn_ty)
            ret_c = c_type(ret)
            if params:
                params_c = ", ".join(c_type(p) for p in params)
            else:
                params_c = "void"
            self.w(f"typedef {ret_c} (*{td_name})({params_c});")
        self.w("")

    # -------------------------
    # Class emission
    # -------------------------

    def _emit_class_struct(self, cls: ClassDecl) -> None:
        name = cls.name
        if name in self.extern_type_info:
            self._emit_extern_type_struct(cls)
            return
        self.w(f"struct __lang_rt_Class_{name} " + "{")
        self.ind += 1
        self.w("__lang_rt_Rc rc;")
        for fd in cls.fields:
            self.w(f"{c_type(fd.ty.name)} {_ci(fd.name)};")
        self.ind -= 1
        self.w("};")
        self.w("")
        # Forward declare retain/release/methods
        self.w(f"static void __lang_rt_class_{name}_dtor(void* obj);")
        self.w(f"static void __lang_rt_class_{name}_retain(__lang_rt_Class_{name}* o);")
        self.w(f"static void __lang_rt_class_{name}_release(__lang_rt_Class_{name}* o);")
        for m in cls.methods:
            if m.name == "init":
                # Constructor returns new instance
                params_c = ", ".join([f"{c_type(p.ty.name)} {_ci(p.name)}" for p in m.params[1:]])
                self.w(f"static __lang_rt_Class_{name}* __lang_rt_class_{name}_new(__lang_rt_Src __lang_rt__src{',' if params_c else ''} {params_c});")
            else:
                ret_c = c_type(m.ret.name)
                params_c = f"__lang_rt_Class_{name}* self"
                for p in m.params[1:]:
                    params_c += f", {c_type(p.ty.name)} {_ci(p.name)}"
                self.w(f"static {ret_c} __lang_rt_class_{name}_{m.name}({params_c});")
        self.w("")

    def _emit_extern_type_struct(self, cls: ClassDecl) -> None:
        """Emit wrapper struct for an extern opaque type: refcount + raw C pointer."""
        name = cls.name
        c_type_name, _ = self.extern_type_info[name]
        self.w(f"struct __lang_rt_Class_{name} " + "{")
        self.ind += 1
        self.w("__lang_rt_Rc rc;")
        self.w(f"{c_type_name}* ptr;")
        self.ind -= 1
        self.w("};")
        self.w("")
        self.w(f"static void __lang_rt_class_{name}_dtor(void* obj);")
        self.w(f"static void __lang_rt_class_{name}_retain(__lang_rt_Class_{name}* o);")
        self.w(f"static void __lang_rt_class_{name}_release(__lang_rt_Class_{name}* o);")
        self.w(f"static __lang_rt_Class_{name}* __lang_rt_extern_{name}_wrap({c_type_name}* ptr);")
        self.w("")

    def _emit_extern_type_methods(self, cls: ClassDecl) -> None:
        """Emit dtor/retain/release/wrap for an extern opaque type."""
        name = cls.name
        c_type_name, c_dtor = self.extern_type_info[name]

        # Destructor — calls the C library's destroy function (if one was declared)
        self.w(f"static void __lang_rt_class_{name}_dtor(void* obj) " + "{")
        self.ind += 1
        self.w(f"__lang_rt_Class_{name}* self = (__lang_rt_Class_{name}*)obj;")
        if c_dtor:
            self.w(f"if (self->ptr) {c_dtor}(self->ptr);")
        self.w("__LANG_RT_LEAK_UNTRACK(self);")
        self.w("free(self);")
        self.ind -= 1
        self.w("}")
        self.w("")

        # Retain / release
        self.w(f"static void __lang_rt_class_{name}_retain(__lang_rt_Class_{name}* o) " + "{ __lang_rt_retain(o); }")
        self.w(f"static void __lang_rt_class_{name}_release(__lang_rt_Class_{name}* o) " + "{ __lang_rt_release(o, __lang_rt_class_" + name + "_dtor); }")
        self.w("")

        # Wrap: create a refcounted box around a raw C pointer
        self.w(f"static __lang_rt_Class_{name}* __lang_rt_extern_{name}_wrap({c_type_name}* ptr) " + "{")
        self.ind += 1
        self.w(f"__lang_rt_Class_{name}* obj = (__lang_rt_Class_{name}*)malloc(sizeof(__lang_rt_Class_{name}));")
        self.w("__lang_rt_rc_init(&obj->rc);")
        self.w(f'__LANG_RT_LEAK_TRACK(obj, "{name}", NULL, 0, 0);')
        self.w("obj->ptr = ptr;")
        self.w("return obj;")
        self.ind -= 1
        self.w("}")
        self.w("")

    def _emit_class_methods(self, cls: ClassDecl) -> None:
        name = cls.name
        if name in self.extern_type_info:
            self._emit_extern_type_methods(cls)
            return

        # Destructor
        self.w(f"static void __lang_rt_class_{name}_dtor(void* obj) " + "{")
        self.ind += 1
        self.w(f"__lang_rt_Class_{name}* self = (__lang_rt_Class_{name}*)obj;")
        for fd in cls.fields:
            if is_ref_type(fd.ty.name):
                if fd.ty.name == "str":
                    self.w(f"if (self->{_ci(fd.name)}) __lang_rt_str_release(self->{_ci(fd.name)});")
                elif _is_list_type(fd.ty.name):
                    tag = _elem_tag(_list_elem(fd.ty.name))
                    self.w(f"if (self->{_ci(fd.name)}) __lang_rt_list_{tag}_release(self->{_ci(fd.name)});")
                elif _is_dict_type(fd.ty.name):
                    combined = _dict_combined_tag(fd.ty.name)
                    self.w(f"if (self->{_ci(fd.name)}) __lang_rt_dict_{combined}_release(self->{_ci(fd.name)});")
                elif fd.ty.name in self.iface_defs:
                    self.w(f"if (self->{_ci(fd.name)}.obj) self->{_ci(fd.name)}.vtbl->release(self->{_ci(fd.name)}.obj);")
                elif fd.ty.name in self.class_defs:
                    self.w(f"if (self->{_ci(fd.name)}) __lang_rt_class_{fd.ty.name}_release(self->{_ci(fd.name)});")
        self.w("__LANG_RT_LEAK_UNTRACK(self);")
        self.w("free(self);")
        self.ind -= 1
        self.w("}")
        self.w("")

        # Retain / release
        self.w(f"static void __lang_rt_class_{name}_retain(__lang_rt_Class_{name}* o) " + "{ __lang_rt_retain(o); }")
        self.w(f"static void __lang_rt_class_{name}_release(__lang_rt_Class_{name}* o) " + "{ __lang_rt_release(o, __lang_rt_class_" + name + "_dtor); }")
        self.w("")

        # Constructor (init method)
        init_method = None
        for m in cls.methods:
            if m.name == "init":
                init_method = m
                break

        params_c = ", ".join([f"{c_type(p.ty.name)} {_ci(p.name)}" for p in (init_method.params[1:] if init_method else [])])
        self.w(f"static __lang_rt_Class_{name}* __lang_rt_class_{name}_new(__lang_rt_Src __lang_rt__src{',' if params_c else ''} {params_c}) " + "{")
        self.ind += 1
        self.w(f"__lang_rt_Class_{name}* self = (__lang_rt_Class_{name}*)__lang_rt_malloc(__lang_rt__src, sizeof(__lang_rt_Class_{name}));")
        self.w("__lang_rt_rc_init(&self->rc);")
        self.w(f'__LANG_RT_LEAK_TRACK(self, "{name}", __lang_rt__src.file, __lang_rt__src.line, __lang_rt__src.col);')
        # Zero-init all fields
        for fd in cls.fields:
            if fd.ty.name in self.iface_defs:
                self.w(f"self->{_ci(fd.name)}.obj = NULL;")
                self.w(f"self->{_ci(fd.name)}.vtbl = NULL;")
            elif is_ref_type(fd.ty.name):
                self.w(f"self->{_ci(fd.name)} = NULL;")
            elif fd.ty.name in ("i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64"):
                self.w(f"self->{_ci(fd.name)} = 0;")
            elif fd.ty.name in ("f32", "f64"):
                self.w(f"self->{_ci(fd.name)} = 0.0;")
            elif fd.ty.name == "bool":
                self.w(f"self->{_ci(fd.name)} = false;")
            elif fd.ty.name in ENUM_NAMES:
                self.w(f"self->{_ci(fd.name)} = 0;")

        # Emit init body if present
        if init_method:
            self.push_scope()
            # 'self' is already defined as a local variable above
            vi_self = VarInfo(c_name="self", ty=name)
            self.env[-1]["self"] = vi_self
            # Do NOT add self to scope_vars (we don't release self at scope end)
            for p in init_method.params[1:]:
                vi = VarInfo(c_name=_ci(p.name), ty=p.ty.name)
                self.env[-1][p.name] = vi
                self.scope_vars[-1].append(vi)
            for st in init_method.body.stmts:
                self._emit_stmt(st, allow_break=False, allow_continue=False)
            # Don't pop_scope normally (we handle cleanup manually)
            self.env.pop()
            self.scope_vars.pop()

        self.w("return self;")
        self.ind -= 1
        self.w("}")
        self.w("")

        # Other methods
        for m in cls.methods:
            if m.name == "init":
                continue
            self._emit_class_method(cls, m)

    def _emit_class_method(self, cls: ClassDecl, m: FuncDecl) -> None:
        name = cls.name
        ret_c = c_type(m.ret.name)
        params_c = f"__lang_rt_Class_{name}* self"
        for p in m.params[1:]:
            params_c += f", {c_type(p.ty.name)} {_ci(p.name)}"

        self.cur_fn_ret = m.ret.name
        self.w(f"static {ret_c} __lang_rt_class_{name}_{m.name}({params_c}) " + "{")
        self.ind += 1

        self.push_scope()
        # self is in scope but not owned by this function (don't release)
        vi_self = VarInfo(c_name="self", ty=name)
        self.env[-1]["self"] = vi_self
        # params (non-self) are borrowed from caller (don't release)
        for p in m.params[1:]:
            vi = VarInfo(c_name=_ci(p.name), ty=p.ty.name)
            self.env[-1][p.name] = vi

        for st in m.body.stmts:
            self._emit_stmt(st, allow_break=False, allow_continue=False)

        # default return
        self._emit_default_return(m.ret.name, _src(m.loc))
        self.pop_scope(_src(m.loc))
        self.ind -= 1
        self.w("}")
        self.w("")
        self.cur_fn_ret = None

    # -------------------------
    # Struct emission
    # -------------------------

    def _emit_struct_typedef(self, st: StructDecl) -> None:
        """Emit a C typedef for a value-type struct (no __lang_rt_Rc, no heap)."""
        name = st.name
        self.w(f"typedef struct __lang_rt_Struct_{name}_s " + "{")
        self.ind += 1
        for fd in st.fields:
            self.w(f"{c_type(fd.ty.name)} {_ci(fd.name)};")
        self.ind -= 1
        self.w("}" + f" __lang_rt_Struct_{name};")
        # Forward declare methods
        for m in st.methods:
            ret_c = c_type(m.ret.name)
            params_c = f"__lang_rt_Struct_{name} self"
            for p in m.params[1:]:
                params_c += f", {c_type(p.ty.name)} {_ci(p.name)}"
            self.w(f"static {ret_c} __lang_rt_struct_{name}_{m.name}({params_c});")
        self.w("")

    def _emit_struct_method(self, st: StructDecl, m: FuncDecl) -> None:
        name = st.name
        ret_c = c_type(m.ret.name)
        params_c = f"__lang_rt_Struct_{name} self"
        for p in m.params[1:]:
            params_c += f", {c_type(p.ty.name)} {_ci(p.name)}"

        self.cur_fn_ret = m.ret.name
        self.w(f"static {ret_c} __lang_rt_struct_{name}_{m.name}({params_c}) " + "{")
        self.ind += 1

        self.push_scope()
        # self is passed by value — treat as a local (but don't release it since struct is not ref type)
        vi_self = VarInfo(c_name="self", ty=name)
        self.env[-1]["self"] = vi_self
        # params (non-self) — borrowed from caller
        for p in m.params[1:]:
            vi = VarInfo(c_name=_ci(p.name), ty=p.ty.name)
            self.env[-1][p.name] = vi

        for stmt in m.body.stmts:
            self._emit_stmt(stmt, allow_break=False, allow_continue=False)

        # default return
        self._emit_default_return(m.ret.name, _src(m.loc))
        self.pop_scope(_src(m.loc))
        self.ind -= 1
        self.w("}")
        self.w("")
        self.cur_fn_ret = None

    # -------------------------
    # Interface emission
    # -------------------------

    def _emit_iface_types(self, iface: InterfaceDecl) -> None:
        """Emit vtable struct and fat pointer type for an interface."""
        name = iface.name
        # Vtable struct
        self.w(f"typedef struct __lang_rt_Vtbl_{name} " + "{")
        self.ind += 1
        self.w("void (*retain)(void*);")
        self.w("void (*release)(void*);")
        for ms in iface.method_sigs:
            ret_c = c_type(ms.ret.name)
            params = "void*"
            for p in ms.params[1:]:  # skip self
                params += f", {c_type(p.ty.name)}"
            self.w(f"{ret_c} (*{_ci(ms.name)})({params});")
        self.ind -= 1
        self.w("}" + f" __lang_rt_Vtbl_{name};")
        self.w("")
        # Fat pointer struct
        self.w(f"typedef struct __lang_rt_Iface_{name} " + "{")
        self.ind += 1
        self.w("void* obj;")
        self.w(f"__lang_rt_Vtbl_{name}* vtbl;")
        self.ind -= 1
        self.w("}" + f" __lang_rt_Iface_{name};")
        self.w("")

    def _emit_vtable_instance(self, cls: ClassDecl, iface: InterfaceDecl) -> None:
        """Emit a static vtable instance for a class implementing an interface."""
        cname = cls.name
        iname = iface.name
        self.w(f"static __lang_rt_Vtbl_{iname} __lang_rt_vtbl_{cname}_as_{iname} = " + "{")
        self.ind += 1
        self.w(f".retain = (void(*)(void*))__lang_rt_class_{cname}_retain,")
        self.w(f".release = (void(*)(void*))__lang_rt_class_{cname}_release,")
        for ms in iface.method_sigs:
            ret_c = c_type(ms.ret.name)
            params = "void*"
            for p in ms.params[1:]:
                params += f", {c_type(p.ty.name)}"
            self.w(f".{_ci(ms.name)} = ({ret_c}(*)({params}))__lang_rt_class_{cname}_{ms.name},")
        self.ind -= 1
        self.w("};")
        self.w("")

    # -------------------------
    # Functions / statements
    # -------------------------

    def _fn_proto(self, f: FuncDecl) -> str:
        ret_c = c_type(f.ret.name)
        params_c = ", ".join([f"{c_type(p.ty.name)} {_ci(p.name)}" for p in f.params])
        if not params_c:
            params_c = "void"
        return f"static {ret_c} __lang_rt_fn_{f.name}({params_c})"

    def _emit_extern_wrapper(self, f: FuncDecl) -> None:
        """Emit a thin wrapper that calls the C function for an extern library function.
        For extern types: unwrap params (->ptr) and wrap returns (__lang_rt_extern_X_wrap)."""
        self.w(self._fn_proto(f) + " {")
        self.ind += 1

        # Build argument list, unwrapping extern type params
        args = []
        for p in f.params:
            if p.ty.name in self.extern_type_info:
                args.append(f"{_ci(p.name)}->ptr")
            else:
                args.append(_ci(p.name))
        args_str = ", ".join(args)

        ret_ty = f.ret.name
        if ret_ty == "void":
            self.w(f"{f.extern_c_name}({args_str});")
        elif ret_ty in self.extern_type_info:
            # Wrap raw C pointer in refcounted box
            self.w(f"return __lang_rt_extern_{ret_ty}_wrap({f.extern_c_name}({args_str}));")
        else:
            self.w(f"return {f.extern_c_name}({args_str});")

        self.ind -= 1
        self.w("}")

    def _emit_function(self, f: FuncDecl) -> None:
        self.cur_fn_ret = f.ret.name
        self.w(self._fn_proto(f) + " {")
        self.ind += 1

        self.push_scope()

        # Parameters: declare in env but NOT in scope_vars.
        # Parameters are borrowed from caller; caller manages ownership.
        for p in f.params:
            vi = VarInfo(c_name=_ci(p.name), ty=p.ty.name)
            self.env[-1][p.name] = vi

        # body
        for st in f.body.stmts:
            self._emit_stmt(st, allow_break=False, allow_continue=False)

        # default return if missing (typechecker should prevent)
        self._emit_default_return(f.ret.name, _src(f.loc))

        self.pop_scope(_src(f.loc))
        self.ind -= 1
        self.w("}")
        self.cur_fn_ret = None

    def _emit_stmt(self, st: Stmt, allow_break: bool, allow_continue: bool) -> None:
        if isinstance(st, SVarDecl):
            ty = st.ty.name
            ct = c_type(ty)
            self._mark_type_use(ty)
            vi = self.declare_var(st.name, ty)
            src = _src(st.loc)

            if st.is_static:
                vi.is_static = True
                expr_c, expr_ty = self._emit_expr(st.value)
                expr_c = self._maybe_wrap_iface(expr_c, expr_ty, ty)
                # C requires static initializers to be compile-time constants.
                # Use a guard flag for lazy one-time initialization.
                guard = f"_init_{vi.c_name}"
                self.w(f"static int {guard} = 0;")
                self.w(f"static {ct} {vi.c_name};")
                self.w(f"if (!{guard}) " + "{")
                self.ind += 1
                self.w(f"{guard} = 1;")
                self.w(f"{vi.c_name} = {expr_c};")
                if is_ref_type(ty) and self._expr_is_borrowed(st.value):
                    self._emit_retain_value(ty, vi.c_name, src)
                self.ind -= 1
                self.w("}")
            else:
                expr_c, expr_ty = self._emit_expr(st.value)
                # Wrap class->interface conversion
                expr_c = self._maybe_wrap_iface(expr_c, expr_ty, ty)
                self.w(f"{ct} {vi.c_name} = {expr_c};")
                if is_ref_type(ty) and self._expr_is_borrowed(st.value):
                    self._emit_retain_value(ty, vi.c_name, src)
            self._flush_pending_releases(src)
            return

        if isinstance(st, SAssign):
            vi = self.lookup(st.name, st.loc)
            src = _src(st.loc)
            expr_c, expr_ty = self._emit_expr(st.value)

            # "=" assignment: release old if ref, then assign, then retain if borrowed
            if st.op == "=":
                if is_ref_type(vi.ty):
                    # Wrap class->interface conversion
                    expr_c = self._maybe_wrap_iface(expr_c, expr_ty, vi.ty)
                    # Materialize RHS into temp FIRST (RHS may reference LHS variable)
                    tmp = self.new_tmp()
                    self.w(f"{c_type(vi.ty)} {tmp} = {expr_c};")
                    # Retain if borrowed (e.g., variable read, append, member access)
                    if self._expr_is_borrowed(st.value):
                        self._emit_retain_value(vi.ty, tmp, src)
                    # Release old value
                    self._emit_release(vi, src)
                    # Assign
                    self.w(f"{vi.c_name} = {tmp};")
                    self._flush_pending_releases(src)
                else:
                    self.w(f"{vi.c_name} = {expr_c};")
                    self._flush_pending_releases(src)
                return

            # compound assigns: numeric types only (except str +=)
            if st.op in {"+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="}:
                if st.op == "+=" and vi.ty == "str":
                    # str += str: concat, release old, assign new
                    tmp = self.new_tmp()
                    self.w(f"__lang_rt_Str* {tmp} = __lang_rt_str_concat({src}, {vi.c_name}, {expr_c});")
                    self.w(f"__lang_rt_str_release({vi.c_name}); (void){src};")
                    if not self._expr_is_borrowed(st.value):
                        self.w(f"__lang_rt_str_release({expr_c}); (void){src};")
                    self.w(f"{vi.c_name} = {tmp};")
                    return
                # no releases/retains for numeric
                self.w(f"{vi.c_name} {st.op} {expr_c};")
                return

            raise RuntimeError(f"{st.loc.file}:{st.loc.line}:{st.loc.col}: unknown assignment op {st.op}")

        if isinstance(st, SMemberAssign):
            src = _src(st.loc)
            obj_c, obj_ty = self._emit_expr(st.obj)
            expr_c, expr_ty = self._emit_expr(st.value)

            # Struct fields: value type, dot access, no refcounting
            if obj_ty in self.struct_defs:
                field_c = f"{obj_c}.{_ci(st.member)}"
                if st.op == "=":
                    self.w(f"{field_c} = {expr_c};")
                elif st.op in {"+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="}:
                    self.w(f"{field_c} {st.op} {expr_c};")
                self._flush_pending_releases(src)
                return

            # Null check before class field write (arrow access)
            if obj_ty in self.class_defs:
                self.w(f"__lang_rt_null_check({obj_c}, {src});")

            field_c = f"{obj_c}->{_ci(st.member)}"

            # Get the field type from class defs
            field_ty = None
            if obj_ty in self.class_defs:
                for fd in self.class_defs[obj_ty].fields:
                    if fd.name == st.member:
                        field_ty = fd.ty.name
                        break

            if st.op == "=":
                # Wrap class->interface conversion
                expr_c = self._maybe_wrap_iface(expr_c, expr_ty, field_ty or expr_ty)
                if field_ty and is_ref_type(field_ty):
                    # Materialize RHS into temp FIRST (RHS may reference the same field)
                    tmp = self.new_tmp()
                    self.w(f"{c_type(field_ty)} {tmp} = {expr_c};")
                    # Retain if borrowed
                    if self._expr_is_borrowed(st.value):
                        self._emit_retain_value(field_ty, tmp, src)
                    # Release old value
                    tmp_vi = VarInfo(c_name=field_c, ty=field_ty)
                    self._emit_release(tmp_vi, src)
                    # Assign
                    self.w(f"{field_c} = {tmp};")
                else:
                    self.w(f"{field_c} = {expr_c};")
            elif st.op in {"+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="}:
                self.w(f"{field_c} {st.op} {expr_c};")
            self._flush_pending_releases(src)
            return

        if isinstance(st, SIndexAssign):
            src = _src(st.loc)
            obj_c, obj_ty = self._emit_expr(st.obj)
            idx_c, idx_ty = self._emit_arg_safe(st.index)
            expr_c, expr_ty = self._emit_arg_safe(st.value)
            if _is_list_type(obj_ty):
                elem = _list_elem(obj_ty)
                tag = _elem_tag(elem)
                self.used_list_tags.add(tag)
                expr_c = self._maybe_wrap_iface(expr_c, expr_ty, elem)
                self.w(f"__lang_rt_list_{tag}_set({src}, {obj_c}, {idx_c}, {expr_c});")
            elif _is_dict_type(obj_ty):
                val = _dict_val(obj_ty)
                combined = _dict_combined_tag(obj_ty)
                self.used_dict_tags.add(combined)
                expr_c = self._maybe_wrap_iface(expr_c, expr_ty, val)
                self.w(f"__lang_rt_dict_{combined}_set({src}, {obj_c}, {idx_c}, {expr_c});")
            else:
                raise RuntimeError(f"{st.loc.file}:{st.loc.line}:{st.loc.col}: subscript assignment not supported on type '{obj_ty}'")
            self._flush_pending_releases(src)
            return

        if isinstance(st, SExpr):
            src = _src(st.loc)
            expr_c, expr_ty = self._emit_expr(st.expr)
            if expr_ty == "void":
                # void expressions (e.g. print, push) — just emit as statement
                self.w(f"{expr_c};")
                # For print: emit newline separately (it's no longer a comma expr)
                if isinstance(st.expr, ECall) and isinstance(st.expr.callee, EVar) and st.expr.callee.name == "print":
                    self.w("__lang_rt_print_ln();")
            elif is_ref_type(expr_ty) and not self._expr_is_borrowed(st.expr):
                # expression statements: if expr produces an owned ref, release it
                tmp = self.new_tmp()
                self.w(f"{c_type(expr_ty)} {tmp} = {expr_c};")
                self._emit_release(VarInfo(tmp, expr_ty), src)
            else:
                self.w(f"(void)({expr_c});")
            self._flush_pending_releases(src)
            return

        if isinstance(st, SReturn):
            src = _src(st.loc)
            if st.value is None:
                # Void return: release all scopes before returning
                self._flush_pending_releases(src)
                self._release_all_scopes(src)
                self._emit_return_default_for(self.cur_fn_ret, src)
                return
            expr_c, expr_ty = self._emit_expr(st.value)
            # Materialize return value into a temp BEFORE releasing scopes,
            # because the return expression may reference local vars/params
            ret_ty = self.cur_fn_ret
            # Wrap class->interface if needed
            wrapped_c = self._maybe_wrap_iface(expr_c, expr_ty, ret_ty)
            actual_ty = ret_ty if (ret_ty in self.iface_defs and expr_ty in self.class_defs) else expr_ty
            # None literal: use function return type for the temp declaration
            if actual_ty == "none":
                actual_ty = ret_ty
            ret_tmp = self.new_tmp()
            self.w(f"{c_type(actual_ty)} {ret_tmp} = {wrapped_c};")
            # Retain BEFORE flushing pending releases — the return temp may alias
            # a pending-release temp (e.g. `return func()` where func() result was
            # materialized).  Retaining first keeps the object alive through the flush.
            if is_ref_type(actual_ty) and self._expr_is_borrowed(st.value):
                self._emit_retain_value(actual_ty, ret_tmp, src)
            self._flush_pending_releases(src)
            self._release_all_scopes(src)
            self.w(f"return {ret_tmp};")
            return

        if isinstance(st, SBreak):
            if not allow_break:
                raise RuntimeError(f"{st.loc.file}:{st.loc.line}:{st.loc.col}: break not inside loop")
            src = _src(st.loc)
            self._release_loop_scopes(src)
            self.w("break;")
            return

        if isinstance(st, SContinue):
            if not allow_continue:
                raise RuntimeError(f"{st.loc.file}:{st.loc.line}:{st.loc.col}: continue not inside loop")
            src = _src(st.loc)
            self._release_loop_scopes(src)
            self.w("continue;")
            return

        if isinstance(st, SWhile):
            src = _src(st.loc)
            # Use while(1) + break pattern so that side-effect statements from
            # the condition (short-circuit &&/||, null checks, bounds checks)
            # are re-evaluated on every iteration.
            self.w("while (1) {")
            self.ind += 1
            cond_c, cond_ty = self._emit_expr(st.cond)
            if self._pending_releases:
                tmp = self.new_tmp()
                self.w(f"bool {tmp} = {cond_c};")
                cond_c = tmp
            self._flush_pending_releases(src)
            self.w(f"if (!({cond_c})) break;")
            self._loop_scope_depth.append(len(self.scope_vars))
            self.push_scope()
            for s2 in st.body.stmts:
                self._emit_stmt(s2, allow_break=True, allow_continue=True)
            self.pop_scope(src)
            self._loop_scope_depth.pop()
            self.ind -= 1
            self.w("}")
            return

        if isinstance(st, SFor):
            src = _src(st.loc)
            # Evaluate iterable (must be a list type)
            iter_c, iter_ty = self._emit_expr(st.iterable)
            # Determine list tag and element type from List[X] format
            if _is_list_type(iter_ty):
                elem_ty = _list_elem(iter_ty)
                tag = _elem_tag(elem_ty)
                c_elem = _elem_c_type(elem_ty)
            else:
                raise RuntimeError(f"{st.loc.file}:{st.loc.line}:{st.loc.col}: for-in requires list type, got {iter_ty}")
            # Materialize iterable into a temp (it's owned by the call, e.g. range())
            iter_tmp = self.new_tmp()
            idx_tmp = self.new_tmp()
            self.w(f"__lang_rt_List_{tag}* {iter_tmp} = {iter_c};")
            self._loop_scope_depth.append(len(self.scope_vars))
            self.push_scope()
            vi = self.declare_var(st.var_name, elem_ty)
            self.w(f"for (int64_t {idx_tmp} = 0; {idx_tmp} < (int64_t){iter_tmp}->len; {idx_tmp}++) " + "{")
            self.ind += 1
            self.w(f"{c_elem} {vi.c_name} = {iter_tmp}->data[(uint32_t){idx_tmp}];")
            # If element is a ref type, retain it (loop var borrows from list)
            if is_ref_type(elem_ty):
                self._emit_retain_value(elem_ty, vi.c_name, src)
            # Push inner scope for body-declared variables so they get released
            # at the end of each iteration (break/continue also release via _release_loop_scopes)
            self.push_scope()
            for s2 in st.body.stmts:
                self._emit_stmt(s2, allow_break=True, allow_continue=True)
            self.pop_scope(src)
            # Release loop var if ref type
            if is_ref_type(elem_ty):
                self._emit_release(vi, src)
            self.ind -= 1
            self.w("}")
            # Release iterator list if it was owned (e.g. from range() or keys())
            if not self._expr_is_borrowed(st.iterable):
                tmp_vi = VarInfo(iter_tmp, iter_ty)
                self._emit_release(tmp_vi, src)
            self._flush_pending_releases(src)
            self._loop_scope_depth.pop()
            self.env.pop()
            self.scope_vars.pop()
            return

        if isinstance(st, SIf):
            src = _src(st.loc)
            first = True
            elif_depth = 0
            for arm in st.arms:
                if arm.cond is None:
                    self.w("else {")
                else:
                    if first:
                        cond_c, cond_ty = self._emit_expr(arm.cond)
                        if self._pending_releases:
                            tmp = self.new_tmp()
                            self.w(f"bool {tmp} = {cond_c};")
                            cond_c = tmp
                        self._flush_pending_releases(src)
                        self.w(f"if ({cond_c}) " + "{")
                        first = False
                    else:
                        # Wrap elif in else { ... } so condition side-effects
                        # (e.g. null checks) don't break the C if-else chain.
                        self.w("else {")
                        self.ind += 1
                        elif_depth += 1
                        cond_c, cond_ty = self._emit_expr(arm.cond)
                        if self._pending_releases:
                            tmp = self.new_tmp()
                            self.w(f"bool {tmp} = {cond_c};")
                            cond_c = tmp
                        self._flush_pending_releases(src)
                        self.w(f"if ({cond_c}) " + "{")
                self.ind += 1
                self.push_scope()
                for s2 in arm.block.stmts:
                    self._emit_stmt(s2, allow_break=allow_break, allow_continue=allow_continue)
                self.pop_scope(src)
                self.ind -= 1
                self.w("}")
            for _ in range(elif_depth):
                self.ind -= 1
                self.w("}")
            return

        if isinstance(st, SBlock):
            src = _src(st.loc)
            self.w("{")
            self.ind += 1
            self.push_scope()
            for s2 in st.stmts:
                self._emit_stmt(s2, allow_break, allow_continue)
            self.pop_scope(src)
            self.ind -= 1
            self.w("}")
            return

        if isinstance(st, STupleDestructure):
            src = _src(st.loc)
            expr_c, expr_ty = self._emit_expr(st.value)
            elem_types = _tuple_elem_types(expr_ty)
            struct_name = _tuple_struct_name(expr_ty)
            self._mark_type_use(expr_ty)
            tmp = self.new_tmp()
            self.w(f"{struct_name} {tmp} = {expr_c};")
            borrowed = self._expr_is_borrowed(st.value)
            for i, (name, ety) in enumerate(zip(st.names, elem_types)):
                vi = self.declare_var(name, ety)
                ct = c_type(ety)
                self.w(f"{ct} {vi.c_name} = {tmp}.f{i};")
                if is_ref_type(ety) and borrowed:
                    self._emit_retain_value(ety, vi.c_name, src)
            self._flush_pending_releases(src)
            return

        raise RuntimeError(f"unhandled stmt {type(st).__name__}")

    def _release_all_scopes(self, src: str) -> None:
        # release locals from inner to outer, but stop before global scope
        # skip static vars — they persist across calls
        for scope in reversed(self.scope_vars[self._global_scope_depth:]):
            for v in reversed(scope):
                if is_ref_type(v.ty) and not v.is_static:
                    self._emit_release(v, src)

    def _release_loop_scopes(self, src: str) -> None:
        # release all ref-type locals from current scope down to loop boundary
        # used by break/continue to clean up before exiting a loop iteration
        depth = self._loop_scope_depth[-1]
        for scope in reversed(self.scope_vars[depth:]):
            for v in reversed(scope):
                if is_ref_type(v.ty) and not v.is_static:
                    self._emit_release(v, src)

    def _emit_default_return(self, ret_ty: str, src: str) -> None:
        # if execution reaches end of function, release locals and return default
        self._flush_pending_releases(src)
        self._release_all_scopes(src)
        self._emit_return_default_for(ret_ty, src)

    def _emit_return_default_for(self, ret_ty: Optional[str], src: str) -> None:
        if ret_ty is None or ret_ty == "void":
            self.w("return;")
            return
        if ret_ty in ("i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64"):
            self.w("return 0;")
        elif ret_ty in ("f32", "f64"):
            self.w("return 0.0;")
        elif ret_ty == "bool":
            self.w("return false;")
        elif ret_ty == "str":
            self.w("return (__lang_rt_Str*)0;")
        elif _is_list_type(ret_ty) or _is_dict_type(ret_ty):
            self.w("return (void*)0;")
        elif ret_ty in self.class_defs:
            self.w(f"return (__lang_rt_Class_{ret_ty}*)0;")
        elif ret_ty in IFACE_NAMES:
            self.w(f"return (__lang_rt_Iface_{ret_ty}){{.obj = NULL, .vtbl = NULL}};")
        elif _is_tuple_type(ret_ty):
            struct_name = _tuple_struct_name(ret_ty)
            self.w(f"return ({struct_name}){{0}};")
        elif ret_ty in STRUCT_NAMES:
            ct = c_type(ret_ty)
            self.w(f"return ({ct}){{0}};")
        else:
            self.w("return 0;")

    def _flush_pending_releases(self, src: str) -> None:
        """Release any temporary owned refs materialized during call argument evaluation."""
        for v in self._pending_releases:
            self._emit_release(v, src)
        self._pending_releases.clear()

    def _emit_arg_safe(self, arg: Expr) -> Tuple[str, str]:
        """Emit a call argument. If it's an owned ref (e.g. string literal), materialize
        to a temp and schedule cleanup so it doesn't leak."""
        ac, aty = self._emit_expr(arg)
        if is_ref_type(aty) and not self._expr_is_borrowed(arg):
            tmp = self.new_tmp()
            self.w(f"{c_type(aty)} {tmp} = {ac};")
            self._pending_releases.append(VarInfo(tmp, aty))
            return (tmp, aty)
        return (ac, aty)

    # -------------------------
    # Expressions
    # -------------------------

    def _expr_is_borrowed(self, e: Expr) -> bool:
        # Only variable reads are "borrowed".
        # String literals are immortal statics — no retain/release needed.
        # None returns NULL (not owned).
        if isinstance(e, ENone):
            return True  # NULL — no retain/release needed
        if isinstance(e, EString):
            return True  # immortal static — no retain/release needed
        if isinstance(e, EMemberAccess):
            # Check for enum variant access: EnumName.VARIANT
            if isinstance(e.obj, EVar) and e.obj.name in ENUM_NAMES:
                return True  # constant integer — no retain/release
            return True  # field access is borrowed (like a variable read)
        if isinstance(e, EIndex):
            return True  # subscript access is borrowed (like a variable read)
        if isinstance(e, EAs):
            return True  # downcast extracts a borrowed pointer from fat pointer
        if isinstance(e, ETuple):
            return False  # tuple expressions create a new value
        # Builtin get()/lookup() return borrowed refs from container storage
        if isinstance(e, ECall) and isinstance(e.callee, EVar) and e.callee.name in ("get", "lookup"):
            return True
        return isinstance(e, EVar)

    def _emit_expr(self, e: Expr) -> Tuple[str, str]:
        """
        Returns (C_expr_string, type_name_in_language).
        Type is derived from nodes minimally; real typechecking should annotate AST.
        For now:
          - literals have obvious types
          - vars resolved from env
          - calls resolved from builtin signatures / func_sigs
          - ops assumed to be validated by typechecker (we still infer simple cases)
        """
        if isinstance(e, EInt):
            ty = getattr(e, "ty", "i64")
            return (str(e.value), ty)
        if isinstance(e, EFloat):
            ty = getattr(e, "ty", "f64")
            return (repr(e.value), ty)
        if isinstance(e, EBool):
            return ("true" if e.value else "false", "bool")
        if isinstance(e, EChar):
            ty = getattr(e, "ty", "i64")
            val = _unescape_char_literal(e.raw)
            return (str(val), ty)
        if isinstance(e, EString):
            data = _unescape___lang_rt_string(e.raw)
            lit = _c_escape_bytes(data)
            # Intern: reuse the same static __lang_rt_Str for identical literals
            if lit not in self._string_lits:
                self._string_lit_idx += 1
                name = f"___lang_rt_lit_{self._string_lit_idx}"
                self._string_lits[lit] = name
            return (f"&{self._string_lits[lit]}", "str")
        if isinstance(e, ENone):
            return ("NULL", "none")
        if isinstance(e, EVar):
            if e.name in self.extern_constants:
                c_expr, bismut_ty = self.extern_constants[e.name]
                return (f"({c_expr})", bismut_ty)
            # Check if typechecker annotated this as a function pointer reference
            ty = getattr(e, "ty", None)
            if ty and _is_fn_type(ty) and e.name in self.func_sigs:
                return (f"__lang_rt_fn_{e.name}", ty)
            vi = self.lookup(e.name, e.loc)
            return (vi.c_name, vi.ty)

        if isinstance(e, EUnary):
            rhs_c, rhs_ty = self._emit_expr(e.rhs)
            if e.op == "-":
                return (f"(-({rhs_c}))", rhs_ty)
            if e.op == "not":
                return (f"(!({rhs_c}))", "bool")
            if e.op == "~":
                return (f"(~({rhs_c}))", rhs_ty)
            raise RuntimeError(f"{e.loc.file}:{e.loc.line}:{e.loc.col}: unknown unary op {e.op}")

        if isinstance(e, EIs):
            lhs_c, lhs_ty = self._emit_expr(e.expr)
            rhs_ty = e.type_name
            # 'x is None' — null check
            if rhs_ty == "None":
                if lhs_ty in self.iface_defs:
                    return (f"({lhs_c}.obj == NULL)", "bool")
                return (f"({lhs_c} == NULL)", "bool")
            # Interface variable: runtime vtable check
            if lhs_ty in self.iface_defs:
                # rhs_ty must be a class that implements this interface
                if rhs_ty in self.class_implements and lhs_ty in self.class_implements[rhs_ty]:
                    return (f"({lhs_c}.vtbl == &__lang_rt_vtbl_{rhs_ty}_as_{lhs_ty})", "bool")
                # Class doesn't implement the interface — always false
                return ("0", "bool")
            # Concrete type: static check, always true or false
            if lhs_ty == rhs_ty:
                return ("1", "bool")
            return ("0", "bool")

        if isinstance(e, EAs):
            lhs_c, lhs_ty = self._emit_expr(e.expr)
            target = e.type_name
            iface_ty = getattr(e, "lhs_ty", lhs_ty)
            src = _src(e.loc)
            # Materialize the fat pointer to a temp (avoids double-evaluation)
            tmp = self.new_tmp()
            self.w(f"__lang_rt_Iface_{iface_ty} {tmp} = {lhs_c};")
            # Checked downcast: verifies vtable and null at runtime
            return (f"((__lang_rt_Class_{target}*)__lang_rt_downcast({src}, {tmp}.obj, {tmp}.vtbl, &__lang_rt_vtbl_{target}_as_{iface_ty}, \"{target}\"))", target)

        if isinstance(e, EBinary):
            op = e.op

            # Short-circuit 'and' and 'or': only evaluate RHS when LHS permits.
            # This is critical because _emit_expr(rhs) can emit side-effect
            # statements (null checks, bounds checks) that must not run when
            # the LHS already determines the result.
            if op in ("and", "or"):
                a_c, _a_ty = self._emit_expr(e.lhs)
                tmp = self.new_tmp()
                self.w(f"bool {tmp} = {a_c};")
                self._flush_pending_releases(_src(e.loc))
                guard = tmp if op == "and" else f"!{tmp}"
                self.w(f"if ({guard}) " + "{")
                self.ind += 1
                b_c, _b_ty = self._emit_expr(e.rhs)
                self.w(f"{tmp} = {b_c};")
                self._flush_pending_releases(_src(e.loc))
                self.ind -= 1
                self.w("}")
                return (tmp, "bool")

            a_c, a_ty = self._emit_expr(e.lhs)
            b_c, b_ty = self._emit_expr(e.rhs)

            # Materialize owned ref-type operands so they get cleaned up
            if is_ref_type(a_ty) and not self._expr_is_borrowed(e.lhs):
                tmp = self.new_tmp()
                self.w(f"{c_type(a_ty)} {tmp} = {a_c};")
                self._pending_releases.append(VarInfo(tmp, a_ty))
                a_c = tmp
            if is_ref_type(b_ty) and not self._expr_is_borrowed(e.rhs):
                tmp = self.new_tmp()
                self.w(f"{c_type(b_ty)} {tmp} = {b_c};")
                self._pending_releases.append(VarInfo(tmp, b_ty))
                b_c = tmp

            # comparisons -> bool
            if op in ("==", "!=", "<", "<=", ">", ">="):
                # special-case strings: use __lang_rt_str_eq for == and !=
                if a_ty == "str" and b_ty == "str" and op in ("==", "!="):
                    expr = f"__lang_rt_str_eq({a_c}, {b_c})"
                    if op == "!=":
                        expr = f"!({expr})"
                    return (expr, "bool")
                # None comparisons: pointer == NULL
                if (a_ty == "none" or b_ty == "none") and op in ("==", "!="):
                    # Interface fat pointer: compare .obj field
                    if a_ty in self.iface_defs:
                        return (f"({a_c}.obj {op} NULL)", "bool")
                    if b_ty in self.iface_defs:
                        return (f"({b_c}.obj {op} NULL)", "bool")
                    return (f"({a_c} {op} {b_c})", "bool")
                return (f"({a_c} {op} {b_c})", "bool")

            # arithmetic
            if op in ("+", "-", "*", "/", "%"):
                if op == "+" and a_ty == "str":
                    return (f"__lang_rt_str_concat({_src(e.loc)}, {a_c}, {b_c})", "str")
                return (f"({a_c} {op} {b_c})", a_ty)

            # bitwise
            if op in ("&", "|", "^", "<<", ">>"):
                return (f"({a_c} {op} {b_c})", a_ty)

            raise RuntimeError(f"{e.loc.file}:{e.loc.line}:{e.loc.col}: unknown binary op {op}")

        if isinstance(e, ECall):
            return self._emit_call(e)

        if isinstance(e, EMemberAccess):
            # Check for enum variant access: EnumName.VARIANT
            if isinstance(e.obj, EVar) and e.obj.name in ENUM_NAMES:
                enum_name = e.obj.name
                value = self.enum_variants[enum_name][e.member]
                return (str(value), "i64")
            obj_c, obj_ty = self._emit_expr(e.obj)
            # Materialize owned ref-type objects (e.g. field access on a call
            # result like func().field) so the temporary is released.
            if is_ref_type(obj_ty) and not self._expr_is_borrowed(e.obj):
                tmp = self.new_tmp()
                self.w(f"{c_type(obj_ty)} {tmp} = {obj_c};")
                self._pending_releases.append(VarInfo(tmp, obj_ty))
                obj_c = tmp
            # Get field type from struct defs (value type — dot access)
            if obj_ty in self.struct_defs:
                for fd in self.struct_defs[obj_ty].fields:
                    if fd.name == e.member:
                        return (f"{obj_c}.{_ci(e.member)}", fd.ty.name)
            # Get field type from class defs (pointer — arrow access)
            if obj_ty in self.class_defs:
                src = _src(e.loc)
                self.w(f"__lang_rt_null_check({obj_c}, {src});")
                for fd in self.class_defs[obj_ty].fields:
                    if fd.name == e.member:
                        return (f"{obj_c}->{_ci(e.member)}", fd.ty.name)
            raise RuntimeError(f"{e.loc.file}:{e.loc.line}:{e.loc.col}: unknown member '{e.member}' on type '{obj_ty}'")

        if isinstance(e, EIndex):
            src = _src(e.loc)
            obj_c, obj_ty = self._emit_expr(e.obj)
            idx_c, idx_ty = self._emit_arg_safe(e.index)
            if _is_list_type(obj_ty):
                elem = _list_elem(obj_ty)
                tag = _elem_tag(elem)
                self.used_list_tags.add(tag)
                return (f"__lang_rt_list_{tag}_get({src}, {obj_c}, {idx_c})", elem)
            if _is_dict_type(obj_ty):
                val = _dict_val(obj_ty)
                combined = _dict_combined_tag(obj_ty)
                self.used_dict_tags.add(combined)
                return (f"__lang_rt_dict_{combined}_get({src}, {obj_c}, {idx_c})", val)
            if obj_ty == "str":
                return (f"__lang_rt_str_get({src}, {obj_c}, {idx_c})", "i64")
            raise RuntimeError(f"{e.loc.file}:{e.loc.line}:{e.loc.col}: subscript not supported on type '{obj_ty}'")

        if isinstance(e, EListLit):
            tp = e.elem_type
            tag = _elem_tag(tp)
            self.used_list_tags.add(tag)
            src = _src(e.loc)
            tmp = self.new_tmp()
            self.w(f"{c_type(f'List[{tp}]')} {tmp} = __lang_rt_list_{tag}_new({src});")
            for elem in e.elems:
                ec, ety = self._emit_arg_safe(elem)
                ec = self._maybe_wrap_iface(ec, ety, tp)
                self.w(f"__lang_rt_list_{tag}_push({src}, {tmp}, {ec});")
            return (tmp, f"List[{tp}]")

        if isinstance(e, EDictLit):
            ktp = e.key_type
            tp = e.val_type
            combined = f"{_elem_tag(ktp)}_{_elem_tag(tp)}"
            self.used_dict_tags.add(combined)
            src = _src(e.loc)
            dict_ty = f"Dict[{ktp},{tp}]"
            tmp = self.new_tmp()
            self.w(f"{c_type(dict_ty)} {tmp} = __lang_rt_dict_{combined}_new({src});")
            for key, val in zip(e.keys, e.vals):
                kc, _ = self._emit_arg_safe(key)
                vc, vty = self._emit_arg_safe(val)
                vc = self._maybe_wrap_iface(vc, vty, tp)
                self.w(f"__lang_rt_dict_{combined}_set({src}, {tmp}, {kc}, {vc});")
            return (tmp, dict_ty)

        if isinstance(e, ETuple):
            tuple_ty = getattr(e, 'ty')
            target_elems = _tuple_elem_types(tuple_ty)
            struct_name = _tuple_struct_name(tuple_ty)
            self._mark_type_use(tuple_ty)
            elem_data = []
            for i, elem in enumerate(e.elems):
                ec, ety = self._emit_expr(elem)
                ec = self._maybe_wrap_iface(ec, ety, target_elems[i])
                elem_data.append((ec, ety, target_elems[i], elem))
            tmp = self.new_tmp()
            fields = ", ".join(f".f{i} = {ec}" for i, (ec, _, _, _) in enumerate(elem_data))
            self.w(f"{struct_name} {tmp} = {{{fields}}};")
            src = _src(e.loc)
            for i, (_, _, target_ety, sub_expr) in enumerate(elem_data):
                if is_ref_type(target_ety) and self._expr_is_borrowed(sub_expr):
                    self._emit_retain_value(target_ety, f"{tmp}.f{i}", src)
            return (tmp, tuple_ty)

        raise RuntimeError(f"unhandled expr {type(e).__name__}")

    def _emit_call(self, e: ECall) -> Tuple[str, str]:
        # Method call: obj.method(args)
        if isinstance(e.callee, EMemberAccess):
            obj_c, obj_ty = self._emit_expr(e.callee.obj)
            # Materialize owned ref-type receivers (e.g. chained calls like
            # a.method().method2()) so the intermediate is released.
            if is_ref_type(obj_ty) and not self._expr_is_borrowed(e.callee.obj):
                tmp = self.new_tmp()
                self.w(f"{c_type(obj_ty)} {tmp} = {obj_c};")
                self._pending_releases.append(VarInfo(tmp, obj_ty))
                obj_c = tmp
            mname = e.callee.member
            src = _src(e.loc)
            # Interface vtable dispatch
            if obj_ty in self.iface_defs:
                self.w(f"__lang_rt_null_check({obj_c}.obj, {src});")
                iface = self.iface_defs[obj_ty]
                args_c: List[str] = [f"{obj_c}.obj"]
                for arg in e.args:
                    ac, _ = self._emit_arg_safe(arg)
                    args_c.append(ac)
                for ms in iface.method_sigs:
                    if ms.name == mname:
                        ret_ty = ms.ret.name
                        return (f"{obj_c}.vtbl->{_ci(mname)}({', '.join(args_c)})", ret_ty)
                raise RuntimeError(f"{e.loc.file}:{e.loc.line}:{e.loc.col}: unknown interface method '{mname}' on '{obj_ty}'")
            # Emit args
            args_c: List[str] = [obj_c]
            for arg in e.args:
                ac, _ = self._emit_arg_safe(arg)
                args_c.append(ac)
            # Get return type from struct defs
            if obj_ty in self.struct_defs:
                for m in self.struct_defs[obj_ty].methods:
                    if m.name == mname:
                        ret_ty = m.ret.name
                        return (f"__lang_rt_struct_{obj_ty}_{mname}({', '.join(args_c)})", ret_ty)
            # Get return type from class defs
            if obj_ty in self.class_defs:
                self.w(f"__lang_rt_null_check({obj_c}, {src});")
                for m in self.class_defs[obj_ty].methods:
                    if m.name == mname:
                        ret_ty = m.ret.name
                        return (f"__lang_rt_class_{obj_ty}_{mname}({', '.join(args_c)})", ret_ty)
            raise RuntimeError(f"{e.loc.file}:{e.loc.line}:{e.loc.col}: unknown method '{mname}' on '{obj_ty}'")

        # Expression-based function pointer call: e.g. ops[0](3, 4)
        if not isinstance(e.callee, EVar):
            callee_c, callee_ty = self._emit_expr(e.callee)
            if _is_fn_type(callee_ty):
                args_c: List[str] = []
                for arg in e.args:
                    ac, _ = self._emit_arg_safe(arg)
                    args_c.append(ac)
                ret_ty = _fn_ret_type(callee_ty)
                return (f"{callee_c}({', '.join(args_c)})", ret_ty)
            raise RuntimeError(f"{e.loc.file}:{e.loc.line}:{e.loc.col}: callee must be identifier")

        name = e.callee.name
        src = _src(e.loc)

        # Shorthand: emit builtin arg (materializes owned refs for cleanup)
        def _ba(i: int) -> str:
            ac, _ = self._emit_arg_safe(e.args[i])
            return ac

        # ---- function pointer call: variable with Fn(...) type ----
        if name not in self.func_sigs and name not in CAST_TYPES and name not in self.class_defs:
            try:
                vi = self.lookup(name, e.loc)
                if _is_fn_type(vi.ty):
                    args_c: List[str] = []
                    for arg in e.args:
                        ac, _ = self._emit_arg_safe(arg)
                        args_c.append(ac)
                    ret_ty = _fn_ret_type(vi.ty)
                    return (f"{vi.c_name}({', '.join(args_c)})", ret_ty)
            except RuntimeError:
                pass

        # ---- type cast builtins: i8(x), i16(x), i32(x), i64(x), f32(x), f64(x) ----
        if name in CAST_TYPES:
            arg_c, arg_ty = self._emit_arg_safe(e.args[0])
            target_c = PRIM_C[name]
            return (f"(({target_c})({arg_c}))", name)

        # ---- print (overloaded, returns void) ----
        if name == "print":
            arg_c, arg_ty = self._emit_arg_safe(e.args[0])
            if arg_ty in ENUM_NAMES:
                arg_ty = "i64"
            if arg_ty in CAST_TYPES:
                return (f"__lang_rt_print_{arg_ty}({arg_c})", "void")
            if arg_ty == "bool":
                return (f"__lang_rt_print_bool({arg_c})", "void")
            if arg_ty == "str":
                return (f"__lang_rt_print_str({arg_c})", "void")
            return (f"printf(\"%p\\n\", (void*)({arg_c}))", "void")

        # ---- format (variadic string formatting, returns str) ----
        if name == "format":
            fmt_c, _ = self._emit_arg_safe(e.args[0])
            nargs = len(e.args) - 1
            if nargs == 0:
                result_tmp = self.new_tmp()
                self.w(f"__lang_rt_Str* {result_tmp} = __lang_rt_format({src}, {fmt_c}, NULL, 0);")
                return (result_tmp, "str")
            arr_tmp = self.new_tmp()
            self.w(f"__lang_rt_FmtArg {arr_tmp}[{nargs}];")
            for i, arg in enumerate(e.args[1:]):
                ac, aty = self._emit_arg_safe(arg)
                if aty in ENUM_NAMES:
                    aty = "i64"
                if aty in ("i8", "i16", "i32", "i64"):
                    self.w(f"{arr_tmp}[{i}].tag = __LANG_RT_FMT_I64; {arr_tmp}[{i}].val.i = (int64_t)({ac});")
                elif aty in ("u8", "u16", "u32", "u64"):
                    self.w(f"{arr_tmp}[{i}].tag = __LANG_RT_FMT_U64; {arr_tmp}[{i}].val.u = (uint64_t)({ac});")
                elif aty in ("f32", "f64"):
                    self.w(f"{arr_tmp}[{i}].tag = __LANG_RT_FMT_F64; {arr_tmp}[{i}].val.f = (double)({ac});")
                elif aty == "bool":
                    self.w(f"{arr_tmp}[{i}].tag = __LANG_RT_FMT_BOOL; {arr_tmp}[{i}].val.b = ({ac});")
                elif aty == "str":
                    self.w(f"{arr_tmp}[{i}].tag = __LANG_RT_FMT_STR; {arr_tmp}[{i}].val.s = ({ac});")
            result_tmp = self.new_tmp()
            self.w(f"__lang_rt_Str* {result_tmp} = __lang_rt_format({src}, {fmt_c}, {arr_tmp}, {nargs});")
            return (result_tmp, "str")

        # ---- range (1-3 i64 args, returns List[i64]) ----
        if name == "range":
            self.used_list_tags.add("I64")
            nargs = len(e.args)
            if nargs == 1:
                return (f"__lang_rt_range({src}, 0, {_ba(0)}, 1)", "List[i64]")
            elif nargs == 2:
                return (f"__lang_rt_range({src}, {_ba(0)}, {_ba(1)}, 1)", "List[i64]")
            else:
                return (f"__lang_rt_range({src}, {_ba(0)}, {_ba(1)}, {_ba(2)})", "List[i64]")

        # ---- keys (1 dict arg, returns List[K]) ----
        if name == "keys":
            arg_c, arg_ty = self._emit_arg_safe(e.args[0])
            if _is_dict_type(arg_ty):
                k = _dict_key(arg_ty)
                key_tag = _elem_tag(k)
                self.used_list_tags.add(key_tag)
                combined = _dict_combined_tag(arg_ty)
                return (f"__lang_rt_dict_{combined}_keys({src}, {arg_c})", f"List[{k}]")
            raise RuntimeError(f"{e.loc.file}:{e.loc.line}:{e.loc.col}: keys() requires dict type")

        # ---- len() — overloaded, no type param needed ----
        if name == "len":
            arg_c, arg_ty = self._emit_arg_safe(e.args[0])
            if _is_list_type(arg_ty):
                tag = _elem_tag(_list_elem(arg_ty))
                return (f"__lang_rt_list_{tag}_len({arg_c})", "i64")
            if _is_dict_type(arg_ty):
                combined = _dict_combined_tag(arg_ty)
                return (f"__lang_rt_dict_{combined}_len({arg_c})", "i64")
            if arg_ty == "str":
                return (f"((int64_t)({arg_c})->len)", "i64")
            raise RuntimeError(f"{e.loc.file}:{e.loc.line}:{e.loc.col}: len() does not support type '{arg_ty}'")

        # ---- generic container ops: name[T](...) or name[K,V](...) ----
        if e.type_param is not None:
            tp = e.type_param
            tag = _elem_tag(tp)
            cty = _elem_c_type(tp)
            # Helper: emit value arg with interface wrapping if needed
            def _ba_val(i: int) -> str:
                ac, aty = self._emit_arg_safe(e.args[i])
                return self._maybe_wrap_iface(ac, aty, tp)
            if name == "List":
                self.used_list_tags.add(tag)
                return (f"__lang_rt_list_{tag}_new({src})", f"List[{tp}]")
            if name == "append":
                self.used_list_tags.add(tag)
                return (f"__lang_rt_list_{tag}_push({src}, {_ba(0)}, {_ba_val(1)})", "void")
            if name == "get":
                self.used_list_tags.add(tag)
                return (f"__lang_rt_list_{tag}_get({src}, {_ba(0)}, {_ba(1)})", tp)
            if name == "set":
                self.used_list_tags.add(tag)
                return (f"__lang_rt_list_{tag}_set({src}, {_ba(0)}, {_ba(1)}, {_ba_val(2)})", "void")
            if name == "pop":
                self.used_list_tags.add(tag)
                return (f"__lang_rt_list_{tag}_pop({src}, {_ba(0)})", tp)
            if name == "remove":
                self.used_list_tags.add(tag)
                return (f"__lang_rt_list_{tag}_remove({src}, {_ba(0)}, {_ba(1)})", "void")
            if name == "Dict":
                # tp is "K,V" — combined tag
                k, v = _split_dict_inner(tp)
                combined = f"{_elem_tag(k)}_{_elem_tag(v)}"
                self.used_dict_tags.add(combined)
                return (f"__lang_rt_dict_{combined}_new({src})", f"Dict[{tp}]")
            if name == "put":
                k, v = _split_dict_inner(tp)
                combined = f"{_elem_tag(k)}_{_elem_tag(v)}"
                self.used_dict_tags.add(combined)
                def _ba_dval(i: int) -> str:
                    ac, aty = self._emit_arg_safe(e.args[i])
                    return self._maybe_wrap_iface(ac, aty, v)
                return (f"__lang_rt_dict_{combined}_set({src}, {_ba(0)}, {_ba(1)}, {_ba_dval(2)})", "void")
            if name == "lookup":
                k, v = _split_dict_inner(tp)
                combined = f"{_elem_tag(k)}_{_elem_tag(v)}"
                self.used_dict_tags.add(combined)
                return (f"__lang_rt_dict_{combined}_get({src}, {_ba(0)}, {_ba(1)})", v)
            if name == "has":
                k, v = _split_dict_inner(tp)
                combined = f"{_elem_tag(k)}_{_elem_tag(v)}"
                self.used_dict_tags.add(combined)
                return (f"__lang_rt_dict_{combined}_has({src}, {_ba(0)}, {_ba(1)})", "bool")

            # ---- user-defined generic function call ----
            mangled = f"{name}_{tag}"
            if mangled in self.func_sigs:
                param_tys, ret_ty = self.func_sigs[mangled]
                args_c: List[str] = []
                for arg in e.args:
                    ac, aty = self._emit_arg_safe(arg)
                    args_c.append(ac)
                return (f"__lang_rt_fn_{mangled}({', '.join(args_c)})", ret_ty)

            raise RuntimeError(f"{e.loc.file}:{e.loc.line}:{e.loc.col}: unknown generic function '{name}[{tp}]'")

        # ---- constructor call: ClassName(args) ----
        if name in self.class_defs:
            # Gather init param types for class→interface wrapping
            init_param_tys: List[str] = []
            for m in self.class_defs[name].methods:
                if m.name == "init":
                    init_param_tys = [p.ty.name for p in m.params[1:]]
                    break
            args_c: List[str] = [src]
            for i, arg in enumerate(e.args):
                ac, aty = self._emit_arg_safe(arg)
                if i < len(init_param_tys):
                    ac = self._maybe_wrap_iface(ac, aty, init_param_tys[i])
                args_c.append(ac)
            return (f"__lang_rt_class_{name}_new({', '.join(args_c)})", name)

        # ---- struct construction: StructName(field1, field2, ...) ----
        if name in self.struct_defs:
            st_def = self.struct_defs[name]
            field_inits: List[str] = []
            for i, (fd, arg) in enumerate(zip(st_def.fields, e.args)):
                ac, aty = self._emit_arg_safe(arg)
                field_inits.append(f".{_ci(fd.name)} = {ac}")
            ct = c_type(name)
            return (f"({ct}){{{', '.join(field_inits)}}}", name)

        # ---- user-defined function ----
        if name not in self.func_sigs:
            raise RuntimeError(f"{e.loc.file}:{e.loc.line}:{e.loc.col}: unknown function '{name}'")
        param_tys, ret_ty = self.func_sigs[name]

        args_c: List[str] = []
        for i, arg in enumerate(e.args):
            ac, aty = self._emit_arg_safe(arg)
            # Wrap class->interface at call site if needed
            if i < len(param_tys):
                ac = self._maybe_wrap_iface(ac, aty, param_tys[i])
            args_c.append(ac)
        return (f"__lang_rt_fn_{name}({', '.join(args_c)})", ret_ty)

    # -------------------------
    # Global variables
    # -------------------------

    def _emit_global_vars(self, prog: Program) -> None:
        """Emit top-level SVarDecl as file-scope C globals, and set up a
        persistent global env scope so functions can see them."""
        # Push global scope that persists for all function codegen
        self.push_scope()
        for st in prog.stmts:
            if isinstance(st, SVarDecl):
                if st.name in self.extern_constants:
                    continue
                ty = st.ty.name
                ct = c_type(ty)
                self._mark_type_use(ty)
                vi = self.declare_var(st.name, ty)
                # Emit file-scope declaration with zero-init
                if is_ref_type(ty) or ty in self.iface_defs or ty in STRUCT_NAMES:
                    self.w(f"static {ct} {vi.c_name} = {{0}};")
                else:
                    self.w(f"static {ct} {vi.c_name} = 0;")
        self.w("")

    # -------------------------
    # Program + main bootstrap
    # -------------------------

    def _emit_program(self, prog: Program) -> None:
        self.w("static void __lang_rt_program(void) {")
        self.ind += 1
        # Don't push a new scope — global vars are already in self.env[0]
        # Only emit the initializations and non-VarDecl statements
        for st in prog.stmts:
            if isinstance(st, SVarDecl):
                if st.name in self.extern_constants:
                    continue
                # Global was already declared at file scope; just emit the assignment
                vi = self.lookup(st.name, st.loc)
                src = _src(st.loc)
                expr_c, expr_ty = self._emit_expr(st.value)
                expr_c = self._maybe_wrap_iface(expr_c, expr_ty, st.ty.name)
                self.w(f"{vi.c_name} = {expr_c};")
                if is_ref_type(st.ty.name) and self._expr_is_borrowed(st.value):
                    self._emit_retain_value(st.ty.name, vi.c_name, src)
                self._flush_pending_releases(src)
            else:
                self._emit_stmt(st, allow_break=False, allow_continue=False)
        # Release global ref-type variables at program exit
        for scope in reversed(self.scope_vars[:self._global_scope_depth]):
            for v in reversed(scope):
                if is_ref_type(v.ty):
                    self._emit_release(v, "\"global cleanup\"")
        # Run leak report after all globals are released
        self.w("__LANG_RT_LEAK_REPORT();")
        self.ind -= 1
        self.w("}")

    def _emit_main(self, prog: Program) -> None:
        self.w("int main(int argc, char** argv) {")
        self.ind += 1
        self.w("__lang_rt_argc_ = argc;")
        self.w("__lang_rt_argv_ = argv;")
        self.w("__lang_rt_program();")
        self.w("return 0;")
        self.ind -= 1
        self.w("}")


def generate_c(prog: Program, debug_leaks: bool = False) -> str:
    return CodeGen(debug_leaks=debug_leaks).generate(prog)
