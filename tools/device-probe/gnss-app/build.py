#!/usr/bin/env python3
"""Build only the foreground GPS diagnostic with an existing Android SDK/JDK."""
import argparse
from pathlib import Path
import shutil
import subprocess
import zipfile


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--build-tools", default="35.0.0")
    parser.add_argument("--platform", default="android-35")
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    output = args.out_dir.resolve()
    tools = args.sdk.resolve() / "build-tools" / args.build_tools
    android = args.sdk.resolve() / "platforms" / args.platform / "android.jar"
    suffix = ".exe" if (tools / "aapt2.exe").exists() else ""
    java, javac, keytool = (shutil.which(name) for name in ("java", "javac", "keytool"))
    required = [java, javac, keytool, android, tools / ("aapt2" + suffix),
                tools / ("zipalign" + suffix), tools / "lib/d8.jar", tools / "lib/apksigner.jar"]
    if any(not path or not Path(path).is_file() for path in required):
        parser.error("SDK/JDK tools missing; provide a complete existing SDK and JDK on PATH")
    classes = output / "classes"
    dex = output / "dex"
    classes.mkdir(parents=True, exist_ok=True)
    dex.mkdir(parents=True, exist_ok=True)
    run(javac, "-source", "8", "-target", "8", "-classpath", android,
        "-d", classes, source / "MainActivity.java")
    run(java, "-cp", tools / "lib/d8.jar", "com.android.tools.r8.D8", "--lib", android,
        "--min-api", "24", "--output", dex, *sorted(classes.rglob("*.class")))
    unsigned = output / "unsigned.apk"
    aligned = output / "aligned.apk"
    signed = output / "j2prime-gps-probe.apk"
    run(tools / ("aapt2" + suffix), "link", "-o", unsigned, "--manifest",
        source / "AndroidManifest.xml", "-I", android)
    with zipfile.ZipFile(unsigned, "a", zipfile.ZIP_DEFLATED) as archive:
        archive.write(dex / "classes.dex", "classes.dex")
    run(tools / ("zipalign" + suffix), "-f", "4", unsigned, aligned)
    key = output / "diagnostic-debug.jks"
    # Disposable local diagnostic key; this is the conventional public debug password.
    if not key.exists():
        run(keytool, "-genkeypair", "-noprompt", "-keystore", key, "-storetype", "JKS",
            "-storepass", "android", "-keypass", "android", "-alias", "diagnostic",
            "-keyalg", "RSA", "-keysize", "2048", "-validity", "3650",
            "-dname", "CN=J2 Prime local diagnostic")
    run(java, "-jar", tools / "lib/apksigner.jar", "sign", "--ks", key,
        "--ks-key-alias", "diagnostic", "--ks-pass", "pass:android", "--key-pass",
        "pass:android", "--out", signed, aligned)
    run(java, "-jar", tools / "lib/apksigner.jar", "verify", signed)
    print("Built and signature-verified:", signed)


if __name__ == "__main__":
    main()
