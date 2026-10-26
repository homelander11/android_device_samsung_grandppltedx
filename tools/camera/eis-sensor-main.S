/* SPDX-License-Identifier: Apache-2.0 */
/* Pinned block replacement; see sensor-startup.json for RVA and hashes. */
.syntax unified
.thumb
.section .text,"ax",%progbits
.global sensor_guard
.type sensor_guard,%function
.thumb_func
sensor_guard:
 cbnz r0, .Lpresent
 str.w r0, [r4, #0x738]
 str.w r0, [r4, #0x73c]
 b .Lsetup
.Lpresent:
 ldr r1, .Lcb
.Lcb_add:
 add r1, pc
 ldr r1, [r1]
 ldr r5, [r0]
 ldr r3, [r5, #12]
 blx r3
 ldr.w r0, [r4, #0x610]
 movs r1, #0
 movs r2, #0x21
 ldr r3, [r0]
 ldr r3, [r3, #16]
 blx r3
 str.w r0, [r4, #0x73c]
 ldr.w r0, [r4, #0x610]
 movs r1, #2
 movs r2, #0x21
 ldr r3, [r0]
 ldr r3, [r3, #16]
 blx r3
 str.w r0, [r4, #0x738]
.Lsetup:
 ldr.w r11, .Ltag
.Ltag_add:
 add r11, pc
 ldr.w r10, .Lfun
.Lfun_add:
 add r10, pc
 adds r4, #4
 b .Lend
.balign 4
.Lcb: .word 1096220 - (766280 + (.Lcb_add-sensor_guard) + 4)
.Ltag: .word 1028595 - (766280 + (.Ltag_add-sensor_guard) + 4)
.Lfun: .word 1061832 - (766280 + (.Lfun_add-sensor_guard) + 4)
.org 0x90, 0
.Lend:
.size sensor_guard, .-sensor_guard
