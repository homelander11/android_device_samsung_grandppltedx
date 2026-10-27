/* SPDX-License-Identifier: Apache-2.0 */
/* Compatibility for the pinned grandppltedx Cam1DeviceBase ABI. Its old
 * allocators omit the request_memory cookie. Bind a separate allocator to
 * each physical camera when callbacks are registered; retain explicit cookies.
 * Open ID at 0xbc is verified in this vendor class's constructor. This module
 * must only be loaded by the device's camera-provider service.
 */
#include <dlfcn.h>
#include <pthread.h>

typedef struct camera_memory CameraMemory;
typedef CameraMemory *(*MemoryFn)(int, unsigned int, unsigned int, void *);
typedef void (*NotifyFn)(int, int, int, void *);
typedef void (*DataFn)(int, const CameraMemory *, unsigned int, void *, void *);
typedef void (*TimestampFn)(long long, int, const CameraMemory *, unsigned int, void *);
typedef void (*SetterFn)(void *, NotifyFn, DataFn, TimestampFn, MemoryFn, void *);
extern int __android_log_print(int, const char *, const char *, ...);

static const char setter_symbol[] =
    "_ZN7android14Cam1DeviceBase12setCallbacksEPFviiiPvEPFviPK13camera_memoryjP21camera_frame_metadataS1_EPFvxiS6_jS1_EPFPS4_ijjS1_ES1_";
static struct {
    MemoryFn memory;
    NotifyFn notify;
    void *cookie;
    unsigned int fallbacks;
    unsigned int capture_depth;
    unsigned int capture_focus_events;
} slots[2];
static pthread_mutex_t slot_lock = PTHREAD_MUTEX_INITIALIZER;
static SetterFn original_setter;
typedef int (*TakePictureFn)(void *);
static TakePictureFn original_take_picture;
static int pq_unavailable_logged;

static void lock_slots(void) {
    pthread_mutex_lock(&slot_lock);
}
static void unlock_slots(void) { pthread_mutex_unlock(&slot_lock); }

static CameraMemory *memory_for(unsigned int id, int fd, unsigned int size,
                                unsigned int count, void *cookie) {
    MemoryFn memory;
    void *registered;
    unsigned int first = 0;
    lock_slots();
    memory = slots[id].memory;
    registered = slots[id].cookie;
    if (!cookie && slots[id].fallbacks++ == 0) first = 1;
    unlock_slots();
    if (first) __android_log_print(4, "J2PrimeCamCtx", "memory cookie supplied for camera %u", id);
    return memory ? memory(fd, size, count, cookie ? cookie : registered) : 0;
}
static CameraMemory *memory0(int fd, unsigned int size, unsigned int count, void *cookie) {
    return memory_for(0, fd, size, count, cookie);
}
static CameraMemory *memory1(int fd, unsigned int size, unsigned int count, void *cookie) {
    return memory_for(1, fd, size, count, cookie);
}

static void notify_for(unsigned int id, int message, int ext1, int ext2, void *cookie) {
    lock_slots();
    NotifyFn notify = slots[id].notify;
    int internal_focus = slots[id].capture_depth && (message == 4 || message == 0x800);
    int first = internal_focus && slots[id].capture_focus_events++ == 0;
    unlock_slots();
    if (first) __android_log_print(4, "J2PrimeCamCtx", "internal precapture focus notification omitted for camera %u", id);
    /* takePicture holds CameraClient's lock while MTK waits for synchronous
     * precapture. Public focus callbacks from that internal AF cycle wait for
     * the same lock. Complete internal AF without re-entering the framework.
     * Outside capture, forward focus normally; shutter/error/data are unchanged.
     */
    if (!internal_focus && notify) notify(message, ext1, ext2, cookie);
}
static void notify0(int message, int ext1, int ext2, void *cookie) {
    notify_for(0, message, ext1, ext2, cookie);
}
static void notify1(int message, int ext1, int ext2, void *cookie) {
    notify_for(1, message, ext1, ext2, cookie);
}

void camera_set_callbacks(void *, NotifyFn, DataFn, TimestampFn, MemoryFn, void *)
    __asm__("_ZN7android14Cam1DeviceBase12setCallbacksEPFviiiPvEPFviPK13camera_memoryjP21camera_frame_metadataS1_EPFvxiS6_jS1_EPFPS4_ijjS1_ES1_");
