# Bismut Language Reference

A statically-typed, Python-like language that compiles to C99.

---

## Types

| Type | Description |
|------|-------------|
| `i8` `i16` `i32` `i64` | Signed integers |
| `u8` `u16` `u32` `u64` | Unsigned integers |
| `f32` `f64` | IEEE-754 floats |
| `bool` | `True` / `False` |
| `str` | Immutable refcounted string |
| `None` | Null for reference types |
| `List[T]` | Dynamic array |
| `Dict[K, V]` | Hash map (keys: int, str, bool, enum) |
| `Fn(A, B) -> R` | Function pointer |
| `(T1, T2, ...)` | Tuple (min 2 elements) |

No implicit casts. `i32 + i64` is a compile error — use explicit casts: `i64(x)`, `f32(y)`, etc.

---

## Variables & Constants

```
x: i64 = 10                # Typed declaration
name: str = "hello"
flag: bool = True

n := 42                    # Type inferred (i64 for int, f64 for float)
msg := "world"

const MAX: i64 = 100       # Constant, cannot be reassigned
```

### Global & Static Variables

```
count: i64 = 0             # File-scope global

def counter() -> i64
    static n: i64 = 0      # Persists across function calls
    n += 1
    return n
end
```

---

## Functions

```
def add(a: i64, b: i64) -> i64
    return a + b
end

def greet(name: str)       # Void — no return type
    print(name)
end
```

### Generics

```
def identity[T](x: T) -> T
    return x
end

a := identity[i64](42)    # Explicit type param
b := identity("hello")    # Inferred from argument
```

### Function Pointers

```
f: Fn(i64, i64) -> i64 = add
print(f(3, 4))            # 7

def apply(op: Fn(i64, i64) -> i64, x: i64, y: i64) -> i64
    return op(x, y)
end
```

Only references to named top-level functions. No lambdas/closures.

---

## Control Flow

```
if x > 5
    print(x)
elif x == 0
    print(0)
else
    print(-1)
end

while i < 10
    i += 1
end

for i:i64 in range(10)            # 0..9
for i:i64 in range(3, 7)          # 3..6
for i:i64 in range(10, 0, -2)     # 10, 8, 6, 4, 2
for n:i64 in nums                  # Iterate List
for k:str in keys(d)               # Iterate Dict keys
```

`break` and `continue` work in `while` and `for` loops.

---

## Strings

```
s := "hello"               # Double quotes
s := 'hello'               # Single quotes (equivalent)
s := """multi
line"""                     # Triple quotes

c := 'A'                   # Char literal -> i64 (ASCII code)
code := s[0]               # Char code at index -> i64

# Escape sequences: \n \t \r \\ \" \' \0 (char literals only)
```

### String Formatting

```
s := format("Hello {}, age {}", "Alice", 30)
s := format("{} + {} = {}", 1, 2, 3)
s := format("literal braces: {{}}")
```

Supports `i64`, `f64`, `bool`, `str`, enums, all integer types. Returns `str`.

### String Concatenation

```
s := "hello" + " world"
s += "!"
```

---

## Collections

### List

```
nums := List[i64]()
nums := List[i64]() {10, 20, 30}   # Literal

append(nums, 42)
print(nums[0])             # Subscript read
nums[0] = 99               # Subscript write
print(len(nums))
```

### Dict

```
d := Dict[str, i64]()
d := Dict[str, i64]() {"a": 1, "b": 2}   # Literal

d["key"] = 42
print(d["key"])
print(has(d, "key"))       # True
print(len(d))

for k:str in keys(d)       # Iterate keys
    print(k)
end
```

### Builtin Operations

| Function | Description |
|----------|-------------|
| `append(lst, val)` | Push to list |
| `len(x)` | Length of list, dict, or str |
| `has(d, key)` | Dict key exists? |
| `keys(d)` | Dict keys as `List[K]` |
| `range(n)` / `range(a,b)` / `range(a,b,step)` | Integer range |

---

## Tuples

```
def get_pair() -> (i64, str)
    return (42, "hello")
end

a, b := get_pair()         # Destructure (declares new vars)

t: (i64, str) = (100, "world")
x, y := t
```

Tuples are value types (stack-allocated). Minimum 2 elements.

---

## Classes

```
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

p := Point(10, 20)
print(p.x)
print(p.sum())
```

Classes are refcounted heap objects. Self-referential fields allowed (`Node.next: Node`).
Mutual circular references between classes are rejected.

---

## Structs

```
struct Vec2
    x: f64
    y: f64

    def length(self) -> f64
        return self.x + self.y
    end
end

v := Vec2(3.0, 4.0)       # Positional construction
v.x = 10.0

v2 := v                    # Value copy (original unchanged)
```

Structs are value types — stack-allocated, no heap, no refcounting.
Fields restricted to value types only (primitives, enums, other structs).
No `init` — constructed positionally. Methods receive `self` by value.

---

## Enums

```
enum Color
    RED, GREEN, BLUE
end

enum Status
    OK = 0
    ERROR = 10
    PENDING                 # Auto-increments to 11
end

x: Color = Color.GREEN
n: i64 = Color.BLUE        # Interchangeable with i64
```

---

## Interfaces

```
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

s: IShape = Circle(5.0)    # Polymorphic variable
print(s.area())

# Multiple interfaces
class Rect : IShape, IDrawable
    ...
end
```

Interface variables support `None`, `==`/`!=`. No field access through interfaces — methods only.

