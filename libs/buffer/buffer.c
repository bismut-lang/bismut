/*
 * buffer — byte buffer C library for Bismut.
 * Growable byte array with separate write (append) and read (cursor) positions.
 * Supports explicit endianness for all integer and float types.
 */

#include <string.h>
#include <stdlib.h>

typedef struct {
    uint8_t* data;
    uint32_t len;       /* bytes written (write position) */
    uint32_t cap;       /* allocated capacity */
    uint32_t pos;       /* read cursor */
} __clib__buffer_Buffer;

/* ── helpers ──────────────────────────────────────────────────────── */

static inline __lang_rt_Src __clib__buffer_src(void) {
    return (__lang_rt_Src){"<buffer>", 0, 0};
}

static void __clib__buffer_grow(__clib__buffer_Buffer* buf, uint32_t need) {
    if (buf->cap >= need) return;
    uint32_t cap = buf->cap;
    while (cap < need) cap *= 2;
    buf->data = (uint8_t*)__lang_rt_realloc(__clib__buffer_src(), buf->data, cap);
    buf->cap = cap;
}

static void __clib__buffer_check_read(__clib__buffer_Buffer* buf, uint32_t n) {
    if (buf->pos + n > buf->len) {
        __lang_rt_fail(__LANG_RT_ERR_PANIC, __clib__buffer_src(), "buffer: read past end");
    }
}

/* ── constructor / destructor ─────────────────────────────────────── */

static __clib__buffer_Buffer* __clib__buffer_new(void) {
    __clib__buffer_Buffer* buf = (__clib__buffer_Buffer*)__lang_rt_malloc(__clib__buffer_src(), sizeof(__clib__buffer_Buffer));
    buf->cap = 256;
    buf->len = 0;
    buf->pos = 0;
    buf->data = (uint8_t*)__lang_rt_malloc(__clib__buffer_src(), buf->cap);
    return buf;
}

static __clib__buffer_Buffer* __clib__buffer_from_str(__lang_rt_Str* s) {
    __clib__buffer_Buffer* buf = __clib__buffer_new();
    if (s && s->len > 0) {
        __clib__buffer_grow(buf, s->len);
        memcpy(buf->data, s->data, s->len);
        buf->len = s->len;
    }
    return buf;
}

static void __clib__buffer_destroy(__clib__buffer_Buffer* buf) {
    free(buf->data);
    free(buf);
}

/* ── write: single byte / bytes ───────────────────────────────────── */

static void __clib__buffer_write_byte(__clib__buffer_Buffer* buf, int64_t val) {
    __clib__buffer_grow(buf, buf->len + 1);
    buf->data[buf->len++] = (uint8_t)(val & 0xFF);
}

static void __clib__buffer_write_bytes(__clib__buffer_Buffer* buf, __lang_rt_Str* s) {
    if (!s || s->len == 0) return;
    __clib__buffer_grow(buf, buf->len + s->len);
    memcpy(buf->data + buf->len, s->data, s->len);
    buf->len += s->len;
}

static void __clib__buffer_write_str_zt(__clib__buffer_Buffer* buf, __lang_rt_Str* s) {
    if (s && s->len > 0) {
        __clib__buffer_grow(buf, buf->len + s->len + 1);
        memcpy(buf->data + buf->len, s->data, s->len);
        buf->len += s->len;
    } else {
        __clib__buffer_grow(buf, buf->len + 1);
    }
    buf->data[buf->len++] = 0;
}

/* ── write: integers — little endian ──────────────────────────────── */

static void __clib__buffer_write_i16_le(__clib__buffer_Buffer* buf, int64_t val) {
    __clib__buffer_grow(buf, buf->len + 2);
    buf->data[buf->len++] = (uint8_t)(val & 0xFF);
    buf->data[buf->len++] = (uint8_t)((val >> 8) & 0xFF);
}

static void __clib__buffer_write_i32_le(__clib__buffer_Buffer* buf, int64_t val) {
    __clib__buffer_grow(buf, buf->len + 4);
    buf->data[buf->len++] = (uint8_t)(val & 0xFF);
    buf->data[buf->len++] = (uint8_t)((val >> 8) & 0xFF);
    buf->data[buf->len++] = (uint8_t)((val >> 16) & 0xFF);
    buf->data[buf->len++] = (uint8_t)((val >> 24) & 0xFF);
}

static void __clib__buffer_write_i64_le(__clib__buffer_Buffer* buf, int64_t val) {
    __clib__buffer_grow(buf, buf->len + 8);
    for (int i = 0; i < 8; i++) {
        buf->data[buf->len++] = (uint8_t)((val >> (i * 8)) & 0xFF);
    }
}

/* ── write: integers — big endian ─────────────────────────────────── */