void camera_set_callbacks(void *device, NotifyFn notify, DataFn data,
                         TimestampFn timestamp, MemoryFn memory, void *cookie) {
    /* Explicit-handle lookup returns the real definition even though its
     * vtable relocations are interposed by this provider-only global DSO.
     * Keep the reference: legacy camera DSOs are unsafe to unload explicitly.
     */
    lock_slots();
    SetterFn setter = original_setter;
    unlock_slots();
    if (!setter) {
        void *handle = dlopen("libcam.device1.so", RTLD_NOW | RTLD_NOLOAD);
        setter = handle ? (SetterFn)dlsym(handle, setter_symbol) : 0;
        if (!setter || setter == camera_set_callbacks) {
            __android_log_print(6, "J2PrimeCamCtx", "original callback setter unavailable");
            return;
        }
        lock_slots();
        original_setter = setter;
        unlock_slots();
    }
    unsigned int id = *(const unsigned int *)((const char *)device + 0xbc);
    if (id > 1) { setter(device, notify, data, timestamp, memory, cookie); return; }
    lock_slots();
    slots[id].memory = memory;
    slots[id].notify = notify;
    slots[id].cookie = cookie;
    slots[id].fallbacks = 0;
    unlock_slots();
    __android_log_print(4, "J2PrimeCamCtx", "registered callbacks for camera %u", id);
    setter(device, notify ? (id ? notify1 : notify0) : notify, data, timestamp,
           memory ? (id ? memory1 : memory0) : memory, cookie);
}

int camera_take_picture(void *) __asm__("_ZN7android14Cam1DeviceBase11takePictureEv");
int camera_take_picture(void *device) {
    lock_slots();
    TakePictureFn take = original_take_picture;
    unlock_slots();
    if (!take) {
        void *handle = dlopen("libcam.device1.so", RTLD_NOW | RTLD_NOLOAD);
        take = handle ? (TakePictureFn)dlsym(handle,
            "_ZN7android14Cam1DeviceBase11takePictureEv") : 0;
        if (!take || take == camera_take_picture) return -38;
        lock_slots();
        original_take_picture = take;
        unlock_slots();
    }
    unsigned int id = *(const unsigned int *)((const char *)device + 0xbc);
    if (id > 1) return take(device);
    lock_slots();
    if (slots[id].capture_depth++ == 0) slots[id].capture_focus_events = 0;
    unlock_slots();
    int result = take(device);
    lock_slots();
    --slots[id].capture_depth;
    unlock_slots();
    return result;
}

void j2prime_camera_memory_compat_init(void) { }

/* The pinned legacy perf bridge puts 52-byte Parcel objects on its stack.
 * Android 11's constructor writes 60 bytes. The controller's existing
 * uninitialized path skips these optional boosts; kernel DVFS/thermal control
 * continues normally. Do not enter the incompatible Binder bridge.
 */
_Bool camera_cpu_init(void *) __asm__("_ZN10CpuCtrlImp4initEv");
_Bool camera_cpu_init(void *device) {
    (void)device;
    __android_log_print(4, "J2PrimeCamCtx", "legacy CPU boost unavailable on this Binder ABI");
    return 0;
}

/* Preview's DpEngine_DynamicSharpness waits indefinitely in this old Binder
 * client for a PQ service absent from this ROM. getTDSHPFlag checks
 * assertStateLocked's status before using its remote object. Report ENODEV
 * through that existing failure path; the engine retains its disabled/default
 * quality settings. This provider-only override never loads a legacy PQ Binder
 * object into the Android 11 process.
 */
int camera_pq_unavailable(const void *)
    __asm__("_ZNK7android8PQClient17assertStateLockedEv");
int camera_pq_unavailable(const void *client) {
    (void)client;
    lock_slots();
    int first = !pq_unavailable_logged;
    pq_unavailable_logged = 1;
    unlock_slots();
    if (first) __android_log_print(4, "J2PrimeCamCtx", "legacy PQ service unavailable; retaining engine defaults");
    return -19;
}
