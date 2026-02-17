from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

from lexer import Token, SrcLoc


# -------------------------
# Helpers
# -------------------------

def _split_dict_tp(tp: str):
    """Split 'K,V' type param into (key_type, val_type), handling nested types."""
    depth = 0
    for i, ch in enumerate(tp):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "," and depth == 0:
            return tp[:i], tp[i+1:]
    raise ValueError(f"invalid dict type params: {tp}")


# -------------------------
# Errors
# -------------------------

class ParseError(Exception):
    def __init__(self, tok: Token, msg: str):
        self.tok = tok
        self.msg = msg
        super().__init__(self.__str__())

    def __str__(self) -> str:
        loc = self.tok.loc
        where = f"{loc.file}:{loc.line}:{loc.col}"
        return f"{where}: parse error: {self.msg} (got {self.tok.kind} {self.tok.lexeme!r})"


# -------------------------
# AST Types
# -------------------------

@dataclass(frozen=True)
class TypeRef:
    loc: SrcLoc
    name: str  # e.g. "i64", "f64", "bool", "str", "ListI64", "DictStrI64"


# -------------------------
# AST Expressions
# -------------------------

@dataclass
class Expr:
    loc: SrcLoc

@dataclass
class EInt(Expr):
    value: int

@dataclass
class EFloat(Expr):
    value: float

@dataclass
class EString(Expr):
    raw: str  # includes quotes; unescape later

@dataclass
class EChar(Expr):
    raw: str  # includes quotes; unescape later

@dataclass
class EBool(Expr):
    value: bool

@dataclass
class ENone(Expr):
    pass

@dataclass
class EVar(Expr):
    name: str

@dataclass
class EUnary(Expr):
    op: str
    rhs: Expr

@dataclass
class EBinary(Expr):
    op: str
    lhs: Expr
    rhs: Expr

@dataclass
class ECall(Expr):
    callee: Expr
    args: List[Expr]
    type_param: Optional[str] = None

@dataclass
class EMemberAccess(Expr):
    obj: Expr
    member: str

@dataclass
class EIs(Expr):
    expr: Expr
    type_name: str  # RHS type name (e.g. "i64", "Circle", "Shape")

@dataclass
class EAs(Expr):
    expr: Expr
    type_name: str  # target type name for downcast (e.g. "Circle")

@dataclass
class EIndex(Expr):
    obj: Expr
    index: Expr

@dataclass
class ETuple(Expr):
    elems: List[Expr]

@dataclass
class EListLit(Expr):
    """List[T]() {elem1, elem2, ...} — list constructor with initializer."""
    elem_type: str              # e.g. "i64", "str"
    elems: List[Expr]

@dataclass
class EDictLit(Expr):
    """Dict[K,V]() {key: val, ...} — dict constructor with initializer."""
    key_type: str               # e.g. "str", "i64"
    val_type: str               # e.g. "i64", "str"
    keys: List[Expr]            # key expressions
    vals: List[Expr]            # value expressions


# -------------------------
# AST Statements / Decls
# -------------------------

@dataclass
class Stmt:
    loc: SrcLoc

@dataclass
class SVarDecl(Stmt):
    name: str
    ty: Optional[TypeRef]   # None for := shorthand (type inferred)
    value: Expr
    is_const: bool = False
    is_static: bool = False

@dataclass
class STupleDestructure(Stmt):
    names: List[str]
    value: Expr

@dataclass
class SAssign(Stmt):
    name: str
    op: str   # "=", "+=", ...
    value: Expr

@dataclass
class SMemberAssign(Stmt):
    obj: Expr
    member: str
    op: str   # "=", "+=", ...
    value: Expr

@dataclass
class SIndexAssign(Stmt):
    obj: Expr
    index: Expr
    op: str   # "=" only for now
    value: Expr

@dataclass
class SExpr(Stmt):
    expr: Expr

@dataclass
class SReturn(Stmt):
    value: Optional[Expr]

@dataclass
class SBreak(Stmt):
    pass

@dataclass
class SContinue(Stmt):
    pass

@dataclass
class SBlock(Stmt):
    stmts: List[Stmt]

@dataclass
class IfArm:
    loc: SrcLoc
    cond: Optional[Expr]   # None for else
    block: SBlock

@dataclass
class SIf(Stmt):
    arms: List[IfArm]      # if + elif* + optional else

@dataclass
class SWhile(Stmt):
    cond: Expr
    body: SBlock

@dataclass
class SFor(Stmt):
    var_name: str
    var_ty: TypeRef     # explicit element type annotation
    iterable: Expr     # any expression that evaluates to a list type
    body: SBlock

@dataclass
class Param:
    loc: SrcLoc
    name: str
    ty: TypeRef

@dataclass
class FuncDecl:
    loc: SrcLoc
    name: str
    params: List[Param]
    ret: TypeRef
    body: SBlock
    type_params: List[str] = field(default_factory=list)  # e.g. ["T"] for def foo[T](...)
    extern_c_name: Optional[str] = None  # C function name for extern libs (no body emitted)
    doc: str = ""  # doc comment text (consecutive # comments above declaration)

