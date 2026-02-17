// __lang_rt_error.h (C99) — runtime errors with source location
#pragma once
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>

typedef struct __lang_rt_Src {
    const char* file;  // stable pointer (C literal is fine)
    int32_t line;      // 1-based
    int32_t col;       // 1-based (or 0)
} __lang_rt_Src;

static inline __lang_rt_Src __lang_rt_src(const char* file, int32_t line, int32_t col) {
    __lang_rt_Src s;
    s.file = file ? file : "<unknown>";
    s.line = line;
    s.col = col;
    return s;
}

typedef enum __lang_rt_ErrKind {
    __LANG_RT_ERR_PANIC = 1,
    __LANG_RT_ERR_TYPE,
    __LANG_RT_ERR_OOB,
    __LANG_RT_ERR_KEY,
    __LANG_RT_ERR_ALLOC,
    __LANG_RT_ERR_IO,
    __LANG_RT_ERR_ASSERT,
} __lang_rt_ErrKind;

static inline const char* __lang_rt_err_name(__lang_rt_ErrKind k) {
    switch (k) {
        case __LANG_RT_ERR_PANIC: return "panic";
        case __LANG_RT_ERR_TYPE:  return "type error";
        case __LANG_RT_ERR_OOB:   return "out of bounds";
        case __LANG_RT_ERR_KEY:   return "key error";
        case __LANG_RT_ERR_ALLOC: return "alloc error";
        case __LANG_RT_ERR_IO:    return "io error";
        case __LANG_RT_ERR_ASSERT:return "assert";
        default:           return "error";
    }
}

static inline void __lang_rt_vfail(__lang_rt_ErrKind kind, __lang_rt_Src src, const char* fmt, va_list ap) {
    if (src.file && src.line > 0) {
        if (src.col > 0) fprintf(stderr, "%s:%d:%d: %s: ", src.file, (int)src.line, (int)src.col, __lang_rt_err_name(kind));
        else             fprintf(stderr, "%s:%d: %s: ", src.file, (int)src.line, __lang_rt_err_name(kind));
    } else {
        fprintf(stderr, "%s: ", __lang_rt_err_name(kind));
    }
    vfprintf(stderr, fmt, ap);
    fputc('\n', stderr);
    abort();
}

static inline void __lang_rt_fail(__lang_rt_ErrKind kind, __lang_rt_Src src, const char* fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    __lang_rt_vfail(kind, src, fmt, ap);
    va_end(ap);
}

static inline void __lang_rt_oob(__lang_rt_Src src, const char* msg)  { __lang_rt_fail(__LANG_RT_ERR_OOB, src, "%s", msg); }
static inline void __lang_rt_key(__lang_rt_Src src, const char* msg)  { __lang_rt_fail(__LANG_RT_ERR_KEY, src, "%s", msg); }
static inline void __lang_rt_panic(__lang_rt_Src src, const char* msg){ __lang_rt_fail(__LANG_RT_ERR_PANIC, src, "%s", msg); }
static inline void __lang_rt_null_check(const void* p, __lang_rt_Src src) { if (!p) __lang_rt_panic(src, "null pointer dereference"); }

// Checked downcast: verify vtable matches before extracting obj pointer
static inline void* __lang_rt_downcast(__lang_rt_Src src, void* obj, const void* actual_vtbl,
                                const void* expected_vtbl, const char* target_name) {
    if (!obj) __lang_rt_fail(__LANG_RT_ERR_PANIC, src, "'as %s' failed: object is None", target_name);
    if (actual_vtbl != expected_vtbl) __lang_rt_fail(__LANG_RT_ERR_TYPE, src, "'as %s' failed: object is not %s", target_name, target_name);
    return obj;
}
