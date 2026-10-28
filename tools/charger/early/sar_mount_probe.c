/* SPDX-License-Identifier: Apache-2.0
 * Reproduce the legacy charging remount's path loop in a private namespace.
 * Never writes the system partition and refuses PID 1/default execution.
 */
extern int raw6(int,int,int,int,int,int,int);
#define P(x) ((int)(x))
static int same(const char *a,const char *b) { while(*a && *a==*b){a++;b++;}return *a==*b; }
static int open_charger(void) { return raw6(5,P("/system/bin/charger"),0,0,0,0,0); }
#ifdef J2PRIME_RS_FRONTEND
static
#endif
__attribute__((used)) int wrapper_start(unsigned *stack) {
    char **argv=(char **)(stack+1);
    if(stack[0]!=2 || !same(argv[1],"--run") || raw6(20,0,0,0,0,0,0)==1)return 78;
    if(raw6(24,0,0,0,0,0,0)!=0)return 77;
    if(raw6(337,0x20000,0,0,0,0,0)<0)return 1;
    if(raw6(21,0,P("/"),0,0x44000,0,0)<0)return 2;
    int fd=open_charger();if(fd<0)return 3;raw6(6,fd,0,0,0,0,0);
    /* Bind the SAR filesystem root at /system, equivalent to the old mount. */
    if(raw6(21,P("/"),P("/system"),0,4096,0,0)<0)return 4;
    int bad=open_charger();
    if(bad>=0)raw6(6,bad,0,0,0,0,0);
    if(raw6(52,P("/system"),2,0,0,0,0)<0)return 5;
    if(bad!=-40)return 6;
    fd=open_charger();if(fd<0)return 7;raw6(6,fd,0,0,0,0,0);
    const char text[]="PASS SAR remount reproduces ELOOP; unmount restores charger path; private namespace only\n";
    raw6(4,1,P(text),sizeof(text)-1,0,0,0);
    return 0;
}
