# SPDX-License-Identifier: Apache-2.0
LOCAL_PATH := $(call my-dir)

# WITH_LINEAGE_CHARGER=false suppresses Lineage's competing description.
# Keep its unchanged density-selected images through explicit dependencies.
include $(CLEAR_VARS)
LOCAL_MODULE := grandppltedx_charger_animation
LOCAL_MODULE_STEM := animation.txt
LOCAL_SRC_FILES := animation.txt
LOCAL_MODULE_CLASS := ETC
LOCAL_MODULE_TAGS := optional
LOCAL_MODULE_PATH := $(TARGET_OUT_PRODUCT_ETC)/res/values/charger
LOCAL_REQUIRED_MODULES := lineage_charger_battery_scale lineage_charger_battery_fail
include $(BUILD_PREBUILT)