static void __clib__buffer_write_i16_be(__clib__buffer_Buffer* buf, int64_t val) {
    __clib__buffer_grow(buf, buf->len + 2);
    buf->data[buf->len++] = (uint8_t)((val >> 8) & 0xFF);
    buf->data[buf->len++] = (uint8_t)(val & 0xFF);
}

static void __clib__buffer_write_i32_be(__clib__buffer_Buffer* buf, int64_t val) {
    __clib__buffer_grow(buf, buf->len + 4);
    buf->data[buf->len++] = (uint8_t)((val >> 24) & 0xFF);
    buf->data[buf->len++] = (uint8_t)((val >> 16) & 0xFF);
    buf->data[buf->len++] = (uint8_t)((val >> 8) & 0xFF);
    buf->data[buf->len++] = (uint8_t)(val & 0xFF);
}

static void __clib__buffer_write_i64_be(__clib__buffer_Buffer* buf, int64_t val) {
    __clib__buffer_grow(buf, buf->len + 8);
    for (int i = 7; i >= 0; i--) {
        buf->data[buf->len++] = (uint8_t)((val >> (i * 8)) & 0xFF);
    }
}

/* ── write: floats ────────────────────────────────────────────────── */

static void __clib__buffer_write_f32_le(__clib__buffer_Buffer* buf, double val) {
    float f = (float)val;
    uint32_t u;
    memcpy(&u, &f, 4);
    __clib__buffer_grow(buf, buf->len + 4);
    buf->data[buf->len++] = (uint8_t)(u & 0xFF);
    buf->data[buf->len++] = (uint8_t)((u >> 8) & 0xFF);
    buf->data[buf->len++] = (uint8_t)((u >> 16) & 0xFF);
    buf->data[buf->len++] = (uint8_t)((u >> 24) & 0xFF);
}

static void __clib__buffer_write_f32_be(__clib__buffer_Buffer* buf, double val) {
    float f = (float)val;
    uint32_t u;
    memcpy(&u, &f, 4);
    __clib__buffer_grow(buf, buf->len + 4);
    buf->data[buf->len++] = (uint8_t)((u >> 24) & 0xFF);
    buf->data[buf->len++] = (uint8_t)((u >> 16) & 0xFF);
    buf->data[buf->len++] = (uint8_t)((u >> 8) & 0xFF);
    buf->data[buf->len++] = (uint8_t)(u & 0xFF);
}

static void __clib__buffer_write_f64_le(__clib__buffer_Buffer* buf, double val) {
    uint64_t u;
    memcpy(&u, &val, 8);
    __clib__buffer_grow(buf, buf->len + 8);
    for (int i = 0; i < 8; i++) {
        buf->data[buf->len++] = (uint8_t)((u >> (i * 8)) & 0xFF);
    }
}

static void __clib__buffer_write_f64_be(__clib__buffer_Buffer* buf, double val) {
    uint64_t u;
    memcpy(&u, &val, 8);
    __clib__buffer_grow(buf, buf->len + 8);
    for (int i = 7; i >= 0; i--) {
        buf->data[buf->len++] = (uint8_t)((u >> (i * 8)) & 0xFF);
    }
}

/* ── read: single byte ────────────────────────────────────────────── */

static int64_t __clib__buffer_read_u8(__clib__buffer_Buffer* buf) {
    __clib__buffer_check_read(buf, 1);
    return (int64_t)buf->data[buf->pos++];
}

static int64_t __clib__buffer_read_i8(__clib__buffer_Buffer* buf) {
    __clib__buffer_check_read(buf, 1);
    return (int64_t)(int8_t)buf->data[buf->pos++];
}

static __lang_rt_Str* __clib__buffer_read_bytes(__clib__buffer_Buffer* buf, int64_t n) {
    if (n < 0) __lang_rt_fail(__LANG_RT_ERR_PANIC, __clib__buffer_src(), "buffer: negative read length");
    uint32_t count = (uint32_t)n;
    __clib__buffer_check_read(buf, count);
    __lang_rt_Src src = __clib__buffer_src();
    char* data = (char*)__lang_rt_malloc(src, (size_t)count + 1);
    memcpy(data, buf->data + buf->pos, count);
    data[count] = 0;
    buf->pos += count;
    __lang_rt_Str* s = (__lang_rt_Str*)__lang_rt_malloc(src, sizeof(__lang_rt_Str));
    __lang_rt_rc_init(&s->rc);
    s->len = count;
    s->data = (const char*)data;
    return s;
}

