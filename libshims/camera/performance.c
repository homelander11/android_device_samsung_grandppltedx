/* SPDX-License-Identifier: Apache-2.0 */
/* The legacy Binder bridge uses 52-byte stack Parcels; Android 11 writes 60.
 * Camera algorithms also call its C entry points directly, independently of
 * CpuCtrlImp. Reject optional boost registration through the documented -1
 * result and leave the algorithm's existing no-boost path intact. Load only in
 * this camera provider, never as a replacement for the system's performance API.
 */
int PerfServiceNative_userRegScn(void) { return -1; }

void PerfServiceNative_userRegScnConfig(int handle, int command,
                                      int p1, int p2, int p3, int p4) {
    (void)handle; (void)command;
    (void)p1; (void)p2; (void)p3; (void)p4;
}
void PerfServiceNative_userEnable(int handle) { (void)handle; }
void PerfServiceNative_userDisable(int handle) { (void)handle; }
void PerfServiceNative_userUnregScn(int handle) { (void)handle; }
