/* SPDX-License-Identifier: Apache-2.0 */
/* Isolated ABI contract test; no camera devices, Binder calls or NVRAM I/O. */
typedef struct camera_memory { void *data;unsigned size;void *handle;
 void (*release)(struct camera_memory*); } CameraMemory;
typedef CameraMemory *(*MemoryFn)(int,unsigned,unsigned,void*);
typedef void (*NotifyFn)(int,int,int,void*);
typedef void (*DataFn)(int,const CameraMemory*,unsigned,void*,void*);
typedef void (*TimestampFn)(long long,int,const CameraMemory*,unsigned,void*);
extern int check_pq(const void*) __asm__("_ZNK7android8PQClient17assertStateLockedEv");
extern int PerfServiceNative_userRegScn(void);
extern void PerfServiceNative_userRegScnConfig(int,int,int,int,int,int);
extern void PerfServiceNative_userEnable(int);
extern void PerfServiceNative_userDisable(int);
extern void PerfServiceNative_userUnregScn(int);
extern _Bool check_cpu_init(void*) __asm__("_ZN10CpuCtrlImp4initEv");
extern void call_setter(void*,NotifyFn,DataFn,TimestampFn,MemoryFn,void*) __asm__("_ZN7android14Cam1DeviceBase12setCallbacksEPFviiiPvEPFviPK13camera_memoryjP21camera_frame_metadataS1_EPFvxiS6_jS1_EPFPS4_ijjS1_ES1_");
static unsigned device0[64],device1[64],device2[64];
static MemoryFn registered[2],last_fn;
static NotifyFn registered_notify[2];
static TimestampFn registered_timestamp[2];
static CameraMemory *memory_result;
static CameraMemory dummy_memory;
static unsigned char video_data[115200*2+8];
static CameraMemory video_memory;
static int timestamp_count,timestamp_message;
static long long timestamp_time;
static unsigned timestamp_index;
static const CameraMemory *timestamp_memory;
static void *timestamp_cookie;
static void timestamp_notice(long long t,int m,const CameraMemory *mem,unsigned i,void*c){
 timestamp_count++;timestamp_time=t;timestamp_message=m;timestamp_memory=mem;timestamp_index=i;timestamp_cookie=c;
}
static int notify_count[2],notify_message[2],notify_ext1[2],notify_ext2[2],capture_bad,nest_test,in_nested;
static void *notify_cookie[2];
extern int call_take(void*) __asm__("_ZN7android14Cam1DeviceBase11takePictureEv");
extern int call_metadata(void*,_Bool) __asm__("_ZN7android14Cam1DeviceBase22storeMetaDataInBuffersEb");
extern void call_af_move(void*,_Bool) __asm__("_ZN10CallBack3A12enableAFMoveEb");
static unsigned af_callback[8];
static int metadata_calls,metadata_status;
static void *metadata_device;
static _Bool metadata_enabled;
static int real_metadata(void *device,_Bool enable){metadata_calls++;metadata_device=device;metadata_enabled=enable;return metadata_status;}
static void *registered_user[2],*seen_user;
static int seen_fd,flags_ok=1;
static unsigned seen_size,seen_count;
static const char *thread_name;static void *thread_self;static int thread_priority;static unsigned thread_stack;
extern int j2prime_camera_thread_run(void*,const char*,int,unsigned);
int thread_original(void*,const char*,int,unsigned) __asm__("_ZN7android6Thread3runEPKcij");
int thread_original(void *self,const char *name,int priority,unsigned stack){thread_self=self;thread_name=name;thread_priority=priority;thread_stack=stack;return -47;}
static int same(const char *a,const char *b){while(*a && *a==*b){a++;b++;}return *a==*b;}
static int preview_session_calls[2];
int j2prime_camera_preview_new_session(unsigned id){if(id>1)return -22;preview_session_calls[id]++;return 0;}
static CameraMemory *legacy_mem(int fd,unsigned size,unsigned count,void *user){
 seen_fd=fd;seen_size=size;seen_count=count;seen_user=user;return memory_result?memory_result:&dummy_memory;
}
static void real_setter(void *device,NotifyFn n,DataFn d,TimestampFn t,MemoryFn mem,void *user){
 unsigned id=((unsigned*)device)[47];last_fn=mem;
 if(id<2){registered[id]=mem;registered_user[id]=user;registered_notify[id]=n;registered_timestamp[id]=t;}
}
static void notice0(int m,int a,int b,void*c){notify_count[0]++;notify_message[0]=m;notify_ext1[0]=a;notify_ext2[0]=b;notify_cookie[0]=c;}
static void notice1(int m,int a,int b,void*c){notify_count[1]++;notify_message[1]=m;notify_ext1[1]=a;notify_ext2[1]=b;notify_cookie[1]=c;}
static int real_take(void *device){
 unsigned id=((unsigned*)device)[47];if(id>1)return -61;
 int count=notify_count[id];
 registered_notify[id](4,1,2,registered_user[id]);
 registered_notify[id](0x800,3,4,registered_user[id]);
 if(notify_count[id]!=count)capture_bad=1;
 if(nest_test && !in_nested){
  in_nested=1;if(call_take(device)!=-61)capture_bad=1;in_nested=0;
  count=notify_count[id];registered_notify[id](4,5,6,registered_user[id]);
  if(notify_count[id]!=count)capture_bad=1;
 }
 registered_notify[id](2,-3,7,registered_user[id]);
 if(notify_message[id]!=2 || notify_ext1[id]!=-3 || notify_ext2[id]!=7 || notify_cookie[id]!=registered_user[id])capture_bad=1;
 registered_notify[id](1,9,-8,registered_user[id]);
 if(notify_message[id]!=1 || notify_ext1[id]!=9 || notify_ext2[id]!=-8)capture_bad=1;
 unsigned other=id^1;count=notify_count[other];
 registered_notify[other](4,11,12,registered_user[other]);if(notify_count[other]!=count+1)capture_bad=1;
 return -61;
}
void *mock_open(const char *name,int flags) __asm__("__wrap_dlopen");
void *mock_open(const char *name,int flags){if(flags!=4)flags_ok=0;return (void*)1;}
void *mock_sym(void *handle,const char *name) __asm__("__wrap_dlsym");
void *mock_sym(void *handle,const char *name){if(same(name,"_ZN7android6Thread3runEPKcij"))return(void*)&thread_original;
 if(same(name,"_ZN7android14Cam1DeviceBase11takePictureEv"))return(void*)&real_take;
 if(same(name,"_ZN7android14Cam1DeviceBase22storeMetaDataInBuffersEb"))return(void*)&real_metadata;
 return(void*)&real_setter;}
