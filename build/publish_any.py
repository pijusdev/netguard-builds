#!/usr/bin/env python3
"""publish_any.py — po udanym buildzie dowolnego repo aktualizuje docs/data/builds.json i status.json.

Użycie: python3 publish_any.py <repo_url> <commit> <app_name> <plik1.apk> [plik2.apk ...]
Pliki APK muszą już leżeć w docs/dist/.
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "docs")
DIST = os.path.join(SITE, "dist")
BUILDS_JSON = os.path.join(SITE, "data", "builds.json")
STATUS_JSON = os.path.join(SITE, "data", "status.json")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def guess_abi(fn):
    low = fn.lower()
    if "arm64" in low or "universal" in low or "fat" in low:
        return "arm64-v8a"
    if "arm" in low or "v7a" in low:
        return "armeabi-v7a"
    if "x86_64" in low:
        return "x86_64"
    if "x86" in low:
        return "x86"
    return "universal"


def main():
    if len(sys.argv) < 5:
        print("użycie: publish_any.py <repo_url> <commit> <app_name> <apk1> [apk2 ...]", file=sys.stderr)
        sys.exit(2)
    repo_url, commit, app_name = sys.argv[1], sys.argv[2], sys.argv[3]
    apks = sys.argv[4:]

    with open(BUILDS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    data["updated"] = now_iso()
    builds = {b["file"]: b for b in data.get("builds", [])}

    for fn in apks:
        path = os.path.join(DIST, fn)
        if not os.path.isfile(path):
            print(f"  ! brak pliku: {path}", file=sys.stderr)
            continue
        rel = f"dist/{fn}"
        builds[rel] = {
            "version": commit[:7],
            "abi": guess_abi(fn),
            "label": f"{app_name} · {os.path.splitext(fn)[0]}",
            "file": rel,
            "size": os.path.getsize(path),
            "sha256": sha256(path),
            "date": now_iso()[:10],
            "repo": repo_url,
            "app": app_name,
            "note": f"Zbudowane z {repo_url} @ {commit[:7]}",
        }
        print(f"  + {rel} ({builds[rel]['size']} B)")

    data["builds"] = sorted(builds.values(), key=lambda b: b.get("date", ""), reverse=True)
    with open(BUILDS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    with open(STATUS_JSON, encoding="utf-8") as f:
        status = json.load(f)
    start = os.environ.get("BUILD_START")
    duration = int(time.time()) - int(start) if start else 0
    status.update({
        "state": "idle",
        "step": f"Gotowe: {app_name} @ {commit[:7]}",
        "started": None,
        "updated": now_iso(),
        "lastBuild": {
            "version": f"{app_name}@{commit[:7]}",
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
