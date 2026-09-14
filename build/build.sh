#!/usr/bin/env bash
# build.sh — kompiluje NetGuard (build debug = Pro odblokowane) i wyprowadza APK per-ABI.
# Wymaga: JDK 21 w PATH, ANDROID_HOME zainstalowane (platform 36, build-tools, NDK 25.2, cmake).
# Użycie: ./build.sh [wersja]  (domyślnie z build/VERSION)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(cat "$SCRIPT_DIR/VERSION" 2>/dev/null || echo 2.337)"
VERSION="${1:-$VERSION}"

WORK="$SCRIPT_DIR/work"
SRC="$WORK/NetGuard"
OUT="$SCRIPT_DIR/out"
NDK_VERSION="25.2.9519653"
PLATFORM="android-36"
BUILD_TOOLS="36.0.0"

echo "==> NetGuard build v$VERSION"
echo "==> ANDROID_HOME=$ANDROID_HOME"

# --- 1. środowisko SDK ---
CMDLINE="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"
if [ ! -x "$CMDLINE" ]; then
  echo "==> Instaluję cmdline-tools"
  mkdir -p "$ANDROID_HOME/cmdline-tools"
  curl -fsSL https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -o "$WORK/clt.zip"
  unzip -q "$WORK/clt.zip" -d "$ANDROID_HOME/cmdline-tools"
  mv "$ANDROID_HOME/cmdline-tools/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest"
fi
echo "==> Akceptuję licencje + instaluję komponenty SDK"
yes | "$CMDLINE" --licenses >/dev/null 2>&1 || true
"$CMDLINE" "platform-tools" "platforms;$PLATFORM" "build-tools;$BUILD_TOOLS" "ndk;$NDK_VERSION" "cmake;3.22.1" >/dev/null

# --- 2. źródła ---
echo "==> Pobieram źródła NetGuard v$VERSION"
rm -rf "$SRC"
if git -C "$WORK" rev-parse --is-inside-work-tree >/dev/null 2>&1; then :; fi
git clone --depth 1 --branch "v$VERSION" https://github.com/M66B/NetGuard.git "$SRC" 2>/dev/null \
  || git clone --depth 1 https://github.com/M66B/NetGuard.git "$SRC"

# --- 3. patche (minimalne, bez zmiany logiki) ---
echo "==> Stosuję patche builda"
# (a) nowoczesna składnia compileSdk
sed -i 's/compileSdkVersion = 36/compileSdk 36/' "$SRC/app/build.gradle"
# (b) keystore debug (standardowy klucz Androida, NIE prywatny)
cat > "$SRC/keystore.properties" <<'EOF'
storeFile=debug.keystore
storePassword=android
keyAlias=androiddebugkey
keyPassword=android
EOF
# (c) splits per-ABI + universal — żeby mieć osobne APK pod procesor
python3 - "$SRC/app/build.gradle" <<'PY'
import sys, re
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
splits = """
    splits {
        abi {
            enable true
            reset()
            include 'armeabi-v7a', 'arm64-v8a'
            universalApk true
        }
    }
"""
# wstawiamy splits zaraz po bloku android { ... defaultConfig ... } -> przed buildTypes
s = s.replace("    buildTypes {", splits + "    buildTypes {", 1)
open(p, "w", encoding="utf-8").write(s)
print("==> splits per-ABI dodane")
PY

# --- 4. build ---
echo "==> Kompiluję (assembleDebug) — to trwa kilka minut"
cd "$SRC"
chmod +x gradlew
./gradlew assembleDebug --no-daemon --stacktrace 2>&1 | tee "$SCRIPT_DIR/build.log" | tail -40

# --- 5. zbieram APK ---
echo "==> Zbieram APK"
rm -rf "$OUT"; mkdir -p "$OUT"
APK_DIR="$SRC/app/build/outputs/apk/debug"
declare -A ABI_MAP=( ["armeabi-v7a"]="arm32" ["arm64-v8a"]="arm64" )
for f in "$APK_DIR"/*.apk; do
  [ -e "$f" ] || continue
  base="$(basename "$f")"
  if [ "$base" = "NetGuard-v${VERSION}-debug.apk" ]; then
    cp "$f" "$OUT/NetGuard-v${VERSION}-universal.apk"
    echo "    universal: NetGuard-v${VERSION}-universal.apk"
  else
    for abi in "${!ABI_MAP[@]}"; do
      if [[ "$base" == *"$abi"* ]]; then
        cp "$f" "$OUT/NetGuard-v${VERSION}-${ABI_MAP[$abi]}.apk"
        echo "    ${ABI_MAP[$abi]}: NetGuard-v${VERSION}-${ABI_MAP[$abi]}.apk"
      fi
    done
  fi
done

echo "==> Gotowe. APK w $OUT:"
ls -la "$OUT"
