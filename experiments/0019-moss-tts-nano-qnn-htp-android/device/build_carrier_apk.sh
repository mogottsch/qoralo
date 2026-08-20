#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)";EXP="$ROOT/experiments/0019-moss-tts-nano-qnn-htp-android";SRC="$ROOT/experiments/0018-moss-tts-nano-onnx-android/android";OUT="$EXP/.local/carrier-android";JNI="$OUT/app/src/main/jniLibs/arm64-v8a"
rm -rf "$OUT";mkdir -p "$OUT";cp -a "$SRC/gradle" "$SRC/gradlew" "$SRC/settings.gradle.kts" "$SRC/build.gradle.kts" "$SRC/app" "$OUT/";rm -rf "$OUT/.gradle" "$OUT/app/build";mkdir -p "$JNI"
python3 - "$OUT" <<'PY'
from pathlib import Path
import sys
r=Path(sys.argv[1]);m=r/'app/src/main/AndroidManifest.xml';s=m.read_text().replace('android:allowBackup="false"','android:allowBackup="false"\n        android:extractNativeLibs="true"').replace('        <activity','        <uses-native-library android:name="libcdsprpc.so" android:required="true" />\n        <activity');m.write_text(s)
b=r/'app/build.gradle.kts';s=b.read_text().replace('    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.20.0")\n','');s+='\nandroid { packaging { jniLibs { useLegacyPackaging = true } } }\n';b.write_text(s)
main=r/'app/src/main/java/com/openmoss/ttsnano/onnxruntime/MainActivity.kt'
for p in main.parent.glob('*.kt'): p.unlink()
main.write_text('''package com.openmoss.ttsnano.onnxruntime
import android.app.Activity
import android.os.Bundle
class MainActivity: Activity() { override fun onCreate(state: Bundle?) { super.onCreate(state); finish() } }
''')
PY
cp "$EXP/.local/moss-fixed-e2e-android" "$JNI/libmossrunner.so"
ORT="$ROOT/experiments/0010-supertonic-qnn-htp-feasibility/.local/ort-v1.27.1-qnn-2.49.0-android-arm64/package";QAIRT=/home/moritz/opt/qairt/2.49.0.260730
cp "$ORT/libonnxruntime.so" "$ORT/libc++_shared.so" "$JNI/"
cp "$QAIRT/lib/aarch64-android/libQnnHtp.so" "$QAIRT/lib/aarch64-android/libQnnHtpPrepare.so" "$QAIRT/lib/aarch64-android/libQnnHtpV73Stub.so" "$QAIRT/lib/aarch64-android/libQnnSystem.so" "$JNI/"
cp "$QAIRT/lib/hexagon-v73/unsigned/libQnnHtpV73Skel.so" "$JNI/"
(cd "$OUT";ANDROID_HOME=/home/moritz/opt/android-sdk ANDROID_SDK_ROOT=/home/moritz/opt/android-sdk JAVA_HOME=/home/moritz/opt/jdk-17 ./gradlew --no-daemon :app:assembleDebug)
APK="$OUT/app/build/outputs/apk/debug/app-debug.apk";[[ -f "$APK" ]];sha256sum "$APK";echo "$APK"
