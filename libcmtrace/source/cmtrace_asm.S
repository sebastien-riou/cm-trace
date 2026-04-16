
  .syntax unified
  .cpu cortex-m3
  .thumb

	.section .bss
	.global stepper_entry_sp
stepper_entry_sp:
	.word	0

	.section  .text,"ax",%progbits
	.global stepper_entry
	.global stepper
	.type  stepper_entry, %function
stepper_entry:
	push {lr}
	ldr r1,=stepper_entry_sp
	str sp,[r1]
	b stepper

  	.global stepper_next
  	.type  stepper_next, %function
stepper_next:
	ldr r1,=stepper_entry_sp
	ldr sp,[r1]
	b stepper

  	.global stepper_done
	.type  stepper_done, %function
stepper_done:
	ldr r1,=stepper_entry_sp
	ldr sp,[r1]
	pop {pc}

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
