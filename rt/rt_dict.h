// __lang_rt_dict.h (C99) — generic macro template for Dict[K, V]
#pragma once
#include <stdint.h>
#include <string.h>
#include "rt_rc.h"
#include "rt_alloc.h"
#include "rt_str.h"
#include "rt_error.h"

// open addressing with tombstones
#ifndef __LANG_RT_SLOT_DEFINED
#define __LANG_RT_SLOT_DEFINED
typedef enum { __LANG_RT_SLOT_EMPTY=0, __LANG_RT_SLOT_FULL=1, __LANG_RT_SLOT_TOMB=2 } __lang_rt_SlotState;
#endif

// --- hashing primitives ---

static inline uint64_t __lang_rt_hash_bytes_fnv1a(const char* data, uint32_t len) {
    uint64_t h = 1469598103934665603ULL;
    for (uint32_t i = 0; i < len; i++) { h ^= (uint8_t)data[i]; h *= 1099511628211ULL; }
    return h ? h : 1ULL;
}

static inline uint64_t __lang_rt_hash_u64(uint64_t x) {
    x ^= x >> 33; x *= 0xff51afd7ed558ccdULL; x ^= x >> 33; x *= 0xc4ceb9fe1a85ec53ULL; x ^= x >> 33;
    return x ? x : 1ULL;
}

// --- key-type helpers (used as macro arguments) ---

// str keys: hash, eq, clone, drop
#define __LANG_RT_KHASH_STR(k) __lang_rt_hash_bytes_fnv1a((k)->data, (k)->len)
#define __LANG_RT_KEQ_STR(a, b) __lang_rt_str_eq((a), (b))
#define __LANG_RT_KCLONE_STR(dst, src) do { (dst) = (src); __lang_rt_str_retain((src)); } while(0)
#define __LANG_RT_KDROP_STR(k) __lang_rt_str_release((k))
#define __LANG_RT_KNULL_STR(k) (!(k))

// integer keys: hash, eq, clone, drop (works for all int types and bool)
#define __LANG_RT_KHASH_INT(k) __lang_rt_hash_u64((uint64_t)(k))
#define __LANG_RT_KEQ_INT(a, b) ((a) == (b))
#define __LANG_RT_KCLONE_INT(dst, src) do { (dst) = (src); } while(0)
#define __LANG_RT_KDROP_INT(k) ((void)(k))
#define __LANG_RT_KNULL_INT(k) (0)

// --- generic dict macro ---
// NAME = tag (e.g. STR_I64, I64_STR)
// K = C key type
// V = C value type
// KHASH(k) -> uint64_t hash
// KEQ(a,b) -> int equality
// KCLONE(dst,src) -> clone key (retain for ref types)
// KDROP(k) -> drop key (release for ref types)
// KNULL(k) -> int, true if key is null (for str keys), always false for ints
// VCLONE(dst,src) -> clone value
// VDROP(v) -> drop value

