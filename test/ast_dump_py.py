#!/usr/bin/env python3
"""
Dump the Python parser's AST in the same text format as mut_parse.dump_ast().
Used to compare AST outputs between the two parsers.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lexer import Lexer, Token
from parser import (
    Parser, Program, FuncDecl, ClassDecl, StructDecl, InterfaceDecl,
    EnumDecl, EnumVariant, MethodSig, FieldDecl, Param, TypeRef,
    ImportDecl, ExternDecl,
    Expr, EInt, EFloat, EString, EChar, EBool, ENone, EVar,
    EUnary, EBinary, ECall, EMemberAccess, EIs, EAs, EIndex, ETuple,
    EListLit, EDictLit,
    Stmt, SVarDecl, STupleDestructure, SAssign, SMemberAssign, SIndexAssign,
    SExpr, SReturn, SBreak, SContinue, SBlock, IfArm, SIf, SWhile, SFor,
)
from preprocess import preprocess

# Map EInt id -> raw lexeme (to preserve hex/binary/octal format)
_int_raw: dict = {}


def _best_loc(st):
    """Get the best source location for a statement (SExpr.loc is buggy — points to newline after)."""
    if isinstance(st, SExpr):
        return st.expr.loc
    if isinstance(st, SVarDecl):
        return st.loc
    if isinstance(st, STupleDestructure):
        return st.loc
    return st.loc


def dump_type(tr: TypeRef, indent: int):
    """Dump a TypeRef as the equivalent mut_parse node."""
    pfx = "  " * indent
    name = tr.name
    if name.startswith("List["):
        print(f"{pfx}TYPE_LIST({name})")
    elif name.startswith("Dict["):
        print(f"{pfx}TYPE_DICT({name})")
    elif name.startswith("Fn("):
        print(f"{pfx}TYPE_FN({name})")
    elif name.startswith("(") and "," in name:
        # Tuple type: (i64,str) -> TYPE_TUPLE with TYPE children
        print(f"{pfx}TYPE_TUPLE(()")
        # Parse the inner type names
        inner = name[1:-1]  # strip parens
        parts = _split_tuple_types(inner)
        for p in parts:
            dump_type(TypeRef(loc=tr.loc, name=p), indent + 1)
    else:
        print(f"{pfx}TYPE({name})")


def _split_tuple_types(s: str) -> list:
    """Split comma-separated type names, respecting nested parens/brackets."""
    parts = []
    depth = 0
    cur = ""
    for c in s:
        if c in ("(", "["):
            depth += 1
            cur += c
        elif c in (")", "]"):
            depth -= 1
            cur += c
        elif c == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += c
    if cur:
        parts.append(cur)
    return parts


def dump_expr(e: Expr, indent: int):
    pfx = "  " * indent
    if isinstance(e, EInt):
        print(f"{pfx}INT_LIT({e.value})")
    elif isinstance(e, EFloat):
        # Match mut_parse: uses the raw literal text.
        # Python parser stores float, so format it.
        val = e.value
        # Use repr-like formatting but strip trailing zeros carefully
        s = repr(val)
        print(f"{pfx}FLOAT_LIT({s})")
    elif isinstance(e, EString):
        print(f"{pfx}STRING_LIT({e.raw})")
    elif isinstance(e, EChar):
        print(f"{pfx}CHAR_LIT({e.raw})")
    elif isinstance(e, EBool):
        print(f"{pfx}BOOL_LIT({e.value})")
    elif isinstance(e, ENone):
        print(f"{pfx}NONE_LIT(None)")
    elif isinstance(e, EVar):
        print(f"{pfx}IDENT({e.name})")
    elif isinstance(e, EBinary):
        print(f"{pfx}BINARY({e.op})")
        dump_expr(e.lhs, indent + 1)
        dump_expr(e.rhs, indent + 1)
    elif isinstance(e, EUnary):
        print(f"{pfx}UNARY({e.op})")
        dump_expr(e.rhs, indent + 1)
    elif isinstance(e, ECall):
        tp = e.type_param or ""
        if tp:
            print(f"{pfx}CALL({tp})")
        else:
            print(f"{pfx}CALL")
        dump_expr(e.callee, indent + 1)
        for arg in e.args:
            dump_expr(arg, indent + 1)
    elif isinstance(e, EIndex):
        print(f"{pfx}INDEX")
        dump_expr(e.obj, indent + 1)
        dump_expr(e.index, indent + 1)
    elif isinstance(e, EMemberAccess):
        print(f"{pfx}MEMBER({e.member})")
        dump_expr(e.obj, indent + 1)
    elif isinstance(e, EIs):
        print(f"{pfx}IS({e.type_name})")
        dump_expr(e.expr, indent + 1)
    elif isinstance(e, EAs):
        print(f"{pfx}AS({e.type_name})")
        dump_expr(e.expr, indent + 1)
    elif isinstance(e, ETuple):
        print(f"{pfx}TUPLE_EXPR(()")
        for el in e.elems:
            dump_expr(el, indent + 1)
    elif isinstance(e, EListLit):
        print(f"{pfx}LIST_LIT({e.elem_type})")
        for el in e.elems:
            dump_expr(el, indent + 1)
    elif isinstance(e, EDictLit):
        print(f"{pfx}DICT_LIT({e.val_type})")
        for k, v in zip(e.keys, e.vals):
            dump_expr(k, indent + 1)
            dump_expr(v, indent + 1)
    else:
        print(f"{pfx}???({type(e).__name__})")


def dump_stmt(st: Stmt, indent: int):
    pfx = "  " * indent
    if isinstance(st, SVarDecl):
        if st.is_const:
            kind = "CONST_DECL"
        elif st.is_static:
            kind = "STATIC_DECL"
        else:
            kind = "VAR_DECL"
        print(f"{pfx}{kind}({st.name})")
        if st.ty is not None:
            dump_type(st.ty, indent + 1)
        dump_expr(st.value, indent + 1)
    elif isinstance(st, STupleDestructure):
        print(f"{pfx}TUPLE_DESTRUCT")
        for n in st.names:
            print(f"{'  ' * (indent+1)}IDENT({n})")
        dump_expr(st.value, indent + 1)
    elif isinstance(st, SAssign):
        print(f"{pfx}ASSIGN({st.op})")
        print(f"{'  ' * (indent+1)}IDENT({st.name})")
        dump_expr(st.value, indent + 1)
    elif isinstance(st, SMemberAssign):
        print(f"{pfx}MEMBER_ASSIGN({st.op})")
        # SMemberAssign stores obj+member separately; mut_parse stores as MEMBER child
        print(f"{'  ' * (indent+1)}MEMBER({st.member})")
        dump_expr(st.obj, indent + 2)
        dump_expr(st.value, indent + 1)
    elif isinstance(st, SIndexAssign):
        print(f"{pfx}INDEX_ASSIGN({st.op})")
        dump_expr(st.obj, indent + 1)
        dump_expr(st.index, indent + 1)
        dump_expr(st.value, indent + 1)
    elif isinstance(st, SExpr):
        print(f"{pfx}EXPR_STMT")
        dump_expr(st.expr, indent + 1)
    elif isinstance(st, SReturn):
        print(f"{pfx}RETURN")
        if st.value is not None:
            dump_expr(st.value, indent + 1)
    elif isinstance(st, SBreak):
        print(f"{pfx}BREAK(break)")
    elif isinstance(st, SContinue):
        print(f"{pfx}CONTINUE(continue)")
    elif isinstance(st, SIf):
        print(f"{pfx}IF")
        for arm in st.arms:
            dump_if_arm(arm, indent + 1)
    elif isinstance(st, SWhile):
        print(f"{pfx}WHILE")
        dump_expr(st.cond, indent + 1)
        dump_block(st.body, indent + 1)
    elif isinstance(st, SFor):
        print(f"{pfx}FOR({st.var_name})")
        dump_type(st.var_ty, indent + 1)
        dump_expr(st.iterable, indent + 1)
        dump_block(st.body, indent + 1)
    else:
        print(f"{pfx}???({type(st).__name__})")


def dump_if_arm(arm: IfArm, indent: int):
    pfx = "  " * indent
    if arm.cond is None:
        print(f"{pfx}IF_ARM(else)")
        dump_block(arm.block, indent + 1)
    else:
        # First arm is "if", rest are "elif"
        # We need to track this — caller should pass label
        # For now, check: if this is first in the parent's list, use "if", else "elif"
        # We'll use a hack: dump_if_arm_labeled
        pass


def dump_if_labeled(sif: SIf, indent: int):
    """Dump SIf with correct if/elif/else labels."""
    pfx = "  " * indent
    print(f"{pfx}IF")
    for i, arm in enumerate(sif.arms):
        apfx = "  " * (indent + 1)
        if arm.cond is None:
            print(f"{apfx}IF_ARM(else)")
            dump_block(arm.block, indent + 2)
        else:
            label = "if" if i == 0 else "elif"
            print(f"{apfx}IF_ARM({label})")
            dump_expr(arm.cond, indent + 2)
            dump_block(arm.block, indent + 2)


def dump_block(block: SBlock, indent: int):
    pfx = "  " * indent
    print(f"{pfx}BLOCK")
    for st in block.stmts:
        dump_stmt(st, indent + 1)


def dump_param(p: Param, indent: int):
    pfx = "  " * indent
    print(f"{pfx}PARAM({p.name})")
    dump_type(p.ty, indent + 1)


def dump_func(f: FuncDecl, indent: int):
    pfx = "  " * indent
    print(f"{pfx}FUNC_DECL({f.name})")
    # Type params
    for tp in f.type_params:
        print(f"{'  ' * (indent+1)}TYPE_PARAM({tp})")
    # Params block
    ppfx = "  " * (indent + 1)
    print(f"{ppfx}BLOCK(params)")
    for p in f.params:
        dump_param(p, indent + 2)
    # Return type
    dump_type(f.ret, indent + 1)
    # Body
    dump_block(f.body, indent + 1)


def dump_method_sig(m: MethodSig, indent: int):
    pfx = "  " * indent
    print(f"{pfx}METHOD_SIG({m.name})")
    ppfx = "  " * (indent + 1)
    print(f"{ppfx}BLOCK(params)")
    for p in m.params:
        dump_param(p, indent + 2)
    dump_type(m.ret, indent + 1)


def dump_field(f: FieldDecl, indent: int):
    pfx = "  " * indent
    print(f"{pfx}FIELD_DECL({f.name})")
    dump_type(f.ty, indent + 1)


def dump_class(c: ClassDecl, indent: int):
    pfx = "  " * indent
    print(f"{pfx}CLASS_DECL({c.name})")
    # Interface types first (in mut_parse they appear as TYPE children)
    for iname in c.implements:
        print(f"{'  ' * (indent+1)}TYPE({iname})")
    for f in c.fields:
        dump_field(f, indent + 1)
    for m in c.methods:
        dump_func(m, indent + 1)


def dump_struct(s: StructDecl, indent: int):
    pfx = "  " * indent
    print(f"{pfx}STRUCT_DECL({s.name})")
    for f in s.fields:
        dump_field(f, indent + 1)
    for m in s.methods:
        dump_func(m, indent + 1)


def dump_interface(iface: InterfaceDecl, indent: int):
    pfx = "  " * indent
    print(f"{pfx}INTERFACE_DECL({iface.name})")
    for m in iface.method_sigs:
        dump_method_sig(m, indent + 1)


def dump_enum(en: EnumDecl, indent: int):
    pfx = "  " * indent
    print(f"{pfx}ENUM_DECL({en.name})")
    for v in en.variants:
        vpfx = "  " * (indent + 1)
        if v.value is not None:
            print(f"{vpfx}ENUM_VARIANT({v.value})")
        else:
            print(f"{vpfx}ENUM_VARIANT({v.name})")


def dump_program(prog: Program, filename: str):
    print(f"PROGRAM({filename})")
    # Externs and imports in source order (by line)
    ei_items = []
    for e in prog.externs:
        ei_items.append((e.loc.line, e.loc.col, 'extern', e))
    for imp in prog.imports:
        ei_items.append((imp.loc.line, imp.loc.col, 'import', imp))
    ei_items.sort(key=lambda x: (x[0], x[1]))
    for _, _, kind, item in ei_items:
        pfx = "  "
        if kind == 'extern':
            print(f"{pfx}EXTERN({item.name})")
            print(f"{pfx}  IDENT({item.alias})")
        else:
            print(f"{pfx}IMPORT({item.module})")
            print(f"{pfx}  IDENT({item.alias})")
    # Declarations and statements — interleaved in source order
    # Python parser separates them; we need to reconstruct source order
    # Collect all with their source locations
    items = []
    for f in prog.funcs:
        if f.extern_c_name is not None:
            continue  # skip extern-synthesized funcs
        items.append((f.loc.line, f.loc.col, 'func', f))
    for c in prog.classes:
        items.append((c.loc.line, c.loc.col, 'class', c))
    for s in prog.structs:
        items.append((s.loc.line, s.loc.col, 'struct', s))
    for i in prog.interfaces:
        items.append((i.loc.line, i.loc.col, 'iface', i))
    for e in prog.enums:
        items.append((e.loc.line, e.loc.col, 'enum', e))
    for st in prog.stmts:
        loc = _best_loc(st)
        items.append((loc.line, loc.col, 'stmt', st))
    items.sort(key=lambda x: (x[0], x[1]))
    for _, _, kind, item in items:
        if kind == 'func':
            dump_func(item, 1)
        elif kind == 'class':
            dump_class(item, 1)
        elif kind == 'struct':
            dump_struct(item, 1)
        elif kind == 'iface':
            dump_interface(item, 1)
        elif kind == 'enum':
            dump_enum(item, 1)
        elif kind == 'stmt':
            dump_stmt(item, 1)


# Override dump_stmt to use dump_if_labeled for SIf
_orig_dump_stmt = dump_stmt
def dump_stmt(st: Stmt, indent: int):
    if isinstance(st, SIf):
        dump_if_labeled(st, indent)
    else:
        _orig_dump_stmt(st, indent)


def _populate_int_raw(node, int_lits_by_pos):
    """Walk the AST and set _int_raw[id(eint)] for each EInt from token lexemes."""
    if isinstance(node, EInt):
        raw = int_lits_by_pos.get((node.loc.line, node.loc.col))
        if raw:
            _int_raw[id(node)] = raw
        return
    # Walk all fields
    if isinstance(node, Program):
        for f in node.funcs:
            _populate_int_raw(f, int_lits_by_pos)
        for c in node.classes:
            _populate_int_raw(c, int_lits_by_pos)
        for s in node.structs:
            _populate_int_raw(s, int_lits_by_pos)
        for i in node.interfaces:
            _populate_int_raw(i, int_lits_by_pos)
        for e in node.enums:
            _populate_int_raw(e, int_lits_by_pos)
        for st in node.stmts:
            _populate_int_raw(st, int_lits_by_pos)
        return
    if isinstance(node, FuncDecl):
        for p in node.params:
            _populate_int_raw(p, int_lits_by_pos)
        _populate_int_raw(node.body, int_lits_by_pos)
        return
    if isinstance(node, ClassDecl):
        for f in node.fields:
            _populate_int_raw(f, int_lits_by_pos)
        for m in node.methods:
            _populate_int_raw(m, int_lits_by_pos)
        return
    if isinstance(node, StructDecl):
        for f in node.fields:
            _populate_int_raw(f, int_lits_by_pos)
        for m in node.methods:
            _populate_int_raw(m, int_lits_by_pos)
        return
    if isinstance(node, SBlock):
        for st in node.stmts:
            _populate_int_raw(st, int_lits_by_pos)
        return
    if isinstance(node, SVarDecl):
        _populate_int_raw(node.value, int_lits_by_pos)
        return
    if isinstance(node, STupleDestructure):
        _populate_int_raw(node.value, int_lits_by_pos)
        return
    if isinstance(node, SAssign):
        _populate_int_raw(node.value, int_lits_by_pos)
        return
    if isinstance(node, SMemberAssign):
        _populate_int_raw(node.obj, int_lits_by_pos)
        _populate_int_raw(node.value, int_lits_by_pos)
        return
    if isinstance(node, SIndexAssign):
        _populate_int_raw(node.obj, int_lits_by_pos)
        _populate_int_raw(node.index, int_lits_by_pos)
        _populate_int_raw(node.value, int_lits_by_pos)
        return
    if isinstance(node, SExpr):
        _populate_int_raw(node.expr, int_lits_by_pos)
        return
    if isinstance(node, SReturn):
        if node.value:
            _populate_int_raw(node.value, int_lits_by_pos)
        return
    if isinstance(node, SIf):
        for arm in node.arms:
            if arm.cond:
                _populate_int_raw(arm.cond, int_lits_by_pos)
            _populate_int_raw(arm.block, int_lits_by_pos)
        return
    if isinstance(node, SWhile):
        _populate_int_raw(node.cond, int_lits_by_pos)
        _populate_int_raw(node.body, int_lits_by_pos)
        return
    if isinstance(node, SFor):
        _populate_int_raw(node.iterable, int_lits_by_pos)
        _populate_int_raw(node.body, int_lits_by_pos)
        return
    if isinstance(node, EBinary):
        _populate_int_raw(node.lhs, int_lits_by_pos)
        _populate_int_raw(node.rhs, int_lits_by_pos)
        return
    if isinstance(node, EUnary):
        _populate_int_raw(node.rhs, int_lits_by_pos)
        return
    if isinstance(node, ECall):
        _populate_int_raw(node.callee, int_lits_by_pos)
        for a in node.args:
            _populate_int_raw(a, int_lits_by_pos)
        return
    if isinstance(node, EIndex):
        _populate_int_raw(node.obj, int_lits_by_pos)
        _populate_int_raw(node.index, int_lits_by_pos)
        return
    if isinstance(node, EMemberAccess):
        _populate_int_raw(node.obj, int_lits_by_pos)
        return
    if isinstance(node, EIs):
        _populate_int_raw(node.expr, int_lits_by_pos)
        return
    if isinstance(node, EAs):
        _populate_int_raw(node.expr, int_lits_by_pos)
        return
    if isinstance(node, ETuple):
        for el in node.elems:
            _populate_int_raw(el, int_lits_by_pos)
        return
    if isinstance(node, EListLit):
        for el in node.elems:
            _populate_int_raw(el, int_lits_by_pos)
        return
    if isinstance(node, EDictLit):
        for k in node.keys:
            _populate_int_raw(k, int_lits_by_pos)
        for v in node.vals:
            _populate_int_raw(v, int_lits_by_pos)
        return
    if isinstance(node, EnumDecl):
        return  # variants don't contain EInt nodes
    # Ignore other node types (Param, FieldDecl, etc.)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test/ast_dump_py.py <file.mut>", file=sys.stderr)
        sys.exit(1)
    path = sys.argv[1]
    src = open(path, encoding="utf-8").read()
    src = preprocess(src, file=path)
    toks = Lexer(src, file=path).tokenize()
    # Build a mapping from (line, col) -> raw lexeme for integer literals
    int_lits_by_pos = {}
    for t in toks:
        if t.kind == "INT" and t.lexeme:
            int_lits_by_pos[(t.loc.line, t.loc.col)] = t.lexeme
    prog = Parser(toks).parse_program()
    # Walk the AST to populate _int_raw for all EInt nodes
    _populate_int_raw(prog, int_lits_by_pos)
    dump_program(prog, path)


if __name__ == "__main__":
    main()
