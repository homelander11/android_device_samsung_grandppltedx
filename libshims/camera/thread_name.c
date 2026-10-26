/* SPDX-License-Identifier: Apache-2.0 */
/* Camera-only legacy Thread::run import adapter. */
extern int android_thread_run(void *thread, const char *name, int priority,
                              unsigned int stack_size)
    __asm__("_ZN7android6Thread3runEPKcij");
int j2prime_camera_thread_run(void *thread, const char *name, int priority,
                              unsigned int stack_size) {
    return android_thread_run(thread, name ? name : "MtkCam", priority, stack_size);
}
