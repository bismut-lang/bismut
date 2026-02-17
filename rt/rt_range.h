// __lang_rt_range.h (C99) — range() builtin returning __lang_rt_List_I64
#pragma once
#include "rt_error.h"

// Forward-declared; user must have __LANG_RT_LIST_DEFINE(I64, ...) instantiated before calling.
// __lang_rt_range builds a __lang_rt_List_I64* with values [start, start+step, start+2*step, ...) < end (when step>0).
// step<0: counts down while > end.  step==0 is an error.

static inline __lang_rt_List_I64* __lang_rt_range(__lang_rt_Src src, int64_t start, int64_t end, int64_t step) {
    if (step == 0) __lang_rt_fail(__LANG_RT_ERR_PANIC, src, "range(): step must not be 0");
    __lang_rt_List_I64* a = __lang_rt_list_I64_new(src);
    if (step > 0) {
        for (int64_t v = start; v < end; v += step) {
            __lang_rt_list_I64_push(src, a, v);
        }
    } else {
        for (int64_t v = start; v > end; v += step) {
            __lang_rt_list_I64_push(src, a, v);
        }
    }
    return a;
}
