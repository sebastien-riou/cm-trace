# cm-trace
Cycle accurate trace for ARM Cortex-M, for real (I am looking at you ETM...)

It targets Cortex-M3 and 'higher' (meaning any Cortex-M to date bar M0,M0+ and M1).

It succesfully build on:
- M3
- M4
- M7
- M33

Others have not been attempted yet.

It has been tested only Cortex-M3 and Cortex-M4. 

## Overview
- In the embedded code:
    - Link your app against the C library 
    - Implement the few support functions:
        - mandatory:
            - `__io_putchar`
            - `__io_getchar`
            - set the debug monitor IRQ vector to `DebugMon_Handler`
        - optional:
            - `cmtrace_clear_caches`
    - Invoke `cmtrace_trace_loop` in your app
- On host computer:
    - Invoke the python script `cmtrace-capture`: it communicates with `cmtrace_trace_loop` and create a trace file on the host computer
    - Invoke the python script `cmtrace-dump` to read back the trace file

Function traced in the example:
````
00000000 <umul64>:
   0:	4343      	muls	r3, r0
   2:	fb02 3101 	mla	r1, r2, r1, r3
   6:	fba0 0202 	umull	r0, r2, r0, r2
   a:	4411      	add	r1, r2
   c:	4770      	bx	lr
````

Example of output highlighting the difference between Cortex-M3 and Cortex-M4 for `umull` instruction :
````
$ pipenv run cmtrace-dump cmtrace-stm32f207.elf-test_umul64_16_16.cmtrace 
 index|        PC|opcode|cycles|cycles sum
     1|0x080020ba|  muls|     2|         2
     2|0x080020bc|   mla|     2|         4
     3|0x080020c0| umull|     3|         7
     4|0x080020c4|   add|     1|         8
     5|0x080020c6|    bx|     1|         9
$ pipenv run cmtrace-dump cmtrace-stm32f207.elf-test_umul64_32_16.cmtrace 
 index|        PC|opcode|cycles|cycles sum
     1|0x080020ba|  muls|     2|         2
     2|0x080020bc|   mla|     2|         4
     3|0x080020c0| umull|     4|         8
     4|0x080020c4|   add|     1|         9
     5|0x080020c6|    bx|     1|        10
$ pipenv run cmtrace-dump test-stm32f411.elf-test_umul64_16_16.cmtrace 
 index|        PC|opcode|cycles|cycles sum
     1|0x0800294c| mul.w|     2|         2
     2|0x08002950|   mla|     2|         4
     3|0x08002954| umull|     1|         5
     4|0x08002958|   add|     1|         6
     5|0x0800295a|    bx|     1|         7
$ pipenv run cmtrace-dump test-stm32f411.elf-test_umul64_32_16.cmtrace 
 index|        PC|opcode|cycles|cycles sum
     1|0x0800294c| mul.w|     2|         2
     2|0x08002950|   mla|     2|         4
     3|0x08002954| umull|     1|         5
     4|0x08002958|   add|     1|         6
     5|0x0800295a|    bx|     1|         7

````

## Installation of Python package
- Choose a working directory
- If it does not have a pipenv yet: `touch Pipfile`
- `pipenv install git+https://github.com/sebastien-riou/cm-trace.git`

## Technical notes

### Tracing concept
1. X = 0
2. Setup:
    - Clean the caches
    - Setup DWT timer interrupt at time X 
3. Run the target function
4. Handle interrupt
    - if return address is end address, exit
    - if return address is start address, start logging return address
    - increment X
    - return to step 2

### Logging concept
Simply send 32 bit address and cycle number over UART (yes that's a bit redundant)