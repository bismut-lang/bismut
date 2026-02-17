// __lang_rt_sb.h (C99) — refcounted string builder
#pragma once
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <inttypes.h>
#include "rt_rc.h"
#include "rt_alloc.h"
#include "rt_str.h"

typedef struct __lang_rt_Sb {
    __lang_rt_Rc rc;
    uint32_t len;
    uint32_t cap;
    char* data;
} __lang_rt_Sb;

static inline void __lang_rt_sb_dtor(void* obj) {
    __lang_rt_Sb* sb = (__lang_rt_Sb*)obj;
    free(sb->data);
    free(sb);
}

static inline __lang_rt_Sb* __lang_rt_sb_new(__lang_rt_Src src) {
    __lang_rt_Sb* sb = (__lang_rt_Sb*)__lang_rt_malloc(src, sizeof(__lang_rt_Sb));
    __lang_rt_rc_init(&sb->rc);
    sb->len = 0;
    sb->cap = 64;
    sb->data = (char*)__lang_rt_malloc(src, sb->cap);
    sb->data[0] = 0;
    return sb;
}

static inline void __lang_rt_sb_retain(__lang_rt_Sb* sb) { __lang_rt_retain(sb); }
static inline void __lang_rt_sb_release(__lang_rt_Sb* sb) { __lang_rt_release(sb, __lang_rt_sb_dtor); }

static inline void __lang_rt_sb_grow(__lang_rt_Src src, __lang_rt_Sb* sb, uint32_t need) {
    if (sb->cap >= need) return;
    uint32_t cap = sb->cap;
    while (cap < need) cap *= 2;
    sb->data = (char*)__lang_rt_realloc(src, sb->data, cap);
    sb->cap = cap;
}

static inline void __lang_rt_sb_append_bytes(__lang_rt_Src src, __lang_rt_Sb* sb, const char* data, uint32_t len) {
    __lang_rt_sb_grow(src, sb, sb->len + len + 1);
    memcpy(sb->data + sb->len, data, len);
    sb->len += len;
    sb->data[sb->len] = 0;
}

static inline void __lang_rt_sb_append_str(__lang_rt_Src src, __lang_rt_Sb* sb, __lang_rt_Str* s) {
    if (!s) return;
    __lang_rt_sb_append_bytes(src, sb, s->data, s->len);
}

static inline void __lang_rt_sb_append_i64(__lang_rt_Src src, __lang_rt_Sb* sb, int64_t v) {
    char buf[32];
    int n = snprintf(buf, sizeof(buf), "%" PRId64, v);
    __lang_rt_sb_append_bytes(src, sb, buf, (uint32_t)n);
}

static inline void __lang_rt_sb_append_f64(__lang_rt_Src src, __lang_rt_Sb* sb, double v) {
    char buf[64];
    int n = snprintf(buf, sizeof(buf), "%.17g", v);
    __lang_rt_sb_append_bytes(src, sb, buf, (uint32_t)n);
}

static inline void __lang_rt_sb_append_bool(__lang_rt_Src src, __lang_rt_Sb* sb, int v) {
    if (v) __lang_rt_sb_append_bytes(src, sb, "true", 4);
    else   __lang_rt_sb_append_bytes(src, sb, "false", 5);
}

// Build a __lang_rt_Str from current contents. Does NOT consume/reset the builder.
static inline __lang_rt_Str* __lang_rt_sb_build(__lang_rt_Src src, __lang_rt_Sb* sb) {
    return __lang_rt_str_new_bytes(src, sb->data, sb->len);
}

// Reset builder contents (reuse buffer)
static inline void __lang_rt_sb_clear(__lang_rt_Src src, __lang_rt_Sb* sb) {
    (void)src;
    sb->len = 0;
    sb->data[0] = 0;
}

static inline int64_t __lang_rt_sb_len(__lang_rt_Sb* sb) { return (int64_t)sb->len; }
