/* SPDX-License-Identifier: Apache-2.0 */
.syntax unified
.arm
.text
.global _start
.type _start,%function
_start:
    mov r0, sp
    bl wrapper_start
    mov r7, #1
    svc #0
    b .
.size _start, .-_start

/* AAPCS raw6(number, a, b, c, d, e, f), Linux ARM EABI syscall. */
.global raw6
.type raw6,%function
raw6:
    push {r4, r5, r7, lr}
    mov r7, r0
    mov r0, r1
    mov r1, r2
    mov r2, r3
    ldr r3, [sp, #16]
    ldr r4, [sp, #20]
    ldr r5, [sp, #24]
    svc #0
    pop {r4, r5, r7, pc}
.size raw6, .-raw6

.global memcpy
.type memcpy,%function
memcpy:
    mov ip, r0
1:  cmp r2, #0
    bxeq lr
    ldrb r3, [r1], #1
    strb r3, [ip], #1
    sub r2, r2, #1
    b 1b
.size memcpy, .-memcpy
.global __aeabi_memcpy
.set __aeabi_memcpy, memcpy
.global __aeabi_memcpy4
.set __aeabi_memcpy4, memcpy
.global __aeabi_memcpy8
.set __aeabi_memcpy8, memcpy

.global memset
.type memset,%function
memset:
    mov ip, r0
2:  cmp r2, #0
    bxeq lr
    strb r1, [ip], #1
    sub r2, r2, #1
    b 2b
.size memset, .-memset
.global __aeabi_memclr
.type __aeabi_memclr,%function
__aeabi_memclr:
    mov r2, r1
    mov r1, #0
    b memset
.global __aeabi_memclr4
.set __aeabi_memclr4, __aeabi_memclr
.global __aeabi_memclr8
.set __aeabi_memclr8, __aeabi_memclr
.section .note.GNU-stack,"",%progbits
