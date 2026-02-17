/*
 * os — C implementation for the os Bismut extern library.
 * Process execution, time, and system access. Cross-platform (Linux, Mac, Windows).
 * Uses runtime headers already included in out.c.
 */

// argc/argv stored by main() — declared in generated out.c
extern int __lang_rt_argc_;
extern char** __lang_rt_argv_;

static int64_t __clib__os_exec(__lang_rt_Str* cmd) {
    __lang_rt_Src src = __LANG_RT_SRC("<os>", 0, 0);
    return __lang_rt_exec(src, cmd);
}

static double __clib__os_time_now(void) {
    return __lang_rt_time_now();
}

static void __clib__os_exit(int64_t code) {
    exit((int)code);
}

static int64_t __clib__os_argc(void) {
    return (int64_t)__lang_rt_argc_;
}

static __lang_rt_Str* __clib__os_argv(int64_t index) {
    __lang_rt_Src src = __LANG_RT_SRC("<os>", 0, 0);
    if (index < 0 || index >= __lang_rt_argc_) {
        __lang_rt_fail(__LANG_RT_ERR_OOB, src, "argv: index out of range");
    }
    return __lang_rt_str_new_cstr(src, __lang_rt_argv_[(int)index]);
}
