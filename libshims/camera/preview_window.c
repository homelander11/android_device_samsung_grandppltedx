/* SPDX-License-Identifier: Apache-2.0 */
/* The pinned MTK HAL recovers an Android 6 ANativeWindowBuffer by subtracting
 * 60 bytes from preview_stream_ops' handle pointer. The HIDL HAL1 wrapper
 * returns a standalone handle instead. Supply the legacy container and map
 * enqueue/cancel/lock back to the original pointer. Buffer handles and image
 * contents remain owned by Android's preview window.
 */
#include <dlfcn.h>
#include <hardware/camera.h>
#include <pthread.h>
#include <stddef.h>
#include <stdlib.h>

typedef preview_stream_ops_t Ops;
_Static_assert(sizeof(Ops) == 44, "unexpected preview-stream ABI");
typedef struct LegacyBase LegacyBase;
struct LegacyBase {
    int magic, version;
    void *reserved[4];
    void (*inc_ref)(LegacyBase *);
    void (*dec_ref)(LegacyBase *);
};
typedef struct {
    LegacyBase common;
    int width, height, stride, format, usage;
    void *reserved[2];
    buffer_handle_t handle;
    void *reserved_proc[8];
} LegacyBuffer;
_Static_assert(sizeof(void *) == 4, "only the pinned 32-bit camera ABI is supported");
_Static_assert(offsetof(LegacyBuffer, handle) == 60, "legacy handle offset");
_Static_assert(offsetof(LegacyBase, inc_ref) == 24, "legacy incRef offset");
_Static_assert(sizeof(LegacyBuffer) == 96, "legacy buffer size");

typedef struct Window Window;
typedef struct Buffer Buffer;
struct Buffer {
    LegacyBuffer legacy;
    Window *owner;
    Buffer *next;
    buffer_handle_t *original;
    unsigned int refs; /* one map reference plus the HAL's strong references */
    int dequeued;
};
struct Window {
    Ops ops; /* first: every callback receives this address */
    Ops *original;
    pthread_mutex_t lock;
    Buffer *buffers;
    int width, height, format, usage;
    unsigned int in_flight;
    int changing;
};
static Window windows[2] = {
    { .lock = PTHREAD_MUTEX_INITIALIZER },
    { .lock = PTHREAD_MUTEX_INITIALIZER },
};
static pthread_mutex_t setter_lock = PTHREAD_MUTEX_INITIALIZER;
typedef int (*Setter)(void *, Ops *);
static Setter original_setter;
extern int __android_log_print(int, const char *, const char *, ...);

static void inc_ref(LegacyBase *base) {
    Buffer *b = (Buffer *)base;
    pthread_mutex_lock(&b->owner->lock);
    ++b->refs;
    pthread_mutex_unlock(&b->owner->lock);
}
static void dec_ref(LegacyBase *base) {
    Buffer *b = (Buffer *)base;
    pthread_mutex_lock(&b->owner->lock);
    if (b->refs > 1) --b->refs;
    else __android_log_print(6, "J2PrimeCamWin", "unbalanced native-buffer reference");
    pthread_mutex_unlock(&b->owner->lock);
}
static Buffer *find_buffer(Window *w, buffer_handle_t *handle, int original) {
    for (Buffer *b = w->buffers; b; b = b->next)
        if ((original ? b->original : &b->legacy.handle) == handle) return b;
    return 0;
}
/* Caller holds lock. Do not invalidate containers while the HAL uses them. */
static int busy(Window *w) {
    if (w->changing || w->in_flight) return 1;
    for (Buffer *b = w->buffers; b; b = b->next)
        if (b->dequeued || b->refs != 1) return 1;
    return 0;
}
static void clear_buffers(Window *w) {
    Buffer *b = w->buffers;
    w->buffers = 0;
    while (b) { Buffer *next = b->next; free(b); b = next; }
}
static int dequeue(Ops *ops, buffer_handle_t **handle, int *stride) {
    Window *w = (Window *)ops;
    if (!handle || !stride) return -22;
    pthread_mutex_lock(&w->lock);
    Ops *real = w->original;
    if (!real || w->changing) { pthread_mutex_unlock(&w->lock); return -19; }
    ++w->in_flight;
    pthread_mutex_unlock(&w->lock);
    buffer_handle_t *native = 0;
    int result = real->dequeue_buffer(real, &native, stride);
    pthread_mutex_lock(&w->lock);
    --w->in_flight;
    if (result) { pthread_mutex_unlock(&w->lock); return result; }
    if (!native || !*native) { pthread_mutex_unlock(&w->lock); return -22; }
    Buffer *b = find_buffer(w, native, 1);
    if (!b) {
        b = calloc(1, sizeof(*b));
        if (!b) {
            ++w->in_flight;
            pthread_mutex_unlock(&w->lock);
            real->cancel_buffer(real, native);
            pthread_mutex_lock(&w->lock);
            --w->in_flight;
            pthread_mutex_unlock(&w->lock);
            return -12;
        }
        b->owner = w;
        b->original = native;
        b->refs = 1;
        b->legacy.common.magic = 0x5f626672;
        b->legacy.common.version = sizeof(LegacyBuffer);
        b->legacy.common.inc_ref = inc_ref;
        b->legacy.common.dec_ref = dec_ref;
        b->next = w->buffers;
        w->buffers = b;
    }
    if (b->dequeued || (b->legacy.handle && b->legacy.handle != *native)) {
        pthread_mutex_unlock(&w->lock);
        return -22;
    }
    b->legacy.width = w->width;
    b->legacy.height = w->height;
    b->legacy.stride = *stride;
    b->legacy.format = w->format;
    b->legacy.usage = w->usage;
    b->legacy.handle = *native;
    b->dequeued = 1;
    *handle = &b->legacy.handle;
    pthread_mutex_unlock(&w->lock);
    return 0;
}
static int buffer_op(Ops *ops, buffer_handle_t *handle, int operation) {
    Window *w = (Window *)ops;
    pthread_mutex_lock(&w->lock);
    Ops *real = w->original;
    Buffer *b = find_buffer(w, handle, 0);
    if (!real || !b || !b->dequeued || w->changing) {
        pthread_mutex_unlock(&w->lock); return -22;
    }
    buffer_handle_t *native = b->original;
    ++w->in_flight;
    pthread_mutex_unlock(&w->lock);
    int result = operation == 0 ? real->enqueue_buffer(real, native) :
                 operation == 1 ? real->cancel_buffer(real, native) :
                                  real->lock_buffer(real, native);
    pthread_mutex_lock(&w->lock);
    --w->in_flight;
    if (!result && operation != 2) b->dequeued = 0;
    pthread_mutex_unlock(&w->lock);
    return result;
}
static int enqueue(Ops *w, buffer_handle_t *h) { return buffer_op(w, h, 0); }
static int cancel(Ops *w, buffer_handle_t *h) { return buffer_op(w, h, 1); }
static int lock_buffer(Ops *w, buffer_handle_t *h) { return buffer_op(w, h, 2); }

