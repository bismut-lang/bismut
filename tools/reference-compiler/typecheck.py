from __future__ import annotations
import copy
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from parser import (
    Program, FuncDecl, ClassDecl, StructDecl, FieldDecl, Param, TypeRef, InterfaceDecl, MethodSig, EnumDecl,
    Stmt, SVarDecl, SAssign, SMemberAssign, SIndexAssign, SExpr, SReturn, SBreak, SContinue, SIf, SWhile, SFor, SBlock, IfArm,
    Expr, EInt, EFloat, EString, EChar, EBool, ENone, EVar, EUnary, EBinary, ECall, EMemberAccess, EIndex, EIs, EAs,
    ETuple, STupleDestructure, EListLit, EDictLit,
)

# -------------------------
# Generic type helpers
# -------------------------

# Base known types (no generics); list/dict checked dynamically
KNOWN_BASE_TYPES = {
    "i8", "i16", "i32", "i64",
    "u8", "u16", "u32", "u64",
    "f32", "f64",
    "bool", "str", "void",
}

INT_TYPES = {"i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64"}
FLOAT_TYPES = {"f32", "f64"}
NUM_TYPES = INT_TYPES | FLOAT_TYPES

# Type cast builtins: type name -> set of source types it can cast from
CAST_TYPES = {"i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64", "f32", "f64"}

def is_list_type(ty: str) -> bool:
    return ty.startswith("List[") and ty.endswith("]")

def list_elem_type(ty: str) -> str:
    """List[i64] -> i64, List[Person] -> Person"""
    return ty[5:-1]

def is_dict_type(ty: str) -> bool:
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

def dict_key_type(ty: str) -> str:
    """Dict[str,i64] -> str"""
    k, _ = _split_dict_inner(ty[5:-1])
    return k

def dict_val_type(ty: str) -> str:
    """Dict[str,i64] -> i64"""
    _, v = _split_dict_inner(ty[5:-1])
    return v

def is_fn_type(ty: str) -> bool:
    return ty.startswith("Fn(") and ")->" in ty

def is_tuple_type(ty: str) -> bool:
    return len(ty) >= 5 and ty[0] == "(" and ty[-1] == ")"

def tuple_elem_types(ty: str) -> List[str]:
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

def fn_param_types(ty: str) -> List[str]:
    """Fn(i64,str)->bool -> ['i64', 'str']"""
    inner = ty[3:ty.index(")->")]
    if not inner:
        return []
    # Parse respecting nested Fn() types
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

def fn_ret_type(ty: str) -> str:
    """Fn(i64,str)->bool -> 'bool'"""
    return ty[ty.index(")->") + 3:]

# Builtin function signatures: name -> ([param_types], return_type)
BUILTIN_SIGS: Dict[str, Tuple[List[str], str]] = {}

# Generic container ops: name -> lambda(type_param) -> ([param_types], return_type)
# Used for List[T](), append[T](), get[T](), Dict[T](), put[T](), lookup[T](), etc.
GENERIC_CONTAINER_OPS: Dict[str, object] = {
    "List":    lambda tp: ([], f"List[{tp}]"),
    "append":  lambda tp: ([f"List[{tp}]", tp], "void"),
    "get":     lambda tp: ([f"List[{tp}]", "i64"], tp),
    "set":     lambda tp: ([f"List[{tp}]", "i64", tp], "void"),
    "pop":     lambda tp: ([f"List[{tp}]"], tp),
    "remove":  lambda tp: ([f"List[{tp}]", "i64"], "void"),
    "Dict":    lambda tp: ([], f"Dict[{tp}]"),
    "put":     lambda tp: ([f"Dict[{tp}]", _split_dict_inner(tp)[0], _split_dict_inner(tp)[1]], "void"),
    "lookup":  lambda tp: ([f"Dict[{tp}]", _split_dict_inner(tp)[0]], _split_dict_inner(tp)[1]),
    "has":     lambda tp: ([f"Dict[{tp}]", _split_dict_inner(tp)[0]], "bool"),
}

# Mapping for type inference: which generic ops work on lists vs dicts
_LIST_GENERIC_OPS = {"append", "get", "set", "pop", "remove"}
_DICT_GENERIC_OPS = {"put", "lookup", "has"}

# Allowed dict key types: integers, str, bool, enums
_HASHABLE_BASE = INT_TYPES | {"str", "bool"}

def _check_dict_key_type(loc, kty: str, checker) -> None:
    """Validate that kty is an allowed dict key type."""
    if kty in _HASHABLE_BASE:
        return
    if hasattr(checker, 'enums') and kty in checker.enums:
        return
    raise TypeError(loc, f"type '{kty}' cannot be used as dict key (allowed: integers, str, bool, enums)")


class TypeError(Exception):
    def __init__(self, loc, msg: str):
        self.loc = loc
        self.msg = msg
        super().__init__(self.__str__())

    def __str__(self) -> str:
        return f"{self.loc.file}:{self.loc.line}:{self.loc.col}: type error: {self.msg}"



def _is_ref_type(t: str) -> bool:
    if t == "str":
        return True
    if is_list_type(t) or is_dict_type(t):
        return True
    if t in _USER_CLASS_NAMES:
        return True
    if t in _USER_INTERFACE_NAMES:
        return True
    return False


def _is_truthy_type(t: str) -> bool:
    """Returns True if this type can be used in boolean contexts (if, while, not, and, or).
    Truthy types: bool, all integers, all ref types (None is falsy)."""
    if t == "bool":
        return True
    if _resolve_enum_ty(t) in INT_TYPES:
        return True
    if _is_ref_type(t):
        return True
    return False

# Set of registered user class names (populated during check())
_USER_CLASS_NAMES: set = set()
# Set of registered struct names (populated during check())
_USER_STRUCT_NAMES: set = set()
# Set of registered interface names (populated during check())
_USER_INTERFACE_NAMES: set = set()
# Set of registered enum type names (populated during check())
_USER_ENUM_NAMES: set = set()
# Mapping: class name -> set of interface names it implements
_CLASS_IMPLEMENTS: Dict[str, set] = {}


# none is assignable to any reference type
# class is assignable to any interface it implements
def _assignable(src_ty: str, dst_ty: str) -> bool:
    if src_ty == dst_ty:
        return True
    # Enum types are interchangeable with i64
    if _resolve_enum_ty(src_ty) == _resolve_enum_ty(dst_ty):
        return True
    if src_ty == "none" and _is_ref_type(dst_ty):
        return True
    if dst_ty in _USER_INTERFACE_NAMES and src_ty in _CLASS_IMPLEMENTS:
        if dst_ty in _CLASS_IMPLEMENTS[src_ty]:
            return True
    return False


def _resolve_enum_ty(ty: str) -> str:
    """Resolve enum type names to i64."""
    if ty in _USER_ENUM_NAMES:
        return "i64"
    return ty


def _is_known(t: str) -> bool:
    if t in KNOWN_BASE_TYPES:
        return True
    if t in _USER_CLASS_NAMES:
        return True
    if t in _USER_STRUCT_NAMES:
        return True
    if t in _USER_INTERFACE_NAMES:
        return True
    if t in _USER_ENUM_NAMES:
        return True
    if is_list_type(t):
        return _is_known(list_elem_type(t))
    if is_dict_type(t):
        return _is_known(dict_key_type(t)) and _is_known(dict_val_type(t))
    if is_fn_type(t):
        for pt in fn_param_types(t):
            if not _is_known(pt):
                return False
        return _is_known(fn_ret_type(t))
    if is_tuple_type(t):
        return all(_is_known(et) for et in tuple_elem_types(t))
    return False


def _require_known(loc, t: str) -> None:
    if not _is_known(t):
        raise TypeError(loc, f"unknown type '{t}'")


def _set_expr_ty(e: Expr, ty: str) -> str:
    setattr(e, "ty", ty)
    return ty


def expr_ty(e: Expr) -> str:
    ty = getattr(e, "ty", None)
    if ty is None:
        raise RuntimeError("expression not annotated with type (typechecker bug)")
    return ty


@dataclass
class VarInfo:
    ty: str
    is_const: bool = False


