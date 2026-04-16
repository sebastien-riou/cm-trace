#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include "cmtrace.h"

#include "cm.h"

#define DWT_FUNC0_CYCMATCH 			(1<<7)
#define DWT_FUNC0_GEN_WATCHPOINT 	4

int __io_putchar(int ch);

__attribute__((weak)) void cmtrace_clear_caches(){
}

__attribute__((weak)) void cmtrace_com_tx(const void*buf, unsigned int size){
    const uint8_t*buf8 = (const uint8_t*)buf;
    for(unsigned int i=0;i<size;i++){
        __io_putchar(buf8[i]);
    }
}

void dwt_stop(){
	DWT->CTRL &= 0xFFFFFFFE ; // disable counter
}
void dwt_run(){
	DWT->CTRL |= 1 ; // enable counter
}
void dwt_init(){
	if ((CoreDebug->DHCSR & 0x1) != 0) {
		printf("Halting Debug Enabled - Please reset\n");
		while(1);
	}
	// code to set up debug monitor mode
	const uint32_t mon_en_bit = 16;
	CoreDebug->DEMCR |= 1 << mon_en_bit;
	// Priority for DebugMonitor Exception is bits[7:0]
	SCB->SHP[3] = 0x00;//highest prio
	CoreDebug->DEMCR |= 0x01000000;
	ITM->LAR = 0xC5ACCE55; // enable access
	dwt_stop();
	DWT->CYCCNT = 0; // reset the counter
}

void dwt_setup_as_timer(uint32_t cycles){
	dwt_stop();
	//setup break point based on clock cycles
	DWT->CYCCNT = 0; // reset the counter
	DWT->COMP0 = cycles;
    #if __CORTEX_M < 23
	DWT->MASK0 = 0;
    #endif
	DWT->FUNCTION0 = DWT_FUNC0_CYCMATCH | DWT_FUNC0_GEN_WATCHPOINT;
	__enable_irq();
	dwt_run();
}
uint32_t dwt_read_cycles(){
	return DWT->CYCCNT;
}
void stepper_entry();
void stepper_next();
void stepper_done();

bool stepper_start_done;
bool stepper_end_done;
uint32_t stepper_last_pc;
uint32_t stepper_target_return_address;
volatile uint32_t stepper_start_cycles;
volatile uint32_t stepper_end_cycles;
volatile uint32_t stepper_total_cycles;
volatile uint32_t stepper_cycles;
cmtrace_target_t stepper_target;
void stepper_core(){
	const uint32_t start = DWT->CYCCNT;
	stepper_target();
	const uint32_t end = DWT->CYCCNT;
	dwt_stop();
	stepper_start_cycles = start;
	stepper_end_cycles = end;
	stepper_total_cycles = stepper_end_cycles-stepper_start_cycles;
	if(0xFFFFFFFF!=stepper_cycles){
		stepper_done();
	}
}
void stepper(){
	cmtrace_clear_caches();
	dwt_setup_as_timer(stepper_cycles);
	stepper_core();
}
void cmtrace_init(cmtrace_target_t target){
    stepper_target = target;
	stepper_start_done=0;
	stepper_end_done=0;
	stepper_cycles=0xFFFFFFFF;
	stepper_last_pc = 0xFFFFFFFF;
	stepper_target_return_address = 0xFFFFFFFF;
	dwt_init();
	stepper();
	const uint32_t min_dwt = stepper_start_cycles-2;
	printf("stepper calibration: min_dwt = %lu\n",min_dwt);
	printf("total cycles = %lu\n",stepper_total_cycles);
	stepper_cycles = min_dwt;
	stepper_entry();
	printf("stepper done\n");
}

typedef struct __attribute__((packed)) ContextStateFrame {
  uint32_t r0;
  uint32_t r1;
  uint32_t r2;
  uint32_t r3;
  uint32_t r12;
  uint32_t lr;
  uint32_t return_address;
  uint32_t xpsr;
} sContextStateFrame;

void dump_dfsr(){
	const uint32_t dfsr_dwt_evt_bitmask = (1 << 2);
	const uint32_t dfsr_bkpt_evt_bitmask = (1 << 1);
	const uint32_t dfsr_halt_evt_bitmask = (1 << 0);
    const uint32_t dfsr = SCB->DFSR;
	const bool is_dwt_dbg_evt = (dfsr & dfsr_dwt_evt_bitmask);
	const bool is_bkpt_dbg_evt = (dfsr & dfsr_bkpt_evt_bitmask);
	const bool is_halt_dbg_evt = (dfsr & dfsr_halt_evt_bitmask);
	printf("DFSR:  0x%08lx (bkpt=%d, halt=%d, dwt=%d)", dfsr,(int)is_bkpt_dbg_evt, (int)is_halt_dbg_evt,(int)is_dwt_dbg_evt);
}

void stepper_debug_monitor_handler(sContextStateFrame *frame){
	const uint32_t dfsr_dwt_evt_bitmask = (1 << 2);
	if(!stepper_start_done){
		const uint32_t start_target = (uint32_t)(stepper_target) & 0xFFFFFFFE;
		if(frame->return_address == start_target){
			printf("---- start ----\n");
			stepper_start_done=1;
			stepper_target_return_address = frame->lr & 0xFFFFFFFE;
		}
	}
	if(!stepper_end_done){
		if(frame->return_address == stepper_target_return_address){
			printf("---- end ----\n");
			stepper_end_done=1;
		}
	}
	printf("%6lu: PC=0x%08lx\n",stepper_cycles,frame->return_address);

	dwt_stop();
	DWT->CYCCNT = 0; // reset the counter
	SCB->DFSR = dfsr_dwt_evt_bitmask; //clear IRQ event mask
	stepper_cycles++;
	frame->return_address = (uint32_t)stepper_next;
}
__attribute__((naked)) void DebugMon_Handler(void){
  __asm volatile(
      "tst lr, #4 \n"
      "ite eq \n"
      "mrseq r0, msp \n"
      "mrsne r0, psp \n"
      "b stepper_debug_monitor_handler \n");
}