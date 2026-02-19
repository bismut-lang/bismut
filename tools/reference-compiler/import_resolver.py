from lexer import Lexer, SrcLoc
from parser import (Parser, Program, FuncDecl, ClassDecl, StructDecl, InterfaceDecl,
                       ImportDecl, ExternDecl, EnumDecl, TypeRef, Param, FieldDecl, SBlock,
                       EVar, ECall, EMemberAccess, EInt, EFloat, EString, EBool,
                       EIndex, EBinary, EUnary, EIs, EAs, EListLit, EDictLit, ETuple,
                       SVarDecl, SAssign, SMemberAssign, SIndexAssign, STupleDestructure,
                       SExpr, SReturn, SIf, SWhile, SFor)
from mutlib import find_lib, parse_mutlib
from preprocess import preprocess

import sys
import os


def parse_file(path: str, extra_defines: set[str] | None = None) -> Program:
    src = open(path, encoding="utf-8").read()
    src = preprocess(src, file=path, extra_defines=extra_defines)
    lexer = Lexer(src, file=path)
    toks = lexer.tokenize()
    return Parser(toks, comments=lexer.comments).parse_program()


# --------------- AST walkers ---------------

def _walk_stmts(stmts, on_tr, on_ex):
    """Walk all statements, applying on_tr to TypeRefs and on_ex to Exprs."""
    for st in stmts:
        if isinstance(st, SVarDecl):
            if st.ty:
                st.ty = on_tr(st.ty)
            st.value = on_ex(st.value)
        elif isinstance(st, SAssign):
            st.name = on_ex(EVar(loc=st.loc, name=st.name)).name
            st.value = on_ex(st.value)
        elif isinstance(st, SMemberAssign):
            st.obj = on_ex(st.obj)
            st.value = on_ex(st.value)
        elif isinstance(st, SIndexAssign):
            st.obj = on_ex(st.obj)
            st.index = on_ex(st.index)
            st.value = on_ex(st.value)
        elif isinstance(st, SExpr):
            st.expr = on_ex(st.expr)
        elif isinstance(st, SReturn):
            if st.value:
                st.value = on_ex(st.value)
        elif isinstance(st, SIf):
            for arm in st.arms:
                if arm.cond:
                    arm.cond = on_ex(arm.cond)
                _walk_stmts(arm.block.stmts, on_tr, on_ex)
        elif isinstance(st, SWhile):
            st.cond = on_ex(st.cond)
            _walk_stmts(st.body.stmts, on_tr, on_ex)
        elif isinstance(st, STupleDestructure):
            st.value = on_ex(st.value)
        elif isinstance(st, SFor):
            st.var_ty = on_tr(st.var_ty)
            st.iterable = on_ex(st.iterable)
            _walk_stmts(st.body.stmts, on_tr, on_ex)


def _walk_decls(funcs, classes, ifaces, on_tr, on_ex, structs=None, rmap=None):
    """Walk declarations, applying on_tr to TypeRefs and on_ex to Exprs.

    When rmap is provided, expression renaming is scope-aware: parameter and
    local variable names that collide with top-level names in the rename map
    are excluded from renaming within that function/method body.
    """
    def _scoped_on_ex(params, stmts, rmap):
        if rmap is None:
            return on_ex
        local_names = _collect_local_names(params, stmts)
        shadowed = local_names & rmap.keys()
        if not shadowed:
            return on_ex
        scoped_rmap = {k: v for k, v in rmap.items() if k not in local_names}
        return lambda e, r=scoped_rmap: _rename_expr(e, r)

    for f in funcs:
        for p in f.params:
            p.ty = on_tr(p.ty)
        f.ret = on_tr(f.ret)
        scope_ex = _scoped_on_ex(f.params, f.body.stmts, rmap)
        _walk_stmts(f.body.stmts, on_tr, scope_ex)
    for c in classes:
        for fd in c.fields:
            fd.ty = on_tr(fd.ty)
        for m in c.methods:
            for p in m.params:
                p.ty = on_tr(p.ty)
            m.ret = on_tr(m.ret)
            scope_ex = _scoped_on_ex(m.params, m.body.stmts, rmap)
            _walk_stmts(m.body.stmts, on_tr, scope_ex)
    for st in (structs or []):
        for fd in st.fields:
            fd.ty = on_tr(fd.ty)
        for m in st.methods:
            for p in m.params:
                p.ty = on_tr(p.ty)
            m.ret = on_tr(m.ret)
            scope_ex = _scoped_on_ex(m.params, m.body.stmts, rmap)
            _walk_stmts(m.body.stmts, on_tr, scope_ex)
    for iface in ifaces:
        for ms in iface.method_sigs:
            for p in ms.params:
                p.ty = on_tr(p.ty)
            ms.ret = on_tr(ms.ret)


