# Writing C Libraries for Bismut

This guide explains how to create native C extension libraries for Bismut. These libraries let you extend the language with functionality implemented in C — wrapping system APIs, existing C libraries, or performance-critical code.

## Library Layout

A Bismut C library lives in a directory under `libs/`:

```
libs/
  mylib/
    mylib.mutlib    # manifest — declares types, functions, constants, build flags
    mylib.c         # C implementation
```

The directory name, the `.mutlib` file name, and the `.c` file name must all match.

**Resolution order**: the compiler looks for `libs/` relative to the source file first, then `libs/` relative to the compiler.

## The Manifest (`.mutlib`)

The `.mutlib` file is an INI-style manifest with four optional sections: `[types]`, `[functions]`, `[constants]`, and `[flags]`.

### `[types]` — Opaque Types

Declares C types that Bismut wraps in a refcounted box.

```ini
[types]
BismutName = c_type_name
```

- `BismutName` becomes a Bismut type that behaves like a class: it's a ref type, can be `None`, and is refcounted
- `c_type_name` is the C struct/typedef name — Bismut stores a `c_type_name*` inside a wrapper struct
- You cannot access fields on opaque types from Bismut — all interaction goes through declared functions

**Example** (from `buffer.mutlib`):
```ini
[types]
Buffer = __clib__buffer_Buffer
```

### `[functions]` — Function Declarations

Declares functions with Bismut signatures mapped to C function names.

```ini
[functions]
bismut_name(param: type, param: type) -> ret_type = c_function_name
```

- Omit `-> ret_type` for void functions (or write `-> void` explicitly)
- The C function must be `static` in the `.c` file
- Parameter and return types use Bismut type names: `i64`, `f64`, `str`, `bool`, or any type declared in `[types]`

**Destructors** are tagged with `[dtor]`:
```ini
destroy(obj: MyType) [dtor] = c_destroy_function
```

