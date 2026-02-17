from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class SrcLoc:
    file: str
    index: int   # 0-based absolute index
    line: int    # 1-based
    col: int     # 1-based
    length: int  # token length

    def at(self) -> str:
        return f"{self.file}:{self.line}:{self.col}"


@dataclass(frozen=True)
class Token:
    kind: str     # "IDENT", "INT", "FLOAT", "STRING", "NEWLINE", "EOF", "KW_DEF", "+=", "->", ...
    lexeme: str
    loc: SrcLoc

    def __repr__(self) -> str:
        return f"Token({self.kind}, {self.lexeme!r}, {self.loc.at()})"


class LexError(Exception):
    def __init__(self, loc: SrcLoc, msg: str, line_text: Optional[str] = None):
        self.loc = loc
        self.msg = msg
        self.line_text = line_text
        super().__init__(self.__str__())

    def __str__(self) -> str:
        s = f"{self.loc.at()}: lex error: {self.msg}"
        if self.line_text is not None:
            caret = " " * max(0, self.loc.col - 1) + "^"
            s += "\n" + self.line_text.rstrip("\n") + "\n" + caret
        return s


KEYWORDS = {
    "def": "KW_DEF",
    "if": "KW_IF",
    "elif": "KW_ELIF",
    "else": "KW_ELSE",
    "while": "KW_WHILE",
    "return": "KW_RETURN",
    "break": "KW_BREAK",
    "continue": "KW_CONTINUE",
    "end": "KW_END",
    "True": "KW_TRUE",
    "False": "KW_FALSE",
    "None": "KW_NONE",
    "class": "KW_CLASS",
    "for": "KW_FOR",
    "in": "KW_IN",
    "interface": "KW_INTERFACE",
    "import": "KW_IMPORT",
    "as": "KW_AS",
    "extern": "KW_EXTERN",
    "enum": "KW_ENUM",
    "const": "KW_CONST",
    "static": "KW_STATIC",
    "is": "KW_IS",
    "struct": "KW_STRUCT",
    "not": "KW_NOT",
    "and": "KW_AND",
    "or": "KW_OR",
}

# longest-first (max munch)
MULTI = [
    "->", ":=",
    "==", "!=", "<=", ">=",
    "<<=", ">>=",
    "<<", ">>",
    "+=", "-=", "*=", "/=", "%=",
    "&=", "|=", "^=",
]

SINGLE = set("()[],;:.=+-*/%<>&|^~{}")

def is_ident_start(ch: str) -> bool:
    return ch.isalpha() or ch == "_"

