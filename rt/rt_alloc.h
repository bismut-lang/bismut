// __lang_rt_alloc.h (C99) — allocation helpers
#pragma once
#include <stdlib.h>
#include <string.h>
#include "rt_error.h"

static inline void* __lang_rt_malloc(__lang_rt_Src src, size_t n) {
    void* p = malloc(n);
    if (!p) __lang_rt_fail(__LANG_RT_ERR_ALLOC, src, "out of memory");
    return p;
}
static inline void* __lang_rt_calloc(__lang_rt_Src src, size_t count, size_t size) {
    void* p = calloc(count, size);
    if (!p) __lang_rt_fail(__LANG_RT_ERR_ALLOC, src, "out of memory");
    return p;
}
static inline void* __lang_rt_realloc(__lang_rt_Src src, void* p, size_t n) {
    void* q = realloc(p, n);
    if (!q) __lang_rt_fail(__LANG_RT_ERR_ALLOC, src, "out of memory");
    return q;
}
static inline void __lang_rt_free(void* p) {
    free(p);
}
