# Bismut — Language Specification (NOT FINAL)

Bismut (`.mut` files) is a statically-typed, Python-like language that compiles
to C99.  The goal is **Python's readability with native C performance** — no
VM, no GC, no runtime overhead, but still memory managed.

Blocks are closed explicitly with `end`.  Indentation has no syntactic meaning.

Build & run:

    python3 tools/reference-compiler/main.py file.mut && gcc -O2 -std=c99 -Irt -o out out.c -lm && ./out

------------------------------------------------------------
1. LEXICAL STRUCTURE
------------------------------------------------------------

1.1 Identifiers

    Pattern: [A-Za-z_][A-Za-z0-9_]*
    Case sensitive.

1.2 Whitespace

    Spaces, tabs, carriage returns are ignored.
    Newlines may terminate statements.

    Implicit line continuation: newlines inside matching pairs of
    (), [], or {} are suppressed by the lexer.  This allows
    function calls, declarations, collection literals, and
    parenthesized expressions to span multiple lines:

        result := add(
            10,
            20,
            30
        )

        nums := List[i64]() {
            1, 2, 3,
            4, 5, 6
        }

        def compute(a: i64,
                    b: i64,
                    c: i64) -> i64
            return a + b + c
        end

1.3 Comments

    # comment

1.4 Literals

    Integers:   0   123   -5 (unary minus)
    Hex:        0xFF   0x1A3F
    Binary:     0b1010   0b11111111

    Floats:     1.0   0.25   1.2e3   1.2E-4

    Strings:    "hello"   'hello'
                Escapes: \n \t \\ \" \'
    Multiline:  """multi
                line"""

    Char:       'A'   '\n'   '\0'
                Produces an i64 value (ASCII code).
                Distinguished from single-char strings by context.

    Booleans:   True   False

    None:       None   (null for reference types)

------------------------------------------------------------
1A. NAMING CONVENTIONS
------------------------------------------------------------

    Functions, variables:   snake_case        add_item, total_count
    Classes:                PascalCase        Point, HttpClient
    Structs:                PascalCase        Vec2, Rect
    Interfaces:             I-prefix          IShape, IDrawable, IVisitor
    Enums:                  PascalCase        Color, Status
    Enum variants:          UPPER_SNAKE       Color.RED, Status.OK
    Constants:              UPPER_SNAKE       MAX_SIZE, PI

Interface names always start with a capital I followed by PascalCase.
This makes it immediately clear at every usage site whether a type
is a concrete class/struct or an abstract interface.

------------------------------------------------------------
2. TYPES
------------------------------------------------------------

