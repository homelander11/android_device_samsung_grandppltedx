/* SPDX-License-Identifier: Apache-2.0
 * Temporary boot diagnostic, never part of the normal product build.
 * A static ARM PID 1 wrapper: exec the unchanged Android first-stage init.
 * Only Samsung's androidboot.mode=charger prefix starts a private logger.
 * No UI, power-control, calibration or SELinux changes; no dynamic libraries.
 */
#ifndef DIAG_FIXTURE
#define DIAG_FIXTURE 0
#endif
extern int raw6(int, int, int, int, int, int, int);
#define P(x) ((int)(x))
static int call0(int n) { return raw6(n,0,0,0,0,0,0); }
static int call1(int n,int a) { return raw6(n,a,0,0,0,0,0); }
static int call2(int n,int a,int b) { return raw6(n,a,b,0,0,0,0); }
static int call3(int n,int a,int b,int c) { return raw6(n,a,b,c,0,0,0); }
static unsigned str_count(const char *s) { unsigned n=0; while(s[n])n++;return n; }
static int equal(const char *a,const char *b) {
    while(*a && *a==*b){a++;b++;}return *a==*b;
}
static int contains_charger(const char *s) {
    const char *tag="androidboot.mode=charger";
    for(unsigned i=0;s[i];i++) {
        if(i && s[i-1]!=' ' && s[i-1]!='\n' && s[i-1]!='\t')continue;
        unsigned n=0;while(tag[n] && s[i+n]==tag[n])n++;
        /* Match Samsung sec_batt.c's seven-character value prefix. */
        if(!tag[n])return 1;
    }
    return 0;
}
static void put(int fd,const char *s,unsigned n) {
    while(n){int r=call3(4,fd,P(s),n);if(r<=0)return;s+=r;n-=(unsigned)r;}
}
static void text(int fd,const char *s) { put(fd,s,str_count(s)); }
static void pause_for(int sec,int ns) { int t[2]={sec,ns};call2(162,P(t),0); }
static char cmdline[4096];
static char kernel_log[1048576];

static void read_cmdline(void) {
    int made=raw6(21,P("proc"),P("/proc"),P("proc"),14,0,0)==0;
    int fd=call3(5,P("/proc/cmdline"),0,0);
    if(fd>=0){int n=call3(3,fd,P(cmdline),sizeof(cmdline)-1);if(n>0)cmdline[n]=0;call1(6,fd);}
    if(made)call2(52,P("/proc"),2);
}

static void logger(void) {
    /* Keep the cache mount out of Android init's mount namespace. */
    if(call1(337,0x20000)<0)call1(1,20);
    if(raw6(21,0,P("/"),0,0x44000,0,0)<0)call1(1,21);
#if DIAG_FIXTURE
    const char *node="/dev/j2prime-early-fixture-cache-node";
    const char *where="/data/local/tmp/j2prime-early-fixture-cache";
    const char *path="/data/local/tmp/j2prime-early-fixture-cache/early.log";
    unsigned dev=(7u<<8); /* Verified fixture-only RAM loop0. */
#else
    const char *node="/charger_debug_cache";
    const char *where="/cache";
    const char *path="/cache/j2prime-early-charger.log";
    /* Pinned SM-G532G partition table; verified by the recovery installer. */
    unsigned dev=(179u<<8)|27u;
#endif
    call2(39,P(where),0700);
    if(call3(14,P(node),0060600,dev)<0)call1(1,22);
    int mounted=0;
    for(unsigned n=0;n<20;n++) {
        if(raw6(21,P(node),P(where),P("ext4"),6,0,0)==0){mounted=1;break;}
        pause_for(0,250000000);
    }
    if(!mounted)call1(1,23);
    int fd=call3(5,P(path),0xa0241,0600); /* WRONLY|CREAT|TRUNC|NOFOLLOW|CLOEXEC */
    if(fd<0)call1(1,24);
    text(fd,"J2PRIME EARLY CHARGER: static ramdisk logger\nCMDLINE: ");
    text(fd,cmdline);text(fd,"\n");call1(118,fd);call0(36);
#if DIAG_FIXTURE
    unsigned count=2;
#else
    unsigned count=6;
#endif
    for(unsigned n=0;n<count;n++) {
        char marker[2]={(char)('0'+n),0};
        text(fd,"\n=== KERNEL SNAPSHOT ");text(fd,marker);text(fd," ===\n");
        int size=call3(103,3,P(kernel_log),sizeof(kernel_log));
        if(size>0)put(fd,kernel_log,(unsigned)size);
        else text(fd,"Kernel-log read unavailable after policy change\n");
        call1(118,fd);call0(36);
#if DIAG_FIXTURE
        if(n+1<count)pause_for(0,100000000);
#else
        if(n+1<count)pause_for(1<<n,0);
#endif
    }
    call1(6,fd);call2(52,P(where),0);call1(1,0);
}

static int self_test(void) {
    if(!contains_charger("androidboot.mode=charger") ||
       !contains_charger("a=1 androidboot.mode=charger_extra z=2") ||
       contains_charger("xandroidboot.mode=charger") ||
       contains_charger("androidboot.mode=charging") ||
       contains_charger("androidboot.mode=unknown"))return 70;
    text(1,"PASS static ARM syscall and Samsung charger-prefix self-test\n");
    return 0;
}

#ifdef J2PRIME_RS_FRONTEND
static
#endif
__attribute__((used)) int wrapper_start(unsigned *stack) {
    unsigned argc=stack[0];char **argv=(char **)(stack+1);
    char **env=(char **)(stack+argc+2);
    int pid=call0(20);
    if(pid!=1) {
        if(argc==2 && equal(argv[1],"--self-test"))return self_test();
#if DIAG_FIXTURE
        if(argc!=2 || !equal(argv[1],"--fixture"))return 78;
        if(call1(337,0x20000)<0 || raw6(21,0,P("/"),0,0x44000,0,0)<0)return 79;
#else
        text(2,"Refusing non-PID1 execution (use --self-test only)\n");
        return 78;
#endif
    }
    read_cmdline();
    int charging=contains_charger(cmdline);
#if DIAG_FIXTURE == 1
    charging=1;
#elif DIAG_FIXTURE == 2
    charging=0;
#endif
    if(charging) {
        int child=call0(2);
        if(child==0){logger();call1(1,25);}
#if DIAG_FIXTURE
        if(child<0)return 80;
        int status=0;raw6(114,child,P(&status),0,0,0,0);
        if(status)return 81;
#endif
    }
#if DIAG_FIXTURE
    char *test_argv[2]={"/system/bin/true",0};
    call3(11,P("/system/bin/true"),P(test_argv),P(env));
#else
    /* Same PID, exact original argv/environment and unchanged init bytes. */
    call3(11,P("/init.real"),P(argv),P(env));
#endif
    text(2,"Failed to exec original first-stage init\n");
    if(pid!=1)return 82;
    for(;;)pause_for(60,0);
}