@dataclass
class MethodSig:
    loc: SrcLoc
    name: str
    params: List[Param]     # includes self
    ret: TypeRef

@dataclass
class InterfaceDecl:
    loc: SrcLoc
    name: str
    method_sigs: List[MethodSig]
    doc: str = ""

@dataclass
class FieldDecl:
    loc: SrcLoc
    name: str
    ty: TypeRef

@dataclass
class ClassDecl:
    loc: SrcLoc
    name: str
    fields: List[FieldDecl]
    methods: List[FuncDecl]  # includes init
    implements: List[str] = field(default_factory=list)  # interface names
    doc: str = ""

@dataclass
class StructDecl:
    loc: SrcLoc
    name: str
    fields: List[FieldDecl]
    methods: List[FuncDecl]
    doc: str = ""

@dataclass
class ImportDecl:
    loc: SrcLoc
    module: str  # e.g. "shapes" or "lib.shapes" (dots become path separators)
    alias: str   # e.g. "shapes" (default: last segment of module path)

@dataclass
class ExternDecl:
    loc: SrcLoc
    name: str   # library name, e.g. "pxmath"
    alias: str  # alias for qualified access, e.g. "math"

@dataclass
class EnumVariant:
    loc: SrcLoc
    name: str
    value: Optional[int]  # None = auto-increment

@dataclass
class EnumDecl:
    loc: SrcLoc
    name: str
    variants: List[EnumVariant]
    doc: str = ""

@dataclass
class Program:
    loc: SrcLoc
    funcs: List[FuncDecl]
    classes: List[ClassDecl]
    structs: List[StructDecl]
    interfaces: List[InterfaceDecl]
    enums: List[EnumDecl]
    imports: List[ImportDecl]
    externs: List[ExternDecl]
    stmts: List[Stmt]  # allow top-level statements for scripts
    extern_includes: List[str] = field(default_factory=list)  # abs paths to C source files
    extern_cflags: List[str] = field(default_factory=list)
    extern_ldflags: List[str] = field(default_factory=list)
    extern_type_info: dict = field(default_factory=dict)  # mangled_name -> (c_type, c_dtor)
    extern_constants: dict = field(default_factory=dict)  # mangled_name -> (c_expr, bismut_type)


# -------------------------
# Pratt precedence
# -------------------------

PREC = {
    "KW_OR": 1,
    "KW_AND": 2,
    "|": 3,
    "^": 4,
    "&": 5,
    "==": 6, "!=": 6,
    "<": 7, "<=": 7, ">": 7, ">=": 7,
    "<<": 8, ">>": 8,
    "+": 9, "-": 9,
    "*": 10, "/": 10, "%": 10,
}

UNARY_OPS = {"KW_NOT", "-", "~"}

ASSIGN_OPS = {"=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="}

STMT_END_KINDS = {";", "NEWLINE"}


# -------------------------
# Parser
# -------------------------

