/*
 * tcc — C implementation for the tcc Bismut extern library.
 * Embedded TCC compiler via libtcc. Linux/Windows only.
 * Uses runtime headers already included in out.c.
 */

#include <libtcc.h>

static TCCState* __clib__tcc_new(void) {
    return tcc_new();
}

static void __clib__tcc_destroy(TCCState* s) {
    if (s) tcc_delete(s);
}

static int64_t __clib__tcc_set_output_exe(TCCState* s) {
    return (int64_t)tcc_set_output_type(s, TCC_OUTPUT_EXE);
}

static void __clib__tcc_set_options(TCCState* s, __lang_rt_Str* opts) {
    tcc_set_options(s, opts->data);
}

static int64_t __clib__tcc_add_include_path(TCCState* s, __lang_rt_Str* path) {
    return (int64_t)tcc_add_include_path(s, path->data);
}

static int64_t __clib__tcc_add_library_path(TCCState* s, __lang_rt_Str* path) {
    return (int64_t)tcc_add_library_path(s, path->data);
}

static int64_t __clib__tcc_add_library(TCCState* s, __lang_rt_Str* name) {
    return (int64_t)tcc_add_library(s, name->data);
}

static int64_t __clib__tcc_compile_string(TCCState* s, __lang_rt_Str* code) {
    return (int64_t)tcc_compile_string(s, code->data);
}

static int64_t __clib__tcc_output_file(TCCState* s, __lang_rt_Str* filename) {
    return (int64_t)tcc_output_file(s, filename->data);
}

static void __clib__tcc_set_lib_path(TCCState* s, __lang_rt_Str* path) {
    tcc_set_lib_path(s, path->data);
}
