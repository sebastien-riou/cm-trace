#pragma once

typedef void (*cmtrace_target_t)(void);

//functions that may be overriden by application
void cmtrace_clear_caches();

//functions to use "as is"
void cmtrace_trace_loop();
void cmtrace_trace(cmtrace_target_t target);

//test functions
void test_umul64_16_16();
void test_umul64_32_16();
void test_umul64_32_32();