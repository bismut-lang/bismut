// __lang_rt_print.h (C99) — small print helpers
#pragma once
#include <stdio.h>
#include <inttypes.h>
#include "rt_str.h"

static inline void __lang_rt_print_i8(int8_t x)   { printf("%" PRId8, x); }
static inline void __lang_rt_print_i16(int16_t x)  { printf("%" PRId16, x); }
static inline void __lang_rt_print_i32(int32_t x)  { printf("%" PRId32, x); }
static inline void __lang_rt_print_i64(int64_t x)  { printf("%" PRId64, x); }
static inline void __lang_rt_print_u8(uint8_t x)   { printf("%" PRIu8, x); }
static inline void __lang_rt_print_u16(uint16_t x)  { printf("%" PRIu16, x); }
static inline void __lang_rt_print_u32(uint32_t x)  { printf("%" PRIu32, x); }
static inline void __lang_rt_print_u64(uint64_t x)  { printf("%" PRIu64, x); }
static inline void __lang_rt_print_f32(float x)    { printf("%.9g", x); }
static inline void __lang_rt_print_f64(double x)   { printf("%.17g", x); }
static inline void __lang_rt_print_bool(int b)    { fputs(b ? "true" : "false", stdout); }
static inline void __lang_rt_print_str(__lang_rt_Str* s)  { if (!s) fputs("nil", stdout); else fwrite(s->data, 1, s->len, stdout); }
static inline void __lang_rt_print_ln(void)       { fputc('\n', stdout); }
