/* SPDX-License-Identifier: Apache-2.0 */
/* Isolated preview ABI contract test; no hardware access. */
#include <hardware/camera.h>
typedef preview_stream_ops_t Ops;
extern int camera_set_preview(void*,Ops*) __asm__("_ZN7android14Cam1DeviceBase16setPreviewWindowEP18preview_stream_ops");
extern int j2prime_camera_preview_new_session(unsigned);
static unsigned dev0[64],dev1[64],dev2[64];
static Ops real0,real1,*registered[2],*last_ops;
static buffer_handle_t raw0=(buffer_handle_t)0x11110000,raw1=(buffer_handle_t)0x22220000;
static unsigned pool[32][128],used[32];
static int bad,alloc_fail,dequeue_error,buffer_error,cancels,alive,config_calls;
static int setter_result,geometry[3],usage,crop[4],swap;
static int test_session_during_dequeue;
static long long timestamp;
void *mock_memset(void*,int,unsigned) __asm__("__wrap_memset");
void *mock_memset(void*p,int v,unsigned n){volatile unsigned char*b=p;for(unsigned i=0;i<n;i++)b[i]=(unsigned char)v;return p;}
static int same(const char*a,const char*b){while(*a && *a==*b){a++;b++;}return *a==*b;}
void *mock_alloc(unsigned n,unsigned size) __asm__("__wrap_calloc");
void *mock_alloc(unsigned n,unsigned size){
 if(alloc_fail)return 0;if(n*size>512){bad=1;return 0;}
 for(unsigned i=0;i<32;i++)if(!used[i]){used[i]=1;alive++;for(unsigned j=0;j<128;j++)pool[i][j]=0;return pool[i];}
 bad=1;return 0;
}
void mock_free(void*p) __asm__("__wrap_free");
void mock_free(void*p){for(unsigned i=0;i<32;i++)if(p==pool[i]&&used[i]){used[i]=0;alive--;return;}bad=1;}
int mock_log(int p,const char*t,const char*s,...) __asm__("__wrap___android_log_print");
int mock_log(int p,const char*t,const char*s,...){return 0;}
static int real_setter(void*d,Ops*ops){unsigned id=((unsigned*)d)[47];last_ops=ops;if(id<2)registered[id]=ops;return setter_result;}
void *mock_open(const char*n,int flags) __asm__("__wrap_dlopen");
void *mock_open(const char*n,int flags){if(flags!=4||!same(n,"libcam.device1.so"))bad=1;return(void*)1;}
void *mock_sym(void*h,const char*n) __asm__("__wrap_dlsym");
void *mock_sym(void*h,const char*n){if(!same(n,"_ZN7android14Cam1DeviceBase16setPreviewWindowEP18preview_stream_ops"))bad=1;return(void*)&real_setter;}
static int dq(Ops*w,buffer_handle_t**h,int*s){if(w!=&real0&&w!=&real1)bad=1;if(test_session_during_dequeue && j2prime_camera_preview_new_session(0)!=-16)bad=1;if(dequeue_error)return dequeue_error;*h=w==&real0?&raw0:&raw1;*s=672;return 0;}
static int eq(Ops*w,buffer_handle_t*h){if(w==&real0?h!=&raw0:w==&real1?h!=&raw1:1)bad=1;return buffer_error;}
static int cancel(Ops*w,buffer_handle_t*h){cancels++;return eq(w,h);}
static int count(Ops*w,int n){if(w!=&real0&&w!=&real1)bad=1;config_calls++;return n==7?0:-77;}
static int geom(Ops*w,int x,int y,int f){if(w!=&real0&&w!=&real1)bad=1;config_calls++;geometry[0]=x;geometry[1]=y;geometry[2]=f;return 0;}
static int usg(Ops*w,int n){if(w!=&real0&&w!=&real1)bad=1;config_calls++;usage=n;return 0;}
static int crp(Ops*w,int l,int t,int r,int b){if(w!=&real0&&w!=&real1)bad=1;crop[0]=l;crop[1]=t;crop[2]=r;crop[3]=b;return -18;}
static int swp(Ops*w,int n){if(w!=&real0&&w!=&real1)bad=1;swap=n;return -19;}
static int minimum(const Ops*w,int*n){if(w!=&real0&&w!=&real1)bad=1;*n=2;return 0;}
static int ts(Ops*w,long long n){if(w!=&real0&&w!=&real1)bad=1;timestamp=n;return -20;}
static void init(Ops*w){w->dequeue_buffer=dq;w->enqueue_buffer=eq;w->cancel_buffer=cancel;w->set_buffer_count=count;w->set_buffers_geometry=geom;w->set_crop=crp;w->set_usage=usg;w->set_swap_interval=swp;w->get_min_undequeued_buffer_count=minimum;w->lock_buffer=eq;w->set_timestamp=ts;}
int main(void){
 int rc=1,s,n;buffer_handle_t *h0=0,*h1=0,*again=0;unsigned *b0;
 dev0[47]=0;dev1[47]=1;dev2[47]=2;init(&real0);init(&real1);
 if(camera_set_preview(dev0,&real0)||!registered[0]||registered[0]==&real0)goto done;
 if(camera_set_preview(dev1,&real1)||!registered[1]||registered[1]==registered[0])goto done;
 Ops*w=registered[0],*f=registered[1];
 if(w->set_buffers_geometry(w,640,480,17)||w->set_usage(w,0x300)||w->set_buffer_count(w,7))goto done;
 if(w->dequeue_buffer(w,&h0,&s)||h0==&raw0||*h0!=raw0||s!=672)goto done;
 b0=(unsigned*)((char*)h0-60);
 if(b0[0]!=0x5f626672||b0[1]!=96||b0[8]!=640||b0[9]!=480||b0[10]!=672||b0[11]!=17||b0[12]!=0x300)goto done;
 int rebind_alive=alive;
 if(camera_set_preview(dev0,&real0)||registered[0]!=w||alive!=rebind_alive||b0[8]!=640)goto done;
 if(w->set_buffer_count(w,7)!=-16||camera_set_preview(dev0,0)!=-16)goto done;
 ((void(*)(void*))b0[6])(b0);
 if(w->lock_buffer(w,h0)||w->enqueue_buffer(w,h0))goto done;
 if(j2prime_camera_preview_new_session(0)!=-16)goto done;
 if(w->set_buffers_geometry(w,320,240,17)!=-16)goto done;
 ((void(*)(void*))b0[7])(b0);
 if(w->dequeue_buffer(w,&again,&s)||again!=h0)goto done;
 buffer_error=-33;if(w->enqueue_buffer(w,h0)!=-33)goto done;buffer_error=0;
 if(w->cancel_buffer(w,h0)||w->enqueue_buffer(w,h0)!=-22)goto done;
 if(f->set_buffers_geometry(f,320,240,17)||f->dequeue_buffer(f,&h1,&s)||h1==h0||*h1!=raw1||f->cancel_buffer(f,h1))goto done;
 if(w->set_crop(w,1,2,3,4)!=-18||crop[0]!=1||crop[3]!=4)goto done;
 if(w->set_swap_interval(w,3)!=-19||swap!=3)goto done;
 if(w->set_timestamp(w,0x1122334455667788LL)!=-20||timestamp!=0x1122334455667788LL)goto done;
 if(w->get_min_undequeued_buffer_count(w,&n)||n!=2)goto done;
 if(w->set_buffer_count(w,6)!=-77)goto done;
 alloc_fail=1;n=cancels;if(w->dequeue_buffer(w,&again,&s)!=-12||cancels!=n+1)goto done;alloc_fail=0;
 dequeue_error=-42;if(w->dequeue_buffer(w,&again,&s)!=-42)goto done;dequeue_error=0;
 if(w->dequeue_buffer(w,0,&s)!=-22||w->dequeue_buffer(w,&again,0)!=-22)goto done;
 if(camera_set_preview(dev2,&real0)||last_ops!=&real0)goto done;
 setter_result=-51;if(camera_set_preview(dev0,&real0)!=-51)goto done;setter_result=0;
 /* A new HAL session can clear map-only stale dequeues from a closed client.
  * Ordinary live reconfiguration must still fail, and front state is isolated.
  */
 if(j2prime_camera_preview_new_session(2)!=-22)goto done;
 if(camera_set_preview(dev0,&real0))goto done;
 test_session_during_dequeue=1;
 if(w->dequeue_buffer(w,&h0,&s))goto done;
 test_session_during_dequeue=0;
 int previous_alive=alive;
 if(w->set_buffers_geometry(w,320,240,17)!=-16)goto done;
 if(j2prime_camera_preview_new_session(0)||alive!=previous_alive-1)goto done;
 if(w->dequeue_buffer(w,&again,&s)!=-19)goto done;
 if(f->dequeue_buffer(f,&h1,&s)||f->cancel_buffer(f,h1))goto done;
 if(camera_set_preview(dev0,&real0)||w->set_buffers_geometry(w,320,240,17))goto done;
 if(w->dequeue_buffer(w,&h0,&s)||w->cancel_buffer(w,h0))goto done;
 if(camera_set_preview(dev0,0)||registered[0]||camera_set_preview(dev1,0)||registered[1]||alive||bad)goto done;
 rc=0;
done:return rc;
}
