#!/usr/bin/env python3
"""publish.py — po udanym buildzie aktualizuje docs/data/builds.json i status.json.
Użycie: python3 publish.py <wersja>
Czyta APK z build/out/, liczy size + sha256, aktualizuje metadane i status (state=idle).
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "docs")
OUT = os.path.join(ROOT, "build", "out")
BUILDS_JSON = os.path.join(SITE, "data", "builds.json")
STATUS_JSON = os.path.join(SITE, "data", "status.json")

ABI_INFO = {
    "arm64":     {"abi": "arm64-v8a",     "label": "arm64 · 64-bit",  "note": "Dla większości współczesnych urządzeń (2018+)."},
    "arm32":     {"abi": "armeabi-v7a",   "label": "arm32 · 32-bit",  "note": "Dla starszych / tanich urządzeń 32-bit (np. projektory)."},
    "universal": {"abi": "universal",     "label": "universal · wszystkie", "note": "Uniwersalny — zawiera wszystkie architekturę, największy."},
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    if len(sys.argv) < 2:
        print("użycie: publish.py <wersja>", file=sys.stderr)
        sys.exit(2)
    version = sys.argv[1]

    # --- builds.json ---
    with open(BUILDS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    data["updated"] = now_iso()
    data["source"]["version"] = version
    builds = {b["file"]: b for b in data.get("builds", [])}

    if not os.path.isdir(OUT):
        print(f"brak katalogu {OUT}", file=sys.stderr)
        sys.exit(1)

    for fn in sorted(os.listdir(OUT)):
        if not fn.endswith(".apk"):
            continue
        path = os.path.join(OUT, fn)
        # wyłuskaj klucz ABI z nazwy: NetGuard-v<ver>-<abi>.apk
        key = None
        for k in ABI_INFO:
            if fn.endswith(f"-{k}.apk"):
                key = k
                break
        if not key:
            continue
        info = ABI_INFO[key]
        rel = f"dist/{fn}"
        entry = {
            "version": version,
            "abi": info["abi"],
            "label": info["label"],
            "file": rel,
            "size": os.path.getsize(path),
            "sha256": sha256(path),
            "date": now_iso()[:10],
            "minSdk": 23,
            "proUnlocked": True,
            "note": info["note"],
        }
        builds[rel] = entry
        print(f"  + {rel} ({entry['size']} B)")

    # zachowuję stałą kolejność: arm64, arm32, universal
    order = {"arm64-v8a": 0, "armeabi-v7a": 1, "universal": 2}
    data["builds"] = sorted(builds.values(), key=lambda b: order.get(b["abi"], 9))
    with open(BUILDS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # --- status.json ---
    with open(STATUS_JSON, encoding="utf-8") as f:
        status = json.load(f)
    start = os.environ.get("BUILD_START")
    duration = int(time.time()) - int(start) if start else 0
    status.update({
        "state": "idle",
        "step": "Gotowe",
        "started": None,
        "updated": now_iso(),
        "lastBuild": {
            "version": version,
            "durationSec": max(0, duration),
            "finished": now_iso(),
            "result": "success",
        },
    })
    with open(STATUS_JSON, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("==> builds.json + status.json zaktualizowane")


if __name__ == "__main__":
    main()
