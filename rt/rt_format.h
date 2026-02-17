// __lang_rt_format.h (C99) — format() builtin
#pragma once
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <inttypes.h>
#include "rt_str.h"
#include "rt_sb.h"

typedef enum {
    __LANG_RT_FMT_I64,
    __LANG_RT_FMT_U64,
    __LANG_RT_FMT_F64,
    __LANG_RT_FMT_BOOL,
    __LANG_RT_FMT_STR
} __lang_rt_FmtTag;

typedef struct {
    __lang_rt_FmtTag tag;
    union {
        int64_t  i;
        uint64_t u;
        double   f;
        int      b;
        __lang_rt_Str*   s;
    } val;
} __lang_rt_FmtArg;

static inline __lang_rt_Str* __lang_rt_format(__lang_rt_Src src, __lang_rt_Str* fmt, __lang_rt_FmtArg* args, int nargs) {
    if (!fmt) __lang_rt_fail(__LANG_RT_ERR_PANIC, src, "format: format string is nil");
    __lang_rt_Sb* sb = __lang_rt_sb_new(src);
    const char* p = fmt->data;
    const char* end = p + fmt->len;
    int ai = 0;

    while (p < end) {
        if (*p == '{') {
            if (p + 1 < end && p[1] == '{') {
                __lang_rt_sb_append_bytes(src, sb, "{", 1);
                p += 2;
                continue;
            }
            if (p + 1 < end && p[1] == '}') {
                if (ai >= nargs) __lang_rt_fail(__LANG_RT_ERR_PANIC, src, "format: not enough arguments");
                __lang_rt_FmtArg* a = &args[ai++];
                switch (a->tag) {
                    case __LANG_RT_FMT_I64:  __lang_rt_sb_append_i64(src, sb, a->val.i); break;
                    case __LANG_RT_FMT_U64: {
                        char buf[32];
                        int n = snprintf(buf, sizeof(buf), "%" PRIu64, a->val.u);
                        __lang_rt_sb_append_bytes(src, sb, buf, (uint32_t)n);
                        break;
                    }
                    case __LANG_RT_FMT_F64:  __lang_rt_sb_append_f64(src, sb, a->val.f); break;
                    case __LANG_RT_FMT_BOOL: __lang_rt_sb_append_bool(src, sb, a->val.b); break;
                    case __LANG_RT_FMT_STR:  __lang_rt_sb_append_str(src, sb, a->val.s); break;
                }
                p += 2;
                continue;
            }
            __lang_rt_sb_append_bytes(src, sb, "{", 1);
            p++;
        } else if (*p == '}') {
            if (p + 1 < end && p[1] == '}') {
                __lang_rt_sb_append_bytes(src, sb, "}", 1);
                p += 2;
                continue;
            }
            __lang_rt_sb_append_bytes(src, sb, "}", 1);
            p++;
        } else {
            const char* start = p;
            while (p < end && *p != '{' && *p != '}') p++;
            __lang_rt_sb_append_bytes(src, sb, start, (uint32_t)(p - start));
        }
    }

    __lang_rt_Str* result = __lang_rt_sb_build(src, sb);
    __lang_rt_sb_release(sb);
    return result;
}
