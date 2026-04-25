#pragma once

typedef void (*cmtrace_target_t)(void);

// functions that may be overriden by application
void cmtrace_clear_caches();

void cmtrace_timer_init();//called once per trace
void cmtrace_timer_start(uint32_t cycles);//called to start the timer with a specific timeout (in cycles)
void cmtrace_timer_stop();//called to stop the timer
void cmtrace_timer_irq_ack();//called to ack the timer IRQ. it should also stop the timer.
uint32_t cmtrace_timer_read();//called to read the current timer cycles

// functions to use "as is"
void cmtrace_trace_loop();
void cmtrace_trace(cmtrace_target_t target);
void cmtrace_timer_irq_handler(void);

// test functions
void test_umul64_16_16();
void test_umul64_32_16();
void test_umul64_32_32();
void test_loop64_4();
void test_loop64_32();
void test_loop64_256();
void test_loop64_100k();
void include_test_functions();  