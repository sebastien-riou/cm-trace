#pragma once

#define __CHECK_DEVICE_DEFINES
typedef enum
{
  /******  Cortex-M Processor Exceptions Numbers ****************************************************************/
  NonMaskableInt_IRQn         = -14,    /*!< 2 Non Maskable Interrupt                                          */
  MemoryManagement_IRQn       = -12,    /*!< 4 Cortex-M Memory Management Interrupt                           */
  BusFault_IRQn               = -11,    /*!< 5 Cortex-M Bus Fault Interrupt                                   */
  UsageFault_IRQn             = -10,    /*!< 6 Cortex-M Usage Fault Interrupt                                 */
  SVCall_IRQn                 = -5,     /*!< 11 Cortex-M SV Call Interrupt                                    */
  DebugMonitor_IRQn           = -4,     /*!< 12 Cortex-M Debug Monitor Interrupt                              */
  PendSV_IRQn                 = -2,     /*!< 14 Cortex-M Pend SV Interrupt                                    */
  SysTick_IRQn                = -1,     /*!< 15 Cortex-M System Tick Interrupt                                */
} IRQn_Type;

#include "core_cm7.h"             /* Cortex-M processor and core peripherals */

#define SHP SHPR