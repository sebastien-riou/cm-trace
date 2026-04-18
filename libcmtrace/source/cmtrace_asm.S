
  .syntax unified
  .cpu cortex-m3
  .thumb

	.section .bss
	.global stepper_entry_sp
stepper_entry_sp:
	.word	0
stepper_entry_xpsr:
	.word	0

	.section  .text,"ax",%progbits
	.global stepper_entry
	.global stepper
	.type  stepper_entry, %function
stepper_entry:
	push {lr}
	//save full context
	push {r0,r1,r2,r3,r4,r5,r6,r7,r8,r9,r10,r11,r12}
	ldr r1,=stepper_entry_sp
	str sp,[r1]
	ldr r1,=stepper_entry_xpsr
	mrs	r0, PSR
	str r0,[r1]
	
	blx stepper
stepper_done:
	pop {r0,r1,r2,r3,r4,r5,r6,r7,r8,r9,r10,r11,r12}
	pop {pc}

  	.global stepper_next
  	.type  stepper_next, %function
stepper_next:
	ldr r1,=stepper_entry_sp
	ldr sp,[r1]
	ldr r1,=stepper_entry_xpsr
	msr	PSR, r0
	ldr r0,[r1]
	//restore full context
	pop  {r0,r1,r2,r3,r4,r5,r6,r7,r8,r9,r10,r11,r12}
	push {r0,r1,r2,r3,r4,r5,r6,r7,r8,r9,r10,r11,r12}
	ldr lr,=stepper_done
	add lr,#1
	b stepper



  	.global nop8
	.type  nop8, %function
nop8:
	nop
	nop
	nop
	nop

	nop
	nop
	nop
	nop
	bx	lr
