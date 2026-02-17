// __lang_rt_list.h (C99) — macro template for typed lists
#pragma once
#include <stdint.h>
#include <string.h>
#include "rt_rc.h"
#include "rt_alloc.h"
#include "rt_error.h"

// Define a list type for some element type T.
//
// - NAME: identifier suffix, e.g. I64 => __lang_rt_List_I64
// - T: element C type, e.g. int64_t
// - DROP(elem): statement to drop/release elem (for ref types). For primitives: (void)(elem)
// - CLONE(dst, src): statement to copy/retain src into dst. For primitives: dst = src; For ref types: dst=src; retain(src)
#define __LANG_RT_LIST_DEFINE(NAME, T, DROP, CLONE) \
typedef struct __lang_rt_List_##NAME { \
    __lang_rt_Rc rc; \
    uint32_t len; \
    uint32_t cap; \
    T* data; \
} __lang_rt_List_##NAME; \
\
static inline void __lang_rt_list_##NAME##_dtor(void* obj) { \
    __lang_rt_List_##NAME* a = (__lang_rt_List_##NAME*)obj; \
    for (uint32_t i = 0; i < a->len; i++) { \
        DROP(a->data[i]); \
    } \
    free(a->data); \
    free(a); \
} \
\
static inline __lang_rt_List_##NAME* __lang_rt_list_##NAME##_new(__lang_rt_Src src) { \
    __lang_rt_List_##NAME* a = (__lang_rt_List_##NAME*)__lang_rt_malloc(src, sizeof(__lang_rt_List_##NAME)); \
    __lang_rt_rc_init(&a->rc); \
    a->len = 0; \
    a->cap = 8; \
    a->data = (T*)__lang_rt_calloc(src, a->cap, sizeof(T)); \
    return a; \
} \
\
static inline void __lang_rt_list_##NAME##_retain(__lang_rt_List_##NAME* a) { __lang_rt_retain(a); } \
static inline void __lang_rt_list_##NAME##_release(__lang_rt_List_##NAME* a) { __lang_rt_release(a, __lang_rt_list_##NAME##_dtor); } \
\
static inline void __lang_rt_list_##NAME##_grow(__lang_rt_Src src, __lang_rt_List_##NAME* a, uint32_t need) { \
    if (a->cap >= need) return; \
    uint32_t cap = a->cap; \
    while (cap < need) cap *= 2; \
    a->data = (T*)__lang_rt_realloc(src, a->data, (size_t)cap * sizeof(T)); \
    /* zero-init new area */ \
    memset(a->data + a->cap, 0, (size_t)(cap - a->cap) * sizeof(T)); \
    a->cap = cap; \
} \
\
static inline void __lang_rt_list_##NAME##_push(__lang_rt_Src src, __lang_rt_List_##NAME* a, T v) { \
    __lang_rt_list_##NAME##_grow(src, a, a->len + 1); \
    CLONE(a->data[a->len], v); \
    a->len++; \
} \
\
static inline T __lang_rt_list_##NAME##_get(__lang_rt_Src src, __lang_rt_List_##NAME* a, int64_t idx) { \
    if (idx < 0 || (uint64_t)idx >= a->len) __lang_rt_oob(src, "list index out of range"); \
    return a->data[(uint32_t)idx]; \
} \
\
static inline void __lang_rt_list_##NAME##_set(__lang_rt_Src src, __lang_rt_List_##NAME* a, int64_t idx, T v) { \
    if (idx < 0 || (uint64_t)idx >= a->len) __lang_rt_oob(src, "list index out of range"); \
    uint32_t i = (uint32_t)idx; \
    DROP(a->data[i]); \
    CLONE(a->data[i], v); \
} \
\
static inline int64_t __lang_rt_list_##NAME##_len(__lang_rt_List_##NAME* a) { return (int64_t)a->len; } \
\
static inline T __lang_rt_list_##NAME##_pop(__lang_rt_Src src, __lang_rt_List_##NAME* a) { \
    if (a->len == 0) __lang_rt_oob(src, "pop from empty list"); \
    a->len--; \
    T val = a->data[a->len]; \
    CLONE(val, val); \
    DROP(a->data[a->len]); \
    memset(&a->data[a->len], 0, sizeof(T)); \
    return val; \
} \
\
static inline void __lang_rt_list_##NAME##_remove(__lang_rt_Src src, __lang_rt_List_##NAME* a, int64_t idx) { \
    if (idx < 0 || (uint64_t)idx >= a->len) __lang_rt_oob(src, "list remove index out of range"); \
    uint32_t i = (uint32_t)idx; \
    DROP(a->data[i]); \
    memmove(&a->data[i], &a->data[i+1], (size_t)(a->len - i - 1) * sizeof(T)); \
    a->len--; \
    memset(&a->data[a->len], 0, sizeof(T)); \
}
