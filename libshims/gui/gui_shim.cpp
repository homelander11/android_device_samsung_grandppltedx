#define LOG_TAG "HW_GUI"

#include <ui/GraphicBuffer.h>
#include <ui/GraphicBufferMapper.h>
#include <ui/PixelFormat.h>
#include <ui/Rect.h>
#include <log/log.h>
#include <utils/Errors.h>

#include <dlfcn.h>
#include <stdint.h>
#include <string>

extern "C" {

    // MTK camera libraries use the pre-Android-11 lock ABI. Preserve the
    // implicit this pointer and omit the two optional layout output pointers.
    android::status_t _ZN7android13GraphicBuffer4lockEjPPv(
            android::GraphicBuffer* buffer, uint32_t usage, void** vaddr) {
        if (buffer == nullptr || vaddr == nullptr) {
            return android::BAD_VALUE;
        }
        return buffer->lock(usage, vaddr, nullptr, nullptr);
    }

    /*
     * ---------------------------------------------------------------------------
     * GraphicBufferMapper::lockYCbCr()
     * ---------------------------------------------------------------------------
     *
     * Shim:
     *
     *   lockYCbCr(..., int usage, ...)
     *
     * para:
     *
     *   lockYCbCr(..., uint32_t usage, ...)
     *
     * Como GraphicBufferMapper::lockYCbCr() é método de classe, o primeiro
     * argumento recebido pelo ABI é o ponteiro "this".
     */

    /*
     * Símbolo fornecido pelo libui:
     *
     * android::GraphicBufferMapper::lockYCbCr(
     *     buffer_handle_t,
     *     uint32_t,
     *     const android::Rect&,
     *     android_ycbcr*
     * )
     */
    android::status_t
    _ZN7android19GraphicBufferMapper9lockYCbCrEPK13native_handlejRKNS_4RectEP13android_ycbcr(
        void* thisptr,
        buffer_handle_t handle,
        uint32_t usage,
        const android::Rect& bounds,
        android_ycbcr* ycbcr);


    /*
     * Símbolo legado:
     *
     * android::GraphicBufferMapper::lockYCbCr(
     *     buffer_handle_t,
     *     int,
     *     const android::Rect&,
     *     android_ycbcr*
     * )
     */
    android::status_t
    _ZN7android19GraphicBufferMapper9lockYCbCrEPK13native_handleiRKNS_4RectEP13android_ycbcr(
        void* thisptr,
        buffer_handle_t handle,
        int usage,
        const android::Rect& bounds,
        android_ycbcr* ycbcr) {

        ALOGV(
            "GraphicBufferMapper::lockYCbCr legacy "
            "this=%p handle=%p usage=0x%x",
            thisptr,
            static_cast<const void*>(handle),
              static_cast<uint32_t>(usage)
        );

        return
        _ZN7android19GraphicBufferMapper9lockYCbCrEPK13native_handlejRKNS_4RectEP13android_ycbcr(
            thisptr,
            handle,
            static_cast<uint32_t>(usage),
                                                                                                 bounds,
                                                                                                 ycbcr
        );
        }


        /*
         * ---------------------------------------------------------------------------
         * GraphicBufferMapper::lock()
         * ---------------------------------------------------------------------------
         *
         * ESTE É O SHIM IMPORTANTE PARA O hwcomposer.mt6735.so.
         *
         * O blob antigo procura:
         *
         * _ZN7android19GraphicBufferMapper4lockEPK13native_handlejRKNS_4RectEPPv
         *
         * que corresponde a:
         *
         * GraphicBufferMapper::lock(
         *     buffer_handle_t,
         *     uint32_t usage,
         *     const Rect&,
         *     void**
         * )
         *
         * No Android 11 / LineageOS 18.1, lock() possui também:
         *
         *     int32_t* outBytesPerPixel
         *     int32_t* outBytesPerStride
         *
         * Portanto este shim implementa a ABI antiga e chama a API nova.
         */
        android::status_t
        _ZN7android19GraphicBufferMapper4lockEPK13native_handlejRKNS_4RectEPPv(
            void* thisptr,
            buffer_handle_t handle,
            uint32_t usage,
            const android::Rect& bounds,
            void** vaddr) {

            ALOGV(
                "GraphicBufferMapper::lock legacy "
                "this=%p handle=%p usage=0x%x "
                "rect=[%d,%d,%d,%d]",
                thisptr,
                static_cast<const void*>(handle),
                  usage,
                  bounds.left,
                  bounds.top,
                  bounds.right,
                  bounds.bottom
            );

            if (thisptr == nullptr) {
                ALOGE("GraphicBufferMapper::lock: this == nullptr");
                return android::BAD_VALUE;
            }

            if (handle == nullptr) {
                ALOGE("GraphicBufferMapper::lock: handle == nullptr");
                return android::BAD_VALUE;
            }

            if (vaddr == nullptr) {
                ALOGE("GraphicBufferMapper::lock: vaddr == nullptr");
                return android::BAD_VALUE;
            }

            auto* mapper =
            reinterpret_cast<android::GraphicBufferMapper*>(thisptr);

            android::status_t status = mapper->lock(
                handle,
                usage,
                bounds,
                vaddr,
                nullptr,
                nullptr
            );

            if (status != android::NO_ERROR) {
                ALOGE(
                    "GraphicBufferMapper::lock failed: %d",
                    status
                );
            }

            return status;
            }


            /*
             * Variante ainda mais antiga:
             *
             * GraphicBufferMapper::lock(
             *     buffer_handle_t,
             *     int usage,
             *     const Rect&,
             *     void**
             * )
             *
             * Converte int -> uint32_t e encaminha para o shim acima.
             */
            android::status_t
            _ZN7android19GraphicBufferMapper4lockEPK13native_handleiRKNS_4RectEPPv(
                void* thisptr,
                buffer_handle_t handle,
                int usage,
                const android::Rect& bounds,
                void** vaddr) {

                return
                _ZN7android19GraphicBufferMapper4lockEPK13native_handlejRKNS_4RectEPPv(
                    thisptr,
                    handle,
                    static_cast<uint32_t>(usage),
                                                                                       bounds,
                                                                                       vaddr
                );
                }


                /*
                 * ---------------------------------------------------------------------------
                 * GraphicBuffer constructor
                 * ---------------------------------------------------------------------------
                 *
                 * Blob antigo:
                 *
                 * GraphicBuffer(
                 *     uint32_t width,
                 *     uint32_t height,
                 *     PixelFormat format,
                 *     uint32_t usage
                 * )
                 *
                 * Framework novo:
                 *
                 * GraphicBuffer(
                 *     uint32_t width,
                 *     uint32_t height,
                 *     PixelFormat format,
                 *     uint32_t usage,
                 *     std::string requestorName
                 * )
                 */
                void
                _ZN7android13GraphicBufferC1Ejjij(
                    void* instance,
                    uint32_t inWidth,
                    uint32_t inHeight,
                    android::PixelFormat inFormat,
                    uint32_t inUsage) {

                    using GraphicBufferCtor = void (*)(
                        void*,
                        uint32_t,
                        uint32_t,
                        android::PixelFormat,
                        uint32_t,
                        std::string
                    );

                    static GraphicBufferCtor func = nullptr;

                    if (func == nullptr) {
                        func = reinterpret_cast<GraphicBufferCtor>(
                            dlsym(
                                RTLD_NEXT,
                                "_ZN7android13GraphicBufferC1EjjijNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEE"
                            )
                        );

                        if (func == nullptr) {
                            const char* error = dlerror();

                            ALOGE(
                                "Unable to resolve new GraphicBuffer constructor: %s",
                                error != nullptr ? error : "unknown error"
                            );

                            return;
                        }
                    }

                    ALOGV(
                        "GraphicBuffer legacy ctor "
                        "instance=%p width=%u height=%u format=%d usage=0x%x",
                        instance,
                        inWidth,
                        inHeight,
                        static_cast<int>(inFormat),
                          inUsage
                    );

                    std::string requestorName("HW_GUI");

                    func(
                        instance,
                         inWidth,
                         inHeight,
                         inFormat,
                         inUsage,
                         requestorName
                    );
                    }


                    /*
                     * ---------------------------------------------------------------------------
                     * Fence::wait()
                     * ---------------------------------------------------------------------------
                     *
                     * Converte:
                     *
                     *     Fence::wait(unsigned int)
                     *
                     * para:
                     *
                     *     Fence::wait(int)
                     *
                     * Fence também é classe, portanto precisamos preservar o "this" implícito.
                     */

                    /*
                     * Implementação existente fornecida pelo framework.
                     */
                    android::status_t
                    _ZN7android5Fence4waitEi(
                        void* thisptr,
                        int timeout);


                    /*
                     * Símbolo legado.
                     */
                    android::status_t
                    _ZN7android5Fence4waitEj(
                        void* thisptr,
                        unsigned int timeout) {

                        return _ZN7android5Fence4waitEi(
                            thisptr,
                            static_cast<int>(timeout)
                        );
                        }

} // extern "C"
