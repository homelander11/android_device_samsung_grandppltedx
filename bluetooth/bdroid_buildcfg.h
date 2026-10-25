#ifndef _BDROID_BUILDCFG_H
#define _BDROID_BUILDCFG_H

#define BTM_DEF_LOCAL_NAME   "Galaxy J2 Prime"

// MT6737T reports a maximum of 2 but rejects page 2 with HCI status 0x30.
// Pages 0 and 1 are valid and include the LE host support information.
// Requires patches/android-11/system/bt.
#define BTM_MAX_LOCAL_FEATURES_PAGE 1

#endif