static __lang_rt_Str* __clib__buffer_read_str_zt(__clib__buffer_Buffer* buf) {
    /* Scan for null terminator from current pos */
    uint32_t start = buf->pos;
    while (buf->pos < buf->len && buf->data[buf->pos] != 0) {
        buf->pos++;
    }
    uint32_t slen = buf->pos - start;
    /* Skip past the null terminator if present */
    if (buf->pos < buf->len) buf->pos++;
    __lang_rt_Src src = __clib__buffer_src();
    char* data = (char*)__lang_rt_malloc(src, (size_t)slen + 1);
    memcpy(data, buf->data + start, slen);
    data[slen] = 0;
    __lang_rt_Str* s = (__lang_rt_Str*)__lang_rt_malloc(src, sizeof(__lang_rt_Str));
    __lang_rt_rc_init(&s->rc);
    s->len = slen;
    s->data = (const char*)data;
    return s;
}

/* ── read: integers — little endian (unsigned) ────────────────────── */

static int64_t __clib__buffer_read_u16_le(__clib__buffer_Buffer* buf) {
    __clib__buffer_check_read(buf, 2);
    uint16_t u = (uint16_t)buf->data[buf->pos]
               | ((uint16_t)buf->data[buf->pos + 1] << 8);
    buf->pos += 2;
    return (int64_t)u;
}

static int64_t __clib__buffer_read_u32_le(__clib__buffer_Buffer* buf) {
    __clib__buffer_check_read(buf, 4);
    uint32_t u = (uint32_t)buf->data[buf->pos]
               | ((uint32_t)buf->data[buf->pos + 1] << 8)
               | ((uint32_t)buf->data[buf->pos + 2] << 16)
               | ((uint32_t)buf->data[buf->pos + 3] << 24);
    buf->pos += 4;
    return (int64_t)u;
}

/* ── read: integers — little endian (signed) ──────────────────────── */

static int64_t __clib__buffer_read_i16_le(__clib__buffer_Buffer* buf) {
    __clib__buffer_check_read(buf, 2);
    uint16_t u = (uint16_t)buf->data[buf->pos]
               | ((uint16_t)buf->data[buf->pos + 1] << 8);
    buf->pos += 2;
    return (int64_t)(int16_t)u;
}

static int64_t __clib__buffer_read_i32_le(__clib__buffer_Buffer* buf) {
    __clib__buffer_check_read(buf, 4);
    uint32_t u = (uint32_t)buf->data[buf->pos]
               | ((uint32_t)buf->data[buf->pos + 1] << 8)
               | ((uint32_t)buf->data[buf->pos + 2] << 16)
               | ((uint32_t)buf->data[buf->pos + 3] << 24);
    buf->pos += 4;
    return (int64_t)(int32_t)u;
}

static int64_t __clib__buffer_read_i64_le(__clib__buffer_Buffer* buf) {
    __clib__buffer_check_read(buf, 8);
    uint64_t u = 0;
    for (int i = 0; i < 8; i++) {
        u |= (uint64_t)buf->data[buf->pos + i] << (i * 8);
    }
    buf->pos += 8;
    return (int64_t)u;
}

/* ── read: integers — big endian (unsigned) ───────────────────────── */

static int64_t __clib__buffer_read_u16_be(__clib__buffer_Buffer* buf) {
    __clib__buffer_check_read(buf, 2);
    uint16_t u = ((uint16_t)buf->data[buf->pos] << 8)
               | (uint16_t)buf->data[buf->pos + 1];
    buf->pos += 2;
    return (int64_t)u;
}

static int64_t __clib__buffer_read_u32_be(__clib__buffer_Buffer* buf) {
    __clib__buffer_check_read(buf, 4);
    uint32_t u = ((uint32_t)buf->data[buf->pos] << 24)
               | ((uint32_t)buf->data[buf->pos + 1] << 16)
               | ((uint32_t)buf->data[buf->pos + 2] << 8)
               | (uint32_t)buf->data[buf->pos + 3];
    buf->pos += 4;
    return (int64_t)u;
}

/* ── read: integers — big endian (signed) ─────────────────────────── */

static int64_t __clib__buffer_read_i16_be(__clib__buffer_Buffer* buf) {
    __clib__buffer_check_read(buf, 2);
    uint16_t u = ((uint16_t)buf->data[buf->pos] << 8)
               | (uint16_t)buf->data[buf->pos + 1];
    buf->pos += 2;
    return (int64_t)(int16_t)u;
}

static int64_t __clib__buffer_read_i32_be(__clib__buffer_Buffer* buf) {
    __clib__buffer_check_read(buf, 4);
    uint32_t u = ((uint32_t)buf->data[buf->pos] << 24)
               | ((uint32_t)buf->data[buf->pos + 1] << 16)
               | ((uint32_t)buf->data[buf->pos + 2] << 8)
               | (uint32_t)buf->data[buf->pos + 3];
    buf->pos += 4;
    return (int64_t)(int32_t)u;
}

static int64_t __clib__buffer_read_i64_be(__clib__buffer_Buffer* buf) {
    __clib__buffer_check_read(buf, 8);
    uint64_t u = 0;
    for (int i = 0; i < 8; i++) {
        u |= (uint64_t)buf->data[buf->pos + i] << ((7 - i) * 8);
    }
    buf->pos += 8;
    return (int64_t)u;
}