def is_ident_part(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


class Lexer:
    def __init__(self, source: str, file: str = "<input>"):
        self.src = source
        self.file = file
        self.n = len(source)
        self.i = 0
        self.line = 1
        self.col = 1
        self.comments: List[tuple] = []  # [(line, text), ...] standalone comments

        self._lines = source.splitlines(True)
        self._line_no = 1
        self._line_text = self._lines[0] if self._lines else ""

    def _peek(self, k: int = 0) -> str:
        j = self.i + k
        return self.src[j] if j < self.n else "\0"

    def _advance(self) -> str:
        ch = self._peek(0)
        if ch == "\0":
            return ch
        self.i += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
            self._line_no += 1
            self._line_text = self._lines[self._line_no - 1] if (self._line_no - 1) < len(self._lines) else ""
        else:
            self.col += 1
        return ch

    def _loc_from(self, start_i: int, start_line: int, start_col: int) -> SrcLoc:
        return SrcLoc(self.file, start_i, start_line, start_col, self.i - start_i)

    def _error_here(self, msg: str) -> None:
        loc = SrcLoc(self.file, self.i, self.line, self.col, 1)
        raise LexError(loc, msg, self._line_text)

    def _skip_spaces_and_comments(self) -> Optional[Token]:
        """
        Skips spaces/tabs/CR and comments.
        Returns a NEWLINE token if one or more newlines were consumed, else None.
        Coalesces multiple blank lines to a single NEWLINE token.
        Standalone comments (first non-whitespace on their line) are recorded
        in self.comments as (line, text) for doc-comment extraction.
        """
        saw_nl = False
        while True:
            ch = self._peek(0)

            # spaces/tabs/cr
            if ch in (" ", "\t", "\r"):
                self._advance()
                continue

            # comment: #
            if ch == "#":
                comment_line = self.line
                self._advance()  # skip '#'
                # skip one leading space if present
                if self._peek(0) == " ":
                    self._advance()
                text_start = self.i
                while self._peek(0) not in ("\n", "\0"):
                    self._advance()
                text = self.src[text_start:self.i]
                # Record standalone comments (preceded by newline or at start of file)
                if saw_nl or comment_line == 1:
                    self.comments.append((comment_line, text))
                continue

            # newlines
            if ch == "\n":
                saw_nl = True
                while self._peek(0) == "\n":
                    self._advance()
                continue

            break

        if saw_nl:
            return Token("NEWLINE", "\n", SrcLoc(self.file, self.i, self.line, self.col, 0))
        return None

    def _lex_ident_or_kw(self) -> Token:
        start_i, start_line, start_col = self.i, self.line, self.col
        self._advance()
        while is_ident_part(self._peek(0)):
            self._advance()
        lex = self.src[start_i:self.i]
        kind = KEYWORDS.get(lex, "IDENT")
        return Token(kind, lex, self._loc_from(start_i, start_line, start_col))

    def _lex_number(self) -> Token:
        start_i, start_line, start_col = self.i, self.line, self.col

        # Hex literal: 0x...
        if self._peek(0) == "0" and self._peek(1) in ("x", "X"):
            self._advance()  # '0'
            self._advance()  # 'x'
            if not self._peek(0) in "0123456789abcdefABCDEF":
                self._error_here("expected hex digit after '0x'")
            while self._peek(0) in "0123456789abcdefABCDEF_":
                self._advance()
            lex = self.src[start_i:self.i]
            return Token("INT", lex, self._loc_from(start_i, start_line, start_col))

        # Binary literal: 0b...
        if self._peek(0) == "0" and self._peek(1) in ("b", "B"):
            self._advance()  # '0'
            self._advance()  # 'b'
            if not self._peek(0) in "01":
                self._error_here("expected binary digit after '0b'")
            while self._peek(0) in "01_":
                self._advance()
            lex = self.src[start_i:self.i]
            return Token("INT", lex, self._loc_from(start_i, start_line, start_col))

        while self._peek(0).isdigit():
            self._advance()

        # float: '.' followed by digit
        if self._peek(0) == "." and self._peek(1).isdigit():
            self._advance()
            while self._peek(0).isdigit():
                self._advance()

            # exponent part
            if self._peek(0) in ("e", "E"):
                j = 1
                if self._peek(j) in ("+", "-"):
                    j += 1
                if not self._peek(j).isdigit():
                    self._error_here("malformed float exponent")
                self._advance()
                if self._peek(0) in ("+", "-"):
                    self._advance()
                while self._peek(0).isdigit():
                    self._advance()

            lex = self.src[start_i:self.i]
            return Token("FLOAT", lex, self._loc_from(start_i, start_line, start_col))

        lex = self.src[start_i:self.i]
        return Token("INT", lex, self._loc_from(start_i, start_line, start_col))

    def _lex_string(self) -> Token:
        start_i, start_line, start_col = self.i, self.line, self.col
        quote = self._peek(0)
        assert quote in ("'", '"')

        # Check for triple-quoted string: """ or '''
        if self._peek(1) == quote and self._peek(2) == quote:
            self._advance(); self._advance(); self._advance()  # consume opening triple
            while True:
                ch = self._peek(0)
                if ch == "\0":
                    raise LexError(self._loc_from(start_i, start_line, start_col), "unterminated triple-quoted string", self._line_text)
                if ch == quote and self._peek(1) == quote and self._peek(2) == quote:
                    self._advance(); self._advance(); self._advance()
                    break
                if ch == "\\":
                    self._advance()
                    esc = self._peek(0)
                    if esc in ("n", "t", "r", "\\", '"', "'"):
                        self._advance()
                    else:
                        self._error_here(f"unknown escape '\\{esc}'")
                    continue
                self._advance()
            lex = self.src[start_i:self.i]
            return Token("STRING", lex, self._loc_from(start_i, start_line, start_col))

        # Single char literal: 'x' (single character between single quotes)
        if quote == "'" and self._peek(1) != "'" and self._peek(1) != "\0":
            # Peek ahead to see if this is a char literal: 'x' or '\n' etc.
            save_i, save_line, save_col = self.i, self.line, self.col
            self._advance()  # consume opening '
            ch = self._peek(0)
            if ch == "\\":
                self._advance()
                esc = self._peek(0)
                if esc in ("n", "t", "r", "\\", '"', "'", "0"):
                    self._advance()
                else:
                    # Not a valid char literal, restore and fall through to string
                    self.i, self.line, self.col = save_i, save_line, save_col
                    return self._lex_string_body(start_i, start_line, start_col, quote)
            else:
                self._advance()
            if self._peek(0) == "'":
                self._advance()  # consume closing '
                lex = self.src[start_i:self.i]
                return Token("CHAR", lex, self._loc_from(start_i, start_line, start_col))
            else:
                # Not a char literal (e.g. 'hello'), restore and lex as string
                self.i, self.line, self.col = save_i, save_line, save_col
                return self._lex_string_body(start_i, start_line, start_col, quote)

        return self._lex_string_body(start_i, start_line, start_col, quote)

    def _lex_string_body(self, start_i: int, start_line: int, start_col: int, quote: str) -> Token:
        """Lex a regular (non-triple-quoted) string literal."""
        self._advance()  # consume opening quote

        while True:
            ch = self._peek(0)
            if ch == "\0":
                raise LexError(self._loc_from(start_i, start_line, start_col), "unterminated string literal", self._line_text)
            if ch == "\n":
                raise LexError(self._loc_from(start_i, start_line, start_col), "newline in string literal", self._line_text)
            if ch == quote:
                self._advance()
                break
            if ch == "\\":
                self._advance()
                esc = self._peek(0)
                if esc in ("n", "t", "r", "\\", '"', "'"):
                    self._advance()
                else:
                    self._error_here(f"unknown escape '\\{esc}'")
                continue
            self._advance()

        lex = self.src[start_i:self.i]
        return Token("STRING", lex, self._loc_from(start_i, start_line, start_col))

    def _lex_op_or_punct(self) -> Token:
        start_i, start_line, start_col = self.i, self.line, self.col

        for op in MULTI:
            if self.src.startswith(op, self.i):
                for _ in op:
                    self._advance()
                return Token(op, op, self._loc_from(start_i, start_line, start_col))

        ch = self._peek(0)
        if ch in SINGLE:
            self._advance()
            return Token(ch, ch, self._loc_from(start_i, start_line, start_col))

        self._error_here(f"unexpected character {ch!r}")

    def tokenize(self) -> List[Token]:
        out: List[Token] = []
        paren_depth = 0  # track () [] {} depth — suppress NEWLINEs inside
        while True:
            nl = self._skip_spaces_and_comments()
            if nl is not None and paren_depth == 0:
                out.append(nl)

            if self.i >= self.n:
                out.append(Token("EOF", "", SrcLoc(self.file, self.i, self.line, self.col, 0)))
                return out

            ch = self._peek(0)

            if is_ident_start(ch):
                out.append(self._lex_ident_or_kw())
                continue

            if ch.isdigit():
                out.append(self._lex_number())
                continue

            if ch in ("'", '"'):
                out.append(self._lex_string())
                continue

            tok = self._lex_op_or_punct()
            if tok.kind in ('(', '[', '{'):
                paren_depth += 1
            elif tok.kind in (')', ']', '}'):
                if paren_depth > 0:
                    paren_depth -= 1
            out.append(tok)