# --------------- Module-internal renaming (flat name map) ---------------

def _rename_type_str(name, rmap):
    """Rename type names in a type string. Handles nested generics and comma-separated params recursively."""
    # Handle comma-separated types (e.g. "str,InterfaceInfo" in Dict[K,V])
    if "," in name:
        # Depth-aware split on commas
        parts = []
        depth = 0
        start = 0
        for i, ch in enumerate(name):
            if ch in "[(":
                depth += 1
            elif ch in "])":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append(name[start:i])
                start = i + 1
        parts.append(name[start:])
        if len(parts) > 1:
            return ",".join(_rename_type_str(p, rmap) for p in parts)
    if "[" not in name:
        return rmap.get(name, name)
    br = name.index("[")
    outer, inner = name[:br], name[br+1:-1]
    renamed_inner = _rename_type_str(inner, rmap)
    return f"{outer}[{renamed_inner}]"


def _rename_typeref(tr, rmap):
    """Rename type names using a dict map. Handles nested generics."""
    name = tr.name
    new_name = _rename_type_str(name, rmap)
    if new_name != name:
        return TypeRef(loc=tr.loc, name=new_name)
    return tr


def _rename_expr(e, rmap):
    """Rename EVar names using a dict map. Recursive."""
    if isinstance(e, EVar):
        e.name = rmap.get(e.name, e.name)
        return e
    if isinstance(e, ECall):
        e.callee = _rename_expr(e.callee, rmap)
        e.args = [_rename_expr(a, rmap) for a in e.args]
        if e.type_param:
            e.type_param = _rename_type_str(e.type_param, rmap)
        return e
    if isinstance(e, EMemberAccess):
        e.obj = _rename_expr(e.obj, rmap)
        return e
    if isinstance(e, EIndex):
        e.obj = _rename_expr(e.obj, rmap)
        e.index = _rename_expr(e.index, rmap)
        return e
    if isinstance(e, EBinary):
        e.lhs = _rename_expr(e.lhs, rmap)
        e.rhs = _rename_expr(e.rhs, rmap)
        return e
    if isinstance(e, EUnary):
        e.rhs = _rename_expr(e.rhs, rmap)
        return e
    if isinstance(e, EIs):
        e.expr = _rename_expr(e.expr, rmap)
        return e
    if isinstance(e, EAs):
        e.expr = _rename_expr(e.expr, rmap)
        return e
    if isinstance(e, EListLit):
        e.elems = [_rename_expr(el, rmap) for el in e.elems]
        return e
    if isinstance(e, EDictLit):
        e.keys = [_rename_expr(k, rmap) for k in e.keys]
        e.vals = [_rename_expr(v, rmap) for v in e.vals]
        return e
    if isinstance(e, ETuple):
        e.elems = [_rename_expr(el, rmap) for el in e.elems]
        return e
    return e


# --------------- Dotted-reference resolution (mod.X → mod__X) ---------------

def _collect_local_names(params, stmts):
    """Collect all parameter and local variable names in a function scope."""
    names = {p.name for p in params}
    _collect_stmt_names(stmts, names)
    return names


def _collect_stmt_names(stmts, names):
    """Recursively collect variable names declared in statements."""
    for st in stmts:
        if isinstance(st, SVarDecl):
            names.add(st.name)
        elif isinstance(st, SFor):
            names.add(st.var_name)
            _collect_stmt_names(st.body.stmts, names)
        elif isinstance(st, STupleDestructure):
            for n in st.names:
                names.add(n)
        elif isinstance(st, SIf):
            for arm in st.arms:
                _collect_stmt_names(arm.block.stmts, names)
        elif isinstance(st, SWhile):
            _collect_stmt_names(st.body.stmts, names)


