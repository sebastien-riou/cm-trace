# cm-trace
Cycle accurate trace for Cortex-M, for real (I am looking at you ETM...)

## Concept
1. Setup:
    - Clean the stack
    - Clean the caches
    - Setup a timer interrupt at time X (where X is the number of cycles to get into the target function) 
2. Run the target function
3. Handle interrupt
    - if return address is end address, exit
    - if return address is start address, start logging return address
    - increment X
    - return to step 1

## Logging concept
Simply send 32 bit address and cycle number over UART (yes that's a bit redundant)