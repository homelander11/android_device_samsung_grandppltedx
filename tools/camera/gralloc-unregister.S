/* Pinned gralloc: replace the failed-module-lookup call-stack dump at RVA
 * 0x3c6e with a return through the existing epilogue. The preceding error log
 * remains. Valid-module cleanup does not pass through this instruction.
 * This guards a null dereference; ION/import/playback faults remain separate.
 */
.syntax unified
.thumb
.org 0x3c6e
    b.w 0x3cf6
