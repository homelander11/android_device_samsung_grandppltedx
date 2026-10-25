/* SPDX-License-Identifier: Apache-2.0 */
import android.system.Os;
import android.system.OsConstants;

/** Tests DAC access after dropping root. Never reads or writes file contents. */
public final class UidAccessProbe {
    public static void main(String[] args) throws Exception {
        if (args.length != 3 || Os.getuid() != 0) {
            throw new IllegalArgumentException("Run as root: UID GID PATH");
        }
        Os.setgid(Integer.parseInt(args[1]));
        Os.setuid(Integer.parseInt(args[0]));
        boolean readable = false;
        boolean writable = false;
        try {
            readable = Os.access(args[2], OsConstants.R_OK);
        } catch (android.system.ErrnoException expected) {
            // A denied access is an expected probe result.
        }
        try {
            writable = Os.access(args[2], OsConstants.W_OK);
        } catch (android.system.ErrnoException expected) {
            // A denied access is an expected probe result.
        }
        System.out.println("uid=" + Os.getuid() + " gid=" + Os.getgid()
                + " readable=" + readable + " writable=" + writable);
    }
}
