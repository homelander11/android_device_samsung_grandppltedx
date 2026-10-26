/* SPDX-License-Identifier: Apache-2.0 */
/* At AfMgr::init RVA 0x77f8a: mark unsupported motion assist unavailable. */
.syntax unified
.thumb
movs r0, #0
str r0, [r4, r1]
