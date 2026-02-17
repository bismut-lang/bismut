// __lang_rt_dict_str.h (C99) — macro template for dict[str, V]
#pragma once
#include <stdint.h>
#include <string.h>
#include "rt_rc.h"
#include "rt_alloc.h"
#include "rt_str.h"
#include "rt_error.h"

// open addressing with tombstones
typedef enum { __LANG_RT_SLOT_EMPTY=0, __LANG_RT_SLOT_FULL=1, __LANG_RT_SLOT_TOMB=2 } __lang_rt_SlotState;

static inline uint64_t __lang_rt_hash_bytes_fnv1a(const char* data, uint32_t len) {
    uint64_t h = 1469598103934665603ULL;
    for (uint32_t i = 0; i < len; i++) { h ^= (uint8_t)data[i]; h *= 1099511628211ULL; }
    return h ? h : 1ULL;
}

static inline uint32_t __lang_rt_hash_u64(uint64_t x) {
    x ^= x >> 33; x *= 0xff51afd7ed558ccdULL; x ^= x >> 33; x *= 0xc4ceb9fe1a85ec53ULL; x ^= x >> 33;
    return (uint32_t)x;
}

#define __LANG_RT_DICT_STR_DEFINE(NAME, V, VDROP, VCLONE) \
typedef struct __lang_rt_DictStrEntry_##NAME { \
    __lang_rt_SlotState st; \
    uint64_t hash; \
    __lang_rt_Str* key; \
    V value; \
} __lang_rt_DictStrEntry_##NAME; \
\
typedef struct __lang_rt_DictStr_##NAME { \
    __lang_rt_Rc rc; \
    uint32_t len; \
    uint32_t cap; /* power of two */ \
    __lang_rt_DictStrEntry_##NAME* e; \
} __lang_rt_DictStr_##NAME; \
\
static inline void __lang_rt_dictstr_##NAME##_dtor(void* obj) { \
    __lang_rt_DictStr_##NAME* d = (__lang_rt_DictStr_##NAME*)obj; \
    for (uint32_t i = 0; i < d->cap; i++) { \
        if (d->e[i].st == __LANG_RT_SLOT_FULL) { \
            __lang_rt_str_release(d->e[i].key); \
            VDROP(d->e[i].value); \
        } \
    } \
    free(d->e); \
    free(d); \
} \
\
static inline __lang_rt_DictStr_##NAME* __lang_rt_dictstr_##NAME##_new(__lang_rt_Src src) { \
    __lang_rt_DictStr_##NAME* d = (__lang_rt_DictStr_##NAME*)__lang_rt_malloc(src, sizeof(__lang_rt_DictStr_##NAME)); \
    __lang_rt_rc_init(&d->rc); \
    d->len = 0; \
    d->cap = 16; \
    d->e = (__lang_rt_DictStrEntry_##NAME*)__lang_rt_calloc(src, d->cap, sizeof(__lang_rt_DictStrEntry_##NAME)); \
    return d; \
} \
\
static inline void __lang_rt_dictstr_##NAME##_retain(__lang_rt_DictStr_##NAME* d) { __lang_rt_retain(d); } \
static inline void __lang_rt_dictstr_##NAME##_release(__lang_rt_DictStr_##NAME* d) { __lang_rt_release(d, __lang_rt_dictstr_##NAME##_dtor); } \
\
static inline uint32_t __lang_rt_dictstr_##NAME##_find_slot(__lang_rt_DictStr_##NAME* d, uint64_t h, __lang_rt_Str* key, int* found) { \
    uint32_t mask = d->cap - 1; \
    uint32_t i = __lang_rt_hash_u64(h) & mask; \
    uint32_t first_tomb = UINT32_MAX; \
    for (;;) { \
        __lang_rt_DictStrEntry_##NAME* ent = &d->e[i]; \
        if (ent->st == __LANG_RT_SLOT_EMPTY) { \
            *found = 0; \
            return (first_tomb != UINT32_MAX) ? first_tomb : i; \
        } \
        if (ent->st == __LANG_RT_SLOT_TOMB) { \
            if (first_tomb == UINT32_MAX) first_tomb = i; \
        } else { \
            if (ent->hash == h && __lang_rt_str_eq(ent->key, key)) { \
                *found = 1; \
                return i; \
            } \
        } \
        i = (i + 1) & mask; \
    } \
} \
\
static inline void __lang_rt_dictstr_##NAME##_rehash(__lang_rt_Src src, __lang_rt_DictStr_##NAME* d, uint32_t new_cap) { \
    __lang_rt_DictStrEntry_##NAME* old = d->e; \
    uint32_t old_cap = d->cap; \
    d->cap = new_cap; \
    d->e = (__lang_rt_DictStrEntry_##NAME*)__lang_rt_calloc(src, d->cap, sizeof(__lang_rt_DictStrEntry_##NAME)); \
    d->len = 0; \
    for (uint32_t i = 0; i < old_cap; i++) { \
        if (old[i].st == __LANG_RT_SLOT_FULL) { \
            int found = 0; \
            uint32_t slot = __lang_rt_dictstr_##NAME##_find_slot(d, old[i].hash, old[i].key, &found); \
            __lang_rt_DictStrEntry_##NAME* ent = &d->e[slot]; \
            ent->st = __LANG_RT_SLOT_FULL; \
            ent->hash = old[i].hash; \
            ent->key = old[i].key; /* move ref */ \
            ent->value = old[i].value; /* move */ \
            d->len++; \
        } \
    } \
    free(old); \
} \
\
static inline void __lang_rt_dictstr_##NAME##_set(__lang_rt_Src src, __lang_rt_DictStr_##NAME* d, __lang_rt_Str* key, V value) { \
    if (!key) __lang_rt_fail(__LANG_RT_ERR_KEY, src, "dict key is nil"); \
    /* grow when load > ~0.66 */ \
    if ((d->len + 1) * 3 >= d->cap * 2) __lang_rt_dictstr_##NAME##_rehash(src, d, d->cap * 2); \
    uint64_t h = __lang_rt_hash_bytes_fnv1a(key->data, key->len); \
    int found = 0; \
    uint32_t slot = __lang_rt_dictstr_##NAME##_find_slot(d, h, key, &found); \
    __lang_rt_DictStrEntry_##NAME* ent = &d->e[slot]; \
    if (!found) { \
        ent->st = __LANG_RT_SLOT_FULL; \
        ent->hash = h; \
        ent->key = key; __lang_rt_str_retain(key); \
        VCLONE(ent->value, value); \
        d->len++; \
    } else { \
        VDROP(ent->value); \
        VCLONE(ent->value, value); \
    } \
} \
\
static inline int __lang_rt_dictstr_##NAME##_has(__lang_rt_Src src, __lang_rt_DictStr_##NAME* d, __lang_rt_Str* key) { \
    if (!key) return 0; \
    uint64_t h = __lang_rt_hash_bytes_fnv1a(key->data, key->len); \
    int found = 0; \
    (void)__lang_rt_dictstr_##NAME##_find_slot(d, h, key, &found); \
    return found; \
} \
\
static inline V __lang_rt_dictstr_##NAME##_get(__lang_rt_Src src, __lang_rt_DictStr_##NAME* d, __lang_rt_Str* key) { \
    if (!key) __lang_rt_key(src, "missing dict key"); \
    uint64_t h = __lang_rt_hash_bytes_fnv1a(key->data, key->len); \
    int found = 0; \
    uint32_t slot = __lang_rt_dictstr_##NAME##_find_slot(d, h, key, &found); \
    if (!found) __lang_rt_key(src, "missing dict key"); \
    return d->e[slot].value; \
} \
\
static inline int64_t __lang_rt_dictstr_##NAME##_len(__lang_rt_DictStr_##NAME* d) { return (int64_t)d->len; }