def _resolve_dotted_name(name, aliases):
    """Convert 'alias.X' → 'alias__X' if alias is a known module."""
    if "." in name:
        alias, rest = name.split(".", 1)
        if alias in aliases:
            return f"{alias}__{rest}"
    return name


def _resolve_typeref(tr, aliases):
    """Resolve dotted type names: 'mod.Type' → 'mod__Type'."""
    name = tr.name
    if "[" in name:
        br = name.index("[")
        outer, inner = name[:br], name[br+1:-1]
        new_name = f"{outer}[{_resolve_dotted_name(inner, aliases)}]"
    else:
        new_name = _resolve_dotted_name(name, aliases)
    if new_name != name:
        return TypeRef(loc=tr.loc, name=new_name)
    return tr


def _resolve_expr(e, aliases):
    """Resolve mod.X expressions to mod__X. Recursive."""
    if isinstance(e, EMemberAccess):
        e.obj = _resolve_expr(e.obj, aliases)
        if isinstance(e.obj, EVar) and e.obj.name in aliases:
            return EVar(loc=e.loc, name=f"{e.obj.name}__{e.member}")
        return e
    if isinstance(e, ECall):
        e.callee = _resolve_expr(e.callee, aliases)
        e.args = [_resolve_expr(a, aliases) for a in e.args]
        return e
    if isinstance(e, EIndex):
        e.obj = _resolve_expr(e.obj, aliases)
        e.index = _resolve_expr(e.index, aliases)
        return e
    if isinstance(e, EBinary):
        e.lhs = _resolve_expr(e.lhs, aliases)
        e.rhs = _resolve_expr(e.rhs, aliases)
        return e
    if isinstance(e, EUnary):
        e.rhs = _resolve_expr(e.rhs, aliases)
        return e
    if isinstance(e, EIs):
        e.expr = _resolve_expr(e.expr, aliases)
        return e
    if isinstance(e, EAs):
        e.expr = _resolve_expr(e.expr, aliases)
        return e
    if isinstance(e, EListLit):
        e.elems = [_resolve_expr(el, aliases) for el in e.elems]
        return e
    if isinstance(e, EDictLit):
        e.keys = [_resolve_expr(k, aliases) for k in e.keys]
        e.vals = [_resolve_expr(v, aliases) for v in e.vals]
        return e
    if isinstance(e, ETuple):
        e.elems = [_resolve_expr(el, aliases) for el in e.elems]
        return e
    return e


def _resolve_decls(funcs, classes, ifaces, aliases, structs=None):
    """Scope-aware dotted-reference resolution for declarations.

    For each function/method body, local variable and parameter names that
    shadow a module alias are excluded from alias resolution. This prevents
    e.g. a parameter named 'ap' from being confused with an import alias 'ap'.
    """
    on_tr = lambda tr: _resolve_typeref(tr, aliases)
    for f in funcs:
        for p in f.params:
            p.ty = on_tr(p.ty)
        f.ret = on_tr(f.ret)
        local_names = _collect_local_names(f.params, f.body.stmts)
        effective = aliases - local_names
        if effective == aliases:
            on_ex_f = lambda e: _resolve_expr(e, aliases)
        else:
            on_ex_f = lambda e, ea=effective: _resolve_expr(e, ea)
        _walk_stmts(f.body.stmts, on_tr, on_ex_f)
    for c in classes:
        for fd in c.fields:
            fd.ty = on_tr(fd.ty)
        for m in c.methods:
            for p in m.params:
                p.ty = on_tr(p.ty)
            m.ret = on_tr(m.ret)
            local_names = _collect_local_names(m.params, m.body.stmts)
            effective = aliases - local_names
            if effective == aliases:
                on_ex_m = lambda e: _resolve_expr(e, aliases)
            else:
                on_ex_m = lambda e, ea=effective: _resolve_expr(e, ea)
            _walk_stmts(m.body.stmts, on_tr, on_ex_m)
    for st in (structs or []):
        for fd in st.fields:
            fd.ty = on_tr(fd.ty)
        for m in st.methods:
            for p in m.params:
                p.ty = on_tr(p.ty)
            m.ret = on_tr(m.ret)
            local_names = _collect_local_names(m.params, m.body.stmts)
            effective = aliases - local_names
            if effective == aliases:
                on_ex_m = lambda e: _resolve_expr(e, aliases)
            else:
                on_ex_m = lambda e, ea=effective: _resolve_expr(e, ea)
            _walk_stmts(m.body.stmts, on_tr, on_ex_m)
    for iface in ifaces:
        for ms in iface.method_sigs:
            for p in ms.params:
                p.ty = on_tr(p.ty)
            ms.ret = on_tr(ms.ret)