@dataclass
class ClassInfo:
    name: str
    fields: Dict[str, str]           # field_name -> type_name
    methods: Dict[str, Tuple[List[str], str]]  # method_name -> ([param types excl self], ret_type)
    init_params: List[str]           # param types for constructor (excl self)

@dataclass
class StructInfo:
    name: str
    fields: Dict[str, str]           # field_name -> type_name (ordered)
    field_order: List[str]           # field names in declaration order
    methods: Dict[str, Tuple[List[str], str]]  # method_name -> ([param types excl self], ret_type)

@dataclass
class InterfaceInfo:
    name: str
    methods: Dict[str, Tuple[List[str], str]]  # method_name -> ([param types excl self], ret_type)


class TypeChecker:
    def __init__(self, prog: Program):
        self.prog = prog
        self.funcs: Dict[str, Tuple[List[str], str]] = {}
        self.vars: List[Dict[str, VarInfo]] = []
        self.cur_ret: Optional[str] = None
        self.loop_depth = 0
        self.classes: Dict[str, ClassInfo] = {}
        self.structs: Dict[str, StructInfo] = {}
        self.interfaces: Dict[str, InterfaceInfo] = {}
        self.enum_variants: Dict[str, Dict[str, Tuple[str, int]]] = {}  # enum_name -> {variant_name -> (enum_type, value)}
        self.cur_class: Optional[str] = None  # set when inside a class method
        self.cur_struct: Optional[str] = None  # set when inside a struct method
        self.cur_type_params: List[str] = []   # type params in scope (for generic funcs)
        self.generic_funcs: Dict[str, FuncDecl] = {}  # name -> generic func template
        self.generic_instantiations: Dict[str, Tuple[List[str], str]] = {}  # mangled_name -> (param_tys, ret_ty)

    def check(self) -> None:
        _USER_CLASS_NAMES.clear()
        _USER_STRUCT_NAMES.clear()
        _USER_INTERFACE_NAMES.clear()
        _USER_ENUM_NAMES.clear()
        _CLASS_IMPLEMENTS.clear()

        # Pass 0: register all interface names
        for iface in self.prog.interfaces:
            if iface.name in KNOWN_BASE_TYPES:
                raise TypeError(iface.loc, f"interface '{iface.name}' conflicts with built-in type")
            _USER_INTERFACE_NAMES.add(iface.name)

        # Pass 0b: register all enum names and resolve variant values
        for enum in self.prog.enums:
            if enum.name in KNOWN_BASE_TYPES or enum.name in _USER_INTERFACE_NAMES:
                raise TypeError(enum.loc, f"enum '{enum.name}' conflicts with existing type")
            _USER_ENUM_NAMES.add(enum.name)
            variants: Dict[str, Tuple[str, int]] = {}
            next_val = 0
            for v in enum.variants:
                if v.value is not None:
                    next_val = v.value
                v.value = next_val
                if v.name in variants:
                    raise TypeError(v.loc, f"duplicate enum variant '{v.name}'")
                variants[v.name] = (enum.name, next_val)
                next_val += 1
            self.enum_variants[enum.name] = variants

        # Pass 1: register all class names (enables forward references)
        for cls in self.prog.classes:
            if cls.name in KNOWN_BASE_TYPES:
                raise TypeError(cls.loc, f"class '{cls.name}' conflicts with built-in type")
            if cls.name in _USER_INTERFACE_NAMES:
                raise TypeError(cls.loc, f"class '{cls.name}' conflicts with interface name")
            _USER_CLASS_NAMES.add(cls.name)

        # Pass 1b: register all struct names
        for st in self.prog.structs:
            if st.name in KNOWN_BASE_TYPES or st.name in _USER_CLASS_NAMES or st.name in _USER_INTERFACE_NAMES or st.name in _USER_ENUM_NAMES:
                raise TypeError(st.loc, f"struct '{st.name}' conflicts with existing type")
            _USER_STRUCT_NAMES.add(st.name)

        # Validate and register interfaces
        for iface in self.prog.interfaces:
            methods: Dict[str, Tuple[List[str], str]] = {}
            for ms in iface.method_sigs:
                if not ms.params or ms.params[0].name != "self":
                    raise TypeError(ms.loc, f"interface method '{ms.name}' must have 'self' as first parameter")
                param_tys: List[str] = []
                for p in ms.params[1:]:
                    _require_known(p.loc, p.ty.name)
                    param_tys.append(p.ty.name)
                _require_known(ms.loc, ms.ret.name)
                methods[ms.name] = (param_tys, ms.ret.name)
            self.interfaces[iface.name] = InterfaceInfo(name=iface.name, methods=methods)

        # Pass 2: validate field/method types and build ClassInfo
        for cls in self.prog.classes:
            fields: Dict[str, str] = {}
            for fd in cls.fields:
                _require_known(fd.loc, fd.ty.name)
                fields[fd.name] = fd.ty.name

            methods: Dict[str, Tuple[List[str], str]] = {}
            init_params: List[str] = []
            for m in cls.methods:
                # First param must be 'self'
                if not m.params or m.params[0].name != "self":
                    raise TypeError(m.loc, f"class method '{m.name}' must have 'self' as first parameter")
                param_tys: List[str] = []
                for p in m.params[1:]:  # skip self
                    _require_known(p.loc, p.ty.name)
                    param_tys.append(p.ty.name)
                _require_known(m.loc, m.ret.name)
                methods[m.name] = (param_tys, m.ret.name)
                if m.name == "init":
                    init_params = param_tys

            self.classes[cls.name] = ClassInfo(
                name=cls.name, fields=fields, methods=methods, init_params=init_params
            )

            # Validate implements
            impl_set: set = set()
            for iname in cls.implements:
                if iname not in self.interfaces:
                    raise TypeError(cls.loc, f"class '{cls.name}' implements unknown interface '{iname}'")
                ii = self.interfaces[iname]
                for mname, (iface_ptys, iface_ret) in ii.methods.items():
                    if mname not in methods:
                        raise TypeError(cls.loc, f"class '{cls.name}' is missing method '{mname}' required by interface '{iname}'")
                    cls_ptys, cls_ret = methods[mname]
                    if cls_ptys != iface_ptys or cls_ret != iface_ret:
                        raise TypeError(cls.loc,
                            f"method '{mname}' in class '{cls.name}' has signature "
                            f"({', '.join(cls_ptys)}) -> {cls_ret}, but interface '{iname}' "
                            f"requires ({', '.join(iface_ptys)}) -> {iface_ret}")
                impl_set.add(iname)
            _CLASS_IMPLEMENTS[cls.name] = impl_set

        # Detect circular class references (refcount cycles)
        self._check_circular_refs()

        # Pass 2b: validate struct fields/methods and build StructInfo
        for st in self.prog.structs:
            fields: Dict[str, str] = {}
            field_order: List[str] = []
            for fd in st.fields:
                _require_known(fd.loc, fd.ty.name)
                if _is_ref_type(fd.ty.name):
                    raise TypeError(fd.loc, f"struct field '{fd.name}' cannot have reference type '{fd.ty.name}' — only value types allowed")
                fields[fd.name] = fd.ty.name
                field_order.append(fd.name)

            methods: Dict[str, Tuple[List[str], str]] = {}
            for m in st.methods:
                if m.name == "init":
                    raise TypeError(m.loc, f"structs cannot have 'init' methods — construction is positional by field order")
                if not m.params or m.params[0].name != "self":
                    raise TypeError(m.loc, f"struct method '{m.name}' must have 'self' as first parameter")
                param_tys: List[str] = []
                for p in m.params[1:]:
                    _require_known(p.loc, p.ty.name)
                    param_tys.append(p.ty.name)
                _require_known(m.loc, m.ret.name)
                methods[m.name] = (param_tys, m.ret.name)

            self.structs[st.name] = StructInfo(
                name=st.name, fields=fields, field_order=field_order, methods=methods
            )

        # Detect circular struct references (value types cannot contain themselves)
        def _struct_cycle(start: str, visited: set) -> Optional[str]:
            for fname, fty in self.structs[start].fields.items():
                if fty in self.structs:
                    if fty in visited:
                        return fty
                    visited.add(fty)
                    result = _struct_cycle(fty, visited)
                    if result is not None:
                        return result
                    visited.discard(fty)
            return None
        for st in self.prog.structs:
            target = _struct_cycle(st.name, {st.name})
            if target is not None:
                raise TypeError(st.loc, f"struct '{st.name}' contains itself (directly or indirectly) — value types cannot be recursive")

        # Build function table, validate declared types
        for f in self.prog.funcs:
            if f.type_params:
                # Generic function template — store separately, don't check body yet
                self.generic_funcs[f.name] = f
                continue
            _require_known(f.loc, f.ret.name)
            param_tys: List[str] = []
            for p in f.params:
                _require_known(p.loc, p.ty.name)
                param_tys.append(p.ty.name)
            if f.name in self.funcs:
                raise TypeError(f.loc, f"duplicate function '{f.name}'")
            self.funcs[f.name] = (param_tys, f.ret.name)

        # Typecheck top-level statements first (global scope)
        # This scope persists so functions/methods can access global variables.
        self._push_scope()
        self.cur_ret = None
        self.loop_depth = 0
        for st in self.prog.stmts:
            self._check_stmt(st)

        # Typecheck non-generic functions (global scope is still on the stack)
        for f in self.prog.funcs:
            if f.type_params:
                continue  # skip generic templates
            self._check_func(f)

        # Typecheck class methods
        for cls in self.prog.classes:
            for m in cls.methods:
                self._check_method(cls.name, m)

        # Typecheck struct methods
        for st in self.prog.structs:
            for m in st.methods:
                self._check_struct_method(st.name, m)

        self._pop_scope()

    # -------------------------
    # Scopes
    # -------------------------

    def _push_scope(self) -> None:
        self.vars.append({})

    def _pop_scope(self) -> None:
        self.vars.pop()

    def _declare(self, name: str, ty: str, loc, is_const: bool = False) -> None:
        if name in self.vars[-1]:
            raise TypeError(loc, f"variable '{name}' already declared in this scope")
        self.vars[-1][name] = VarInfo(ty=ty, is_const=is_const)

    def _lookup(self, name: str, loc) -> VarInfo:
        for scope in reversed(self.vars):
            if name in scope:
                return scope[name]
        raise TypeError(loc, f"undefined variable '{name}'")

    # -------------------------
    # Circular reference detection
    # -------------------------

    def _check_circular_refs(self) -> None:
        """Detect mutual reference cycles among class fields (would leak with refcounting).
        Self-references (e.g. Node.next: Node) are allowed — only multi-class
        cycles (A -> B -> A) are rejected."""

        def _extract_class_refs(ty: str) -> set:
            """Extract all class names reachable from a type (including through containers)."""
            refs: set = set()
            if ty in self.classes:
                refs.add(ty)
            elif is_list_type(ty):
                refs |= _extract_class_refs(list_elem_type(ty))
            elif is_dict_type(ty):
                refs |= _extract_class_refs(dict_key_type(ty))
                refs |= _extract_class_refs(dict_val_type(ty))
            return refs

        # Build adjacency: class -> set of class names referenced by fields
        # Self-edges are excluded — a class may reference itself (linked lists, trees)
        adj: Dict[str, set] = {name: set() for name in self.classes}
        field_locs: Dict[str, dict] = {}
        for cls in self.prog.classes:
            locs: dict = {}
            for fd in cls.fields:
                for target in _extract_class_refs(fd.ty.name):
                    if target == cls.name:
                        continue
                    adj[cls.name].add(target)
                    locs[target] = fd.loc
            field_locs[cls.name] = locs

        # DFS-based cycle detection
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {n: WHITE for n in adj}
        parent: Dict[str, Optional[str]] = {n: None for n in adj}

        def dfs(u: str) -> Optional[list]:
            color[u] = GRAY
            for v in adj[u]:
                if v not in color:
                    continue
                if color[v] == GRAY:
                    cycle = [v, u]
                    cur = u
                    while cur != v:
                        cur = parent[cur]
                        if cur is None:
                            break
                        cycle.append(cur)
                    cycle.reverse()
                    return cycle
                if color[v] == WHITE:
                    parent[v] = u
                    result = dfs(v)
                    if result is not None:
                        return result
            color[u] = BLACK
            return None

        for node in adj:
            if color[node] == WHITE:
                cycle = dfs(node)
                if cycle is not None:
                    loc = field_locs[cycle[0]].get(cycle[1] if len(cycle) > 1 else cycle[0])
                    if loc is None:
                        loc = self.prog.classes[0].loc
                    path = " -> ".join(cycle)
                    raise TypeError(loc,
                        f"circular class reference detected: {path}. "
                        f"Classes cannot reference each other in a cycle, "
                        f"including through List or Dict fields")

    # -------------------------
    # Functions / statements
    # -------------------------

    def _check_func(self, f: FuncDecl) -> None:
        self._push_scope()
        self.cur_ret = f.ret.name
        self.loop_depth = 0

        # params are declared
        for p in f.params:
            self._declare(p.name, p.ty.name, p.loc)

        for st in f.body.stmts:
            self._check_stmt(st)

        self._pop_scope()

    def _check_method(self, class_name: str, m: FuncDecl) -> None:
        self._push_scope()
        self.cur_ret = m.ret.name
        self.cur_class = class_name
        self.loop_depth = 0

        # 'self' is first param, type is the class
        self._declare("self", class_name, m.params[0].loc)
        for p in m.params[1:]:
            self._declare(p.name, p.ty.name, p.loc)

        for st in m.body.stmts:
            self._check_stmt(st)

        self.cur_class = None
        self._pop_scope()

    def _check_struct_method(self, struct_name: str, m: FuncDecl) -> None:
        self._push_scope()
        self.cur_ret = m.ret.name
        self.cur_struct = struct_name
        self.loop_depth = 0

        # 'self' is first param, type is the struct
        self._declare("self", struct_name, m.params[0].loc)
        for p in m.params[1:]:
            self._declare(p.name, p.ty.name, p.loc)

        for st in m.body.stmts:
            self._check_stmt(st)

        self.cur_struct = None
        self._pop_scope()

    def _check_stmt(self, st: Stmt) -> None:
        if isinstance(st, SVarDecl):
            # Pass declared type as hint so literals adapt
            hint = st.ty.name if st.ty else None
            val_ty = self._check_expr(st.value, target_ty=hint)
            if st.ty is None:
                # := shorthand — infer type from RHS
                if val_ty == "none":
                    raise TypeError(st.loc, "cannot infer type from 'None' in := declaration")
                if val_ty == "void":
                    raise TypeError(st.loc, "cannot infer type from void expression in := declaration")
                st.ty = TypeRef(st.loc, val_ty)
            else:
                _require_known(st.loc, st.ty.name)
                if not _assignable(val_ty, st.ty.name):
                    raise TypeError(st.loc, f"cannot assign value of type {val_ty} to variable '{st.name}' of type {st.ty.name}")
            if st.is_static and self.cur_ret is None:
                raise TypeError(st.loc, "'static' variables are only allowed inside functions")
            self._declare(st.name, st.ty.name, st.loc, is_const=st.is_const)
            return

        if isinstance(st, SAssign):
            vi = self._lookup(st.name, st.loc)
            if vi.is_const:
                raise TypeError(st.loc, f"cannot assign to constant '{st.name}'")
            rhs_ty = self._check_expr(st.value, target_ty=vi.ty)

            if st.op == "=":
                if not _assignable(rhs_ty, vi.ty):
                    raise TypeError(st.loc, f"cannot assign {rhs_ty} to '{st.name}' of type {vi.ty}")
                return

            # compound assigns numeric only, and rhs must match var type
            if st.op in {"+=", "-=", "*=", "/=", "%="}:
                # str += str is allowed (concatenation)
                if st.op == "+=" and vi.ty == "str":
                    if rhs_ty != "str":
                        raise TypeError(st.loc, f"cannot apply '{st.op}' with str and {rhs_ty}")
                    return
                if vi.ty not in NUM_TYPES:
                    raise TypeError(st.loc, f"compound assignment '{st.op}' only allowed on numeric types, got {vi.ty}")
                if rhs_ty != vi.ty:
                    raise TypeError(st.loc, f"cannot apply '{st.op}' with {vi.ty} and {rhs_ty}")
                return

            if st.op in {"&=", "|=", "^=", "<<=", ">>="}:
                if vi.ty not in INT_TYPES:
                    raise TypeError(st.loc, f"compound assignment '{st.op}' only allowed on integer types, got {vi.ty}")
                if rhs_ty != vi.ty:
                    raise TypeError(st.loc, f"cannot apply '{st.op}' with {vi.ty} and {rhs_ty}")
                return

            raise TypeError(st.loc, f"unknown assignment operator '{st.op}'")

        if isinstance(st, SMemberAssign):
            obj_ty = self._check_expr(st.obj)
            if obj_ty in self.interfaces:
                raise TypeError(st.loc, f"cannot assign fields on interface type '{obj_ty}'")
            if obj_ty in self.structs:
                si = self.structs[obj_ty]
                if st.member not in si.fields:
                    raise TypeError(st.loc, f"struct '{obj_ty}' has no field '{st.member}'")
                field_ty = si.fields[st.member]
                rhs_ty = self._check_expr(st.value, target_ty=field_ty)
                if st.op == "=":
                    if not _assignable(rhs_ty, field_ty):
                        raise TypeError(st.loc, f"cannot assign {rhs_ty} to field '{st.member}' of type {field_ty}")
                    return
                if st.op in {"+=", "-=", "*=", "/=", "%="}:
                    if field_ty not in NUM_TYPES:
                        raise TypeError(st.loc, f"compound assignment '{st.op}' on field only allowed on numeric types, got {field_ty}")
                    if rhs_ty != field_ty:
                        raise TypeError(st.loc, f"cannot apply '{st.op}' with {field_ty} and {rhs_ty}")
                    return
                if st.op in {"&=", "|=", "^=", "<<=", ">>="}:
                    if field_ty not in INT_TYPES:
                        raise TypeError(st.loc, f"compound assignment '{st.op}' on field only allowed on integer types, got {field_ty}")
                    if rhs_ty != field_ty:
                        raise TypeError(st.loc, f"cannot apply '{st.op}' with {field_ty} and {rhs_ty}")
                    return
                raise TypeError(st.loc, f"unknown assignment operator '{st.op}'")
            if obj_ty not in self.classes:
                raise TypeError(st.loc, f"member assignment on non-class type '{obj_ty}'")
            ci = self.classes[obj_ty]
            if st.member not in ci.fields:
                raise TypeError(st.loc, f"class '{obj_ty}' has no field '{st.member}'")
            field_ty = ci.fields[st.member]
            rhs_ty = self._check_expr(st.value, target_ty=field_ty)
            if st.op == "=":
                if not _assignable(rhs_ty, field_ty):
                    raise TypeError(st.loc, f"cannot assign {rhs_ty} to field '{st.member}' of type {field_ty}")
                return
            if st.op in {"+=", "-=", "*=", "/=", "%="}:
                if field_ty not in NUM_TYPES:
                    raise TypeError(st.loc, f"compound assignment '{st.op}' on field only allowed on numeric types, got {field_ty}")
                if rhs_ty != field_ty:
                    raise TypeError(st.loc, f"cannot apply '{st.op}' with {field_ty} and {rhs_ty}")
                return
            if st.op in {"&=", "|=", "^=", "<<=", ">>="}:
                if field_ty not in INT_TYPES:
                    raise TypeError(st.loc, f"compound assignment '{st.op}' on field only allowed on integer types, got {field_ty}")
                if rhs_ty != field_ty:
                    raise TypeError(st.loc, f"cannot apply '{st.op}' with {field_ty} and {rhs_ty}")
                return
            raise TypeError(st.loc, f"unknown assignment operator '{st.op}'")

        if isinstance(st, SIndexAssign):
            obj_ty = self._check_expr(st.obj)
            idx_ty = self._check_expr(st.index)
            if is_list_type(obj_ty):
                if idx_ty != "i64":
                    raise TypeError(st.loc, f"list index must be i64, got {idx_ty}")
                elem = list_elem_type(obj_ty)
                rhs_ty = self._check_expr(st.value, target_ty=elem)
                if st.op != "=":
                    raise TypeError(st.loc, f"only '=' assignment supported for list subscript")
                if not _assignable(rhs_ty, elem):
                    raise TypeError(st.loc, f"cannot assign {rhs_ty} to list element of type {elem}")
                return
            if is_dict_type(obj_ty):
                key = dict_key_type(obj_ty)
                if idx_ty != key:
                    raise TypeError(st.loc, f"dict key must be {key}, got {idx_ty}")
                val = dict_val_type(obj_ty)
                rhs_ty = self._check_expr(st.value, target_ty=val)
                if st.op != "=":
                    raise TypeError(st.loc, f"only '=' assignment supported for dict subscript")
                if not _assignable(rhs_ty, val):
                    raise TypeError(st.loc, f"cannot assign {rhs_ty} to dict value of type {val}")
                return
            rhs_ty = self._check_expr(st.value)
            raise TypeError(st.loc, f"type '{obj_ty}' does not support subscript assignment []")

        if isinstance(st, SExpr):
            self._check_expr(st.expr)
            return

        if isinstance(st, SReturn):
            if self.cur_ret is None:
                raise TypeError(st.loc, "return not allowed at top level")
            if st.value is None:
                # bare return only allowed in void functions
                if self.cur_ret != "void":
                    raise TypeError(st.loc, f"return requires a value of type {self.cur_ret}")
                return
            if self.cur_ret == "void":
                raise TypeError(st.loc, "void function must not return a value")
            vty = self._check_expr(st.value, target_ty=self.cur_ret)
            if not _assignable(vty, self.cur_ret):
                raise TypeError(st.loc, f"return type mismatch: expected {self.cur_ret}, got {vty}")
            return

        if isinstance(st, SBreak):
            if self.loop_depth <= 0:
                raise TypeError(st.loc, "break not inside loop")
            return

        if isinstance(st, SContinue):
            if self.loop_depth <= 0:
                raise TypeError(st.loc, "continue not inside loop")
            return

        if isinstance(st, SWhile):
            cty = self._check_expr(st.cond)
            if not _is_truthy_type(cty):
                raise TypeError(st.loc, f"while condition must be bool, integer, or reference type, got {cty}")
            self.loop_depth += 1
            self._push_scope()
            for s2 in st.body.stmts:
                self._check_stmt(s2)
            self._pop_scope()
            self.loop_depth -= 1
            return

        if isinstance(st, SFor):
            _require_known(st.loc, st.var_ty.name)
            iter_ty = self._check_expr(st.iterable)
            if not is_list_type(iter_ty):
                raise TypeError(st.loc, f"for-in requires a list type, got {iter_ty}")
            elem_ty = list_elem_type(iter_ty)
            if st.var_ty.name != elem_ty:
                raise TypeError(st.loc, f"loop variable type '{st.var_ty.name}' does not match list element type '{elem_ty}'")
            self.loop_depth += 1
            self._push_scope()
            self._declare(st.var_name, elem_ty, st.loc)
            for s2 in st.body.stmts:
                self._check_stmt(s2)
            self._pop_scope()
            self.loop_depth -= 1
            return

        if isinstance(st, SIf):
            for arm in st.arms:
                if arm.cond is not None:
                    cty = self._check_expr(arm.cond)
                    if not _is_truthy_type(cty):
                        raise TypeError(arm.loc, f"if/elif condition must be bool, integer, or reference type, got {cty}")
                self._push_scope()
                for s2 in arm.block.stmts:
                    self._check_stmt(s2)
                self._pop_scope()
            return

        if isinstance(st, SBlock):
            self._push_scope()
            for s2 in st.stmts:
                self._check_stmt(s2)
            self._pop_scope()
            return

        if isinstance(st, STupleDestructure):
            val_ty = self._check_expr(st.value)
            if not is_tuple_type(val_ty):
                raise TypeError(st.loc, f"cannot destructure non-tuple type '{val_ty}'")
            elem_tys = tuple_elem_types(val_ty)
            if len(elem_tys) != len(st.names):
                raise TypeError(st.loc, f"tuple has {len(elem_tys)} elements, but {len(st.names)} names given")
            for name, ety in zip(st.names, elem_tys):
                self._declare(name, ety, st.loc)
            return

        raise TypeError(st.loc, f"unhandled statement {type(st).__name__}")

    # -------------------------
    # Expressions
    # -------------------------

    def _check_expr(self, e: Expr, target_ty: Optional[str] = None) -> str:
        if isinstance(e, EInt):
            if target_ty in INT_TYPES:
                return _set_expr_ty(e, target_ty)
            return _set_expr_ty(e, "i64")

        if isinstance(e, EFloat):
            if target_ty in FLOAT_TYPES:
                return _set_expr_ty(e, target_ty)
            return _set_expr_ty(e, "f64")

        if isinstance(e, EBool):
            return _set_expr_ty(e, "bool")

        if isinstance(e, EString):
            return _set_expr_ty(e, "str")

        if isinstance(e, EChar):
            if target_ty in INT_TYPES:
                return _set_expr_ty(e, target_ty)
            return _set_expr_ty(e, "i64")

        if isinstance(e, ENone):
            return _set_expr_ty(e, "none")

        if isinstance(e, EVar):
            # Function name used as a value (function pointer)
            if target_ty and is_fn_type(target_ty) and e.name in self.funcs:
                param_tys, ret_ty = self.funcs[e.name]
                fn_ty = f"Fn({','.join(param_tys)})->{ret_ty}"
                if fn_ty != target_ty:
                    raise TypeError(e.loc, f"function '{e.name}' has type {fn_ty}, expected {target_ty}")
                return _set_expr_ty(e, fn_ty)
            vi = self._lookup(e.name, e.loc)
            return _set_expr_ty(e, vi.ty)

        if isinstance(e, EUnary):
            rhs_ty = self._check_expr(e.rhs, target_ty=target_ty)
            if e.op == "-":
                if _resolve_enum_ty(rhs_ty) not in NUM_TYPES:
                    raise TypeError(e.loc, f"unary '-' requires numeric, got {rhs_ty}")
                return _set_expr_ty(e, rhs_ty)
            if e.op == "not":
                if not _is_truthy_type(rhs_ty):
                    raise TypeError(e.loc, f"'not' requires bool, integer, or reference type, got {rhs_ty}")
                return _set_expr_ty(e, "bool")
            if e.op == "~":
                if _resolve_enum_ty(rhs_ty) not in INT_TYPES:
                    raise TypeError(e.loc, f"unary '~' requires integer, got {rhs_ty}")
                return _set_expr_ty(e, rhs_ty)
            raise TypeError(e.loc, f"unknown unary operator '{e.op}'")

        if isinstance(e, EIs):
            lhs_ty = self._check_expr(e.expr)
            rhs = e.type_name
            # RHS must be a known type
            if rhs == "None":
                # 'x is None' — syntactic sugar for None check
                return _set_expr_ty(e, "bool")
            if not _is_known(rhs):
                raise TypeError(e.loc, f"'is' right-hand side must be a type name, got '{rhs}'")
            # Store the LHS type for codegen
            setattr(e, "lhs_ty", lhs_ty)
            return _set_expr_ty(e, "bool")

        if isinstance(e, EAs):
            lhs_ty = self._check_expr(e.expr)
            target = e.type_name
            if not _is_known(target):
                raise TypeError(e.loc, f"'as' target must be a type name, got '{target}'")
            # LHS must be an interface type
            if lhs_ty not in self.interfaces:
                raise TypeError(e.loc, f"'as' requires an interface type on the left, got '{lhs_ty}'")
            # Target must be a class that implements the interface
            if target not in self.classes:
                raise TypeError(e.loc, f"'as' target must be a class type, got '{target}'")
            if target not in _CLASS_IMPLEMENTS or lhs_ty not in _CLASS_IMPLEMENTS[target]:
                raise TypeError(e.loc, f"class '{target}' does not implement interface '{lhs_ty}'")
            # Store the LHS type for codegen
            setattr(e, "lhs_ty", lhs_ty)
            return _set_expr_ty(e, target)

        if isinstance(e, EBinary):
            a = self._check_expr(e.lhs)
            # For binary ops, let integer/float literals adapt to the other operand's type
            if a in INT_TYPES and isinstance(e.rhs, (EInt, EChar)):
                b = self._check_expr(e.rhs, target_ty=a)
            elif a in FLOAT_TYPES and isinstance(e.rhs, EFloat):
                b = self._check_expr(e.rhs, target_ty=a)
            else:
                b = self._check_expr(e.rhs)
            # Symmetric: if RHS resolved first and LHS is a literal, re-check LHS
            if b in INT_TYPES and a == "i64" and isinstance(e.lhs, (EInt, EChar)) and b != "i64":
                a = self._check_expr(e.lhs, target_ty=b)
            elif b in FLOAT_TYPES and a == "f64" and isinstance(e.lhs, EFloat) and b != "f64":
                a = self._check_expr(e.lhs, target_ty=b)
            op = e.op
            # Resolve enum types to i64 for operator checks
            ra, rb = _resolve_enum_ty(a), _resolve_enum_ty(b)

            if op in ("+", "-", "*", "/", "%"):
                # str + str → str concatenation
                if op == "+" and a == "str" and b == "str":
                    return _set_expr_ty(e, "str")
                if ra not in NUM_TYPES or rb not in NUM_TYPES:
                    raise TypeError(e.loc, f"operator '{op}' requires numeric operands, got {a} and {b}")
                if ra != rb:
                    raise TypeError(e.loc, f"operator '{op}' requires same numeric type, got {a} and {b}")
                return _set_expr_ty(e, a)

            if op in ("&", "|", "^", "<<", ">>"):
                if ra not in INT_TYPES or rb not in INT_TYPES:
                    raise TypeError(e.loc, f"operator '{op}' requires integer operands, got {a} and {b}")
                if ra != rb:
                    raise TypeError(e.loc, f"operator '{op}' requires same integer type, got {a} and {b}")
                return _set_expr_ty(e, a)

            if op in ("<", "<=", ">", ">="):
                if ra not in NUM_TYPES or rb not in NUM_TYPES:
                    raise TypeError(e.loc, f"comparison '{op}' requires numeric operands, got {a} and {b}")
                if ra != rb:
                    raise TypeError(e.loc, f"comparison '{op}' requires same numeric type, got {a} and {b}")
                return _set_expr_ty(e, "bool")

            if op in ("==", "!="):
                # allow comparing ref types with none
                if a == "none" and _is_ref_type(b):
                    return _set_expr_ty(e, "bool")
                if b == "none" and _is_ref_type(a):
                    return _set_expr_ty(e, "bool")
                if ra != rb:
                    raise TypeError(e.loc, f"equality '{op}' requires same types, got {a} and {b}")
                return _set_expr_ty(e, "bool")

            if op in ("and", "or"):
                if not _is_truthy_type(a) or not _is_truthy_type(b):
                    raise TypeError(e.loc, f"'{op}' requires bool, integer, or reference operands, got {a} and {b}")
                return _set_expr_ty(e, "bool")

            raise TypeError(e.loc, f"unknown binary operator '{op}'")

        if isinstance(e, ECall):
            return self._check_call(e)

        if isinstance(e, EMemberAccess):
            # Check for enum variant access: EnumName.VARIANT
            if isinstance(e.obj, EVar) and e.obj.name in _USER_ENUM_NAMES:
                enum_name = e.obj.name
                variants = self.enum_variants.get(enum_name, {})
                if e.member not in variants:
                    raise TypeError(e.loc, f"enum '{enum_name}' has no variant '{e.member}'")
                return _set_expr_ty(e, enum_name)
            obj_ty = self._check_expr(e.obj)
            if obj_ty in self.interfaces:
                raise TypeError(e.loc, f"cannot access fields on interface type '{obj_ty}'")
            if obj_ty in self.structs:
                si = self.structs[obj_ty]
                if e.member not in si.fields:
                    raise TypeError(e.loc, f"struct '{obj_ty}' has no field '{e.member}'")
                return _set_expr_ty(e, si.fields[e.member])
            if obj_ty not in self.classes:
                raise TypeError(e.loc, f"member access on non-class type '{obj_ty}'")
            ci = self.classes[obj_ty]
            if e.member not in ci.fields:
                raise TypeError(e.loc, f"class '{obj_ty}' has no field '{e.member}'")
            return _set_expr_ty(e, ci.fields[e.member])

        if isinstance(e, EIndex):
            obj_ty = self._check_expr(e.obj)
            idx_ty = self._check_expr(e.index)
            if is_list_type(obj_ty):
                if idx_ty != "i64":
                    raise TypeError(e.loc, f"list index must be i64, got {idx_ty}")
                elem = list_elem_type(obj_ty)
                return _set_expr_ty(e, elem)
            if is_dict_type(obj_ty):
                key = dict_key_type(obj_ty)
                if idx_ty != key:
                    raise TypeError(e.loc, f"dict key must be {key}, got {idx_ty}")
                val = dict_val_type(obj_ty)
                return _set_expr_ty(e, val)
            if obj_ty == "str":
                if idx_ty != "i64":
                    raise TypeError(e.loc, f"string index must be i64, got {idx_ty}")
                return _set_expr_ty(e, "i64")
            raise TypeError(e.loc, f"type '{obj_ty}' does not support subscript []")

        if isinstance(e, ETuple):
            target_elems = None
            if target_ty and is_tuple_type(target_ty):
                target_elems = tuple_elem_types(target_ty)
                if len(target_elems) != len(e.elems):
                    raise TypeError(e.loc, f"tuple has {len(e.elems)} elements, target type expects {len(target_elems)}")
            elem_tys: List[str] = []
            for i, elem in enumerate(e.elems):
                elem_target = target_elems[i] if target_elems else None
                ety = self._check_expr(elem, target_ty=elem_target)
                if target_elems:
                    if not _assignable(ety, target_elems[i]):
                        raise TypeError(elem.loc, f"tuple element {i} has type {ety}, expected {target_elems[i]}")
                elem_tys.append(ety)
            if target_elems:
                result_ty = target_ty
            else:
                result_ty = "(" + ",".join(elem_tys) + ")"
            return _set_expr_ty(e, result_ty)

        if isinstance(e, EListLit):
            tp = e.elem_type
            if not _is_known(tp):
                raise TypeError(e.loc, f"unknown type parameter '{tp}' in List[{tp}]")
            for i, elem in enumerate(e.elems):
                ety = self._check_expr(elem, target_ty=tp)
                if not _assignable(ety, tp):
                    raise TypeError(elem.loc, f"list literal element {i+1} has type {ety}, expected {tp}")
            return _set_expr_ty(e, f"List[{tp}]")

        if isinstance(e, EDictLit):
            ktp = e.key_type
            tp = e.val_type
            if not _is_known(ktp):
                raise TypeError(e.loc, f"unknown key type '{ktp}' in Dict[{ktp},{tp}]")
            if not _is_known(tp):
                raise TypeError(e.loc, f"unknown value type '{tp}' in Dict[{ktp},{tp}]")
            _check_dict_key_type(e.loc, ktp, self)
            for i, key in enumerate(e.keys):
                kty = self._check_expr(key, target_ty=ktp)
                if kty != ktp:
                    raise TypeError(key.loc, f"dict literal key {i+1} must be {ktp}, got {kty}")
            for i, val in enumerate(e.vals):
                vty = self._check_expr(val, target_ty=tp)
                if not _assignable(vty, tp):
                    raise TypeError(val.loc, f"dict literal value {i+1} has type {vty}, expected {tp}")
            return _set_expr_ty(e, f"Dict[{ktp},{tp}]")

        raise TypeError(e.loc, f"unhandled expression {type(e).__name__}")

    def _check_call(self, e: ECall) -> str:
        # Method call: obj.method(args)
        if isinstance(e.callee, EMemberAccess):
            obj_ty = self._check_expr(e.callee.obj)
            # Interface method call
            if obj_ty in self.interfaces:
                ii = self.interfaces[obj_ty]
                mname = e.callee.member
                if mname not in ii.methods:
                    raise TypeError(e.loc, f"interface '{obj_ty}' has no method '{mname}'")
                param_tys, ret_ty = ii.methods[mname]
                if len(param_tys) != len(e.args):
                    raise TypeError(e.loc, f"method '{mname}' expects {len(param_tys)} args (excl self), got {len(e.args)}")
                for i, (pt, arg) in enumerate(zip(param_tys, e.args)):
                    at = self._check_expr(arg, target_ty=pt)
                    if not _assignable(at, pt):
                        raise TypeError(arg.loc, f"argument {i+1} of '{mname}' expected {pt}, got {at}")
                return _set_expr_ty(e, ret_ty)
            # Class method call
            if obj_ty in self.structs:
                si = self.structs[obj_ty]
                mname = e.callee.member
                if mname not in si.methods:
                    raise TypeError(e.loc, f"struct '{obj_ty}' has no method '{mname}'")
                param_tys, ret_ty = si.methods[mname]
                if len(param_tys) != len(e.args):
                    raise TypeError(e.loc, f"method '{mname}' expects {len(param_tys)} args (excl self), got {len(e.args)}")
                for i, (pt, arg) in enumerate(zip(param_tys, e.args)):
                    at = self._check_expr(arg, target_ty=pt)
                    if not _assignable(at, pt):
                        raise TypeError(arg.loc, f"argument {i+1} of '{mname}' expected {pt}, got {at}")
                return _set_expr_ty(e, ret_ty)
            if obj_ty not in self.classes:
                raise TypeError(e.loc, f"method call on non-class type '{obj_ty}'")
            ci = self.classes[obj_ty]
            mname = e.callee.member
            if mname not in ci.methods:
                raise TypeError(e.loc, f"class '{obj_ty}' has no method '{mname}'")
            param_tys, ret_ty = ci.methods[mname]
            if len(param_tys) != len(e.args):
                raise TypeError(e.loc, f"method '{mname}' expects {len(param_tys)} args (excl self), got {len(e.args)}")
            for i, (pt, arg) in enumerate(zip(param_tys, e.args)):
                at = self._check_expr(arg, target_ty=pt)
                if not _assignable(at, pt):
                    raise TypeError(arg.loc, f"argument {i+1} of '{mname}' expected {pt}, got {at}")
            return _set_expr_ty(e, ret_ty)

        # Expression-based function pointer call: e.g. ops[0](3, 4) or get_fn()(x)
        if not isinstance(e.callee, EVar):
            callee_ty = self._check_expr(e.callee)
            if is_fn_type(callee_ty):
                param_tys = fn_param_types(callee_ty)
                ret_ty = fn_ret_type(callee_ty)
                if len(param_tys) != len(e.args):
                    raise TypeError(e.loc, f"function pointer expects {len(param_tys)} args, got {len(e.args)}")
                for i, (pt, arg) in enumerate(zip(param_tys, e.args)):
                    at = self._check_expr(arg, target_ty=pt)
                    if not _assignable(at, pt):
                        raise TypeError(arg.loc, f"argument {i+1} of function pointer expected {pt}, got {at}")
                return _set_expr_ty(e, ret_ty)
            raise TypeError(e.loc, "callee must be identifier")

        name = e.callee.name

        # Function pointer call: variable with Fn(...) type
        if name not in self.funcs and name not in CAST_TYPES and name not in ("print", "range", "keys", "len", "format") and name not in GENERIC_CONTAINER_OPS and name not in self.classes and name not in self.interfaces and name not in self.generic_funcs:
            # Check if it's a variable with Fn type
            try:
                vi = self._lookup(name, e.loc)
                if is_fn_type(vi.ty):
                    param_tys = fn_param_types(vi.ty)
                    ret_ty = fn_ret_type(vi.ty)
                    if len(param_tys) != len(e.args):
                        raise TypeError(e.loc, f"function pointer '{name}' expects {len(param_tys)} args, got {len(e.args)}")
                    for i, (pt, arg) in enumerate(zip(param_tys, e.args)):
                        at = self._check_expr(arg, target_ty=pt)
                        if not _assignable(at, pt):
                            raise TypeError(arg.loc, f"argument {i+1} of function pointer '{name}' expected {pt}, got {at}")
                    return _set_expr_ty(e, ret_ty)
            except TypeError:
                pass

        # Type cast builtins: i8(x), i16(x), i32(x), i64(x), f32(x), f64(x)
        if name in CAST_TYPES:
            if len(e.args) != 1:
                raise TypeError(e.loc, f"{name}() expects 1 argument")
            aty = self._check_expr(e.args[0])
            raty = _resolve_enum_ty(aty)
            if raty not in NUM_TYPES:
                raise TypeError(e.loc, f"{name}() requires a numeric argument, got {aty}")
            return _set_expr_ty(e, name)

        # print is special (overloaded by arg type)
        if name == "print":
            if len(e.args) != 1:
                raise TypeError(e.loc, "print(x) expects 1 argument")
            aty = self._check_expr(e.args[0])
            raty = _resolve_enum_ty(aty)
            if raty not in NUM_TYPES and raty not in ("bool", "str"):
                raise TypeError(e.loc, f"print() does not support type {aty}")
            return _set_expr_ty(e, "void")

        # format() — variadic string formatting, returns str
        if name == "format":
            if len(e.args) < 1:
                raise TypeError(e.loc, "format() expects at least 1 argument (the format string)")
            fmt_ty = self._check_expr(e.args[0])
            if fmt_ty != "str":
                raise TypeError(e.args[0].loc, f"format() first argument must be str, got {fmt_ty}")
            for i, arg in enumerate(e.args[1:], start=2):
                aty = self._check_expr(arg)
                raty = _resolve_enum_ty(aty)
                if raty not in NUM_TYPES and raty not in ("bool", "str"):
                    raise TypeError(arg.loc, f"format() argument {i} has unsupported type {aty}")
            return _set_expr_ty(e, "str")

        # range() is special (1-3 i64 args, returns List[i64])
        if name == "range":
            if len(e.args) < 1 or len(e.args) > 3:
                raise TypeError(e.loc, f"range() expects 1-3 arguments, got {len(e.args)}")
            for i, arg in enumerate(e.args):
                at = self._check_expr(arg)
                if at != "i64":
                    raise TypeError(arg.loc, f"argument {i+1} of 'range' must be i64, got {at}")
            return _set_expr_ty(e, "List[i64]")

        # keys() is special (1 dict arg, returns List[K])
        if name == "keys":
            if len(e.args) != 1:
                raise TypeError(e.loc, "keys() expects 1 argument")
            at = self._check_expr(e.args[0])
            if not is_dict_type(at):
                raise TypeError(e.loc, f"keys() requires a dict type, got {at}")
            k = dict_key_type(at)
            return _set_expr_ty(e, f"List[{k}]")

        # len() — overloaded, works on list/dict/str (no type param needed)
        if name == "len":
            if len(e.args) != 1:
                raise TypeError(e.loc, "len() expects 1 argument")
            at = self._check_expr(e.args[0])
            if is_list_type(at) or is_dict_type(at) or at == "str":
                return _set_expr_ty(e, "i64")
            raise TypeError(e.loc, f"len() does not support type {at}")

        # Generic container operations: name[T](...) or name[K,V](...) with explicit type param
        if e.type_param is not None and name in GENERIC_CONTAINER_OPS:
            tp = e.type_param
            # For dict ops, tp is "K,V" — validate both parts
            if name in _DICT_GENERIC_OPS or name == "Dict":
                k, v = _split_dict_inner(tp)
                if not _is_known(k):
                    raise TypeError(e.loc, f"unknown key type '{k}' in '{name}[{tp}]'")
                if not _is_known(v):
                    raise TypeError(e.loc, f"unknown value type '{v}' in '{name}[{tp}]'")
                _check_dict_key_type(e.loc, k, self)
            else:
                if not _is_known(tp):
                    raise TypeError(e.loc, f"unknown type parameter '{tp}' in '{name}[{tp}]'")
            param_tys, ret_ty = GENERIC_CONTAINER_OPS[name](tp)
            if len(param_tys) != len(e.args):
                raise TypeError(e.loc, f"'{name}[{tp}]' expects {len(param_tys)} args, got {len(e.args)}")
            for i, (pt, arg) in enumerate(zip(param_tys, e.args)):
                at = self._check_expr(arg, target_ty=pt)
                if not _assignable(at, pt):
                    raise TypeError(arg.loc, f"argument {i+1} of '{name}[{tp}]' expected {pt}, got {at}")
            return _set_expr_ty(e, ret_ty)

        # Type inference for generic container ops (no explicit type param)
        if e.type_param is None and name in GENERIC_CONTAINER_OPS and name not in ("List", "Dict") and len(e.args) > 0:
            # Infer T from first argument's type
            first_ty = self._check_expr(e.args[0])
            inferred_tp = None
            if name in _LIST_GENERIC_OPS and is_list_type(first_ty):
                inferred_tp = list_elem_type(first_ty)
            elif name in _DICT_GENERIC_OPS and is_dict_type(first_ty):
                # Infer full "K,V" from Dict[K,V]
                inferred_tp = first_ty[5:-1]  # extract "K,V" from "Dict[K,V]"
            if inferred_tp is not None:
                e.type_param = inferred_tp
                param_tys, ret_ty = GENERIC_CONTAINER_OPS[name](inferred_tp)
                if len(param_tys) != len(e.args):
                    raise TypeError(e.loc, f"'{name}' expects {len(param_tys)} args, got {len(e.args)}")
                # first arg already checked
                for i, (pt, arg) in enumerate(zip(param_tys, e.args)):
                    if i == 0:
                        continue  # already checked
                    at = self._check_expr(arg, target_ty=pt)
                    if not _assignable(at, pt):
                        raise TypeError(arg.loc, f"argument {i+1} of '{name}' expected {pt}, got {at}")
                return _set_expr_ty(e, ret_ty)

        # Generic container ops with explicit type_param (for unknown ops, raise error)
        if e.type_param is not None and name not in GENERIC_CONTAINER_OPS:
            # Could be a user-defined generic function — check below
            pass

        # Check builtin signature table
        if name in BUILTIN_SIGS:
            param_tys, ret_ty = BUILTIN_SIGS[name]
            if len(param_tys) != len(e.args):
                raise TypeError(e.loc, f"builtin '{name}' expects {len(param_tys)} args, got {len(e.args)}")
            for i, (pt, arg) in enumerate(zip(param_tys, e.args)):
                at = self._check_expr(arg)
                if at != pt:
                    raise TypeError(arg.loc, f"argument {i+1} of '{name}' expected {pt}, got {at}")
            return _set_expr_ty(e, ret_ty)

        # Interfaces cannot be constructed
        if name in self.interfaces:
            raise TypeError(e.loc, f"cannot construct interface '{name}' — only classes can be instantiated")

        # Constructor call: ClassName(args)
        if name in self.classes:
            ci = self.classes[name]
            if len(ci.init_params) != len(e.args):
                raise TypeError(e.loc, f"constructor '{name}' expects {len(ci.init_params)} args, got {len(e.args)}")
            for i, (pt, arg) in enumerate(zip(ci.init_params, e.args)):
                at = self._check_expr(arg, target_ty=pt)
                if not _assignable(at, pt):
                    raise TypeError(arg.loc, f"argument {i+1} of constructor '{name}' expected {pt}, got {at}")
            return _set_expr_ty(e, name)

        # Struct construction: StructName(field1, field2, ...) positional by field order
        if name in self.structs:
            si = self.structs[name]
            expected = len(si.field_order)
            if expected != len(e.args):
                raise TypeError(e.loc, f"struct '{name}' has {expected} fields, got {len(e.args)} arguments")
            for i, fname in enumerate(si.field_order):
                fty = si.fields[fname]
                at = self._check_expr(e.args[i], target_ty=fty)
                if not _assignable(at, fty):
                    raise TypeError(e.args[i].loc, f"field '{fname}' of struct '{name}' expected {fty}, got {at}")
            return _set_expr_ty(e, name)

        # User-defined generic function call
        if name in self.generic_funcs:
            return self._check_generic_call(e, name)

        # user functions
        if name not in self.funcs:
            raise TypeError(e.loc, f"unknown function '{name}'")

        param_tys, ret_ty = self.funcs[name]
        if len(param_tys) != len(e.args):
            raise TypeError(e.loc, f"function '{name}' expects {len(param_tys)} args, got {len(e.args)}")

        for i, (pt, arg) in enumerate(zip(param_tys, e.args)):
            at = self._check_expr(arg, target_ty=pt)
            if at != pt and not _assignable(at, pt):
                raise TypeError(arg.loc, f"argument {i+1} of '{name}' expected {pt}, got {at}")

        return _set_expr_ty(e, ret_ty)

    def _check_generic_call(self, e: ECall, name: str) -> str:
        """Handle calls to user-defined generic functions."""
        gf = self.generic_funcs[name]

        # Check all arg types first
        arg_types = [self._check_expr(arg) for arg in e.args]

        # Determine concrete type parameter
        if e.type_param is not None:
            concrete_tp = e.type_param
            if not _is_known(concrete_tp):
                raise TypeError(e.loc, f"unknown type parameter '{concrete_tp}' in '{name}[{concrete_tp}]'")
        else:
            # Infer type parameter from arguments
            concrete_tp = self._infer_user_generic_type(gf, arg_types, e.loc)
            e.type_param = concrete_tp

        # Build type substitution map
        type_sub = {gf.type_params[0]: concrete_tp}

        # Substitute types in param list and return type
        param_tys = [_subst_type_name(p.ty.name, type_sub) for p in gf.params]
        ret_ty = _subst_type_name(gf.ret.name, type_sub)

        # Validate arity and arg types
        if len(param_tys) != len(e.args):
            raise TypeError(e.loc, f"'{name}' expects {len(param_tys)} args, got {len(e.args)}")
        for i, (pt, at) in enumerate(zip(param_tys, arg_types)):
            if not _assignable(at, pt):
                raise TypeError(e.args[i].loc, f"argument {i+1} of '{name}' expected {pt}, got {at}")

        # Create and register the concrete instantiation if not already done
        tag = _elem_tag(concrete_tp)
        mangled = f"{name}_{tag}"
        if mangled not in self.funcs:
            concrete_func = _instantiate_func(gf, type_sub, mangled)
            self.funcs[mangled] = (param_tys, ret_ty)
            self.prog.funcs.append(concrete_func)
            # Typecheck the concrete instantiation
            self._check_func(concrete_func)

        return _set_expr_ty(e, ret_ty)

    def _infer_user_generic_type(self, gf: FuncDecl, arg_types: List[str], loc) -> str:
        """Infer the type parameter from argument types for a user-defined generic function."""
        tp_name = gf.type_params[0]  # e.g. "T"
        for p, at in zip(gf.params, arg_types):
            pt = p.ty.name
            if pt == tp_name:
                return at
            if is_list_type(pt) and pt[5:-1] == tp_name and is_list_type(at):
                return list_elem_type(at)
            if is_dict_type(pt) and is_dict_type(at):
                # Match val type of Dict[K,T] against Dict[K,V]
                pt_val = dict_val_type(pt)
                if pt_val == tp_name:
                    return dict_val_type(at)
        raise TypeError(loc, f"cannot infer type parameter '{tp_name}' for generic function '{gf.name}'")


