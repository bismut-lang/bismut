// __lang_rt_file.h (C99) — cross-platform file I/O
#pragma once
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "rt_error.h"
#include "rt_str.h"

// Read entire file into a __lang_rt_Str. Returns NULL on failure.
static inline __lang_rt_Str* __lang_rt_file_read(__lang_rt_Src src, __lang_rt_Str* path) {
    if (!path) __lang_rt_fail(__LANG_RT_ERR_IO, src, "file_read: path is nil");
    FILE* f = fopen(path->data, "rb");
    if (!f) __lang_rt_fail(__LANG_RT_ERR_IO, src, "file_read: cannot open '%s'", path->data);
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    char* buf = (char*)malloc((size_t)sz + 1);
    if (!buf) { fclose(f); __lang_rt_fail(__LANG_RT_ERR_ALLOC, src, "file_read: out of memory"); }
    size_t got = fread(buf, 1, (size_t)sz, f);
    fclose(f);
    buf[got] = 0;
    __lang_rt_Str* s = __lang_rt_str_new_bytes(src, buf, (uint32_t)got);
    free(buf);
    return s;
}

// Write string to file. Overwrites.
static inline void __lang_rt_file_write(__lang_rt_Src src, __lang_rt_Str* path, __lang_rt_Str* content) {
    if (!path) __lang_rt_fail(__LANG_RT_ERR_IO, src, "file_write: path is nil");
    if (!content) __lang_rt_fail(__LANG_RT_ERR_IO, src, "file_write: content is nil");
    FILE* f = fopen(path->data, "wb");
    if (!f) __lang_rt_fail(__LANG_RT_ERR_IO, src, "file_write: cannot open '%s'", path->data);
    fwrite(content->data, 1, content->len, f);
    fclose(f);
}

// Append string to file.
static inline void __lang_rt_file_append(__lang_rt_Src src, __lang_rt_Str* path, __lang_rt_Str* content) {
    if (!path) __lang_rt_fail(__LANG_RT_ERR_IO, src, "file_append: path is nil");
    if (!content) __lang_rt_fail(__LANG_RT_ERR_IO, src, "file_append: content is nil");
    FILE* f = fopen(path->data, "ab");
    if (!f) __lang_rt_fail(__LANG_RT_ERR_IO, src, "file_append: cannot open '%s'", path->data);
    fwrite(content->data, 1, content->len, f);
    fclose(f);
}

// Check if file exists (cross-platform C99)
static inline int __lang_rt_file_exists(__lang_rt_Str* path) {
    if (!path) return 0;
    FILE* f = fopen(path->data, "rb");
    if (f) { fclose(f); return 1; }
    return 0;
}

// Check if directory exists
#ifdef _WIN32
  #include <windows.h>
  static inline int __lang_rt_dir_exists(__lang_rt_Str* path) {
      if (!path) return 0;
      DWORD attr = GetFileAttributesA(path->data);
      return (attr != INVALID_FILE_ATTRIBUTES && (attr & FILE_ATTRIBUTE_DIRECTORY));
  }
#else
  #include <sys/stat.h>
  static inline int __lang_rt_dir_exists(__lang_rt_Str* path) {
      if (!path) return 0;
      struct stat st;
      if (stat(path->data, &st) != 0) return 0;
      return S_ISDIR(st.st_mode);
  }
#endif
