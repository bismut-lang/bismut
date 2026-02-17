// __lang_rt_str.h (C99) — refcounted string
#pragma once
#include <stdint.h>
#include <string.h>
#include <stdio.h>

#include "rt_rc.h"
#include "rt_alloc.h"

typedef struct __lang_rt_Str {
    __lang_rt_Rc rc;        // must be first
    uint32_t len;
    const char* data;  // NUL-terminated for convenience
} __lang_rt_Str;

// Declare an immortal string literal (file-scope static, never freed)
#define __LANG_RT_STR_LIT(name, cstr) \
    static __lang_rt_Str name = { .rc = { .rc = __LANG_RT_RC_IMMORTAL }, .len = (uint32_t)(sizeof(cstr) - 1), .data = (cstr) }

static inline void __lang_rt_str_dtor(void* obj) {
    __lang_rt_Str* s = (__lang_rt_Str*)obj;
    free((void*)s->data);
    free(s);
}

static inline __lang_rt_Str* __lang_rt_str_new_bytes(__lang_rt_Src src, const char* bytes, uint32_t len) {
    __lang_rt_Str* s = (__lang_rt_Str*)__lang_rt_malloc(src, sizeof(__lang_rt_Str));
    __lang_rt_rc_init(&s->rc);
    s->len = len;
    char* buf = (char*)__lang_rt_malloc(src, (size_t)len + 1);
    memcpy(buf, bytes, len);
    buf[len] = 0;
    s->data = buf;
    return s;
}

static inline __lang_rt_Str* __lang_rt_str_new_cstr(__lang_rt_Src src, const char* cstr) {
    return __lang_rt_str_new_bytes(src, cstr, (uint32_t)strlen(cstr));
}

static inline void __lang_rt_str_retain(__lang_rt_Str* s) { __lang_rt_retain(s); }
static inline void __lang_rt_str_release(__lang_rt_Str* s) { __lang_rt_release(s, __lang_rt_str_dtor); }

static inline int __lang_rt_str_eq(__lang_rt_Str* a, __lang_rt_Str* b) {
    if (a == b) return 1;
    if (!a || !b) return 0;
    if (a->len != b->len) return 0;
    return memcmp(a->data, b->data, a->len) == 0;
}

// Safe byte-at-index (returns i64, panics on OOB)
static inline int64_t __lang_rt_str_get(__lang_rt_Src src, __lang_rt_Str* s, int64_t idx) {
    if (!s) __lang_rt_fail(__LANG_RT_ERR_PANIC, src, "str_get: string is nil");
    if (idx < 0 || (uint64_t)idx >= s->len) __lang_rt_oob(src, "str_get: index out of range");
    return (int64_t)(unsigned char)s->data[(uint32_t)idx];
}

// Substring (start inclusive, length). Returns new owned __lang_rt_Str.
static inline __lang_rt_Str* __lang_rt_str_sub(__lang_rt_Src src, __lang_rt_Str* s, int64_t start, int64_t length) {
    if (!s) __lang_rt_fail(__LANG_RT_ERR_PANIC, src, "str_sub: string is nil");
    if (start < 0) start = 0;
    if (start > (int64_t)s->len) start = (int64_t)s->len;
    if (length < 0) length = 0;
    if (start + length > (int64_t)s->len) length = (int64_t)s->len - start;
    return __lang_rt_str_new_bytes(src, s->data + start, (uint32_t)length);
}

// Single-char string from byte value
static inline __lang_rt_Str* __lang_rt_str_chr(__lang_rt_Src src, int64_t byte_val) {
    char c = (char)(byte_val & 0xFF);
    return __lang_rt_str_new_bytes(src, &c, 1);
}

// Find substring. Returns index or -1.
// Length-aware: works correctly with embedded NUL bytes.
static inline int64_t __lang_rt_str_find(__lang_rt_Str* haystack, __lang_rt_Str* needle) {
    if (!haystack || !needle) return -1;
    if (needle->len == 0) return 0;
    if (needle->len > haystack->len) return -1;
    uint32_t limit = haystack->len - needle->len;
    for (uint32_t i = 0; i <= limit; i++) {
        if (memcmp(haystack->data + i, needle->data, needle->len) == 0)
            return (int64_t)i;
    }
    return -1;
}

// Conversions: primitive -> str
#include <inttypes.h>

static inline __lang_rt_Str* __lang_rt_i64_to_str(__lang_rt_Src src, int64_t v) {
    char buf[32];
    int n = snprintf(buf, sizeof(buf), "%" PRId64, v);
    return __lang_rt_str_new_bytes(src, buf, (uint32_t)n);
}

static inline __lang_rt_Str* __lang_rt_f64_to_str(__lang_rt_Src src, double v) {
    char buf[64];
    int n = snprintf(buf, sizeof(buf), "%.17g", v);
    return __lang_rt_str_new_bytes(src, buf, (uint32_t)n);
}

static inline __lang_rt_Str* __lang_rt_bool_to_str(__lang_rt_Src src, int v) {
    return v ? __lang_rt_str_new_bytes(src, "true", 4) : __lang_rt_str_new_bytes(src, "false", 5);
}

// Concatenate two strings -> new owned __lang_rt_Str
static inline __lang_rt_Str* __lang_rt_str_concat(__lang_rt_Src src, __lang_rt_Str* a, __lang_rt_Str* b) {
    if (!a) __lang_rt_fail(__LANG_RT_ERR_PANIC, src, "str_concat: lhs is nil");
    if (!b) __lang_rt_fail(__LANG_RT_ERR_PANIC, src, "str_concat: rhs is nil");
    uint32_t total = a->len + b->len;
    char* buf = (char*)__lang_rt_malloc(src, (size_t)total + 1);
    memcpy(buf, a->data, a->len);
    memcpy(buf + a->len, b->data, b->len);
    buf[total] = 0;
    __lang_rt_Str* s = (__lang_rt_Str*)__lang_rt_malloc(src, sizeof(__lang_rt_Str));
    __lang_rt_rc_init(&s->rc);
    s->len = total;
    s->data = (const char*)buf;
    return s;
}
