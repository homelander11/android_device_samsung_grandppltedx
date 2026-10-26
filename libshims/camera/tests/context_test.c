/* SPDX-License-Identifier: Apache-2.0 */
/* Isolated ABI contract test; no camera devices, Binder calls or NVRAM I/O. */
typedef struct camera_memory CameraMemory;
typedef CameraMemory *(*MemoryFn)(int,unsigned,unsigned,void*);
typedef void (*NotifyFn)(int,int,int,void*);
typedef void (*DataFn)(int,const CameraMemory*,unsigned,void*,void*);
typedef void (*TimestampFn)(long long,int,const CameraMemory*,unsigned,void*);
extern int check_pq(const void*) __asm__("_ZNK7android8PQClient17assertStateLockedEv");
extern _Bool check_cpu_init(void*) __asm__("_ZN10CpuCtrlImp4initEv");
extern void call_setter(void*,NotifyFn,DataFn,TimestampFn,MemoryFn,void*) __asm__("_ZN7android14Cam1DeviceBase12setCallbacksEPFviiiPvEPFviPK13camera_memoryjP21camera_frame_metadataS1_EPFvxiS6_jS1_EPFPS4_ijjS1_ES1_");
static unsigned device0[64],device1[64],device2[64];
static MemoryFn registered[2],last_fn;
static void *registered_user[2],*seen_user;
static int seen_fd,flags_ok=1;
static unsigned seen_size,seen_count;
static const char *thread_name;static void *thread_self;static int thread_priority;static unsigned thread_stack;
extern int j2prime_camera_thread_run(void*,const char*,int,unsigned);
int thread_original(void*,const char*,int,unsigned) __asm__("_ZN7android6Thread3runEPKcij");
int thread_original(void *self,const char *name,int priority,unsigned stack){thread_self=self;thread_name=name;thread_priority=priority;thread_stack=stack;return -47;}
static int same(const char *a,const char *b){while(*a && *a==*b){a++;b++;}return *a==*b;}
static CameraMemory *legacy_mem(int fd,unsigned size,unsigned count,void *user){
 seen_fd=fd;seen_size=size;seen_count=count;seen_user=user;return (CameraMemory*)0x76543210;
}
static void real_setter(void *device,NotifyFn n,DataFn d,TimestampFn t,MemoryFn mem,void *user){
 unsigned id=((unsigned*)device)[47];last_fn=mem;
 if(id<2){registered[id]=mem;registered_user[id]=user;}
}
void *mock_open(const char *name,int flags) __asm__("__wrap_dlopen");
void *mock_open(const char *name,int flags){if(flags!=4)flags_ok=0;return (void*)1;}
void *mock_sym(void *handle,const char *name) __asm__("__wrap_dlsym");
void *mock_sym(void *handle,const char *name){return same(name,"_ZN7android6Thread3runEPKcij") ? (void*)&thread_original : (void*)&real_setter;}
int mock_log(int priority,const char *tag,const char *text, ...) __asm__("__wrap___android_log_print");
int mock_log(int priority,const char *tag,const char *text, ...){return 0;}
int main(void){
 int rc=1;device0[47]=0;device1[47]=1;device2[47]=2;
 call_setter(device0,0,0,0,legacy_mem,(void*)0x11111111);
 call_setter(device1,0,0,0,legacy_mem,(void*)0x22222222);
 if(!flags_ok || !registered[0] || !registered[1] || registered[0]==registered[1])goto done;
 if(registered_user[0]!=(void*)0x11111111 || registered_user[1]!=(void*)0x22222222)goto done;
 if(registered[0](-1,1234,7,0)!=(CameraMemory*)0x76543210 || seen_user!=(void*)0x11111111 || seen_fd!=-1 || seen_size!=1234 || seen_count!=7)goto done;
 registered[1](8,4321,3,0);if(seen_user!=(void*)0x22222222 || seen_fd!=8 || seen_size!=4321 || seen_count!=3)goto done;
 registered[0](-1,1,1,(void*)0x33333333);if(seen_user!=(void*)0x33333333)goto done;
 call_setter(device0,0,0,0,legacy_mem,(void*)0x44444444);
 registered[0](-1,1,1,0);if(seen_user!=(void*)0x44444444)goto done;
 registered[1](-1,1,1,0);if(seen_user!=(void*)0x22222222)goto done;
 call_setter(device2,0,0,0,legacy_mem,(void*)0x55555555);if(last_fn!=legacy_mem)goto done;
 call_setter(device0,0,0,0,0,0);if(registered[0] || registered_user[0])goto done;
 if(j2prime_camera_thread_run((void*)0x11112222,"Given",-9,131072)!=-47 || thread_self!=(void*)0x11112222 || !same(thread_name,"Given") || thread_priority!=-9 || thread_stack!=131072)goto done;
 if(j2prime_camera_thread_run((void*)0x11112222,0,0,0)!=-47 || !same(thread_name,"MtkCam") || thread_priority!=0 || thread_stack!=0)goto done;
 if(j2prime_camera_thread_run((void*)0x11112222,"",4,8192)!=-47 || !same(thread_name,"") || thread_priority!=4 || thread_stack!=8192)goto done;
 if(check_cpu_init(device0))goto done;
 if(check_pq(device0)!=-19 || device0[47]!=0)goto done;
 rc=0;
done:
 return rc;
}