class Parser:
    _BUILTIN_GENERICS = {"List", "Dict", "append", "get", "set", "put", "lookup", "has", "keys", "identity"}

    def __init__(self, tokens: List[Token], comments: Optional[List[tuple]] = None):
        self.toks = tokens
        self.i = 0
        self._comments = comments or []  # [(line, text), ...] from lexer
        if not self.toks or self.toks[-1].kind != "EOF":
            raise ValueError("Token stream must end with EOF")
        self.generic_names = self._prescan_generic_names()

    def _get_doc(self, decl_line: int) -> str:
        """Find consecutive comment lines ending at decl_line - 1."""
        if not self._comments:
            return ""
        target = decl_line - 1
        lines = []
        for line, text in reversed(self._comments):
            if line == target:
                lines.append(text)
                target -= 1
            elif line < target:
                break
        if not lines:
            return ""
        lines.reverse()
        return "\n".join(lines)

    def _prescan_generic_names(self) -> set:
        """Scan tokens for `def IDENT [` patterns to find user-defined generic functions."""
        names = set(self._BUILTIN_GENERICS)
        for j in range(len(self.toks) - 2):
            if (self.toks[j].kind == "KW_DEF"
                    and self.toks[j + 1].kind == "IDENT"
                    and self.toks[j + 2].kind == "["):
                names.add(self.toks[j + 1].lexeme)
        return names

    # ---- token helpers ----

    def peek(self, k: int = 0) -> Token:
        j = self.i + k
        if j < len(self.toks):
            return self.toks[j]
        return self.toks[-1]

    def at_end(self) -> bool:
        return self.peek().kind == "EOF"

    def advance(self) -> Token:
        t = self.peek()
        if not self.at_end():
            self.i += 1
        return t

    def match(self, *kinds: str) -> Optional[Token]:
        if self.peek().kind in kinds:
            return self.advance()
        return None

    def expect(self, kind: str, msg: str) -> Token:
        t = self.peek()
        if t.kind != kind:
            raise ParseError(t, msg)
        return self.advance()

    def expect_ident(self, msg: str = "expected identifier") -> Token:
        t = self.peek()
        if t.kind != "IDENT":
            raise ParseError(t, msg)
        return self.advance()

    def skip_newlines(self) -> None:
        while self.peek().kind == "NEWLINE":
            self.advance()

    def expect_stmt_end(self, msg: str = "expected end of statement") -> None:
        # accept one or more NEWLINEs or a single ';' then optional NEWLINEs
        if self.match(";"):
            self.skip_newlines()
            return
        if self.match("NEWLINE"):
            self.skip_newlines()
            return
        raise ParseError(self.peek(), msg)

    def loc_span(self, a: SrcLoc, b: SrcLoc) -> SrcLoc:
        # best-effort span; uses a.file and index range
        length = max(0, b.index - a.index)
        return SrcLoc(a.file, a.index, a.line, a.col, length)

    # -------------------------
    # Top-level
    # -------------------------

    def parse_program(self) -> Program:
        start = self.peek().loc
        funcs: List[FuncDecl] = []
        classes: List[ClassDecl] = []
        structs: List[StructDecl] = []
        interfaces: List[InterfaceDecl] = []
        enums: List[EnumDecl] = []
        imports: List[ImportDecl] = []
        externs: List[ExternDecl] = []
        stmts: List[Stmt] = []

        self.skip_newlines()

        # Imports and externs must come first
        while not self.at_end() and self.peek().kind in ("KW_IMPORT", "KW_EXTERN"):
            if self.peek().kind == "KW_IMPORT":
                imports.append(self.parse_import())
            else:
                externs.append(self.parse_extern())
            self.skip_newlines()

        while not self.at_end():
            if self.peek().kind == "KW_DEF":
                funcs.append(self.parse_func_decl())
            elif self.peek().kind == "KW_CLASS":
                classes.append(self.parse_class_decl())
            elif self.peek().kind == "KW_STRUCT":
                structs.append(self.parse_struct_decl())
            elif self.peek().kind == "KW_INTERFACE":
                interfaces.append(self.parse_interface_decl())
            elif self.peek().kind == "KW_ENUM":
                enums.append(self.parse_enum_decl())
            else:
                stmts.append(self.parse_stmt())
            self.skip_newlines()

        end = self.peek().loc
        return Program(loc=self.loc_span(start, end), funcs=funcs, classes=classes,
                       structs=structs,
                       interfaces=interfaces, enums=enums, imports=imports,
                       externs=externs, stmts=stmts)

    def parse_import(self) -> ImportDecl:
        """Parse: import module.path [as alias]"""
        kw = self.expect("KW_IMPORT", "expected 'import'")

        # Module path: ident ('.' ident)*
        mod_tok = self.expect_ident("expected module name")
        module = mod_tok.lexeme
        while self.match("."):
            part = self.expect_ident("expected module name after '.'")
            module += "." + part.lexeme

        # Default alias is last segment of module path
        alias = module.rsplit(".", 1)[-1]
        if self.peek().kind == "KW_AS":
            self.advance()
            alias_tok = self.expect_ident("expected alias after 'as'")
            alias = alias_tok.lexeme

        self.expect_stmt_end()
        return ImportDecl(loc=kw.loc, module=module, alias=alias)

    def parse_extern(self) -> ExternDecl:
        """Parse: extern libname [as alias]"""
        kw = self.expect("KW_EXTERN", "expected 'extern'")
        name_tok = self.expect_ident("expected library name")
        alias = name_tok.lexeme
        if self.peek().kind == "KW_AS":
            self.advance()
            alias_tok = self.expect_ident("expected alias after 'as'")
            alias = alias_tok.lexeme
        self.expect_stmt_end()
        return ExternDecl(loc=kw.loc, name=name_tok.lexeme, alias=alias)

    def parse_enum_decl(self) -> EnumDecl:
        """Parse: enum Name\\n  VAR1, VAR2 = N, VAR3\\nend"""
        kw = self.expect("KW_ENUM", "expected 'enum'")
        name_tok = self.expect_ident("expected enum name")
        self.skip_newlines()

        variants: List[EnumVariant] = []
        while self.peek().kind != "KW_END":
            vtok = self.expect_ident("expected enum variant name")
            val: Optional[int] = None
            if self.match("="):
                sign = 1
                if self.peek().kind == "-":
                    self.advance()
                    sign = -1
                num_tok = self.expect("INT", "expected integer value for enum variant")
                val = sign * int(num_tok.lexeme)
            variants.append(EnumVariant(loc=vtok.loc, name=vtok.lexeme, value=val))
            if not self.match(","):
                self.skip_newlines()

        self.expect("KW_END", "expected 'end' to close enum")
        self.skip_newlines()
        return EnumDecl(loc=kw.loc, name=name_tok.lexeme, variants=variants,
                        doc=self._get_doc(kw.loc.line))

    def parse_func_decl(self) -> FuncDecl:
        kw = self.expect("KW_DEF", "expected 'def'")
        name_tok = self.expect_ident("expected function name")

        # Optional type parameters: def name[T, U](...)
        type_params: List[str] = []
        if self.peek().kind == "[":
            self.advance()  # consume '['
            while True:
                tp = self.expect_ident("expected type parameter name")
                type_params.append(tp.lexeme)
                if self.match(","):
                    continue
                break
            self.expect("]", "expected ']' to close type parameters")

        self.expect("(", "expected '(' after function name")

        params: List[Param] = []
        if self.peek().kind != ")":
            while True:
                p = self.parse_param()
                params.append(p)
                if self.match(","):
                    continue
                break
        self.expect(")", "expected ')' after parameters")

        # -> type is optional; omitting it means void
        if self.match("->"):
            ret = self.parse_type_ref()
        else:
            ret = TypeRef(loc=kw.loc, name="void")

        # require statement end after signature: NEWLINE or ';'
        self.expect_stmt_end("expected newline or ';' after function signature")

        body = self.parse_block_until({"KW_END"})
        self.expect("KW_END", "expected 'end' to close function")
        self.expect_stmt_end("expected statement end after 'end'")

        return FuncDecl(loc=kw.loc, name=name_tok.lexeme, params=params, ret=ret, body=body,
                        type_params=type_params, doc=self._get_doc(kw.loc.line))

    def parse_class_decl(self) -> ClassDecl:
        """
        class ClassName
            field1: Type
            field2: Type

            def init(self, p1: Type, p2: Type)
                self.field1 = p1
            end

            def method(self, ...) -> RetType
                ...
            end
        end
        """
        kw = self.expect("KW_CLASS", "expected 'class'")
        name_tok = self.expect_ident("expected class name")

        # Optional implements clause: class Foo: IBar, IBaz
        # Also accepts dotted names: class Foo: mod.IBar
        implements: List[str] = []
        if self.peek().kind == ":":
            self.advance()  # consume ':'
            while True:
                iface = self.expect_ident("expected interface name")
                iname = iface.lexeme
                if self.peek().kind == ".":
                    self.advance()  # consume '.'
                    member = self.expect_ident("expected interface name after '.'")
                    iname = iname + "__" + member.lexeme
                implements.append(iname)
                if not self.match(","):
                    break

        self.expect_stmt_end("expected newline after class header")

        fields: List[FieldDecl] = []
        methods: List[FuncDecl] = []

        self.skip_newlines()
        while not self.at_end() and self.peek().kind != "KW_END":
            if self.peek().kind == "KW_DEF":
                methods.append(self.parse_func_decl())
            elif self.peek().kind == "IDENT" and self.peek(1).kind == ":":
                # field declaration: name: Type
                fname = self.advance()
                self.expect(":", "expected ':'")
                fty = self.parse_type_ref()
                self.expect_stmt_end("expected newline after field declaration")
                fields.append(FieldDecl(loc=fname.loc, name=fname.lexeme, ty=fty))
            else:
                raise ParseError(self.peek(), "expected field declaration or method def in class")
            self.skip_newlines()

        self.expect("KW_END", "expected 'end' to close class")
        self.expect_stmt_end("expected statement end after class 'end'")
        return ClassDecl(loc=kw.loc, name=name_tok.lexeme, fields=fields, methods=methods,
                         implements=implements, doc=self._get_doc(kw.loc.line))

    def parse_struct_decl(self) -> StructDecl:
        """
        struct Name
            x: i64
            y: f64

            def method(self, ...) -> RetType
                ...
            end
        end
        """
        kw = self.expect("KW_STRUCT", "expected 'struct'")
        name_tok = self.expect_ident("expected struct name")
        self.expect_stmt_end("expected newline after struct header")

        fields: List[FieldDecl] = []
        methods: List[FuncDecl] = []

        self.skip_newlines()
        while not self.at_end() and self.peek().kind != "KW_END":
            if self.peek().kind == "KW_DEF":
                methods.append(self.parse_func_decl())
            elif self.peek().kind == "IDENT" and self.peek(1).kind == ":":
                fname = self.advance()
                self.expect(":", "expected ':'")
                fty = self.parse_type_ref()
                self.expect_stmt_end("expected newline after field declaration")
                fields.append(FieldDecl(loc=fname.loc, name=fname.lexeme, ty=fty))
            else:
                raise ParseError(self.peek(), "expected field declaration or method def in struct")
            self.skip_newlines()

        self.expect("KW_END", "expected 'end' to close struct")
        self.expect_stmt_end("expected statement end after struct 'end'")
        return StructDecl(loc=kw.loc, name=name_tok.lexeme, fields=fields, methods=methods,
                          doc=self._get_doc(kw.loc.line))

    def parse_interface_decl(self) -> InterfaceDecl:
        """
        interface IName
            def method(self, p1: Type) -> RetType
            def other(self) -> i64
        end
        """
        kw = self.expect("KW_INTERFACE", "expected 'interface'")
        name_tok = self.expect_ident("expected interface name")
        self.expect_stmt_end("expected newline after interface name")

        method_sigs: List[MethodSig] = []

        self.skip_newlines()
        while not self.at_end() and self.peek().kind != "KW_END":
            if self.peek().kind == "KW_DEF":
                method_sigs.append(self._parse_method_sig())
            else:
                raise ParseError(self.peek(), "expected method signature in interface")
            self.skip_newlines()

        self.expect("KW_END", "expected 'end' to close interface")
        self.expect_stmt_end("expected statement end after interface 'end'")
        return InterfaceDecl(loc=kw.loc, name=name_tok.lexeme, method_sigs=method_sigs,
                              doc=self._get_doc(kw.loc.line))

    def _parse_method_sig(self) -> MethodSig:
        """Parse a method signature (no body): def name(self, params) -> RetType"""
        kw = self.expect("KW_DEF", "expected 'def'")
        name_tok = self.expect_ident("expected method name")
        self.expect("(", "expected '(' after method name")

        params: List[Param] = []
        if self.peek().kind != ")":
            while True:
                p = self.parse_param()
                params.append(p)
                if self.match(","):
                    continue
                break
        self.expect(")", "expected ')' after parameters")

        if self.match("->"):
            ret = self.parse_type_ref()
        else:
            ret = TypeRef(loc=kw.loc, name="void")

        self.expect_stmt_end("expected newline after method signature")
        return MethodSig(loc=kw.loc, name=name_tok.lexeme, params=params, ret=ret)

    def parse_param(self) -> Param:
        name = self.expect_ident("expected parameter name")
        # 'self' doesn't need a type annotation
        if name.lexeme == "self":
            return Param(loc=name.loc, name="self", ty=TypeRef(loc=name.loc, name="Self"))
        self.expect(":", "expected ':' after parameter name")
        ty = self.parse_type_ref()
        return Param(loc=name.loc, name=name.lexeme, ty=ty)

    def parse_type_ref(self) -> TypeRef:
        # Tuple type: (T1, T2, T3)
        if self.peek().kind == "(":
            return self._parse_tuple_type()
        t = self.expect_ident("expected type name")
        name = t.lexeme
        # Fn(T1, T2) -> R  function pointer type
        if name == "Fn" and self.peek().kind == "(":
            self.advance()  # consume '('
            param_names: list[str] = []
            if self.peek().kind != ")":
                pt = self.parse_type_ref()
                param_names.append(pt.name)
                while self.peek().kind == ",":
                    self.advance()  # consume ','
                    pt = self.parse_type_ref()
                    param_names.append(pt.name)
            self.expect(")", "expected ')' to close Fn parameter types")
            ret_name = "void"
            if self.peek().kind == "->":
                self.advance()  # consume '->'
                ret_ref = self.parse_type_ref()
                ret_name = ret_ref.name
            encoded = f"Fn({','.join(param_names)})->{ret_name}"
            return TypeRef(loc=t.loc, name=encoded)
        # Dotted type: module.Type (e.g. shapes.Circle)
        if self.peek().kind == "." and self.peek(1).kind == "IDENT":
            self.advance()  # consume '.'
            member = self.expect_ident("expected type name after '.'")
            name = name + "__" + member.lexeme
        # List[X] or Dict[K,V] generic syntax
        if name == "List" and self.peek().kind == "[":
            self.expect("[", "expected '[' after List")
            inner = self.parse_type_ref()
            self.expect("]", "expected ']' to close generic type")
            return TypeRef(loc=t.loc, name=f"List[{inner.name}]")
        if name == "Dict" and self.peek().kind == "[":
            self.expect("[", "expected '[' after Dict")
            key_ref = self.parse_type_ref()
            self.expect(",", "expected ',' between Dict key and value types")
            val_ref = self.parse_type_ref()
            self.expect("]", "expected ']' to close generic type")
            return TypeRef(loc=t.loc, name=f"Dict[{key_ref.name},{val_ref.name}]")
        return TypeRef(loc=t.loc, name=name)

    def _parse_tuple_type(self) -> TypeRef:
        """Parse tuple type: (T1, T2, T3)"""
        lparen = self.expect("(", "expected '(' for tuple type")
        types = [self.parse_type_ref()]
        while self.match(","):
            types.append(self.parse_type_ref())
        self.expect(")", "expected ')' to close tuple type")
        if len(types) < 2:
            raise ParseError(lparen, "tuple type must have at least 2 elements")
        name = "(" + ",".join(t.name for t in types) + ")"
        return TypeRef(loc=lparen.loc, name=name)

    # -------------------------
    # Statements
    # -------------------------

    def parse_stmt(self) -> Stmt:
        k = self.peek().kind

        if k == "KW_IF":
            return self.parse_if()

        if k == "KW_WHILE":
            return self.parse_while()

        if k == "KW_FOR":
            return self.parse_for()

        if k == "KW_RETURN":
            return self.parse_return()

        if k == "KW_BREAK":
            t = self.advance()
            self.expect_stmt_end("expected end of statement after 'break'")
            return SBreak(loc=t.loc)

        if k == "KW_CONTINUE":
            t = self.advance()
            self.expect_stmt_end("expected end of statement after 'continue'")
            return SContinue(loc=t.loc)

        if k == "KW_DEF":
            raise ParseError(self.peek(), "function declarations are only allowed at top level")

        # tuple destructuring: IDENT, IDENT [, IDENT...] := expr
        if k == "IDENT" and self.peek(1).kind == ",":
            return self.parse_tuple_destructure()

        # const declaration: const NAME: TYPE = expr
        if k == "KW_CONST":
            self.advance()  # consume 'const'
            decl = self.parse_var_decl()
            decl.is_const = True
            return decl

        # static declaration: static NAME: TYPE = expr
        if k == "KW_STATIC":
            self.advance()  # consume 'static'
            decl = self.parse_var_decl()
            decl.is_static = True
            return decl

        # walrus-style declaration: IDENT := expr (type inferred)
        if k == "IDENT" and self.peek(1).kind == ":=":
            return self.parse_walrus_decl()

        # typed variable declaration:
        # IDENT ":" TYPE "=" expr
        if k == "IDENT" and self.peek(1).kind == ":":
            return self.parse_var_decl()

        # member assignment: IDENT.IDENT op expr  (incl self.field = ...)
        if k == "IDENT" and self.peek(1).kind == "." and self.peek(2).kind == "IDENT" and self.peek(3).kind in ASSIGN_OPS:
            return self.parse_member_assign()

        # assignment:
        # IDENT ( = | += ... ) expr
        if k == "IDENT" and self.peek(1).kind in ASSIGN_OPS:
            return self.parse_assign()

        # expression statement (or subscript/member assignment)
        expr = self.parse_expr()

        # subscript assignment: expr[idx] = value
        if isinstance(expr, EIndex) and self.peek().kind in ASSIGN_OPS:
            op = self.advance()
            val = self.parse_expr()
            self.expect_stmt_end("expected end of statement after subscript assignment")
            return SIndexAssign(loc=op.loc, obj=expr.obj, index=expr.index, op=op.kind, value=val)

        # chained member assignment: expr.member op value  (e.g. a.b.c = 10)
        if isinstance(expr, EMemberAccess) and self.peek().kind in ASSIGN_OPS:
            op = self.advance()
            val = self.parse_expr()
            self.expect_stmt_end("expected end of statement after member assignment")
            return SMemberAssign(loc=op.loc, obj=expr.obj, member=expr.member, op=op.kind, value=val)

        self.expect_stmt_end("expected end of statement after expression")
        return SExpr(loc=expr.loc, expr=expr)

    def parse_var_decl(self) -> SVarDecl:
        name = self.expect_ident("expected variable name")
        self.expect(":", "expected ':' in variable declaration")
        ty = self.parse_type_ref()
        self.expect("=", "expected '=' in variable declaration")
        val = self.parse_expr()
        self.expect_stmt_end("expected end of statement after variable declaration")
        return SVarDecl(loc=name.loc, name=name.lexeme, ty=ty, value=val)

    def parse_walrus_decl(self) -> SVarDecl:
        """Parse: IDENT := expr  (type inferred from RHS)"""
        name = self.expect_ident("expected variable name")
        self.expect(":=", "expected ':='")
        val = self.parse_expr()
        self.expect_stmt_end("expected end of statement after := declaration")
        return SVarDecl(loc=name.loc, name=name.lexeme, ty=None, value=val)

    def parse_tuple_destructure(self) -> 'STupleDestructure':
        """Parse: name1, name2 [, name3 ...] := expr"""
        first = self.expect_ident("expected variable name")
        names = [first.lexeme]
        while self.match(","):
            name = self.expect_ident("expected variable name in destructuring")
            names.append(name.lexeme)
        self.expect(":=", "expected ':=' in tuple destructuring")
        val = self.parse_expr()
        self.expect_stmt_end("expected end of statement after tuple destructuring")
        if len(names) < 2:
            raise ParseError(first, "tuple destructuring requires at least 2 variables")
        return STupleDestructure(loc=first.loc, names=names, value=val)

    def parse_assign(self) -> SAssign:
        name = self.expect_ident("expected variable name")
        op = self.advance()  # =, +=, ...
        if op.kind not in ASSIGN_OPS:
            raise ParseError(op, "expected assignment operator")
        val = self.parse_expr()
        self.expect_stmt_end("expected end of statement after assignment")
        return SAssign(loc=op.loc, name=name.lexeme, op=op.kind, value=val)

    def parse_member_assign(self) -> SMemberAssign:
        obj_tok = self.expect_ident("expected object name")
        self.expect(".", "expected '.'")
        member_tok = self.expect_ident("expected member name")
        op = self.advance()
        if op.kind not in ASSIGN_OPS:
            raise ParseError(op, "expected assignment operator")
        val = self.parse_expr()
        self.expect_stmt_end("expected end of statement after member assignment")
        obj_expr = EVar(loc=obj_tok.loc, name=obj_tok.lexeme)
        return SMemberAssign(loc=op.loc, obj=obj_expr, member=member_tok.lexeme, op=op.kind, value=val)

    def parse_return(self) -> SReturn:
        kw = self.expect("KW_RETURN", "expected 'return'")
        # return; or return NEWLINE
        if self.peek().kind in STMT_END_KINDS:
            self.expect_stmt_end("expected end of statement after return")
            return SReturn(loc=kw.loc, value=None)
        v = self.parse_expr()
        self.expect_stmt_end("expected end of statement after return value")
        return SReturn(loc=kw.loc, value=v)

    def parse_if(self) -> SIf:
        kw_if = self.expect("KW_IF", "expected 'if'")
        cond = self.parse_expr()
        self.expect_stmt_end("expected end of statement after if condition")

        arms: List[IfArm] = []
        then_block = self.parse_block_until({"KW_ELIF", "KW_ELSE", "KW_END"})
        arms.append(IfArm(loc=kw_if.loc, cond=cond, block=then_block))

        while self.peek().kind == "KW_ELIF":
            kw_elif = self.advance()
            c = self.parse_expr()
            self.expect_stmt_end("expected end of statement after elif condition")
            blk = self.parse_block_until({"KW_ELIF", "KW_ELSE", "KW_END"})
            arms.append(IfArm(loc=kw_elif.loc, cond=c, block=blk))

        if self.peek().kind == "KW_ELSE":
            kw_else = self.advance()
            self.expect_stmt_end("expected end of statement after else")
            blk = self.parse_block_until({"KW_END"})
            arms.append(IfArm(loc=kw_else.loc, cond=None, block=blk))

        self.expect("KW_END", "expected 'end' to close if")
        self.expect_stmt_end("expected statement end after 'end'")
        return SIf(loc=kw_if.loc, arms=arms)

    def parse_while(self) -> SWhile:
        kw = self.expect("KW_WHILE", "expected 'while'")
        cond = self.parse_expr()
        self.expect_stmt_end("expected end of statement after while condition")
        body = self.parse_block_until({"KW_END"})
        self.expect("KW_END", "expected 'end' to close while")
        self.expect_stmt_end("expected statement end after 'end'")
        return SWhile(loc=kw.loc, cond=cond, body=body)

    def parse_for(self) -> SFor:
        """Parse: for IDENT:TYPE in EXPR ... end
        EXPR is typically range(...), keys(...), or a list variable."""
        kw = self.expect("KW_FOR", "expected 'for'")
        var_tok = self.expect_ident("expected loop variable name")
        self.expect(":", "expected ':' after loop variable name")
        var_ty = self.parse_type_ref()
        self.expect("KW_IN", "expected 'in' after loop variable type")
        iterable = self.parse_expr()
        self.expect_stmt_end("expected end of statement after for header")
        body = self.parse_block_until({"KW_END"})
        self.expect("KW_END", "expected 'end' to close for")
        self.expect_stmt_end("expected statement end after 'end'")
        return SFor(loc=kw.loc, var_name=var_tok.lexeme, var_ty=var_ty, iterable=iterable, body=body)

    def parse_block_until(self, end_kinds: set[str]) -> SBlock:
        """
        Parse statements until next token is in end_kinds (e.g. KW_END/KW_ELIF/KW_ELSE).
        Consumes leading NEWLINEs.
        """
        start = self.peek().loc
        stmts: List[Stmt] = []
        self.skip_newlines()
        while not self.at_end() and self.peek().kind not in end_kinds:
            stmts.append(self.parse_stmt())
            self.skip_newlines()
        end = self.peek().loc
        return SBlock(loc=self.loc_span(start, end), stmts=stmts)

    # -------------------------
    # Expressions (Pratt)
    # -------------------------

    def parse_expr(self) -> Expr:
        return self._parse_expr_bp(0)

    def _parse_expr_bp(self, min_bp: int) -> Expr:
        t = self.advance()
        left = self._nud(t)

        while True:
            t2 = self.peek()

            # member access: expr.ident
            if t2.kind == ".":
                dot = self.advance()
                member = self.expect_ident("expected member name after '.'")
                left = EMemberAccess(loc=dot.loc, obj=left, member=member.lexeme)
                continue

            # '[' — either generic call ident[Type](...) or subscript expr[expr]
            if t2.kind == "[":
                if isinstance(left, EVar) and left.name in self.generic_names:
                    # generic call: ident[Type](...) or ident[K,V](...)
                    self.advance()  # consume '['
                    inner = self.parse_type_ref()
                    # Check for second type param (Dict[K, V] style)
                    if self.peek().kind == ",":
                        self.advance()  # consume ','
                        inner2 = self.parse_type_ref()
                        self.expect("]", "expected ']' to close type parameters")
                        type_param = f"{inner.name},{inner2.name}"
                    else:
                        self.expect("]", "expected ']' to close type parameter")
                        type_param = inner.name
                    left = self._parse_call(left, type_param=type_param)
                    # Check for collection literal: List[T]() {...} or Dict[K,V]() {...}
                    left = self._maybe_collection_lit(left)
                    continue
                else:
                    # subscript: expr[expr]
                    bracket = self.advance()  # consume '['
                    index_expr = self._parse_expr_bp(0)
                    self.expect("]", "expected ']' to close subscript")
                    left = EIndex(loc=bracket.loc, obj=left, index=index_expr)
                    continue

            # call: expr(...)
            if t2.kind == "(":
                left = self._parse_call(left)
                continue

            # 'is' type check: expr is TypeName  (or expr is None)
            if t2.kind == "KW_IS":
                is_prec = 7  # same as comparison operators
                if is_prec < min_bp:
                    break
                is_tok = self.advance()  # consume 'is'
                if self.peek().kind == "KW_NONE":
                    none_tok = self.advance()
                    left = EIs(loc=is_tok.loc, expr=left, type_name="None")
                else:
                    ty = self.parse_type_ref()
                    left = EIs(loc=is_tok.loc, expr=left, type_name=ty.name)
                continue

            # 'as' downcast: expr as ClassName
            if t2.kind == "KW_AS":
                as_prec = 7  # same as comparison operators
                if as_prec < min_bp:
                    break
                as_tok = self.advance()  # consume 'as'
                ty = self.parse_type_ref()
                left = EAs(loc=as_tok.loc, expr=left, type_name=ty.name)
                continue

            # binary ops
            if t2.kind in PREC:
                prec = PREC[t2.kind]
                lbp = prec
                rbp = prec + 1  # left associative
                if lbp < min_bp:
                    break
                op_tok = self.advance()
                rhs = self._parse_expr_bp(rbp)
                left = EBinary(loc=op_tok.loc, op=op_tok.lexeme, lhs=left, rhs=rhs)
                continue

            break

        return left

    def _nud(self, t: Token) -> Expr:
        k = t.kind

        if k == "INT":
            try:
                lex = t.lexeme.replace("_", "")
                v = int(lex, 0)
            except ValueError:
                raise ParseError(t, "invalid integer literal")
            return EInt(loc=t.loc, value=v)

        if k == "FLOAT":
            try:
                v = float(t.lexeme)
            except ValueError:
                raise ParseError(t, "invalid float literal")
            return EFloat(loc=t.loc, value=v)

        if k == "STRING":
            return EString(loc=t.loc, raw=t.lexeme)

        if k == "CHAR":
            return EChar(loc=t.loc, raw=t.lexeme)

        if k == "KW_TRUE":
            return EBool(loc=t.loc, value=True)

        if k == "KW_FALSE":
            return EBool(loc=t.loc, value=False)

        if k == "KW_NONE":
            return ENone(loc=t.loc)

        if k == "IDENT":
            return EVar(loc=t.loc, name=t.lexeme)

        if k in UNARY_OPS:
            rhs = self._parse_expr_bp(11)
            return EUnary(loc=t.loc, op=t.lexeme, rhs=rhs)

        if k == "(":
            inner = self._parse_expr_bp(0)
            if self.peek().kind == ",":
                # Tuple expression: (a, b, ...)
                elems = [inner]
                while self.match(","):
                    elems.append(self._parse_expr_bp(0))
                self.expect(")", "expected ')' to close tuple expression")
                return ETuple(loc=t.loc, elems=elems)
            self.expect(")", "expected ')' to close parenthesized expression")
            return inner

        raise ParseError(t, "expected expression")

    def _parse_call(self, callee: Expr, type_param: Optional[str] = None) -> Expr:
        lpar = self.expect("(", "expected '(' for call")
        args: List[Expr] = []
        if self.peek().kind != ")":
            while True:
                args.append(self._parse_expr_bp(0))
                if self.match(","):
                    continue
                break
        self.expect(")", "expected ')' after call arguments")
        return ECall(loc=lpar.loc, callee=callee, args=args, type_param=type_param)

    def _maybe_collection_lit(self, call: Expr) -> Expr:
        """If call is List[T]() or Dict[T]() followed by '{', parse a collection literal."""
        if not isinstance(call, ECall):
            return call
        if not isinstance(call.callee, EVar):
            return call
        if call.type_param is None:
            return call
        if len(call.args) != 0:
            return call
        if self.peek().kind != "{":
            return call
        name = call.callee.name
        if name == "List":
            return self._parse_list_lit(call)
        if name == "Dict":
            return self._parse_dict_lit(call)
        return call

    def _parse_list_lit(self, call: ECall) -> EListLit:
        """Parse: List[T]() {elem1, elem2, ...}"""
        self.expect("{", "expected '{' for list literal")
        self.skip_newlines()
        elems: List[Expr] = []
        while self.peek().kind != "}":
            elems.append(self._parse_expr_bp(0))
            if self.match(","):
                self.skip_newlines()
                continue
            self.skip_newlines()
            break
        self.expect("}", "expected '}' to close list literal")
        return EListLit(loc=call.loc, elem_type=call.type_param, elems=elems)

    def _parse_dict_lit(self, call: ECall) -> EDictLit:
        """Parse: Dict[K,V]() {key: val, key2: val2, ...}"""
        tp = call.type_param  # "K,V" joined
        key_type, val_type = _split_dict_tp(tp)
        self.expect("{", "expected '{' for dict literal")
        self.skip_newlines()
        keys: List[Expr] = []
        vals: List[Expr] = []
        while self.peek().kind != "}":
            key = self._parse_expr_bp(0)
            self.expect(":", "expected ':' between dict key and value")
            val = self._parse_expr_bp(0)
            keys.append(key)
            vals.append(val)
            if self.match(","):
                self.skip_newlines()
                continue
            self.skip_newlines()
            break
        self.expect("}", "expected '}' to close dict literal")
        return EDictLit(loc=call.loc, key_type=key_type, val_type=val_type, keys=keys, vals=vals)