int mock_log(int priority,const char *tag,const char *text, ...) __asm__("__wrap___android_log_print");
int mock_log(int priority,const char *tag,const char *text, ...){return 0;}
int main(void){
 int rc=1;device0[47]=0;device1[47]=1;device2[47]=2;
 for(unsigned i=0;i<8;i++)af_callback[i]=0x12340000+i;
 call_af_move(af_callback,1);
 for(unsigned i=0;i<8;i++)if(af_callback[i]!=(i==3?1:0x12340000+i))goto done;
 call_af_move(af_callback,0);
 for(unsigned i=0;i<8;i++)if(af_callback[i]!=(i==3?0:0x12340000+i))goto done;
 call_setter(device0,0,0,0,legacy_mem,(void*)0x11111111);
 call_setter(device1,0,0,0,legacy_mem,(void*)0x22222222);
 if(preview_session_calls[0]!=1||preview_session_calls[1]!=1)goto done;
 if(!flags_ok || !registered[0] || !registered[1] || registered[0]==registered[1])goto done;
 if(registered_user[0]!=(void*)0x11111111 || registered_user[1]!=(void*)0x22222222)goto done;
 if(registered[0](-1,1234,7,0)!=&dummy_memory || seen_user!=(void*)0x11111111 || seen_fd!=-1 || seen_size!=1234 || seen_count!=7)goto done;
 registered[1](8,4321,3,0);if(seen_user!=(void*)0x22222222 || seen_fd!=8 || seen_size!=4321 || seen_count!=3)goto done;
 registered[0](-1,1,1,(void*)0x33333333);if(seen_user!=(void*)0x33333333)goto done;
 call_setter(device0,0,0,0,legacy_mem,(void*)0x44444444);
 registered[0](-1,1,1,0);if(seen_user!=(void*)0x44444444)goto done;
 registered[1](-1,1,1,0);if(seen_user!=(void*)0x22222222)goto done;
 call_setter(device2,0,0,0,legacy_mem,(void*)0x55555555);if(last_fn!=legacy_mem)goto done;
 int sessions=preview_session_calls[0];
 call_setter(device0,0,0,0,0,0);if(registered[0] || registered_user[0] || preview_session_calls[0]!=sessions)goto done;
 if(j2prime_camera_thread_run((void*)0x11112222,"Given",-9,131072)!=-47 || thread_self!=(void*)0x11112222 || !same(thread_name,"Given") || thread_priority!=-9 || thread_stack!=131072)goto done;
 if(j2prime_camera_thread_run((void*)0x11112222,0,0,0)!=-47 || !same(thread_name,"MtkCam") || thread_priority!=0 || thread_stack!=0)goto done;
 if(j2prime_camera_thread_run((void*)0x11112222,"",4,8192)!=-47 || !same(thread_name,"") || thread_priority!=4 || thread_stack!=8192)goto done;
 if(check_cpu_init(device0))goto done;
 if(check_pq(device0)!=-19 || device0[47]!=0)goto done;
 if(PerfServiceNative_userRegScn()!=-1)goto done;
 PerfServiceNative_userRegScnConfig(-1,2,3,4,5,6);
 PerfServiceNative_userEnable(-1);PerfServiceNative_userDisable(-1);PerfServiceNative_userUnregScn(-1);
 call_setter(device0,notice0,0,0,legacy_mem,(void*)0x11111111);
 call_setter(device1,notice1,0,0,legacy_mem,(void*)0x22222222);
 registered_notify[0](4,17,-19,registered_user[0]);
 if(notify_count[0]!=1 || notify_message[0]!=4 || notify_ext1[0]!=17 || notify_ext2[0]!=-19 || notify_cookie[0]!=registered_user[0])goto done;
 if(call_take(device0)!=-61 || capture_bad)goto done;
 int before=notify_count[0];registered_notify[0](4,1,2,registered_user[0]);if(notify_count[0]!=before+1)goto done;
 nest_test=1;if(call_take(device0)!=-61 || capture_bad)goto done;nest_test=0;
 before=notify_count[0];registered_notify[0](0x800,1,2,registered_user[0]);if(notify_count[0]!=before+1)goto done;
 if(call_take(device2)!=-61 || capture_bad)goto done;
 call_setter(device0,0,0,0,0,0);if(registered_notify[0])goto done;
 if(call_metadata(device0,1)!=-38 || metadata_calls!=1 || metadata_enabled)goto done;
 metadata_status=-51;
 if(call_metadata(device0,0)!=-51 || metadata_calls!=2 || metadata_device!=device0 || metadata_enabled)goto done;
 if(call_metadata(device1,1)!=-38 || metadata_calls!=3 || metadata_enabled)goto done;
 metadata_status=0;
 if(call_metadata(device1,0)!=0 || metadata_calls!=4 || metadata_device!=device1 || metadata_enabled)goto done;
 /* Two independently indexed raw frames: preserve Y, bounds, pointer, index,
  * timestamp and cookie; swap only the chroma quarters of the selected frame.
  */
 for(unsigned i=0;i<sizeof(video_data);i++)video_data[i]=0xa5;
 for(unsigned f=0;f<2;f++){
  unsigned char *p=video_data+4+f*115200;
  for(unsigned i=0;i<76800;i++)p[i]=81+f;
  for(unsigned i=76800;i<96000;i++)p[i]=240-f;
  for(unsigned i=96000;i<115200;i++)p[i]=90+f;
 }
 video_memory.data=video_data+4;video_memory.size=115200*2;video_memory.handle=(void*)0x11223344;memory_result=&video_memory;
 call_setter(device0,notice0,0,timestamp_notice,legacy_mem,(void*)0x11111111);
 registered[0](-1,115200,2,0);
 registered_timestamp[0](1234567890123LL,0x20,&video_memory,1,(void*)0x99887766);
 if(video_data[4+115200+76800]!=239 || video_data[4+115200+96000]!=91)goto done; /* not raw yet */
 /* CameraClient can retain its default YUV mode without sending a second
  * disable call after metadata is rejected. This request must select raw. */
 if(call_metadata(device0,1)!=-38)goto done;
 registered_timestamp[0](1234567890123LL,0x20,&video_memory,1,(void*)0x99887766);
 if(timestamp_time!=1234567890123LL || timestamp_message!=0x20 || timestamp_memory!=&video_memory || timestamp_index!=1 || timestamp_cookie!=(void*)0x99887766)goto done;
 for(unsigned i=0;i<76800;i++)if(video_data[4+115200+i]!=82)goto done;
 for(unsigned i=76800;i<96000;i++)if(video_data[4+115200+i]!=91)goto done;
 for(unsigned i=96000;i<115200;i++)if(video_data[4+115200+i]!=239)goto done;
 for(unsigned i=76800;i<96000;i++)if(video_data[4+i]!=240)goto done;
 for(unsigned i=96000;i<115200;i++)if(video_data[4+i]!=90)goto done;
 if(video_data[0]!=0xa5 || video_data[3]!=0xa5 || video_data[sizeof(video_data)-1]!=0xa5)goto done;
 registered_timestamp[0](1234567890123LL,0x20,&video_memory,1,0); /* duplicate timestamp does not swap back */
 if(video_data[4+115200+76800]!=91)goto done;
 registered_timestamp[0](1234567890124LL,0x20,&video_memory,2,0); /* out-of-range index */
 registered_timestamp[0](1234567890125LL,0x10,&video_memory,0,0); /* preview data */
 if(video_data[4+76800]!=240)goto done;
 video_memory.size--;
 registered_timestamp[0](1234567890126LL,0x20,&video_memory,0,0); /* inconsistent heap */
 if(video_data[4+76800]!=240)goto done;
 video_memory.size++;
 metadata_status=-51;call_metadata(device0,0);
 registered_timestamp[0](1234567890127LL,0x20,&video_memory,0,0); /* failed raw transition */
 if(video_data[4+76800]!=240)goto done;
 call_setter(device1,notice1,0,timestamp_notice,legacy_mem,(void*)0x22222222);
 metadata_status=0;call_metadata(device1,0);
 registered_timestamp[1](1234567890128LL,0x20,&video_memory,0,0); /* wrong physical camera */
 if(video_data[4+76800]!=240)goto done;
 call_metadata(device0,0);
 CameraMemory unregistered=video_memory;
 unregistered.handle=(void*)0x55667788;
 registered_timestamp[0](1234567890128LL,0x20,&unregistered,0,0);
 if(video_data[4+76800]!=240 || timestamp_memory!=&unregistered)goto done;
 CameraMemory copied=video_memory; /* Actual RecImgBuf copies the descriptor. */
 registered_timestamp[0](1234567890129LL,0x20,&copied,0,0);
 if(video_data[4+76800]!=90 || video_data[4+96000]!=240 || timestamp_memory!=&copied)goto done;
 if(timestamp_count!=10)goto done;
 if(!flags_ok)goto done;
 rc=0;
done:
 return rc;
}