#define __LANG_RT_DICT_DEFINE(NAME, K, V, KHASH, KEQ, KCLONE, KDROP, KNULL, VCLONE, VDROP) \
typedef struct __lang_rt_DictEntry_##NAME { \
    __lang_rt_SlotState st; \
    uint64_t hash; \
    K key; \
    V value; \
} __lang_rt_DictEntry_##NAME; \
\
typedef struct __lang_rt_Dict_##NAME { \
    __lang_rt_Rc rc; \
    uint32_t len; \
    uint32_t cap; \
    __lang_rt_DictEntry_##NAME* e; \
} __lang_rt_Dict_##NAME; \
\
static inline void __lang_rt_dict_##NAME##_dtor(void* obj) { \
    __lang_rt_Dict_##NAME* d = (__lang_rt_Dict_##NAME*)obj; \
    for (uint32_t i = 0; i < d->cap; i++) { \
        if (d->e[i].st == __LANG_RT_SLOT_FULL) { \
            KDROP(d->e[i].key); \
            VDROP(d->e[i].value); \
        } \
    } \
    free(d->e); \
    free(d); \
} \
\
static inline __lang_rt_Dict_##NAME* __lang_rt_dict_##NAME##_new(__lang_rt_Src src) { \
    __lang_rt_Dict_##NAME* d = (__lang_rt_Dict_##NAME*)__lang_rt_malloc(src, sizeof(__lang_rt_Dict_##NAME)); \
    __lang_rt_rc_init(&d->rc); \
    d->len = 0; \
    d->cap = 16; \
    d->e = (__lang_rt_DictEntry_##NAME*)__lang_rt_calloc(src, d->cap, sizeof(__lang_rt_DictEntry_##NAME)); \
    return d; \
} \
\
static inline void __lang_rt_dict_##NAME##_retain(__lang_rt_Dict_##NAME* d) { __lang_rt_retain(d); } \
static inline void __lang_rt_dict_##NAME##_release(__lang_rt_Dict_##NAME* d) { __lang_rt_release(d, __lang_rt_dict_##NAME##_dtor); } \
\
static inline uint32_t __lang_rt_dict_##NAME##_find_slot(__lang_rt_Dict_##NAME* d, uint64_t h, K key, int* found) { \
    uint32_t mask = d->cap - 1; \
    uint32_t i = (uint32_t)(h) & mask; \
    uint32_t first_tomb = UINT32_MAX; \
    for (;;) { \
        __lang_rt_DictEntry_##NAME* ent = &d->e[i]; \
        if (ent->st == __LANG_RT_SLOT_EMPTY) { \
            *found = 0; \
            return (first_tomb != UINT32_MAX) ? first_tomb : i; \
        } \
        if (ent->st == __LANG_RT_SLOT_TOMB) { \
            if (first_tomb == UINT32_MAX) first_tomb = i; \
        } else { \
            if (ent->hash == h && KEQ(ent->key, key)) { \
                *found = 1; \
                return i; \
            } \
        } \
        i = (i + 1) & mask; \
    } \
} \
\
static inline void __lang_rt_dict_##NAME##_rehash(__lang_rt_Src src, __lang_rt_Dict_##NAME* d, uint32_t new_cap) { \
    __lang_rt_DictEntry_##NAME* old = d->e; \
    uint32_t old_cap = d->cap; \
    d->cap = new_cap; \
    d->e = (__lang_rt_DictEntry_##NAME*)__lang_rt_calloc(src, d->cap, sizeof(__lang_rt_DictEntry_##NAME)); \
    d->len = 0; \
    for (uint32_t i = 0; i < old_cap; i++) { \
        if (old[i].st == __LANG_RT_SLOT_FULL) { \
            int found = 0; \
            uint32_t slot = __lang_rt_dict_##NAME##_find_slot(d, old[i].hash, old[i].key, &found); \
            __lang_rt_DictEntry_##NAME* ent = &d->e[slot]; \
            ent->st = __LANG_RT_SLOT_FULL; \
            ent->hash = old[i].hash; \
            ent->key = old[i].key; \
            ent->value = old[i].value; \
            d->len++; \
        } \
    } \
    free(old); \
} \
\
static inline void __lang_rt_dict_##NAME##_set(__lang_rt_Src src, __lang_rt_Dict_##NAME* d, K key, V value) { \
    if (KNULL(key)) __lang_rt_fail(__LANG_RT_ERR_KEY, src, "dict key is nil"); \
    if ((d->len + 1) * 3 >= d->cap * 2) __lang_rt_dict_##NAME##_rehash(src, d, d->cap * 2); \
    uint64_t h = KHASH(key); \
    int found = 0; \
    uint32_t slot = __lang_rt_dict_##NAME##_find_slot(d, h, key, &found); \
    __lang_rt_DictEntry_##NAME* ent = &d->e[slot]; \
    if (!found) { \
        ent->st = __LANG_RT_SLOT_FULL; \
        ent->hash = h; \
        KCLONE(ent->key, key); \
        VCLONE(ent->value, value); \
        d->len++; \
    } else { \
        VDROP(ent->value); \
        VCLONE(ent->value, value); \
    } \
} \
\
static inline int __lang_rt_dict_##NAME##_has(__lang_rt_Src src, __lang_rt_Dict_##NAME* d, K key) { \
    (void)src; \
    uint64_t h = KHASH(key); \
    int found = 0; \
    (void)__lang_rt_dict_##NAME##_find_slot(d, h, key, &found); \
    return found; \
} \
\
static inline V __lang_rt_dict_##NAME##_get(__lang_rt_Src src, __lang_rt_Dict_##NAME* d, K key) { \
    uint64_t h = KHASH(key); \
    int found = 0; \
    uint32_t slot = __lang_rt_dict_##NAME##_find_slot(d, h, key, &found); \
    if (!found) __lang_rt_key(src, "missing dict key"); \
    return d->e[slot].value; \
} \
\
static inline int64_t __lang_rt_dict_##NAME##_len(__lang_rt_Dict_##NAME* d) { return (int64_t)d->len; }

// --- generic keys() macro ---
// KLISTTAG = list tag for key type (e.g. STR, I64)

#define __LANG_RT_DICT_KEYS_DEFINE(NAME, KLISTTAG) \
static inline __lang_rt_List_##KLISTTAG* __lang_rt_dict_##NAME##_keys(__lang_rt_Src src, __lang_rt_Dict_##NAME* d) { \
    __lang_rt_List_##KLISTTAG* out = __lang_rt_list_##KLISTTAG##_new(src); \
    for (uint32_t i = 0; i < d->cap; i++) { \
        if (d->e[i].st == __LANG_RT_SLOT_FULL) { \
            __lang_rt_list_##KLISTTAG##_push(src, out, d->e[i].key); \
        } \
    } \
    return out; \
}
