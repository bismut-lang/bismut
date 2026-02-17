/*
 * pxmatrix — C implementation for the pxmatrix Bismut extern library.
 * Simple row-major matrix with heap-allocated data.
 */

#include <stdlib.h>

typedef struct pxmatrix_t {
    int64_t rows;
    int64_t cols;
    double* data;
} pxmatrix_t;

static pxmatrix_t* pxmatrix_create(int64_t rows, int64_t cols) {
    pxmatrix_t* m = (pxmatrix_t*)malloc(sizeof(pxmatrix_t));
    m->rows = rows;
    m->cols = cols;
    m->data = (double*)calloc((size_t)(rows * cols), sizeof(double));
    return m;
}

static void pxmatrix_destroy(pxmatrix_t* m) {
    if (m) {
        free(m->data);
        free(m);
    }
}

static void pxmatrix_set(pxmatrix_t* m, int64_t r, int64_t c, double v) {
    m->data[r * m->cols + c] = v;
}

static double pxmatrix_get(pxmatrix_t* m, int64_t r, int64_t c) {
    return m->data[r * m->cols + c];
}

static int64_t pxmatrix_rows(pxmatrix_t* m) {
    return m->rows;
}

static int64_t pxmatrix_cols(pxmatrix_t* m) {
    return m->cols;
}
