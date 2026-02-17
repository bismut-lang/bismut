/*
 * string — C implementation for the string Bismut extern library.
 * String operations and type conversions.
 * Uses runtime headers already included in out.c.
 */

static __lang_rt_Str* __clib__string_concat(__lang_rt_Str* a, __lang_rt_Str* b) {
    __lang_rt_Src src = __LANG_RT_SRC("<string>", 0, 0);
    return __lang_rt_str_concat(src, a, b);
}

static __lang_rt_Str* __clib__string_substr(__lang_rt_Str* s, int64_t start, int64_t length) {
    __lang_rt_Src src = __LANG_RT_SRC("<string>", 0, 0);
    return __lang_rt_str_sub(src, s, start, length);
}

static int64_t __clib__string_find(__lang_rt_Str* s, __lang_rt_Str* sub) {
    return __lang_rt_str_find(s, sub);
}

static __lang_rt_Str* __clib__string_chr(int64_t code) {
    __lang_rt_Src src = __LANG_RT_SRC("<string>", 0, 0);
    return __lang_rt_str_chr(src, code);
}

static int64_t __clib__string_char_at(__lang_rt_Str* s, int64_t idx) {
    __lang_rt_Src src = __LANG_RT_SRC("<string>", 0, 0);
    return __lang_rt_str_get(src, s, idx);
}

static __lang_rt_Str* __clib__string_i64_to_str(int64_t n) {
    __lang_rt_Src src = __LANG_RT_SRC("<string>", 0, 0);
    return __lang_rt_i64_to_str(src, n);
}

static __lang_rt_Str* __clib__string_f64_to_str(double n) {
    __lang_rt_Src src = __LANG_RT_SRC("<string>", 0, 0);
    return __lang_rt_f64_to_str(src, n);
}

static __lang_rt_Str* __clib__string_bool_to_str(bool b) {
    __lang_rt_Src src = __LANG_RT_SRC("<string>", 0, 0);
    return __lang_rt_bool_to_str(src, b);
}

static int64_t __clib__string_str_to_i64(__lang_rt_Str* s) {
    __lang_rt_Src src = __LANG_RT_SRC("<string>", 0, 0);
    if (!s) __lang_rt_fail(__LANG_RT_ERR_PANIC, src, "str_to_i64: string is nil");
    const char* p = s->data;
    char* end;
    /* Handle 0b/0B binary and 0o/0O octal prefixes (not in C99 strtoll) */
    if (p[0] == '0' && (p[1] == 'b' || p[1] == 'B')) {
        long long val = strtoll(p + 2, &end, 2);
        return (int64_t)val;
    }
    if (p[0] == '0' && (p[1] == 'o' || p[1] == 'O')) {
        long long val = strtoll(p + 2, &end, 8);
        return (int64_t)val;
    }
    long long val = strtoll(p, &end, 0);
    return (int64_t)val;
}

static double __clib__string_str_to_f64(__lang_rt_Str* s) {
    __lang_rt_Src src = __LANG_RT_SRC("<string>", 0, 0);
    if (!s) __lang_rt_fail(__LANG_RT_ERR_PANIC, src, "str_to_f64: string is nil");
    char* end;
    double val = strtod(s->data, &end);
    return val;
}
