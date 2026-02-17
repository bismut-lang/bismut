// __lang_rt_rc.h (C99) — tiny intrusive refcounting
#pragma once
#include <stdint.h>
#include <stdlib.h>
#include "rt_error.h"

typedef struct __lang_rt_Rc {
    uint32_t rc;
} __lang_rt_Rc;

#define __LANG_RT_RC_IMMORTAL UINT32_MAX

static inline void __lang_rt_rc_init(__lang_rt_Rc* h) { h->rc = 1; }

static inline void __lang_rt_retain(void* obj) {
    if (!obj) return;
    __lang_rt_Rc* h = (__lang_rt_Rc*)obj;
    if (h->rc == __LANG_RT_RC_IMMORTAL) return;
    h->rc++;
}

typedef void (*__lang_rt_DtorFn)(void* obj);

// Suppress false positive: gcc -O2 inlines the dtor through release and sees
// that a static string literal *could* flow to free(), even though the immortal
// refcount guard (rc == UINT32_MAX) prevents it at runtime.
#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wfree-nonheap-object"
#endif

static inline void __lang_rt_release(void* obj, __lang_rt_DtorFn dtor) {
    if (!obj) return;
    __lang_rt_Rc* h = (__lang_rt_Rc*)obj;
    if (h->rc == __LANG_RT_RC_IMMORTAL) return;
    if (h->rc == 0) return;
    h->rc--;
    if (h->rc == 0) dtor(obj);
}

#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC diagnostic pop
#endif
