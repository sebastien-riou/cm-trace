#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include "cmtrace.h"

#include "cm.h"

#define CMTRACE_ASCII_OUT 0

#if CMTRACE_ASCII_OUT
#define CMTRACE_TRACE_CALLER 1
#define PRINTF(...) printf( __VA_ARGS__ )
#else
#define CMTRACE_TRACE_CALLER 0
#define PRINTF(...)
#endif

#define DWT_FUNC0_CYCMATCH 			(1<<7)
#define DWT_FUNC0_GEN_WATCHPOINT 	4

int __io_putchar(int ch);
int __io_getchar(void);

__attribute__((weak)) void cmtrace_clear_caches(){
}

__attribute__((weak)) void cmtrace_com_tx(const void*buf, unsigned int size){
    const uint8_t*buf8 = (const uint8_t*)buf;
    for(unsigned int i=0;i<size;i++){
        __io_putchar(buf8[i]);
    }
}

__attribute__((weak)) void cmtrace_com_rx(void*buf, unsigned int size){
    uint8_t*buf8 = (uint8_t*)buf;
    for(unsigned int i=0;i<size;i++){
        buf8[i] = __io_getchar();
    }
}
#if CMTRACE_ASCII_OUT
void dump_core(uintptr_t addr, uintptr_t size, uintptr_t display_addr){
  printf("@0x%08x, %u bytes:\n\r",display_addr, size);
  uint8_t*r = (uint8_t*)addr;
  uint32_t cnt=1;
  while(size){
    printf("%02x ",*r++);
    size--;
	if(0 == cnt%4) printf(" ");
	cnt++;
  }
  printf("\n\r");
}
void dump(uintptr_t addr, uintptr_t size){
  dump_core(addr,size,addr);
}
#define DUMPI(val) dump((uintptr_t)&val,sizeof val)
void dump_dfsr(){
	const uint32_t dfsr_dwt_evt_bitmask = (1 << 2);
	const uint32_t dfsr_bkpt_evt_bitmask = (1 << 1);
	const uint32_t dfsr_halt_evt_bitmask = (1 << 0);
    const uint32_t dfsr = SCB->DFSR;
	const bool is_dwt_dbg_evt = (dfsr & dfsr_dwt_evt_bitmask);
	const bool is_bkpt_dbg_evt = (dfsr & dfsr_bkpt_evt_bitmask);
	const bool is_halt_dbg_evt = (dfsr & dfsr_halt_evt_bitmask);
	PRINTF("DFSR:  0x%08lx (bkpt=%d, halt=%d, dwt=%d)", dfsr,(int)is_bkpt_dbg_evt, (int)is_halt_dbg_evt,(int)is_dwt_dbg_evt);
}
#endif

#if CMTRACE_ASCII_OUT
	//void cmtrace_tx_init(uint32_t total_cycles){printf("total cycles, including call/ret and timer read = %lu\n",total_cycles);}
	void cmtrace_tx_init(){printf("cmtrace_tx_init\n");}
	void cmtrace_tx_done(uint32_t total_cycles){printf("total cycles, target function only = %lu\n",total_cycles);}
	void cmtrace_tx_pc(uint32_t pc){printf("PC=0x%08lx\n",pc);}
	//void cmtrace_tx_sp(uint32_t sp){printf("SP=0x%08lx\n",sp);}
	void cmtrace_tx_cy(uint32_t cy){printf("%6lu ",cy);}
#else
	void cmtrace_tx_init(){
		const uint8_t hello[] = "cmtrace";
		cmtrace_com_tx(hello,8);
	}
	void cmtrace_tx_done(uint32_t total_cycles){
		const uint32_t ff = 0xFFFFFFFF;
		cmtrace_com_tx(&ff,4);
		cmtrace_com_tx(&total_cycles,4);
	}
	void cmtrace_tx_pc(uint32_t pc){cmtrace_com_tx(&pc,4);}
	//void cmtrace_tx_sp(uint32_t sp){cmtrace_com_tx(&sp,4);}
	void cmtrace_tx_cy(uint32_t cy){cmtrace_com_tx(&cy,4);}
#endif