# ---- helpers for elem tags (shared with codegen) ----
_PRIM_TAG = {"i64": "I64", "f64": "F64", "f32": "F32", "bool": "BOOL", "str": "STR",
             "i8": "I8", "i16": "I16", "i32": "I32",
             "u8": "U8", "u16": "U16", "u32": "U32", "u64": "U64"}

def _elem_tag(elem_ty: str) -> str:
    return _PRIM_TAG.get(elem_ty, elem_ty)


# ---- AST substitution for monomorphization ----

def _subst_type_name(name: str, sub: Dict[str, str]) -> str:
    if name in sub:
        return sub[name]
    if name.startswith("List[") and name.endswith("]"):
        inner = _subst_type_name(name[5:-1], sub)
        return f"List[{inner}]"
    if name.startswith("Dict[") and name.endswith("]"):
        k, v = _split_dict_inner(name[5:-1])
        k_sub = _subst_type_name(k, sub)
        v_sub = _subst_type_name(v, sub)
        return f"Dict[{k_sub},{v_sub}]"
    if is_tuple_type(name):
        elems = tuple_elem_types(name)
        subbed = [_subst_type_name(e, sub) for e in elems]
        return "(" + ",".join(subbed) + ")"
    return name


def _instantiate_func(gf: FuncDecl, type_sub: Dict[str, str], mangled_name: str) -> FuncDecl:
    """Create a concrete FuncDecl from a generic template by substituting type params."""
    concrete = copy.deepcopy(gf)
    concrete.name = mangled_name
    concrete.type_params = []

    # Substitute param types
    for p in concrete.params:
        p.ty = TypeRef(p.ty.loc, _subst_type_name(p.ty.name, type_sub))

    # Substitute return type
    concrete.ret = TypeRef(concrete.ret.loc, _subst_type_name(concrete.ret.name, type_sub))

    # Substitute in body
    _subst_block(concrete.body, type_sub)
    return concrete


