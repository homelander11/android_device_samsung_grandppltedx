# SPDX-License-Identifier: Apache-2.0
# Small standalone component; no Android/ROM build required.
CROSS_COMPILE ?= arm-linux-gnueabi-
CC := $(CROSS_COMPILE)gcc
CFLAGS := -std=c99 -Os -marm -march=armv7-a -ffreestanding -fno-builtin \
          -fno-stack-protector -fno-pic -fno-pie
LDFLAGS := -nostdlib -static -no-pie -Wl,-e,_start,-z,noexecstack,--build-id=none

init-wrapper: init_wrapper.c start.S
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^

sar-mount-probe: sar_mount_probe.c start.S
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^

.PHONY: clean
clean:
	rm -f init-wrapper sar-mount-probe
