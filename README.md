# Bismut

A statically-typed language with Python-like syntax that compiles to C99.
The goal is Python's readability with native C performance -- no VM, no garbage
collector, no runtime overhead.

Bismut is fully self-hosted: the compiler is written in Bismut and can compile
itself.

## Quick look

```
def fib(n: i64) -> i64
    if n < 2
        return n
    end
    return fib(n - 1) + fib(n - 2)
end

result := fib(35)
print(result)
```

More examples in `test/positive/`.

## Building the compiler

The self-hosted compiler needs to be bootstrapped once using the Python
reference compiler, then it can compile itself.

```
# Bootstrap: Python compiler produces C, gcc produces the binary
python3 tools/reference-compiler/main.py src/main.mut
gcc -O2 -std=c99 -Irt -Ilibs/tcc/linux -o bismut out.c -Llibs/tcc/linux -ltcc -ldl -lm

# Now the compiler can compile itself
./bismut build src/main.mut -o bismut -r
```

Requirements: Python 3, GCC (or any C99 compiler), Linux or Windows.

## Usage

```
# Compile a program
./bismut build hello.mut

# Compile and run
./bismut run hello.mut

# Analyze without compiling (JSON diagnostics, for editor integration)
./bismut analyze hello.mut
```

## Language overview

- Explicit types everywhere (no type inference except `:=` shorthand)
- Blocks closed with `end`, not indentation
- Automatic reference counting for heap objects (strings, lists, dicts, classes)
- Value types: primitives, structs, enums, tuples
- Generics via monomorphization
- Interfaces with vtable dispatch
- No implicit type conversions
- Native C library interop via `extern`

### Types

Primitives: `i8`, `i16`, `i32`, `i64`, `u8`, `u16`, `u32`, `u64`, `f32`, `f64`, `bool`, `str`

Containers: `List[T]`, `Dict[K, V]`

User-defined: classes, structs, enums, interfaces

### Standard library

Five libraries ship with the compiler, used via `extern`:

- `string` -- string operations and conversions
- `filesystem` -- file I/O
- `os` -- process execution, time, command-line args
- `stringbuilder` -- efficient string building
- `buffer` -- binary read/write

### Imports

```
import lib.shapes
import lib.helpers as h

c := shapes.Circle(5.0)
print(h.add(3, 4))
```

## Tests

```
# Run all tests with the Python reference compiler
bash test/run.sh

# Run all tests with the self-hosted compiler
bash test/run_selfhost.sh
```

## Documentation

- [Language reference](docs/language-reference.md) -- compact syntax overview
- [Language specification](docs/bismut-spec.md) -- full spec with all details
- [Writing C libraries](docs/writing-c-libraries.md) -- how to create native C extensions

## Project layout

```
src/            Self-hosted compiler (Bismut)
tools/          Reference compiler (Python, for bootstrapping)
rt/             C runtime (refcounting, containers, strings)
libs/           Standard library (C implementations + manifests)
modules/        Standard library (Bismut modules)
test/           Test suite (positive, negative, runtime error tests)
docs/           Documentation
```

## License

GPLv3 with runtime library exception. The compiler is copyleft -- forks must
stay open source. Programs compiled with Bismut are yours, no restrictions.
See [LICENSE.md](LICENSE.md).
