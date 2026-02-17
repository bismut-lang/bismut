// __lang_rt_time.h (C99) — cross-platform monotonic timer
#pragma once

#ifdef _WIN32
  #ifndef WIN32_LEAN_AND_MEAN
    #define WIN32_LEAN_AND_MEAN
  #endif
  #include <windows.h>
  static inline double __lang_rt_time_now(void) {
      LARGE_INTEGER freq, cnt;
      QueryPerformanceFrequency(&freq);
      QueryPerformanceCounter(&cnt);
      return (double)cnt.QuadPart / (double)freq.QuadPart;
  }
#elif defined(__APPLE__)
  #include <mach/mach_time.h>
  static inline double __lang_rt_time_now(void) {
      static mach_timebase_info_data_t tb;
      if (tb.denom == 0) mach_timebase_info(&tb);
      uint64_t t = mach_absolute_time();
      return (double)t * (double)tb.numer / (double)tb.denom / 1e9;
  }
#else
  #include <time.h>
  static inline double __lang_rt_time_now(void) {
      struct timespec ts;
      clock_gettime(CLOCK_MONOTONIC, &ts);
      return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
  }
#endif