### Type Check & Downcast

```
if s is Circle              # Runtime type check -> bool
    c := s as Circle # Downcast to concrete type
    print(c.r)
end

if s is None
    print("no shape")
end
```

---

## Operators

- **Arithmetic:** `+` `-` `*` `/` `%`
- **Bitwise:** `&` (AND) `|` (OR) `^` (XOR) `~` (NOT)
- **Bit shift:** `<<` (left) `>>` (right)
- **Comparison:** `<` `<=` `>` `>=` `==` `!=`
- **Type:** `is` (type check) `as` (downcast)
- **Logical:** `not` `and` `or`
- **String:** `+` (concat) `+=` (append)

### Precedence (high -> low)

| Operators |
|-----------|
| `not` `-` `~` (unary) |
| `*` `/` `%` |
| `+` `-` |
| `<<` `>>` |
| `<` `<=` `>` `>=` `is` `as` |
| `==` `!=` |
| `&` |
| `^` |
| `|` |
| `and` |
| `or` |

### Assignment

`=` `+=` `-=` `*=` `/=` `%=` `&=` `|=` `^=` `<<=` `>>=`

### Comments

```
# Line comment
```

### Multi-Line Expressions

Newlines inside `()`, `[]`, and `{}` are automatically ignored, allowing expressions to span multiple lines:

```
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
```

---

## Truthiness

Used in `if`, `elif`, `while`, `not`, `and`, `or`:

| Type | Falsy | Truthy |
|------|-------|--------|
| `bool` | `False` | `True` |
| Integers / enums | `0` | Non-zero |
| Ref types (str, List, Dict, classes, interfaces) | `None` | Non-null |

`f32`, `f64`, structs, tuples, function pointers are **not** truthy (rejected by typechecker).
`and` / `or` always return `bool`.

---

## Imports

```
import lib.shapes              # Alias defaults to "shapes"
import lib.helpers as h        # Custom alias

c := shapes.Circle(5.0)
s: shapes.IShape = c
print(h.add(3, 4))
```

Imports must appear at the top of the file. Module path uses dots (`import sub.foo` -> `sub/foo.mut`).

---

## Extern Libraries

```
extern string
extern os
extern filesystem as fs

print(string.concat("a", "b"))
fs.write("out.txt", "hello")
rc := os.exec("echo hi")
```

### Standard Library

#### string
`concat(a, b)` · `substr(s, start, len)` · `find(s, sub)` · `chr(code)` · `char_at(s, i)` · `i64_to_str(n)` · `f64_to_str(n)` · `bool_to_str(b)` · `str_to_i64(s)` · `str_to_f64(s)`

#### filesystem
`read(path)` · `write(path, content)` · `append(path, content)` · `exists(path)` · `dir_exists(path)`

#### os
`exec(cmd)` · `time_now()` · `exit(code)` · `argc()` · `argv(index)`

#### stringbuilder
```
extern stringbuilder
sb := stringbuilder.new()
stringbuilder.append_str(sb, "hello ")
stringbuilder.append_i64(sb, 42)
result := stringbuilder.build(sb)   # "hello 42"
```

`new()` · `append_str(sb, s)` · `append_i64(sb, n)` · `append_f64(sb, n)` · `append_bool(sb, b)` · `build(sb)` · `clear(sb)` · `length(sb)`

#### buffer
Binary byte buffer with read/write operations for all integer/float sizes in little-endian and big-endian.

```
extern buffer
buf := buffer.new()
buffer.write_i32_le(buf, 42)
buffer.write_str_zt(buf, "hello")
buffer.seek(buf, 0)
print(buffer.read_i32_le(buf))    # 42
print(buffer.read_str_zt(buf))    # hello
```

Key functions: `new()` · `from_str(s)` · `write_byte` · `write_bytes` · `write_str_zt` · `write_i16_le/be` · `write_i32_le/be` · `write_i64_le/be` · `write_f32_le/be` · `write_f64_le/be` · `read_u8` · `read_i8` · `read_bytes` · `read_str_zt` · `read_u16_le/be` · `read_i16_le/be` · `read_u32_le/be` · `read_i32_le/be` · `read_i64_le/be` · `read_f32_le/be` · `read_f64_le/be` · `length` · `pos` · `remaining` · `seek` · `reset` · `clear` · `to_str` · `slice`

---

## Preprocessor

```
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
```

Predefined: `__LINUX__`, `__MACOS__`, `__WIN__`. Only checks if defined (no values/expressions).

---

## Type Casting

```
x: i64 = 100
y: i32 = i32(x)
z: f64 = f64(y)

# All casts: i8() i16() i32() i64() u8() u16() u32() u64() f32() f64()
```

---

## Quick Examples

### Hello World
```
print("Hello, World!")
```

### FizzBuzz
```
for i:i64 in range(1, 101)
    if i % 15 == 0
        print("FizzBuzz")
    elif i % 3 == 0
        print("Fizz")
    elif i % 5 == 0
        print("Buzz")
    else
        print(i)
    end
end
```

### Linked List
```
class Node
    val: i64
    next: Node

    def init(self, val: i64)
        self.val = val
    end
end

a := Node(1)
b := Node(2)
c := Node(3)
a.next = b
b.next = c

node := a
while node != None
    print(node.val)
    node = node.next
end
```

### File I/O
```
extern filesystem

filesystem.write("data.txt", "Hello from Bismut!")
content := filesystem.read("data.txt")
print(content)
```
