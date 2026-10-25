/* SPDX-License-Identifier: Apache-2.0 */
#include <dlfcn.h>
#include <stdio.h>
#include <unistd.h>

/* Resolve all relocations and run ELF constructors, without calling HAL open,
 * camera enumeration or EGL initialization. ELF constructors do run. Use the
 * device, or in its matching Android userspace; recovery's libraries differ.
 * This is a linker check, not a hardware-function test.
 */
int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s /absolute/path/to/HAL.so\n", argv[0]);
        return 2;
    }
    void *handle = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (handle == NULL) {
        fprintf(stderr, "FAIL: %s: %s\n", argv[1], dlerror());
        return 1;
    }
    printf("PASS: RTLD_NOW %s\n", argv[1]);
    fflush(stdout);
    // HAL services keep these DSOs loaded. Some MTK destructors destroy an
    // already destroyed singleton mutex when dlclose runs; exercise loading
    // only and let the kernel reclaim resources when this probe exits.
    _exit(0);
}
