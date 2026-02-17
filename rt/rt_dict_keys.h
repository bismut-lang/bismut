// __lang_rt_dict_keys.h (C99) — keys() for DictStr types
// Requires __LANG_RT_LIST_DEFINE(STR, ...) and __LANG_RT_DICT_STR_DEFINE(NAME, ...) to be instantiated first.
// Include this AFTER both list and dict instantiations in generated code.
#pragma once

#define __LANG_RT_DICT_STR_KEYS_DEFINE(NAME) \
static inline __lang_rt_List_STR* __lang_rt_dictstr_##NAME##_keys(__lang_rt_Src src, __lang_rt_DictStr_##NAME* d) { \
    __lang_rt_List_STR* out = __lang_rt_list_STR_new(src); \
    for (uint32_t i = 0; i < d->cap; i++) { \
        if (d->e[i].st == __LANG_RT_SLOT_FULL) { \
            __lang_rt_list_STR_push(src, out, d->e[i].key); \
        } \
    } \
    return out; \
}
