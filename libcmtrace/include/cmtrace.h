#pragma once

typedef void (*cmtrace_target_t)(void);

//functions that may be overriden by application
void cmtrace_clear_caches();
void cmtrace_com_tx(const void*buf, unsigned int size);

//functions to use "as is"
void cmtrace_init(cmtrace_target_t target);

