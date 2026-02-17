// __lang_rt_process.h (C99) — cross-platform command execution
#pragma once
#include <stdlib.h>
#include "rt_error.h"
#include "rt_str.h"

// Execute a shell command. Returns exit code.
static inline int64_t __lang_rt_exec(__lang_rt_Src src, __lang_rt_Str* cmd) {
    if (!cmd) __lang_rt_fail(__LANG_RT_ERR_IO, src, "exec: command is nil");
    int rc = system(cmd->data);
#ifdef _WIN32
    return (int64_t)rc;
#else
    // POSIX: WEXITSTATUS extracts the actual exit code
    if (rc == -1) return -1;
    return (int64_t)(rc >> 8) & 0xff;
#endif
}
