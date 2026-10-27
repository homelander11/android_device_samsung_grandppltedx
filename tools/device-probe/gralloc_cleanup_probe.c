/* SPDX-License-Identifier: Apache-2.0 */
/* Separate-process fault injection. Never run inside a graphics service.
 * Prepare the exact candidate with fix_gralloc_unregister.py before running.
 * No display, camera, calibration, pixel data or firmware writes are used.
 */
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <unistd.h>

static unsigned calls;
static uint32_t handle[64];

/* Export from the executable so the subsequently loaded DSO resolves here. */
int hw_get_module(const char *id, const void **out) {
    (void)id;
    ++calls;
    *out = NULL;
    return -2;
}

int main(void) {
    if (dlsym(RTLD_DEFAULT, "hw_get_module") != (void *)&hw_get_module) {
        fprintf(stderr, "FAIL: lookup interception is not active\n");
        return 2;
    }
    void *library = dlopen("/data/local/tmp/j2prime-gralloc-unregister-candidate.so", RTLD_NOW);
    if (!library) {
        fprintf(stderr, "FAIL: %s\n", dlerror());
        return 3;
    }
    void (*unregister_buffer)(void *) = (void (*)(void *))dlsym(library,
        "_Z26gralloc_backend_unregisterP16private_handle_t");
    if (!unregister_buffer) _exit(4);
    handle[0x2c / 4] = 4;
    handle[0x34 / 4] = 0x2000;
    handle[0x50 / 4] = 0x900000;
    handle[0x10 / 4] = 0x55;
    unregister_buffer(handle);
    if (calls != 1 || handle[0x50 / 4] != 0x900000 || handle[0x10 / 4] != 0x55)
        _exit(5);
    puts("PASS: failed-module cleanup returns without touching buffers");
    fflush(stdout);
    _exit(0);
}