def _subst_block(block, type_sub: Dict[str, str]) -> None:
    for st in block.stmts:
        _subst_stmt(st, type_sub)


def _subst_stmt(st, type_sub: Dict[str, str]) -> None:
    if isinstance(st, SVarDecl):
        if st.ty is not None:
            st.ty = TypeRef(st.ty.loc, _subst_type_name(st.ty.name, type_sub))
        _subst_expr(st.value, type_sub)
    elif isinstance(st, STupleDestructure):
        _subst_expr(st.value, type_sub)
    elif isinstance(st, SAssign):
        _subst_expr(st.value, type_sub)
    elif isinstance(st, SMemberAssign):
        _subst_expr(st.obj, type_sub)
        _subst_expr(st.value, type_sub)
    elif isinstance(st, SIndexAssign):
        _subst_expr(st.obj, type_sub)
        _subst_expr(st.index, type_sub)
        _subst_expr(st.value, type_sub)
    elif isinstance(st, SExpr):
        _subst_expr(st.expr, type_sub)
    elif isinstance(st, SReturn):
        if st.value:
            _subst_expr(st.value, type_sub)
    elif isinstance(st, SIf):
        for arm in st.arms:
            if arm.cond:
                _subst_expr(arm.cond, type_sub)
            _subst_block(arm.block, type_sub)
    elif isinstance(st, SWhile):
        _subst_expr(st.cond, type_sub)
        _subst_block(st.body, type_sub)
    elif isinstance(st, SFor):
        st.var_ty = TypeRef(st.var_ty.loc, _subst_type_name(st.var_ty.name, type_sub))
        _subst_expr(st.iterable, type_sub)
        _subst_block(st.body, type_sub)
    elif isinstance(st, SBlock):
        _subst_block(st, type_sub)