void dwt_stop(){
	DWT->CTRL &= 0xFFFFFFFE ; // disable counter
}
void dwt_run(){
	DWT->CTRL |= 1 ; // enable counter
}
void dwt_init(){
	static bool done=0;
	if(done) return;
	if ((CoreDebug->DHCSR & 0x1) != 0) {
		printf("ERROR: Halting Debug Enabled - Please reset\n");
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
	done=1;
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
	PRINTF("setup as timer. ");
	if(DWT->CYCCNT){
		PRINTF("ERROR: DWT->CYCCNT not 0!\n");
		while(1);
	}
	if(DWT->COMP0 != cycles){
		PRINTF("ERROR: DWT->COMP0 not equal to cycles!\n");
		while(1);
	}
	dwt_run();
}
uint32_t dwt_read_cycles(){
	return DWT->CYCCNT;
}
void stepper_entry();
void stepper_next();

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
	PRINTF("start=%lu, end=%lu.",start,end);
    if(0xFFFFFFFF==stepper_cycles){
        //free run trial
        stepper_start_cycles = start;
	    stepper_end_cycles = end;
	    stepper_total_cycles = stepper_end_cycles-stepper_start_cycles;
	}
}

void stepper(){
	cmtrace_clear_caches();
	dwt_setup_as_timer(stepper_cycles);
	stepper_core();
}

void cmtrace_init(cmtrace_target_t target){
	cmtrace_tx_init();
	target = (cmtrace_target_t)((uintptr_t)target | 1);//force thumb bit
	stepper_target = target;
	stepper_start_done=0;
	stepper_end_done=0;
	stepper_cycles=0xFFFFFFFF;
	stepper_last_pc = 0xFFFFFFFF;
	stepper_target_return_address = 0xFFFFFFFF;
	dwt_init();
	stepper_entry();
	const uint32_t min_dwt = stepper_start_cycles-2;
    cmtrace_tx_cy(stepper_total_cycles);
	PRINTF("stepper calibration: min_dwt = %lu\n",min_dwt);
    stepper_cycles = min_dwt;
	stepper_entry();
    cmtrace_tx_done(stepper_total_cycles);
}

void cmtrace_start(){
	uint32_t target;
	while(1){
		cmtrace_com_rx(&target,4);
		cmtrace_init((cmtrace_target_t) target);
	}
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


extern uint32_t stepper_entry_sp;
void stepper_debug_monitor_handler(sContextStateFrame *frame){
	PRINTF("stepper_debug_monitor_handler:");
	const uint32_t dfsr_dwt_evt_bitmask = (1 << 2);
	if(!stepper_start_done){
		const uint32_t start_target = (uint32_t)(stepper_target) & 0xFFFFFFFE;
		if(frame->return_address == start_target){
            PRINTF("---- start ----\n");
			stepper_start_done=1;
            stepper_start_cycles=stepper_cycles;
			stepper_target_return_address = frame->lr & 0xFFFFFFFE;
		}
	}
	if(!stepper_end_done){
		if(frame->return_address == stepper_target_return_address){
            PRINTF("---- end ----\n");
			stepper_end_done = 1;
            stepper_end_cycles = stepper_cycles;
            stepper_total_cycles = 1 + stepper_end_cycles - stepper_start_cycles;
		}
	}
	if((stepper_start_done && !stepper_end_done) || CMTRACE_TRACE_CALLER){
        if(stepper_start_done) {
            cmtrace_tx_cy(1 + stepper_cycles - stepper_start_cycles);
        }else{
            cmtrace_tx_cy(stepper_cycles);
        }
        cmtrace_tx_pc(frame->return_address);
		//printf("LR=0x%08lx\n",frame->lr);
		//printf("SP=0x%08x\n",(uintptr_t)(frame+1));
		//printf("stepper_entry_sp=0x%08x\n",stepper_entry_sp);
		//dump((uintptr_t)frame,sizeof(sContextStateFrame));
		//dump((uintptr_t)(frame+1),64);
    }

	dwt_stop();
	DWT->CYCCNT = 0; // reset the counter
	SCB->DFSR = dfsr_dwt_evt_bitmask; //clear IRQ event mask
	if(!stepper_end_done || CMTRACE_TRACE_CALLER){
        stepper_cycles++;
	    frame->return_address = (uint32_t)stepper_next;
		frame->xpsr &= 0xFF000000;
    }
}
__attribute__((naked)) void DebugMon_Handler(void){
  __asm volatile(
      "tst lr, #4 \n"
      "ite eq \n"
      "mrseq r0, msp \n"
      "mrsne r0, psp \n"
      "b stepper_debug_monitor_handler \n");
}
