/*
 * pxmath — C implementation for the pxmath Bismut extern library.
 */

#include <math.h>
#include <stdint.h>

static double pxmath_sqrt(double x) {
    return sqrt(x);
}

static int64_t pxmath_abs_i64(int64_t x) {
    return x < 0 ? -x : x;
}

static double pxmath_abs_f64(double x) {
    return fabs(x);
}

static double pxmath_pow(double base, double exp) {
    return pow(base, exp);
}

static int64_t pxmath_min_i64(int64_t a, int64_t b) {
    return a < b ? a : b;
}

static int64_t pxmath_max_i64(int64_t a, int64_t b) {
    return a > b ? a : b;
}

static int64_t pxmath_clamp(int64_t val, int64_t lo, int64_t hi) {
    if (val < lo) return lo;
    if (val > hi) return hi;
    return val;
}
