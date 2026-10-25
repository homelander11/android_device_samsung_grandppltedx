// SPDX-License-Identifier: Apache-2.0
#include <android/hardware/light/2.0/ILight.h>
#include <dlfcn.h>
#include <stdio.h>
#include <unistd.h>

// Load the same wrapper/legacy driver as the Light service and enumerate its
// types. Do not register a binder service or call setLight/change brightness.
int main() {
    using android::hardware::light::V2_0::ILight;
    using android::hardware::light::V2_0::Type;
    void* library = dlopen("/vendor/lib/hw/android.hardware.light@2.0-impl.so", RTLD_NOW);
    if (library == nullptr) {
        fprintf(stderr, "FAIL: Light wrapper: %s\n", dlerror());
        return 1;
    }
    auto fetch = reinterpret_cast<ILight* (*)(const char*)>(dlsym(library, "HIDL_FETCH_ILight"));
    if (fetch == nullptr) {
        fprintf(stderr, "FAIL: missing Light factory\n");
        return 1;
    }
    android::sp<ILight> light = fetch("default");
    if (light == nullptr) {
        fprintf(stderr, "FAIL: cannot open the legacy lights module\n");
        return 1;
    }
    bool hasBacklight = false;
    auto status = light->getSupportedTypes([&](const auto& types) {
        for (Type type : types) {
            printf("Legacy Light type: %u\n", static_cast<unsigned>(type));
            hasBacklight |= type == Type::BACKLIGHT;
        }
    });
    bool success = status.isOk() && hasBacklight;
    printf("%s: Light wrapper enumeration, BACKLIGHT=%s; brightness unchanged\n",
           success ? "PASS" : "FAIL", hasBacklight ? "yes" : "no");
    fflush(stdout);
    _exit(success ? 0 : 1);
}