# --------------- Extern resolution ---------------

def _make_dummy_loc(file: str = "<extern>", line: int = 0):
    return SrcLoc(file=file, index=0, line=line, col=1, length=0)


def resolve_externs(prog: Program, src_file: str, compiler_dir: str, target_platform: str | None = None) -> Program:
    """Resolve extern declarations: find libs, parse manifests, inject synthetic decls."""
    module_aliases = set()
    seen_libs = set()  # deduplicate includes for same lib imported with different aliases
    existing_funcs = {f.name for f in prog.funcs}
    existing_classes = {c.name for c in prog.classes}
    existing_consts = {s.name for s in prog.stmts if isinstance(s, SVarDecl)}

    for ext in prog.externs:
        lib_dir = find_lib(ext.name, src_file, compiler_dir)
        if lib_dir is None:
            print(f"{ext.loc.file}:{ext.loc.line}:{ext.loc.col}: extern error: "
                  f"library '{ext.name}' not found", file=sys.stderr)
            sys.exit(1)

        manifest = parse_mutlib(
            os.path.join(lib_dir, f"{ext.name}.mutlib"), ext.name, lib_dir, target_platform=target_platform)

        alias = ext.alias
        loc = _make_dummy_loc()
        manifest_path = os.path.join(lib_dir, f"{ext.name}.mutlib")

        # Create synthetic ClassDecl for each extern type
        for et in manifest.types:
            mangled = f"{alias}__{et.bismut_name}"
            eloc = _make_dummy_loc(file=manifest_path, line=et.line)
            cls = ClassDecl(
                loc=eloc,
                name=mangled,
                fields=[],
                methods=[],
                doc=et.doc,
            )
            if mangled not in existing_classes:
                prog.classes.insert(0, cls)
                existing_classes.add(mangled)
            prog.extern_type_info[mangled] = (et.c_type, et.c_dtor)

        # Build set of extern type bismut names (unmangled) for this lib,
        # so function param/return types referencing them get mangled too
        lib_type_names = {et.bismut_name for et in manifest.types}

        # Create synthetic FuncDecl for each extern function
        for ef in manifest.funcs:
            eloc = _make_dummy_loc(file=manifest_path, line=ef.line)
            params = [Param(loc=eloc, name=pn, ty=TypeRef(loc=eloc, name=pt))
                      for pn, pt in ef.params]
            ret_name = ef.ret_type
            fd = FuncDecl(
                loc=eloc,
                name=f"{alias}__{ef.bismut_name}",
                params=params,
                ret=TypeRef(loc=eloc, name=ret_name),
                body=SBlock(loc=eloc, stmts=[]),
                extern_c_name=ef.c_name,
                doc=ef.doc,
            )
            # Mangle type references within param/return that refer to lib's own types
            for p in fd.params:
                if p.ty.name in lib_type_names:
                    p.ty = TypeRef(loc=loc, name=f"{alias}__{p.ty.name}")
            if fd.ret.name in lib_type_names:
                fd.ret = TypeRef(loc=loc, name=f"{alias}__{fd.ret.name}")
            if fd.name not in existing_funcs:
                prog.funcs.insert(0, fd)
                existing_funcs.add(fd.name)

        # Create synthetic const SVarDecl for each extern constant
        _DUMMY_VALUES = {
            "i8": EInt, "i16": EInt, "i32": EInt, "i64": EInt,
            "u8": EInt, "u16": EInt, "u32": EInt, "u64": EInt,
            "f32": EFloat, "f64": EFloat,
            "bool": EBool, "str": EString,
        }
        for ec in manifest.consts:
            mangled = f"{alias}__{ec.bismut_name}"
            # Create a dummy value expression for the typechecker
            expr_cls = _DUMMY_VALUES.get(ec.ty)
            if expr_cls == EInt:
                dummy_val = EInt(loc=loc, value=0)
            elif expr_cls == EFloat:
                dummy_val = EFloat(loc=loc, value=0.0)
            elif expr_cls == EBool:
                dummy_val = EBool(loc=loc, value=False)
            elif expr_cls == EString:
                dummy_val = EString(loc=loc, raw='""')
            else:
                dummy_val = EInt(loc=loc, value=0)
            decl = SVarDecl(
                loc=loc,
                name=mangled,
                ty=TypeRef(loc=loc, name=ec.ty),
                value=dummy_val,
                is_const=True,
            )
            if mangled not in existing_consts:
                prog.stmts.insert(0, decl)
                existing_consts.add(mangled)
            prog.extern_constants[mangled] = (ec.c_expr, ec.ty)

        # Register C source (deduplicated by lib name and existing includes)
        if ext.name not in seen_libs:
            if manifest.c_source and manifest.c_source not in prog.extern_includes:
                prog.extern_includes.append(manifest.c_source)
            prog.extern_cflags.extend(manifest.cflags)
            prog.extern_ldflags.extend(manifest.ldflags)
            seen_libs.add(ext.name)

        module_aliases.add(alias)

    # Rewrite main program's dotted references for extern aliases (same as imports)
    if module_aliases:
        on_tr = lambda tr: _resolve_typeref(tr, module_aliases)
        on_ex = lambda e: _resolve_expr(e, module_aliases)
        _resolve_decls(prog.funcs, prog.classes, prog.interfaces, module_aliases, structs=prog.structs)
        _walk_stmts(prog.stmts, on_tr, on_ex)

    return prog