The `[dtor]` tag tells the compiler to call this function automatically when the refcount on `MyType` drops to zero. More on this in the [Memory Management](#memory-management) section.

**Example** (from `buffer.mutlib`):
```ini
[functions]
new() -> Buffer = __clib__buffer_new
destroy(buf: Buffer) [dtor] = __clib__buffer_destroy
write_byte(buf: Buffer, val: i64) -> void = __clib__buffer_write_byte
length(buf: Buffer) -> i64 = __clib__buffer_length
to_str(buf: Buffer) -> str = __clib__buffer_to_str
```

### `[constants]` — Compile-Time Constants

Declares constants accessible from Bismut:

```ini
[constants]
MY_CONSTANT: i64 = 42
PI: f64 = 3.14159265358979
```

The value is a C expression that will be emitted verbatim in the generated code.

### `[flags]` — Build Flags

Specifies compiler/linker flags. Supports platform-specific suffixes.

```ini
[flags]
cflags = -I.
ldflags = -lm
cflags_linux = -I{LIB_DIR}/linux
ldflags_linux = -L{LIB_DIR}/linux -lfoo
cflags_macos = -I{LIB_DIR}/macos
ldflags_win = -L{LIB_DIR}/win -lfoo
```

`{LIB_DIR}` is replaced at parse time with the absolute path to the library's directory, so you can reference bundled headers or static libraries without hardcoding paths.

Platform suffixes: `_linux`, `_macos`, `_win`.

## Writing the C Implementation

The `.c` file is `#include`d directly into the generated `out.c`. This means:

1. **All runtime headers are already available** — you don't need to include them
2. **All functions must be `static`** — to avoid linker symbol conflicts
3. **Bismut's runtime types are your types** — strings are `__lang_rt_Str*`, integers are `int64_t`, etc.

### Type Mapping

| Bismut Type | C Type |
|-------------|--------|
| `i8` | `int8_t` |
| `i16` | `int16_t` |
| `i32` | `int32_t` |
| `i64` | `int64_t` |
| `u8` | `uint8_t` |
| `u16` | `uint16_t` |
| `u32` | `uint32_t` |
| `u64` | `uint64_t` |
| `f32` | `float` |
| `f64` | `double` |
| `bool` | `bool` |
| `str` | `__lang_rt_Str*` |
| `void` | `void` |
| Opaque type `T` | `c_type*` (raw pointer, auto-unwrapped) |

### How Parameters and Returns Are Bridged

The compiler generates a thin wrapper for each extern function. The wrapper handles two transformations:

**Parameters — unwrap**: If a parameter is an opaque type, the wrapper extracts the raw C pointer (`param->ptr`) before calling your C function. Your function receives the raw pointer directly.

**Returns — wrap**: If a function returns an opaque type, the wrapper wraps the raw C pointer in a refcounted box after your function returns.

This means:
- **Your C functions never see the Bismut wrapper struct** — opaque type parameters arrive as raw `c_type*` pointers
- **Non-opaque types pass through directly** — `str` parameters arrive as `__lang_rt_Str*`, integers as `int64_t`, etc.

### Naming Conventions

To avoid symbol collisions:

| Scope | Prefix | Example |
|-------|--------|---------|
| Runtime (don't use) | `__lang_rt_` / `__LANG_RT_` | `__lang_rt_Str`, `__lang_rt_retain()` |
| Shipped libraries | `__clib__<libname>_` | `__clib__buffer_new()`, `__clib__os_exec()` |
| Your libraries | Your choice | Avoid `__lang_rt_` and `__clib__` prefixes |

### Available Runtime Helpers

Since the runtime headers are already included, you can use these utilities:

**Allocation** (panics on OOM instead of returning NULL):
```c
void* __lang_rt_malloc(__lang_rt_Src src, size_t n);
void* __lang_rt_calloc(__lang_rt_Src src, size_t count, size_t size);
void* __lang_rt_realloc(__lang_rt_Src src, void* p, size_t n);
void  __lang_rt_free(void* p);
```

**Error reporting** (prints file:line and aborts):
```c
// Create a source location for error messages
__lang_rt_Src src = __LANG_RT_SRC("<mylib>", 0, 0);

// Panic with a message
__lang_rt_fail(__LANG_RT_ERR_PANIC, src, "something went wrong");

// Error kinds: __LANG_RT_ERR_PANIC, __LANG_RT_ERR_OOB, __LANG_RT_ERR_KEY,
//              __LANG_RT_ERR_ALLOC, __LANG_RT_ERR_IO, __LANG_RT_ERR_ASSERT
```

**Strings** — creating Bismut strings from C data:
```c
// From NUL-terminated C string (copies the data, returns owned str with rc=1)
__lang_rt_Str* __lang_rt_str_new_cstr(__lang_rt_Src src, const char* cstr);

// From byte buffer + length (copies, NUL-terminates, returns owned str with rc=1)
__lang_rt_Str* __lang_rt_str_new_bytes(__lang_rt_Src src, const char* bytes, uint32_t len);
```

**Refcounting** (rarely needed in library code, but available):
```c
void __lang_rt_retain(void* obj);
void __lang_rt_release(void* obj, __lang_rt_DtorFn dtor);
void __lang_rt_rc_init(__lang_rt_Rc* h);   // sets rc = 1
```

## Memory Management

This is the most important section. Getting memory management wrong causes leaks or crashes.

### The Ownership Model

Bismut uses **automatic reference counting** (ARC). Every heap object has a refcount header as its first field. The compiler inserts retain/release calls automatically at every assignment, scope exit, and function return.

For extern opaque types, the compiler generates a **wrapper struct**:

```c
// What the compiler generates for your opaque type:
struct __lang_rt_Class_mylib__MyType {
    __lang_rt_Rc rc;      // refcount — managed by Bismut
    my_c_type* ptr;       // raw C pointer — managed by YOU
};
```

The lifecycle:

1. **Construction**: Your `new()` function returns a raw `my_c_type*`. The compiler wraps it in the struct above with `rc = 1`.
2. **Usage**: Bismut retains/releases the wrapper as it flows through variables, function arguments, containers, etc. Your code is never involved in this — it just operates on the raw pointer.
3. **Destruction**: When `rc` drops to 0, the compiler calls your `[dtor]` function with the raw `my_c_type*`, then `free()`s the wrapper struct.

### What Bismut Manages (You Don't Touch)

- Allocating and freeing the **outer wrapper struct**
- Initializing the refcount to 1
- Incrementing/decrementing the refcount as the object flows through Bismut code
- Calling the destructor at the right time (when rc reaches 0)
- Freeing the wrapper struct after the destructor runs

### What You Must Manage

- All **inner resources** of your C type: heap allocations, file handles, sockets, sub-structures
- The C struct itself (the one your constructor `malloc`'d)

Your destructor receives the raw `my_c_type*` pointer. You must free everything:

```c
static void my_destroy(my_c_type* obj) {
    free(obj->data);       // free inner heap allocations
    fclose(obj->handle);   // close file handles
    free(obj);             // free the struct itself
}
```

**If you don't declare a `[dtor]` function**, only the wrapper struct is freed. The inner `my_c_type*` pointer is abandoned — this is a guaranteed memory leak unless your type has no heap allocations.

### String Parameters Are Borrowed

When your C function receives a `__lang_rt_Str*` parameter, it is **borrowed** — you do not own it. Rules:

- **Do not free it** — the caller manages its lifetime
- **Do not store it** beyond the function call — it may be released after your function returns
- If you need the data to outlive the call, **copy it**: `__lang_rt_str_new_cstr(src, s->data)`
- Access the string's content via `s->data` (NUL-terminated `const char*`) and `s->len`
- Always check `if (!s)` — a `None` string arrives as a NULL pointer

### Returning Strings

When your function returns a `__lang_rt_Str*`, it must return a **new, owned** string with `rc = 1`. Use the runtime helpers:

```c
static __lang_rt_Str* my_func(void) {
    __lang_rt_Src src = __LANG_RT_SRC("<mylib>", 0, 0);
    return __lang_rt_str_new_cstr(src, "hello");   // rc = 1, caller takes ownership
}
```

**Never return a string parameter directly** — that would give the caller a borrowed reference, leading to a double-free or use-after-free when the caller releases it.

### Opaque Type Parameters Are Pre-Unwrapped

Your functions receive the raw C pointer, not the Bismut wrapper. The compiler's generated wrapper does:

```c
// Generated by compiler — you never see this:
static void mylib__do_thing(__lang_rt_Class_mylib__MyType* wrapped) {
    my_c_do_thing(wrapped->ptr);   // your function gets the raw pointer
}
```

You don't need to unwrap anything — just use the pointer.

## Common Leak Patterns

### 1. Missing Destructor

```ini
# BAD — no [dtor], inner allocations leak
[types]
Handle = my_handle_t

[functions]
create() -> Handle = my_create
```

```ini
# GOOD — destructor declared, called automatically at rc=0
[types]
Handle = my_handle_t

[functions]
create() -> Handle = my_create
destroy(h: Handle) [dtor] = my_destroy
```

### 2. Incomplete Destructor

```c
typedef struct {
    char* name;      // heap-allocated
    int* data;       // heap-allocated
    FILE* fp;        // open file handle
} my_handle_t;

// BAD — only frees the struct, inner allocations leak
static void my_destroy(my_handle_t* h) {
    free(h);
}

// GOOD — frees everything
static void my_destroy(my_handle_t* h) {
    free(h->name);
    free(h->data);
    if (h->fp) fclose(h->fp);
    free(h);
}
```

### 3. Storing String Parameters Without Copying

```c
typedef struct {
    const char* name;   // danger: borrowed pointer
} my_obj;

// BAD — stores pointer to borrowed string data, use-after-free
static my_obj* my_create(__lang_rt_Str* name) {
    my_obj* o = malloc(sizeof(my_obj));
    o->name = name->data;   // name may be freed after this call returns!
    return o;
}

// GOOD — copies the string data
static my_obj* my_create(__lang_rt_Str* name) {
    my_obj* o = malloc(sizeof(my_obj));
    o->name = strdup(name->data);   // owns its own copy
    return o;
}
```

Remember to `free(o->name)` in the destructor when you `strdup`.

### 4. Returning Strings Without Proper Allocation

```c
// BAD — returns a stack/static pointer, not a proper Bismut string
static __lang_rt_Str* my_name(void) {
    // This is wrong in so many ways — don't do it
    return (__lang_rt_Str*)"hello";
}

// GOOD — returns a properly allocated Bismut string with rc=1
static __lang_rt_Str* my_name(void) {
    __lang_rt_Src src = __LANG_RT_SRC("<mylib>", 0, 0);
    return __lang_rt_str_new_cstr(src, "hello");
}
```

### 5. Allocating Without Using Runtime Helpers

```c
// RISKY — silent NULL on OOM, potential null-deref later
my_t* obj = malloc(sizeof(my_t));

// BETTER — panics immediately with a clear error on OOM
__lang_rt_Src src = __LANG_RT_SRC("<mylib>", 0, 0);
my_t* obj = (my_t*)__lang_rt_malloc(src, sizeof(my_t));
```

Using `__lang_rt_malloc` isn't required, but it gives you fail-fast OOM behavior consistent with the rest of the runtime.

## Complete Example: A Counter Library

### `libs/counter/counter.mutlib`

```ini
[types]
Counter = my_counter_t

[functions]
new(start: i64) -> Counter = my_counter_new
destroy(c: Counter) [dtor] = my_counter_destroy
increment(c: Counter) = my_counter_increment
get(c: Counter) -> i64 = my_counter_get
name(c: Counter) -> str = my_counter_name
set_name(c: Counter, n: str) = my_counter_set_name
```

### `libs/counter/counter.c`

```c
#include <string.h>

typedef struct {
    int64_t value;
    char* name;       // heap-allocated, owned
} my_counter_t;

static my_counter_t* my_counter_new(int64_t start) {
    __lang_rt_Src src = __LANG_RT_SRC("<counter>", 0, 0);
    my_counter_t* c = (my_counter_t*)__lang_rt_malloc(src, sizeof(my_counter_t));
    c->value = start;
    c->name = strdup("unnamed");
    return c;
}

static void my_counter_destroy(my_counter_t* c) {
    free(c->name);    // free inner heap allocation
    free(c);          // free the struct
}

static void my_counter_increment(my_counter_t* c) {
    c->value++;
}

static int64_t my_counter_get(my_counter_t* c) {
    return c->value;
}

static __lang_rt_Str* my_counter_name(my_counter_t* c) {
    __lang_rt_Src src = __LANG_RT_SRC("<counter>", 0, 0);
    return __lang_rt_str_new_cstr(src, c->name);   // new string, rc=1
}

static void my_counter_set_name(my_counter_t* c, __lang_rt_Str* n) {
    free(c->name);                 // free old name
    c->name = strdup(n->data);    // copy borrowed string data
}
```

### Usage in Bismut

```
extern counter

c := counter.new(0)
counter.set_name(c, "hits")
counter.increment(c)
counter.increment(c)
print(counter.name(c))    # hits
print(counter.get(c))     # 2
# c is automatically destroyed when it goes out of scope
```

## Checklist

Before shipping a C library for Bismut:

- [ ] All C functions are `static`
- [ ] Every opaque type with heap allocations has a `[dtor]` function
- [ ] The destructor frees **all** inner resources (heap members, handles, sub-allocations) **and** the struct itself
- [ ] String parameters are treated as borrowed — data is copied if stored beyond the call
- [ ] Returned strings are created with `__lang_rt_str_new_cstr` or `__lang_rt_str_new_bytes` (new allocation, rc=1)
- [ ] NULL checks on `__lang_rt_Str*` parameters before dereferencing `->data`
- [ ] No use of `__lang_rt_` or `__clib__` prefixes in user-authored libraries
- [ ] Build flags use `{LIB_DIR}` for paths to bundled files