2.1 Primitive Types

    i8      signed 8-bit integer
    i16     signed 16-bit integer
    i32     signed 32-bit integer
    i64     signed 64-bit integer
    u8      unsigned 8-bit integer
    u16     unsigned 16-bit integer
    u32     unsigned 32-bit integer
    u64     unsigned 64-bit integer
    f32     IEEE-754 single-precision float
    f64     IEEE-754 double-precision float
    bool    True / False
    str     immutable refcounted string
            String literals ("hello", dict keys, format strings) are
            immortal static objects — zero heap allocation, zero
            refcount overhead.  Only dynamically constructed strings
            (concat, substr, format() results, etc.) are heap-allocated.

    No implicit casts (Go-style): mixing types is an error (i32 + i64 won't compile).
    Integer literals adapt to declared type: x: i8 = 42 makes 42 an i8.
    Hex (0xFF) and binary (0b1010) literals work anywhere integer literals do.
    Char literals ('A') produce i64 values (ASCII code).
    Like all integer literals, char literals adapt to the declared type:
        x: i8 = 'A'        # 'A' becomes i8
        y: i64 = 'A'       # 'A' becomes i64
        z := 'A'            # i64 (default)
    := shorthand defaults to i64 for integers, f64 for floats.

2.1b Type Casting

    Explicit cast builtins convert between numeric types:
        i8(x), i16(x), i32(x), i64(x), u8(x), u16(x), u32(x), u64(x), f32(x), f64(x)

    Examples:
        x: i64 = 100
        y: i32 = i32(x)       # i64 -> i32
        z: f64 = f64(y)       # i32 -> f64

2.2 Container Types (generic)

    List[T]     generic growable array
    Dict[K, V]  generic dictionary (key type K, value type V)

    Allowed key types: all integers (i8–u64), str, bool, enums.
    Disallowed keys: f32, f64, classes, interfaces, List, Dict.

    Examples:
        List[i64]           list of integers
        List[str]           list of strings
        List[Person]        list of user-defined class
        Dict[str, i64]      dict mapping str -> i64
        Dict[str, str]      dict mapping str -> str
        Dict[i64, str]      dict mapping i64 -> str
        Dict[bool, str]     dict mapping bool -> str

2.3 User-Defined Types

    class Name
        ...
    end

    Classes are refcounted heap objects.  See section 8.

2.4 Tuple Types

    (T1, T2)            tuple of two elements
    (T1, T2, T3)        tuple of three elements
    (i64, (str, bool))  nested tuple

    Tuples are fixed-size, heterogeneous value types.
    They compile to C structs (stack-allocated, no heap).
    Minimum 2 elements — single-element tuples are rejected.
    See section 7.4 for usage details.

2.5 Special Types

    None        assignable to any reference type (str, List, Dict, classes)
    void        return type for functions that return nothing

2.6 Type Annotations

    Variable declarations require a type (or use := shorthand).
    Function parameters and return types are mandatory.

------------------------------------------------------------
3. VARIABLE DECLARATIONS
------------------------------------------------------------

3.1 Explicit Type

    name: Type = expression

    Example:
        x: i64 = 10
        name: str = "hello"
        nums: List[i64] = List[i64]()

3.2 := Shorthand (type inferred from RHS)

    name := expression

    Examples:
        n := 42             # inferred i64
        msg := "hello"      # inferred str
        pi := 3.14          # inferred f64
        flag := True         # inferred bool
        nums := List[i64]() # inferred List[i64]

    Rules:
        - Variable must not already exist in same scope.
        - RHS must have a determinable type.

3.3 Constants

    const NAME: TYPE = expression

    Examples:
        const MAX: i64 = 100
        const PI: f64 = 3.14159
        const NAME: str = "bismut"

    Rules:
        - Constants cannot be reassigned (compile-time error).
        - Uses the same SVarDecl node with is_const=True.
        - Works at any scope (top-level or inside functions).

3.4 Global Variables

    Top-level variable declarations are file-scope globals,
    accessible from all functions:

        count: i64 = 0
        prefix: str = "LOG"

        def increment()
            count += 1
        end

        def get_count() -> i64
            return count
        end

    Globals are emitted as static C variables with mangled names
    (no clashes between files).  Ref-type globals are released
    at program exit.

3.5 Static Variables

    Static variables inside functions persist their value across
    calls, like C's static local variables.

    Syntax:
        static NAME: TYPE = expr

    Example:
        def counter() -> i64
            static n: i64 = 0
            n += 1
            return n
        end

    Rules:
        - Only allowed inside functions.
        - Initialized once on first call.
        - Value persists between calls.
        - Works with any type (primitives, str, List, etc.).
        - Not released at function exit.

------------------------------------------------------------
4. STATEMENTS
------------------------------------------------------------

4.1 Statement Termination

    A statement ends with newline or semicolon ';'.

4.2 Assignment

    name = expression
    name += expression
    name -= expression
    name *= expression
    name /= expression
    name %= expression
    name &= expression
    name |= expression
    name ^= expression
    name <<= expression
    name >>= expression

    Also for member access:
        obj.field = expression
        obj.field += expression   (etc.)

    Rules:
        '=' requires exact type match (None assignable to ref types).
        Arithmetic compound assignments (+=, -=, *=, /=, %=) for numeric types.
        += also works for str (string concatenation).
        Bitwise compound assignments (&=, |=, ^=, <<=, >>=) for integer types.

4.3 Expression Statement

    call_something()

4.4 Return

    return expression
    return              # void functions

    Return type must match function return type.

4.5 Break / Continue

    break
    continue

    Valid inside while and for loops.

------------------------------------------------------------
5. BLOCK STRUCTURE
------------------------------------------------------------

All blocks are explicitly closed with 'end'.

5.1 If Statement

    if condition
        statements
    elif condition
        statements
    else
        statements
    end

5.2 While Loop

    while condition
        statements
    end

5.3 For Loop

    # range-based (integers only)
    for i:i64 in range(10)              # 0..9
    for i:i64 in range(3, 7)           # 3..6
    for i:i64 in range(10, 0, -2)     # 10, 8, 6, 4, 2
        statements
    end

    # iterate over List
    for item:i64 in nums               # nums: List[i64]
        statements
    end

    # iterate over Dict keys
    for k:str in keys(d)               # d: Dict[str, i64]
        statements
    end

    The loop variable requires a type annotation (name:Type).

------------------------------------------------------------
6. EXPRESSIONS
------------------------------------------------------------

6.1 Primary Expressions

    Literals:       123   0xFF   0b1010   1.0   "hello"   'A'   True   False   None
    Variable:       x
    Parentheses:    (expression)
    Member access:  obj.field
    Function call:  name(expr, ...)
    Generic call:   name[Type](expr, ...)

6.2 Truthiness

    Bismut has truthiness for boolean contexts (conditions, logical operators, not).
    A "truthy type" is any of:
      - bool
      - Any integer type: i8, i16, i32, i64, u8, u16, u32, u64
      - Enums (which are integer types)
      - Any reference type: str, List[T], Dict[K,V], classes, interfaces

    Truthy values:
      - bool: True is truthy, False is falsy
      - Integers/enums: 0 is falsy, any non-zero value is truthy
      - Reference types: None is falsy, any non-null reference is truthy

    NOT truthy (rejected by the typechecker):
      - f32, f64 (floats)
      - Structs
      - Tuples
      - Function pointers

    Truthiness applies in these contexts:
      - if/elif conditions
      - while conditions
      - Unary not operator
      - and / or operands

    and / or always return bool, regardless of operand types.

6.3 Unary Operators

    -expr      numeric negation (i64 or f64)
    not expr   logical not (truthy types — see 6.2)
    ~expr      bitwise NOT (integer types only)

6.4 Binary Operators

    Arithmetic (same-type numeric operands):
        +  -  *  /  %

    String concatenation:
        +              (str + str -> str)

    Bitwise (same-type integer operands):
        &  |  ^  <<  >>

    Comparisons:
        <  <=  >  >=       (numeric only, same type)
        ==  !=              (same type; also works for str and None)

    Type check:
        expr is TypeName    (returns bool; see 6.6)

    Logical:
        and  or              (truthy types — see 6.2; always returns bool)

6.5 Operator Precedence (high -> low)

    11. unary: not - ~
    10. * / %
     9. + -
     8. << >>
     7. < <= > >=  is  as
     6. == !=
     5. &
     4. ^
     3. |
     2. and
     1. or

6.6 Type Check Operator (is)

    The 'is' operator checks the runtime type of a value.
    LHS is any expression, RHS is a type name (not an expression).
    Returns bool.

    # Concrete types — compile-time constant (zero cost)
    x: i64 = 42
    if x is i64           # true
    if x is f64           # false

    # Classes
    p := Point(1, 2)
    if p is Point         # true

    # Interface variables — runtime vtable pointer comparison
    s: IShape = Circle(5.0)
    if s is Circle        # true
    if s is Rect          # false

    # None check
    s2: IShape = None
    if s2 is None         # true

    # Combines with logical operators naturally
    if s is Circle and s.area() > 10.0
        print("big circle")
    end

    Rules:
        - RHS must be a type name (i64, Point, IShape, None, etc.)
        - For concrete types: resolved at compile time to constant true/false.
        - For interface variables: compares vtable pointer at runtime.
        - 'is None' checks null on any ref type or interface.
        - Same precedence as comparison operators (<, >, etc.).

    All binary operators are left-associative.

6.7 Downcast Operator (as)

    The 'as' operator downcasts an interface variable to a concrete class
    type. This allows accessing class-specific fields and methods that
    are not part of the interface.

    s: IShape = Circle(5.0)
    if s is Circle
        c: Circle = s as Circle
        print(c.r)              # access Circle-specific field
    end

    # Can use inline without a variable
    if s is Circle and (s as Circle).r > 3
        print("big")
    end

    Rules:
        - LHS must be an interface type.
        - RHS must be a class that implements that interface.
        - Same precedence as 'is' and comparison operators.
        - The result type is the concrete class type.
        - Runtime-checked: panics if the object is None or if the
          vtable does not match the target class.  No need to guard
          with 'is' first — the check is built in.
        - The result is a borrowed reference (automatically retained
          when assigned to a variable).

------------------------------------------------------------
7. FUNCTIONS
------------------------------------------------------------

7.1 Basic Functions

    def add(a: i64, b: i64) -> i64
        return a + b
    end

    # void functions omit -> or use -> void
    def greet(name: str)
        print(name)
    end

    Rules:
        - Must be top-level.
        - Parameter and return types are mandatory.
        - No implicit type conversions.

7.2 Generic Functions (user-defined)

    def identity[T](x: T) -> T
        return x
    end

    # explicit type param
    a: i64 = identity[i64](42)

    # type inference (T inferred from argument)
    b: str = identity("hello")

    def first[T](lst: List[T]) -> T
        return get[T](lst, 0)
    end

    Generics use monomorphization: each unique T generates a
    dedicated C function.

7.3 Function Pointers

    Function pointers allow passing and storing references to named
    functions. They are value types (raw C function pointers, no
    refcounting).

    Type syntax: Fn(ParamTypes...) -> ReturnType

    # Declare a function pointer variable
    def add(a: i64, b: i64) -> i64
        return a + b
    end

    f: Fn(i64, i64) -> i64 = add
    print(f(3, 4))             # 7

    # Reassignment
    def mul(a: i64, b: i64) -> i64
        return a * b
    end
    f = mul
    print(f(3, 4))             # 12

    # Pass as parameter
    def apply(op: Fn(i64, i64) -> i64, x: i64, y: i64) -> i64
        return op(x, y)
    end
    print(apply(add, 10, 20))  # 30

    # Return from function
    def pick(flag: bool) -> Fn(i64, i64) -> i64
        if flag
            return add
        end
        return mul
    end

    # Void return: Fn(str) -> void
    # No params:   Fn() -> i64

    Rules:
        - Only references to named top-level functions (no lambdas/closures).
        - Value types: no refcounting.  A function pointer variable
          cannot be None (it is not a ref type, like i64).
        - The return type can be any type including void:
          Fn(str) -> void is a valid function pointer type.
        - The function signature must match the Fn(...) type exactly.
        - Called through the variable like a regular function: f(args).
        - Compiles to a C function pointer typedef.

7.4 Tuples

    Tuples are fixed-size, heterogeneous value types. They compile
    to C structs (stack-allocated, no heap allocation).

    Type syntax: (T1, T2), (T1, T2, T3), etc.

    # Return a tuple from a function
    def get_pair() -> (i64, str)
        return (42, "hello")
    end

    # Destructure with :=
    a, b := get_pair()
    print(a)     # 42
    print(b)     # hello

    # Tuple as variable
    t: (i64, str) = (100, "world")
    p, q := t

    # Tuple as function parameter
    def sum_pair(pair: (i64, i64)) -> i64
        a, b := pair
        return a + b
    end
    print(sum_pair((3, 7)))   # 10

    # Nested tuples
    def get_nested() -> (i64, (str, bool))
        return (1, ("nested", True))
    end
    n, inner := get_nested()
    s, flag := inner

    # Tuples with class elements
    def make_point() -> (Point, str)
        p := Point(10, 20)
        return (p, "origin")
    end
    pt, label := make_point()

    Rules:
        - Value types: compiled to C structs, not heap-allocated.
        - Minimum 2 elements — single-element tuples are rejected.
        - Destructuring uses  a, b := expr  syntax (:= required,
          declares new variables).
        - Destructure arity must match the tuple element count exactly.
        - Ref-type elements (str, List, Dict, classes) are properly
          retained/released.
        - Nested tuples are supported: (i64, (str, bool)).
        - Work as function return types, parameters, and local variables.
        - := shorthand infers the tuple type from the RHS.

------------------------------------------------------------
8. CLASSES
------------------------------------------------------------

    class Point
        x: i64
        y: i64

        def init(self, x: i64, y: i64)
            self.x = x
            self.y = y
        end

        def sum(self) -> i64
            return self.x + self.y
        end
    end

    p: Point = Point(10, 20)
    print(p.x)          # 10
    print(p.sum())       # 30

    # Self-referential types (linked lists, trees, graphs)
    class Node
        val: i64
        next: Node

        def init(self, val: i64)
            self.val = val
        end
    end

    a := Node(1)
    b := Node(2)
    a.next = b              # a -> b -> None (no cycle)
    print(a.next.val)       # 2

    Rules:
        - Fields declared at top of class body with name: Type.
        - Constructor is 'def init(self, ...)' (no return type).
        - Methods take 'self' as first parameter.
        - Classes are refcounted heap objects.
        - Work with List[ClassName] and as generic type params.
        - Self-referential fields are allowed: a class may reference
          its own type (e.g. Node.next: Node) for linked lists, trees,
          and similar data structures.
        - Circular references between classes are allowed — both
          self-referential (Node.next: Node) and mutual (A.b: B +
          B.a: A, including through List or Dict fields). The compiler
          emits a note when it detects a cycle, since objects trapped
          in a reference cycle will leak (their refcounts never reach
          zero). Break the cycle manually before leaving scope (e.g.
          set a field to None or clear a list). The debug-mode leak
          detector catches these at runtime.

------------------------------------------------------------
8b. ENUMS
------------------------------------------------------------

    Enums are simple integer constants.  Each variant is an i64 value.
    Variants are scoped to the enum name — accessed as EnumName.VARIANT.

    enum Color
        RED, GREEN, BLUE
    end

    enum Status
        OK = 0
        ERROR = 10
        PENDING
    end

    # Access variants through the enum name
    c: Color = Color.GREEN
    print(c)                   # 1
    print(Color.GREEN)         # 1
    print(Status.PENDING)      # 11

    # Interchangeable with i64
    x: i64 = Color.BLUE
    print(Color.RED + 1)       # 1

    # Comparison
    if c == Color.GREEN
        print("yes")
    end

    # Use in functions
    def describe(c: Color) -> i64
        return c + 1
    end

    Rules:
        - Variants auto-increment from 0 by default.
        - Explicit = N sets the value; subsequent variants continue
          incrementing from that value.
        - Variants can be comma-separated on one line or on separate lines.
        - Enum types are interchangeable with i64 — assign freely
          between enum and i64 variables.
        - Variant names are scoped to the enum — accessed as
          EnumName.VARIANT (e.g. Color.RED, Status.OK).
        - From imported modules: module.EnumName.VARIANT
          (e.g. lex.TokenKind.TK_EOF).
        - Enums work with all integer operations: arithmetic,
          comparison, print, function parameters.
        - Enums are value types (not refcounted).
        - Different enums may have variants with the same name
          since variants are scoped to their enum.

------------------------------------------------------------
8c. INTERFACES
------------------------------------------------------------

    Interfaces define method signatures that classes can implement.
    They enable polymorphism — a variable of interface type can hold
    any class that implements it.

    interface IShape
        def area(self) -> f64
        def name(self) -> str
    end

    class Circle : IShape
        r: f64

        def init(self, r: f64)
            self.r = r
        end

        def area(self) -> f64
            return self.r * self.r * 3.14159
        end

        def name(self) -> str
            return "Circle"
        end
    end

    # Assign class instance to interface variable
    s: IShape = Circle(5.0)
    print(s.name())          # Circle
    print(s.area())          # 78.539749...

    # Pass class to function expecting interface
    def print_shape(s: IShape)
        print(s.name())
    end
    print_shape(Circle(3.0))

    # None comparison
    s2: IShape = None
    if s2 == None
        print("no shape")
    end

    Rules:
        - Declare with: interface Name ... end
        - Interface body contains method signatures only (no fields, no bodies).
        - A class implements an interface with: class Foo : IFaceName
        - Multiple interfaces: class Foo : IFace1, IFace2
        - The class must define all methods declared in the interface with
          matching parameter types and return type.
        - Interface variables use vtable-based dispatch (fat pointer:
          object pointer + vtable pointer).
        - You cannot construct an interface directly (IShape() is an error).
        - You cannot access fields through an interface — only methods.
        - Interfaces are ref types: assignable from None, comparable
          with == / !=, refcounted.
        - Use the 'is' operator for runtime type checking:
          if s is Circle   # checks vtable pointer
          if s is None     # checks for null

------------------------------------------------------------
8d. STRUCTS (value types)
------------------------------------------------------------

    Structs are pure value types — stack-allocated, no heap, no
    refcounting.  They provide lightweight composite data with
    Python-like syntax and C performance.

    struct Vec2
        x: f64
        y: f64
    end

    v := Vec2(3.0, 4.0)
    print(v.x)            # 3
    v.x = 10.0            # field mutation
    print(v.x)            # 10

    # Value copy semantics
    v2 := v               # copies the entire struct
    v2.x = 99.0
    print(v.x)            # 10  (original unchanged)

    # Methods (self by value)
    struct Point
        x: i64
        y: i64

        def sum(self) -> i64
            return self.x + self.y
        end

        def scale(self, factor: i64) -> Point
            return Point(self.x * factor, self.y * factor)
        end
    end

    p := Point(3, 7)
    print(p.sum())         # 10
    p2 := p.scale(10)
    print(p2.x)            # 30

    # Nested structs
    struct Rect
        origin: Point
        size: Point
    end

    r := Rect(Point(1, 2), Point(10, 20))
    print(r.origin.x)     # 1

    # Structs in lists
    nums: List[Point] = List[Point]()
    append(nums, Point(1, 2))
    print(nums[0].x)       # 1

    Rules:
        - Pure value types: stack-allocated, no heap, no refcounting.
        - Constructed positionally: Vec2(3.0, 4.0) — arguments match
          field declaration order.
        - No init methods.  Use positional construction only.
        - Assignment copies the entire struct (value semantics).
        - Fields are restricted to value types only: primitives (i64,
          f64, bool, etc.), enums, and other structs.  Ref-type fields
          (str, List, Dict, classes) are rejected.
        - Methods receive self by value, not by pointer.  Mutating
          self inside a method does not affect the caller's copy.
        - No interfaces — structs cannot implement interfaces.
        - Work as function parameters, return types, and in List[T].
        - Compound assignment on fields works: s.count += 1.
        - Compiled to C typedef structs with no indirection.
        - Methods compile to static C functions with self passed
          by value.

------------------------------------------------------------
9. CONTAINER BUILTINS (generic)
------------------------------------------------------------

All container operations are generic.  The type parameter can be
explicit (append[i64](nums, 10)) or inferred from the first
argument (append(nums, 10)).

9.1 List Operations

    List[T]()                           constructor
    List[T]() {e1, e2, ...}             constructor with initializer
    append(lst: List[T], val: T)        in-place push (void)
    pop(lst: List[T]) -> T               remove and return last element
    remove(lst: List[T], idx: i64)       remove element at index (void)
    get(lst: List[T], idx: i64) -> T    index access
    set(lst: List[T], idx: i64, val: T) index assign (void)
    len(lst: List[T]) -> i64            length

    Subscript syntax:
        lst[idx]            sugar for get(lst, idx)
        lst[idx] = val      sugar for set(lst, idx, val)

9.2 Dict Operations

    Dict[K, V]()                            constructor
    Dict[K, V]() {k: v, ...}               constructor with initializer
    put(d: Dict[K, V], key: K, val: V)      insert/update (void)
    lookup(d: Dict[K, V], key: K) -> V      key access
    has(d: Dict[K, V], key: K) -> bool      key check
    keys(d: Dict[K, V]) -> List[K]          all keys (for iteration)
    len(d: Dict[K, V]) -> i64              length

    Subscript syntax:
        d[key]              sugar for lookup(d, key)
        d[key] = val        sugar for put(d, key, val)

    Allowed key types: all integers (i8–u64), str, bool, enums.
    Disallowed keys: f32, f64, classes, interfaces, List, Dict.

9.3 Collection Literals

    Constructors can be followed by { } to initialize with elements.

    List literal:
        nums := List[i64]() {10, 20, 30}
        names: List[str] = List[str]() {"alice", "bob"}

    Dict literal (key: value pairs):
        ages := Dict[str, i64]() {"alice": 30, "bob": 25}

    Empty initializer:
        empty := List[i64]() {}

    Trailing commas:
        xs := List[i64]() {1, 2, 3,}

    Multi-line:
        matrix := List[List[i64]]() {
            List[i64]() {1, 2, 3},
            List[i64]() {4, 5, 6}
        }

    Nested containers:
        groups := Dict[str, List[i64]]() {
            "evens": List[i64]() {2, 4, 6},
            "odds": List[i64]() {1, 3, 5}
        }

    With class objects:
        people := List[Person]() {Person("Alice", 30), Person("Bob", 25)}

    Rules:
        - Syntax: List[T]() {elems} or Dict[K, V]() {key: val, ...}
        - Constructor call () must have zero arguments.
        - List elements must match element type T.
        - Dict keys must match key type K, values must match value type V.
        - Trailing commas and newlines inside { } are allowed.
        - Works with all types: primitives, str, classes, structs,
          enums, nested containers.
        - Compiles to constructor + append()/put() per element —
          no special runtime support needed.

------------------------------------------------------------
10. BUILTINS
------------------------------------------------------------

Only a small set of operations are built into the language itself.
Everything else lives in the standard library (section 10b).

10.1 Printing

    print(x)            prints numeric types, bool, and str (adds newline)

10.2 String Length and Indexing

    len(s: str) -> i64                  length
    s[i]                                char code at index (returns i64)

10.3 Range

    range(10)                           returns List[i64]: 0..9
    range(3, 7)                         returns List[i64]: 3..6
    range(10, 0, -2)                    returns List[i64]: 10, 8, 6, 4, 2

    Primarily used in for loops, but can be called anywhere:
        nums := range(5)               # List[i64] with [0, 1, 2, 3, 4]

10.4 String Formatting

    format(fmt, args...)    variadic string formatting, returns str

    Uses {} as auto-typed placeholders. Each {} consumes the next
    argument and formats it according to its type.

    s := format("Hello {}, you are {} years old", "Alice", 30)
    # result: "Hello Alice, you are 30 years old"

    s := format("{} scored {} ({} avg)", "Bob", 42, 3.14)
    # result: "Bob scored 42 (3.1400000000000001 avg)"

    # Escaped braces: {{ -> {, }} -> }
    s := format("set: {{{}}}", "x")    # "set: {x}"

    # No format args — returns the string as-is
    s := format("no args")

    Rules:
        - First argument must be str (the format string).
        - Remaining args: any printable type (all numeric types, bool, str, enums).
        - Each {} consumes the next argument by position.
        - {{ produces a literal {, }} produces a literal }.
        - Returns str (new refcounted string).
        - Panics at runtime if fewer args than {} placeholders.

------------------------------------------------------------
10b. STANDARD LIBRARY
------------------------------------------------------------

Bismut ships five standard extern libraries in libs/ next to the
compiler.  Use them via 'extern':

    extern string
    extern filesystem
    extern os
    extern stringbuilder
    extern buffer

Access functions via the alias: string.concat("a", "b")

10b.1 string — string operations & conversions

    concat(a: str, b: str) -> str               concatenation
    substr(s: str, start: i64, len: i64) -> str  substring
    find(s: str, sub: str) -> i64                find index (-1 if not found)
    chr(code: i64) -> str                        char from ASCII code
    char_at(s: str, i: i64) -> i64               char code at index
    i64_to_str(n: i64) -> str                    integer to string
    f64_to_str(n: f64) -> str                    float to string
    bool_to_str(b: bool) -> str                  bool to string
    str_to_i64(s: str) -> i64                    parse string to integer (decimal, hex, octal)
    str_to_f64(s: str) -> f64                    parse string to float

    Example:
        extern string
        print(string.concat("hello ", "world"))
        print(string.i64_to_str(42))

10b.2 filesystem — file system

    read(path: str) -> str                       read entire file
    write(path: str, content: str)               create/overwrite
    append(path: str, content: str)              append to file
    exists(path: str) -> bool                    file exists?
    dir_exists(path: str) -> bool                directory exists?

    Example:
        extern filesystem
        filesystem.write("out.txt", "hello")
        content := filesystem.read("out.txt")

10b.3 os — process execution, time & environment

    exec(cmd: str) -> i64                        run shell command, exit code
    time_now() -> f64                            high-res timestamp (seconds)
    exit(code: i64)                              terminate process with exit code
    argc() -> i64                                number of command-line arguments
    argv(index: i64) -> str                      get command-line argument by index

    Example:
        extern os
        rc := os.exec("echo hello")
        t := os.time_now()
        if os.argc() > 1
            print(os.argv(1))
        end

10b.4 stringbuilder — StringBuilder (opaque type)

    new() -> StringBuilder                       create builder
    destroy(sb: StringBuilder)             [dtor] destructor (auto-called)
    append_str(sb: StringBuilder, s: str)        append string
    append_i64(sb: StringBuilder, n: i64)        append integer
    append_f64(sb: StringBuilder, n: f64)        append float
    append_bool(sb: StringBuilder, b: bool)      append bool
    build(sb: StringBuilder) -> str              finalize to str
    clear(sb: StringBuilder)                     reset contents
    length(sb: StringBuilder) -> i64             current length

    StringBuilder is an opaque extern type — refcounted, can be None.

    Example:
        extern stringbuilder
        sb := stringbuilder.new()
        stringbuilder.append_str(sb, "hello ")
        stringbuilder.append_i64(sb, 42)
        print(stringbuilder.build(sb))    # hello 42

10b.5 buffer — byte buffer (opaque type)

    new() -> Buffer                              create empty buffer
    from_str(s: str) -> Buffer                   create from raw bytes
    destroy(buf: Buffer)                   [dtor] destructor (auto-called)
    write_byte(buf: Buffer, val: i64)            write single byte
    write_bytes(buf: Buffer, data: str)          write raw bytes
    write_str_zt(buf: Buffer, s: str)            write zero-terminated string
    write_i16_le/be(buf: Buffer, val: i64)       write 16-bit int (LE/BE)
    write_i32_le/be(buf: Buffer, val: i64)       write 32-bit int (LE/BE)
    write_i64_le/be(buf: Buffer, val: i64)       write 64-bit int (LE/BE)
    write_f32_le/be(buf: Buffer, val: f64)       write 32-bit float (LE/BE)
    write_f64_le/be(buf: Buffer, val: f64)       write 64-bit float (LE/BE)
    read_u8(buf: Buffer) -> i64                  read unsigned byte
    read_i8(buf: Buffer) -> i64                  read signed byte
    read_bytes(buf: Buffer, n: i64) -> str       read n raw bytes
    read_str_zt(buf: Buffer) -> str              read zero-terminated string
    read_u16_le/be(buf: Buffer) -> i64           read unsigned 16-bit (LE/BE)
    read_i16_le/be(buf: Buffer) -> i64           read signed 16-bit (LE/BE)
    read_u32_le/be(buf: Buffer) -> i64           read unsigned 32-bit (LE/BE)
    read_i32_le/be(buf: Buffer) -> i64           read signed 32-bit (LE/BE)
    read_i64_le/be(buf: Buffer) -> i64           read signed 64-bit (LE/BE)
    read_f32_le/be(buf: Buffer) -> f64           read 32-bit float (LE/BE)
    read_f64_le/be(buf: Buffer) -> f64           read 64-bit float (LE/BE)
    length(buf: Buffer) -> i64                   total bytes written
    capacity(buf: Buffer) -> i64                 allocated capacity
    pos(buf: Buffer) -> i64                      current read position
    remaining(buf: Buffer) -> i64                bytes left to read
    seek(buf: Buffer, pos: i64)                  set read position
    reset(buf: Buffer)                           reset read position to 0
    clear(buf: Buffer)                           clear all data
    to_str(buf: Buffer) -> str                   buffer contents as string
    slice(buf: Buffer, start: i64, len: i64) -> str  extract byte range

    Buffer is an opaque extern type — refcounted, can be None.

    Example:
        extern buffer
        buf := buffer.new()
        buffer.write_i32_le(buf, 42)
        buffer.write_str_zt(buf, "hello")
        buffer.seek(buf, 0)
        print(buffer.read_i32_le(buf))   # 42
        print(buffer.read_str_zt(buf))   # hello

------------------------------------------------------------
10.8 Imports (modules)
------------------------------------------------------------

    Bismut supports splitting projects into multiple files with
    Go-style imports.

    import lib.shapes
    import lib.helpers as h

    c := shapes.Circle(5.0)
    s: shapes.IShape = c
    print(h.add(3, 4))

    Rules:
        - 'import module.path' brings the module into scope.
          The alias defaults to the last segment: import lib.shapes
          makes shapes.Circle(...) available.
        - 'import module.path as alias' uses a custom alias.
        - Access symbols via alias.Name: shapes.Circle(...) for
          constructors, shapes.IShape for type annotations,
          shapes.func(...) for function calls.
        - Module path uses dots as separators:
          'import sub.foo' resolves to sub/foo.mut.
        - Resolution order: relative to the importing file first,
          then modules/ next to the compiler (standard library modules).
        - Imports must appear at the top of the file, before any
          definitions or statements.
        - Functions, classes, and interfaces are accessible through
          the module alias.
        - Circular imports are detected and rejected.
        - Source positions are preserved — errors in imported code
          reference the original file and line.
        - Internally, imported names are mangled (alias__Name) and
          merged into a flat AST before typechecking; the typechecker
          and codegen are unaware of modules.

------------------------------------------------------------
11. RUNTIME MODEL
------------------------------------------------------------

    - i64, f64, bool are native C values (no heap allocation).
    - str, List, Dict, and classes are heap-allocated
      and automatically refcounted.
    - Opaque extern types (e.g. stringbuilder.StringBuilder) are also
      refcounted via a wrapper struct.
    - Strings are immutable.
    - String literals are immortal: they compile to static C objects
      with a special refcount sentinel (UINT32_MAX).  Retain and
      release are no-ops on immortal objects.  Identical string
      literals within a compilation unit are deduplicated (interned)
      to a single static object.  This means d["key"], print("hello"),
      and format strings have zero allocation cost.
    - Lists and dicts are mutable.
    - Parameters are borrowed (callee does not retain/release).
    - Return values are materialized to a temp before scope cleanup.
    - Ref-type assignment retains new value before releasing old
      (alias-safe).
    - Runtime errors include file/line/column information.

------------------------------------------------------------
12. PREPROCESSOR
------------------------------------------------------------

    Bismut has a text-level preprocessor that runs before the lexer.
    It processes @-directives line-by-line, stripping or including
    source text based on compile-time constants.

    Directives:
        @define NAME          Define a compile-time constant
        @if NAME              Include following lines if NAME is defined
        @elif NAME            Else-if branch
        @else                 Else branch
        @end                  End conditional block

    Predefined constants (based on host platform):
        __LINUX__   — defined on Linux
        __MACOS__   — defined on macOS
        __WIN__     — defined on Windows

    Example:
        @define DEBUG

        @if __LINUX__
        platform: str = "linux"
        @elif __MACOS__
        platform: str = "macos"
        @elif __WIN__
        platform: str = "windows"
        @end

        @if DEBUG
        print(platform)
        @end

    Rules:
    - Directives are processed line-by-line at the text level —
      the lexer/parser never see them.
    - @define inside a dead branch is not evaluated.
    - Nesting is supported: @if inside @if works correctly.
    - Only checks whether a name is defined (no expressions,
      no value comparison).
    - Files without @ directives pass through unchanged.

------------------------------------------------------------
13. EXTERN (NATIVE C LIBRARIES)
------------------------------------------------------------

    Bismut supports native C plugin libraries via `extern`. This allows
    extending the language without recompiling the compiler.

    Syntax:
        extern libname
        extern libname as alias

    Usage:
        extern pxmath as m
        x: f64 = m.sqrt(25.0)

    Libraries live in a `libs/` directory:
        libs/
          libname/
            libname.mutlib    # manifest
            libname.c        # C implementation

    The `.mutlib` manifest declares what the library exports:

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
        cflags_linux = -I{LIB_DIR}/linux
        ldflags_linux = -L{LIB_DIR}/linux -ltcc -ldl
        cflags_win = -I{LIB_DIR}/win
        ldflags_macos = -framework Cocoa

    Flag values in [flags] support the {LIB_DIR} placeholder, which is
    replaced at parse time with the absolute path to the library's
    directory. This lets libraries reference bundled files without
    hardcoding paths.

    Opaque types:
        The [types] section declares opaque C types. Bismut wraps the
        raw C pointer in a refcounted box (refcount header + c_type*).
        The struct layout is hidden from Bismut code — fields cannot be
        accessed directly. Instead, the library exposes getter/setter
        functions:

            [types]
            Matrix = pxmatrix_t

            [functions]
            create(rows: i64, cols: i64) -> Matrix = pxmatrix_create
            destroy(m: Matrix) [dtor] = pxmatrix_destroy
            rows(m: Matrix) -> i64 = pxmatrix_rows
            set(m: Matrix, r: i64, c: i64, v: f64) = pxmatrix_set
            get(m: Matrix, r: i64, c: i64) -> f64 = pxmatrix_get

        This is the same pattern as C's FILE* — you never access
        struct fields directly, only through library functions. This
        keeps the C struct layout as an implementation detail so the
        lib author can change it without breaking Bismut code.

        A function tagged [dtor] is called automatically when the
        refcount drops to 0. The destructor receives the raw C pointer
        and is responsible for freeing all inner resources — heap
        members, file handles, sub-allocations, etc. Bismut only frees
        the outer wrapper struct; the library owns everything inside.
        If a type has no [dtor], the wrapper struct is freed but no
        inner cleanup is performed (suitable for types with no heap
        members).

        Opaque types behave like classes: they are ref types, can be
        None, and work with ==/!=.

    Resolution order:
        1. libs/ relative to the source file
        2. libs/ relative to the compiler

    The C source file is #included in the generated out.c.
    Functions should be declared static.

    C Symbol Naming Conventions:
        To prevent symbol clashes between the runtime, shipped
        libraries, and user C code, Bismut uses strict prefixing
        conventions for all generated C symbols:

        - Runtime symbols (in rt/*.h): prefixed with __lang_rt_
          (functions and types) or __LANG_RT_ (macros).
          Examples: __lang_rt_str_new(), __lang_rt_Str, __LANG_RT_SRC()

        - Shipped library symbols (in libs/): prefixed with
          __clib__<libname>_.
          Examples: __clib__string_concat(), __clib__buffer_Buffer,
          __clib__os_exec()

        - User-authored extern libs: free to use any C naming
          convention, but should avoid the __lang_rt_ and __clib__
          prefixes.

        This ensures zero namespace collisions regardless of what
        user code links against.

------------------------------------------------------------
14. COMPILER CLI
------------------------------------------------------------

The self-hosted compiler provides a subcommand-based interface:

    bismut <command> [options]

    Global options:
      --version, -V           Show version and exit
      --help, -h              Show help and exit

14.1 Commands

    build <file.mut>     Compile to native binary
    run <file.mut>       Build and run
    analyze <file.mut>   Analyze and output JSON diagnostics

14.2 Build

    bismut build <file.mut> [options]

    Compiles <file.mut> through the full pipeline (preprocess → parse →
    resolve → typecheck → codegen) to produce a C file, then invokes
    a C compiler (gcc by default, or embedded TCC with --tcc) to
    produce a native binary.

    Options:
      -o, --output <name>     Output binary name (default: source file stem)
      -r, --release           Optimized release build (-O2; default is debug)
      --no-debug-leaks        Disable leak detector (enabled by default in
                              debug builds)
      -q, --quiet             Suppress warnings and notes
      --cc <path>             C compiler to use (default: gcc)
      --tcc                   Use embedded TCC compiler (no external gcc needed)
      -D, --define <SYMBOL>   Preprocessor define (can be repeated)
      --compiler-dir <dir>    Compiler root directory (default: auto-detect
                              from the bismut binary location)

    The --tcc flag uses the bundled TCC backend. TCC headers and runtime
    libraries are shipped self-contained in libs/tcc/linux/ and
    libs/tcc/win/ — no external C compiler or system headers are needed.

14.3 Run

    bismut run <file.mut> [options]

    Compiles and immediately runs the program using the embedded TCC
    backend (no gcc required).

    Options:
      -r, --release           Optimized release build
      --no-debug-leaks        Disable leak detector
      -q, --quiet             Suppress warnings and notes
      -D, --define <SYMBOL>   Preprocessor define (can be repeated)
      --compiler-dir <dir>    Compiler root directory

14.4 Analyze

    bismut analyze <file.mut> [options]

    Runs the compiler pipeline (preprocess → parse → resolve → typecheck)
    without code generation. Outputs structured JSON diagnostics to stdout.
    Designed for IDE integration (error squigglies, hover, diagnostics).

    Exit code: 0 on success, 1 if errors found.

    Options:
      -D, --define <SYMBOL>   Preprocessor define (can be repeated)
      --compiler-dir <dir>    Compiler root directory

    Output format (JSON):

        {
          "success": true | false,
          "file": "<source file path>",
          "error_count": <int>,
          "warning_count": <int>,
          "diagnostics": [
            {
              "severity": "error" | "warning" | "note",
              "file": "<file path>",
              "line": <int>,
              "col": <int>,
              "span": <int>,
              "message": "<diagnostic text>"
            }
          ]
        }

    Example:

        $ bismut analyze bad.mut --compiler-dir .
        {
          "success": false,
          "file": "bad.mut",
          "error_count": 1,
          "warning_count": 0,
          "diagnostics": [
            {
              "severity": "error",
              "file": "bad.mut",
              "line": 3,
              "col": 5,
              "span": 1,
              "message": "undefined variable 'x'"
            }
          ]
        }

------------------------------------------------------------
15. DEBUG LEAK DETECTOR
------------------------------------------------------------

    The leak detector tracks all heap allocations and reports objects
    still alive at program exit.  It catches reference cycles and
    other memory leaks.

    Enabled by default in debug builds (no -r flag).
    Disabled with --no-debug-leaks or in release builds (-r).

    How it works:
        - Allocation tracking: rt_rc.h maintains a global intrusive
          linked list of all live allocations.  Each refcount header
          has prev/next pointers and a type-name tag.  Allocations
          insert into the list; release at rc=0 removes before freeing.
        - Exit report: after global cleanup, __LANG_RT_LEAK_REPORT()
          walks the live-allocation list.  Any object still alive with
          rc != UINT32_MAX (not immortal) is a leak.  Reports object
          address, type name, and refcount to stderr.
        - Zero overhead in release: all tracking code is guarded behind
          #ifdef __LANG_RT_DEBUG_LEAKS.  Release builds define nothing,
          so the macros expand to no-ops.
        - Covers: classes, strings, lists, dicts, and extern opaque
          types.  Immortal strings (rc = UINT32_MAX) are excluded.

    Example output (2 Node objects trapped in a reference cycle):
        [leak] 0x55f3a1b2c040  type=Node  rc=1
        [leak] 0x55f3a1b2c080  type=Node  rc=1
        2 object(s) leaked.

------------------------------------------------------------
16. COMPLETE EXAMPLE
------------------------------------------------------------

    def fib(n: i64) -> i64
        if n < 2
            return n
        end
        return fib(n - 1) + fib(n - 2)
    end

    # := shorthand
    result := fib(35)
    print(result)

    # generics + type inference
    nums := List[i64]()
    append(nums, 10)
    append(nums, 20)
    append(nums, 30)

    for n:i64 in nums
        print(n)
    end

    print(len(nums))

    # class
    class Point
        x: i64
        y: i64

        def init(self, x: i64, y: i64)
            self.x = x
            self.y = y
        end

        def sum(self) -> i64
            return self.x + self.y
        end
    end

    p: Point = Point(10, 20)
    print(p.sum())