/* ── read: floats ─────────────────────────────────────────────────── */

static double __clib__buffer_read_f32_le(__clib__buffer_Buffer* buf) {
    __clib__buffer_check_read(buf, 4);
    uint32_t u = (uint32_t)buf->data[buf->pos]
               | ((uint32_t)buf->data[buf->pos + 1] << 8)
               | ((uint32_t)buf->data[buf->pos + 2] << 16)
               | ((uint32_t)buf->data[buf->pos + 3] << 24);
    buf->pos += 4;
    float f;
    memcpy(&f, &u, 4);
    return (double)f;
}

static double __clib__buffer_read_f32_be(__clib__buffer_Buffer* buf) {
    __clib__buffer_check_read(buf, 4);
    uint32_t u = ((uint32_t)buf->data[buf->pos] << 24)
               | ((uint32_t)buf->data[buf->pos + 1] << 16)
               | ((uint32_t)buf->data[buf->pos + 2] << 8)
               | (uint32_t)buf->data[buf->pos + 3];
    buf->pos += 4;
    float f;
    memcpy(&f, &u, 4);
    return (double)f;
}

static double __clib__buffer_read_f64_le(__clib__buffer_Buffer* buf) {
    __clib__buffer_check_read(buf, 8);
    uint64_t u = 0;
    for (int i = 0; i < 8; i++) {
        u |= (uint64_t)buf->data[buf->pos + i] << (i * 8);
    }
    buf->pos += 8;
    double d;
    memcpy(&d, &u, 8);
    return d;
}

static double __clib__buffer_read_f64_be(__clib__buffer_Buffer* buf) {
    __clib__buffer_check_read(buf, 8);
    uint64_t u = 0;
    for (int i = 0; i < 8; i++) {
        u |= (uint64_t)buf->data[buf->pos + i] << ((7 - i) * 8);
    }
    buf->pos += 8;
    double d;
    memcpy(&d, &u, 8);
    return d;
}

/* ── utility ──────────────────────────────────────────────────────── */

static int64_t __clib__buffer_length(__clib__buffer_Buffer* buf) {
    return (int64_t)buf->len;
}

static int64_t __clib__buffer_capacity(__clib__buffer_Buffer* buf) {
    return (int64_t)buf->cap;
}

static int64_t __clib__buffer_pos(__clib__buffer_Buffer* buf) {
    return (int64_t)buf->pos;
}

static int64_t __clib__buffer_remaining(__clib__buffer_Buffer* buf) {
    return (int64_t)(buf->len - buf->pos);
}

static void __clib__buffer_seek(__clib__buffer_Buffer* buf, int64_t pos) {
    if (pos < 0 || (uint32_t)pos > buf->len) {
        __lang_rt_fail(__LANG_RT_ERR_PANIC, __clib__buffer_src(), "buffer: seek out of bounds");
    }
    buf->pos = (uint32_t)pos;
}

static void __clib__buffer_reset(__clib__buffer_Buffer* buf) {
    buf->pos = 0;
}

static void __clib__buffer_clear(__clib__buffer_Buffer* buf) {
    buf->len = 0;
    buf->pos = 0;
}

static __lang_rt_Str* __clib__buffer_to_str(__clib__buffer_Buffer* buf) {
    __lang_rt_Src src = __clib__buffer_src();
    char* data = (char*)__lang_rt_malloc(src, (size_t)buf->len + 1);
    memcpy(data, buf->data, buf->len);
    data[buf->len] = 0;
    __lang_rt_Str* s = (__lang_rt_Str*)__lang_rt_malloc(src, sizeof(__lang_rt_Str));
    __lang_rt_rc_init(&s->rc);
    s->len = buf->len;
    s->data = (const char*)data;
    return s;
}

static __lang_rt_Str* __clib__buffer_slice(__clib__buffer_Buffer* buf, int64_t start, int64_t n) {
    if (start < 0 || n < 0 || (uint32_t)(start + n) > buf->len) {
        __lang_rt_fail(__LANG_RT_ERR_PANIC, __clib__buffer_src(), "buffer: slice out of bounds");
    }
    __lang_rt_Src src = __clib__buffer_src();
    uint32_t count = (uint32_t)n;
    char* data = (char*)__lang_rt_malloc(src, (size_t)count + 1);
    memcpy(data, buf->data + (uint32_t)start, count);
    data[count] = 0;
    __lang_rt_Str* s = (__lang_rt_Str*)__lang_rt_malloc(src, sizeof(__lang_rt_Str));
    __lang_rt_rc_init(&s->rc);
    s->len = count;
    s->data = (const char*)data;
    return s;
}
