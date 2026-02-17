/*
 * filesystem — C implementation for the filesystem Bismut extern library.
 * File system operations. Cross-platform (Linux, Mac, Windows).
 * Uses runtime headers already included in out.c.
 */

static __lang_rt_Str* __clib__filesystem_read(__lang_rt_Str* path) {
    __lang_rt_Src src = __LANG_RT_SRC("<filesystem>", 0, 0);
    return __lang_rt_file_read(src, path);
}

static void __clib__filesystem_write(__lang_rt_Str* path, __lang_rt_Str* content) {
    __lang_rt_Src src = __LANG_RT_SRC("<filesystem>", 0, 0);
    __lang_rt_file_write(src, path, content);
}

static void __clib__filesystem_append(__lang_rt_Str* path, __lang_rt_Str* content) {
    __lang_rt_Src src = __LANG_RT_SRC("<filesystem>", 0, 0);
    __lang_rt_file_append(src, path, content);
}

static bool __clib__filesystem_exists(__lang_rt_Str* path) {
    return (bool)__lang_rt_file_exists(path);
}

static bool __clib__filesystem_dir_exists(__lang_rt_Str* path) {
    return (bool)__lang_rt_dir_exists(path);
}
