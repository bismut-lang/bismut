// __lang_rt_rc.h (C99) — tiny intrusive refcounting
#pragma once
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include "rt_error.h"

typedef struct __lang_rt_Rc {
    uint32_t rc;
} __lang_rt_Rc;

#define __LANG_RT_RC_IMMORTAL UINT32_MAX

// ─── Debug leak detector ─────────────────────────────────────────────
// When __LANG_RT_DEBUG_LEAKS is defined, every heap allocation is tracked
// in a linked list. At program exit, surviving objects are reported.
// Zero overhead in release builds.

#ifdef __LANG_RT_DEBUG_LEAKS

typedef struct __lang_rt_LeakNode {
    struct __lang_rt_LeakNode* prev;
    struct __lang_rt_LeakNode* next;
    void* obj;              // pointer to the tracked object
    const char* type_name;  // e.g. "Node", "List[i64]"
    const char* file;       // allocation site
    int32_t line;
    int32_t col;
} __lang_rt_LeakNode;

// Global doubly-linked list head (sentinel)
static __lang_rt_LeakNode __lang_rt_leak_head = {
    &__lang_rt_leak_head, &__lang_rt_leak_head,
    NULL, NULL, NULL, 0, 0
};
static int __lang_rt_leak_atexit_registered = 0;

static void __lang_rt_leak_report(void) {
    __lang_rt_LeakNode* n = __lang_rt_leak_head.next;
    int count = 0;
    while (n != &__lang_rt_leak_head) {
        count++;
        n = n->next;
    }
    if (count == 0) return;
    fprintf(stderr, "\n=== leak detector: %d object(s) leaked ===\n", count);
    n = __lang_rt_leak_head.next;
    while (n != &__lang_rt_leak_head) {
        if (n->file && n->line > 0) {
            fprintf(stderr, "  leak: %s allocated at %s:%d (refcount: %u)\n",
                    n->type_name ? n->type_name : "?",
                    n->file, (int)n->line,
                    (unsigned)((__lang_rt_Rc*)n->obj)->rc);
        } else {
            fprintf(stderr, "  leak: %s (refcount: %u)\n",
                    n->type_name ? n->type_name : "?",
                    (unsigned)((__lang_rt_Rc*)n->obj)->rc);
        }
        n = n->next;
    }
    fprintf(stderr, "  hint: if these are self-referential types, set cyclic fields to None before they go out of scope\n");
    fprintf(stderr, "=== end leak report ===\n");
}

static inline void __lang_rt_leak_track(void* obj, const char* type_name, const char* file, int32_t line, int32_t col) {
    if (!__lang_rt_leak_atexit_registered) {
        atexit(__lang_rt_leak_report);
        __lang_rt_leak_atexit_registered = 1;
    }
    __lang_rt_LeakNode* node = (__lang_rt_LeakNode*)malloc(sizeof(__lang_rt_LeakNode));
    if (!node) return;  // OOM in tracker — silently skip
    node->obj = obj;
    node->type_name = type_name;
    node->file = file;
    node->line = line;
    node->col = col;
    // Insert after head
    node->next = __lang_rt_leak_head.next;
    node->prev = &__lang_rt_leak_head;
    __lang_rt_leak_head.next->prev = node;
    __lang_rt_leak_head.next = node;
}

static inline void __lang_rt_leak_untrack(void* obj) {
    __lang_rt_LeakNode* n = __lang_rt_leak_head.next;
    while (n != &__lang_rt_leak_head) {
        if (n->obj == obj) {
            n->prev->next = n->next;
            n->next->prev = n->prev;
            free(n);
            return;
        }
        n = n->next;
    }
}

#define __LANG_RT_LEAK_TRACK(obj, type, file, line, col) \
    __lang_rt_leak_track((obj), (type), (file), (line), (col))
#define __LANG_RT_LEAK_UNTRACK(obj) __lang_rt_leak_untrack((obj))

#else  /* !__LANG_RT_DEBUG_LEAKS */

#define __LANG_RT_LEAK_TRACK(obj, type, file, line, col) ((void)0)
#define __LANG_RT_LEAK_UNTRACK(obj) ((void)0)

#endif /* __LANG_RT_DEBUG_LEAKS */

// ─── Core refcounting ────────────────────────────────────────────────

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
