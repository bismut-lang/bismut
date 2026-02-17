/*
 * stringbuilder — C implementation for the stringbuilder Bismut extern library.
 * StringBuilder as opaque type wrapping __lang_rt_Sb.
 * Uses runtime headers already included in out.c.
 */

static __lang_rt_Sb* __clib__stringbuilder_new(void) {
    __lang_rt_Src src = __LANG_RT_SRC("<stringbuilder>", 0, 0);
    return __lang_rt_sb_new(src);
}

static void __clib__stringbuilder_destroy(__lang_rt_Sb* sb) {
    __lang_rt_sb_dtor(sb);
}

static void __clib__stringbuilder_append_str(__lang_rt_Sb* sb, __lang_rt_Str* s) {
    __lang_rt_Src src = __LANG_RT_SRC("<stringbuilder>", 0, 0);
    __lang_rt_sb_append_str(src, sb, s);
}

static void __clib__stringbuilder_append_i64(__lang_rt_Sb* sb, int64_t n) {
    __lang_rt_Src src = __LANG_RT_SRC("<stringbuilder>", 0, 0);
    __lang_rt_sb_append_i64(src, sb, n);
}

static void __clib__stringbuilder_append_f64(__lang_rt_Sb* sb, double n) {
    __lang_rt_Src src = __LANG_RT_SRC("<stringbuilder>", 0, 0);
    __lang_rt_sb_append_f64(src, sb, n);
}

static void __clib__stringbuilder_append_bool(__lang_rt_Sb* sb, bool b) {
    __lang_rt_Src src = __LANG_RT_SRC("<stringbuilder>", 0, 0);
    __lang_rt_sb_append_bool(src, sb, (int)b);
}

static __lang_rt_Str* __clib__stringbuilder_build(__lang_rt_Sb* sb) {
    __lang_rt_Src src = __LANG_RT_SRC("<stringbuilder>", 0, 0);
    return __lang_rt_sb_build(src, sb);
}

static void __clib__stringbuilder_clear(__lang_rt_Sb* sb) {
    __lang_rt_Src src = __LANG_RT_SRC("<stringbuilder>", 0, 0);
    __lang_rt_sb_clear(src, sb);
}

static int64_t __clib__stringbuilder_length(__lang_rt_Sb* sb) {
    return __lang_rt_sb_len(sb);
}