# --------------- Import resolution ---------------

def resolve_imports(prog: Program, base_dir: str, loading: set, compiler_dir: str, extra_defines: set[str] | None = None, target_platform: str | None = None) -> Program:
    """Resolve imports: parse modules, mangle names with alias__ prefix, merge, rewrite refs."""
    module_aliases = set()

    for imp in prog.imports:
        rel = imp.module.replace(".", os.sep) + ".mut"
        mod_path = os.path.normpath(os.path.join(base_dir, rel))

        # Fallback: look in <compiler_dir>/modules/
        if not os.path.isfile(mod_path):
            mod_path = os.path.normpath(os.path.join(compiler_dir, "modules", rel))

        # Fallback: look in <compiler_dir>/src/
        if not os.path.isfile(mod_path):
            mod_path = os.path.normpath(os.path.join(compiler_dir, "src", rel))

        if not os.path.isfile(mod_path):
            local_path = os.path.normpath(os.path.join(base_dir, rel))
            modules_path = os.path.normpath(os.path.join(compiler_dir, "modules", rel))
            src_path = os.path.normpath(os.path.join(compiler_dir, "src", rel))
            print(f"{imp.loc.file}:{imp.loc.line}:{imp.loc.col}: import error: "
                  f"module '{imp.module}' not found\n"
                  f"  looked in: {local_path}\n"
                  f"             {modules_path}\n"
                  f"             {src_path}",
                  file=sys.stderr)
            sys.exit(1)

        abs_path = os.path.abspath(mod_path)
        if abs_path in loading:
            print(f"{imp.loc.file}:{imp.loc.line}:{imp.loc.col}: import error: "
                  f"circular import of '{imp.module}'", file=sys.stderr)
            sys.exit(1)

        loading.add(abs_path)
        mod = parse_file(mod_path, extra_defines=extra_defines)
        mod = resolve_imports(mod, os.path.dirname(mod_path), loading, compiler_dir, extra_defines=extra_defines, target_platform=target_platform)
        mod = resolve_externs(mod, mod_path, compiler_dir, target_platform=target_platform)
        loading.discard(abs_path)

        alias = imp.alias

        # Collect names introduced by extern resolution (already mangled, must not re-mangle)
        extern_names = set()
        for f in mod.funcs:
            if f.extern_c_name is not None:
                extern_names.add(f.name)
        for c in mod.classes:
            if c.name in mod.extern_type_info:
                extern_names.add(c.name)
        for st in mod.stmts:
            if isinstance(st, SVarDecl) and st.name in mod.extern_constants:
                extern_names.add(st.name)

        # Collect all top-level names from the module (excluding extern names)
        local_names = set()
        for f in mod.funcs:
            if f.name not in extern_names and '__' not in f.name:
                local_names.add(f.name)
        for c in mod.classes:
            if c.name not in extern_names and '__' not in c.name:
                local_names.add(c.name)
        for st in mod.structs:
            if '__' not in st.name:
                local_names.add(st.name)
        for iface in mod.interfaces:
            if '__' not in iface.name:
                local_names.add(iface.name)
        for enum in mod.enums:
            if '__' not in enum.name:
                local_names.add(enum.name)
        for st in mod.stmts:
            if isinstance(st, SVarDecl) and st.name not in extern_names and '__' not in st.name:
                local_names.add(st.name)

        # Build rename map: original → mangled
        rmap = {name: f"{alias}__{name}" for name in local_names}

        # Rename declaration names
        for f in mod.funcs:
            f.name = rmap.get(f.name, f.name)
        for c in mod.classes:
            c.name = rmap.get(c.name, c.name)
            c.implements = [rmap.get(i, i) for i in c.implements]
        for st in mod.structs:
            st.name = rmap.get(st.name, st.name)
        for iface in mod.interfaces:
            iface.name = rmap.get(iface.name, iface.name)
        for enum in mod.enums:
            enum.name = rmap.get(enum.name, enum.name)
        for st in mod.stmts:
            if isinstance(st, SVarDecl):
                st.name = rmap.get(st.name, st.name)

        # Rename all type refs and expressions within module declarations
        on_tr = lambda tr, r=rmap: _rename_typeref(tr, r)
        on_ex = lambda e, r=rmap: _rename_expr(e, r)
        _walk_decls(mod.funcs, mod.classes, mod.interfaces, on_tr, on_ex, structs=mod.structs, rmap=rmap)
        _walk_stmts(mod.stmts, on_tr, on_ex)

        # Merge into main program, deduplicating extern decls that may appear
        # via multiple import paths (e.g. both A and B import the same extern lib)
        existing_func_names = {f.name for f in prog.funcs}
        existing_class_names = {c.name for c in prog.classes}
        existing_const_names = {s.name for s in prog.stmts if isinstance(s, SVarDecl)}
        for f in mod.funcs:
            if f.name in existing_func_names:
                continue
            prog.funcs.insert(0, f)
            existing_func_names.add(f.name)
        for c in mod.classes:
            if c.name in existing_class_names:
                continue
            prog.classes.insert(0, c)
            existing_class_names.add(c.name)
        for s in mod.stmts:
            if isinstance(s, SVarDecl) and s.name in existing_const_names:
                continue
            prog.stmts.insert(0, s)
            if isinstance(s, SVarDecl):
                existing_const_names.add(s.name)
        existing_struct_names = {s.name for s in prog.structs}
        for s in mod.structs:
            if s.name not in existing_struct_names:
                prog.structs.insert(0, s)
                existing_struct_names.add(s.name)
        existing_iface_names = {i.name for i in prog.interfaces}
        for i in mod.interfaces:
            if i.name not in existing_iface_names:
                prog.interfaces.insert(0, i)
                existing_iface_names.add(i.name)
        existing_enum_names = {e.name for e in prog.enums}
        for e in mod.enums:
            if e.name not in existing_enum_names:
                prog.enums.insert(0, e)
                existing_enum_names.add(e.name)

        # Merge extern artifacts from module
        for inc in mod.extern_includes:
            if inc not in prog.extern_includes:
                prog.extern_includes.append(inc)
        for fl in mod.extern_cflags:
            if fl not in prog.extern_cflags:
                prog.extern_cflags.append(fl)
        for fl in mod.extern_ldflags:
            if fl not in prog.extern_ldflags:
                prog.extern_ldflags.append(fl)
        prog.extern_type_info.update(mod.extern_type_info)
        prog.extern_constants.update(mod.extern_constants)

        module_aliases.add(alias)

    # Rewrite main program's dotted references: mod.X → mod__X
    if module_aliases:
        on_tr = lambda tr: _resolve_typeref(tr, module_aliases)
        on_ex = lambda e: _resolve_expr(e, module_aliases)
        _resolve_decls(prog.funcs, prog.classes, prog.interfaces, module_aliases, structs=prog.structs)
        _walk_stmts(prog.stmts, on_tr, on_ex)

    return prog
