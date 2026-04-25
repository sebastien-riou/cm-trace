#include "cm.h"
#include <stdbool.h>
#include <stdio.h>
#define CMTRACE_ASCII_OUT 0

#if CMTRACE_ASCII_OUT
#define PRINTF(...) printf( __VA_ARGS__ )
#else
#define PRINTF(...)
#endif

#define DWT_FUNC0_CYCMATCH 			(1<<7)
#define DWT_FUNC0_GEN_WATCHPOINT 	4

#define SCB_AIRCR_VECTKEYSTAT_LSB       16
#define SCB_AIRCR_VECTKEYSTAT           (0xFFFF << SCB_AIRCR_VECTKEYSTAT_LSB)
#define SCB_AIRCR_VECTKEY               (0x05FA << SCB_AIRCR_VECTKEYSTAT_LSB)

/** SYSRESETREQ System reset request */
#define SCB_AIRCR_SYSRESETREQ                   (1 << 2)
/** VECTCLRACTIVE clears state information for exceptions */
#define SCB_AIRCR_VECTCLRACTIVE                 (1 << 1)
/** VECTRESET cause local system reset */
#define SCB_AIRCR_VECTRESET                     (1 << 0)

#if CMTRACE_ASCII_OUT
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
		//printf("ERROR: Halting Debug Enabled - Attempting system reset\n");
		//CoreDebug->DHCSR = 0;
		//SCB->AIRCR = SCB_AIRCR_VECTKEY | SCB_AIRCR_SYSRESETREQ;
		printf("ERROR: Halting Debug Enabled - please reset board\n");
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

void dwt_ack_irq(){
    dwt_stop();
    DWT->CYCCNT = 0; // reset the counter
    const uint32_t dfsr_dwt_evt_bitmask = (1 << 2);
    SCB->DFSR = dfsr_dwt_evt_bitmask; //clear IRQ event mask
}

void cmtrace_timer_init(){
    dwt_init();
}

void cmtrace_timer_start(uint32_t cycles){
    dwt_setup_as_timer(cycles);
}

void cmtrace_timer_stop(){
    dwt_stop();
}

void cmtrace_timer_irq_ack(){
    dwt_ack_irq();
}

uint32_t cmtrace_timer_read(){
    return dwt_read_cycles();
}