/* These HIDL operations free the original circulating-buffer map, including on
 * failure. Retire our empty containers before forwarding, and block dequeue
 * during the transition. The HAL must release its buffers before reconfiguring.
 */
static int configure(Ops *ops, int operation, int a, int b, int c) {
    Window *w = (Window *)ops;
    pthread_mutex_lock(&w->lock);
    Ops *real = w->original;
    if (!real || busy(w)) {
        __android_log_print(5, "J2PrimeCamWin", "preview reconfiguration busy (operation %d)", operation);
        pthread_mutex_unlock(&w->lock); return -16;
    }
    w->changing = 1;
    clear_buffers(w);
    pthread_mutex_unlock(&w->lock);
    int result = operation == 0 ? real->set_buffer_count(real, a) :
                 operation == 1 ? real->set_buffers_geometry(real, a, b, c) :
                                  real->set_usage(real, a);
    pthread_mutex_lock(&w->lock);
    if (!result) {
        if (operation == 1) { w->width = a; w->height = b; w->format = c; }
        if (operation == 2) w->usage = a;
    }
    w->changing = 0;
    pthread_mutex_unlock(&w->lock);
    return result;
}
static int set_count(Ops *w, int n) { return configure(w, 0, n, 0, 0); }
static int set_geometry(Ops *w, int x, int y, int f) { return configure(w, 1, x, y, f); }
static int set_usage(Ops *w, int usage) { return configure(w, 2, usage, 0, 0); }
static int set_crop(Ops *ops, int l, int t, int r, int b) {
    Window *w = (Window *)ops;
    return w->original->set_crop(w->original, l, t, r, b);
}
static int set_swap(Ops *ops, int n) {
    Window *w = (Window *)ops;
    return w->original->set_swap_interval(w->original, n);
}
static int get_min(const Ops *ops, int *n) {
    const Window *w = (const Window *)ops;
    return w->original->get_min_undequeued_buffer_count(w->original, n);
}
static int set_timestamp(Ops *ops, long long timestamp) {
    Window *w = (Window *)ops;
    return w->original->set_timestamp(w->original, timestamp);
}

int camera_set_preview(void *, Ops *)
    __asm__("_ZN7android14Cam1DeviceBase16setPreviewWindowEP18preview_stream_ops");
int camera_set_preview(void *device, Ops *ops) {
    pthread_mutex_lock(&setter_lock);
    Setter setter = original_setter;
    if (!setter) {
        void *h = dlopen("libcam.device1.so", RTLD_NOW | RTLD_NOLOAD);
        setter = h ? (Setter)dlsym(h,
            "_ZN7android14Cam1DeviceBase16setPreviewWindowEP18preview_stream_ops") : 0;
        if (setter == camera_set_preview) setter = 0;
        original_setter = setter;
    }
    pthread_mutex_unlock(&setter_lock);
    if (!setter) return -38;
    unsigned int id = *(const unsigned int *)((const char *)device + 0xbc);
    if (id > 1) return setter(device, ops);
    Window *w = &windows[id];
    pthread_mutex_lock(&w->lock);
    if (busy(w)) {
        __android_log_print(5, "J2PrimeCamWin", "preview window busy for camera %u (same=%d, null=%d)",
                            id, ops == w->original, ops == 0);
        pthread_mutex_unlock(&w->lock); return -16;
    }
    clear_buffers(w);
    w->original = ops;
    w->width = w->height = w->format = w->usage = 0;
    w->ops.dequeue_buffer = dequeue;
    w->ops.enqueue_buffer = enqueue;
    w->ops.cancel_buffer = cancel;
    w->ops.set_buffer_count = set_count;
    w->ops.set_buffers_geometry = set_geometry;
    w->ops.set_crop = set_crop;
    w->ops.set_usage = set_usage;
    w->ops.set_swap_interval = set_swap;
    w->ops.get_min_undequeued_buffer_count = get_min;
    w->ops.lock_buffer = lock_buffer;
    w->ops.set_timestamp = set_timestamp;
    pthread_mutex_unlock(&w->lock);
    __android_log_print(4, "J2PrimeCamWin", "preview window registered for camera %u", id);
    return setter(device, ops ? &w->ops : 0);
}