def _subst_expr(e, type_sub: Dict[str, str]) -> None:
    if isinstance(e, ECall):
        if e.type_param and e.type_param in type_sub:
            e.type_param = type_sub[e.type_param]
        _subst_expr(e.callee, type_sub)
        for arg in e.args:
            _subst_expr(arg, type_sub)
    elif isinstance(e, ETuple):
        for elem in e.elems:
            _subst_expr(elem, type_sub)
    elif isinstance(e, EBinary):
        _subst_expr(e.lhs, type_sub)
        _subst_expr(e.rhs, type_sub)
    elif isinstance(e, EUnary):
        _subst_expr(e.rhs, type_sub)
    elif isinstance(e, EMemberAccess):
        _subst_expr(e.obj, type_sub)
    elif isinstance(e, EIndex):
        _subst_expr(e.obj, type_sub)
        _subst_expr(e.index, type_sub)
    elif isinstance(e, EListLit):
        if e.elem_type in type_sub:
            e.elem_type = type_sub[e.elem_type]
        for elem in e.elems:
            _subst_expr(elem, type_sub)
    elif isinstance(e, EDictLit):
        if e.val_type in type_sub:
            e.val_type = type_sub[e.val_type]
        for k in e.keys:
            _subst_expr(k, type_sub)
        for v in e.vals:
            _subst_expr(v, type_sub)


def typecheck(prog: Program) -> None:
    TypeChecker(prog).check()
