#!/usr/bin/env python3
"""
apply_config.py — wypycha pełną konfigurację NetGuarda na urządzenie przez ADB.

Jak to działa:
  NetGuard trzyma reguły (która appa ma internet) w bazie SQLite `Netguard` (tabela `app`,
  kolumna `enabled` = 1 dozwolona / 0 zablokowana) oraz ustawienia globalne w
  `shared_prefs/eu.faircode.netguard_preferences.xml`. Build debug (ten z tej strony) jest
  debuggable, więc `adb shell run-as eu.faircode.netguard` ma dostęp do plików aplikacji —
  na tym bazuje ten skrypt.

  Skrypt generuje świeżą bazę (schemat v22, wersja 2.337) z Twoimi regułami + plik
  preferencji, zatrzymuje NetGuarda, wypycha pliki przez run-as i go uruchamia.

Użycie:
  python3 apply_config.py <konfiguracja.json> [--serial SERIAL] [--dry-run]

Wymaga: adb w PATH, urządzenie podłączone z włączonym debugowaniem USB,
        zainstalowany build debug NetGuarda (eu.faircode.netguard).
"""
import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

PKG = "eu.faircode.netguard"
DB_NAME = "Netguard"
DB_VERSION = 22
PREFS_FILE = "eu.faircode.netguard_preferences.xml"

# Schemat bazy NetGuard v22 (z DatabaseHelper.java)
SCHEMA = [
    ("log", """CREATE TABLE log (
        ID INTEGER PRIMARY KEY AUTOINCREMENT, time INTEGER NOT NULL, version INTEGER,
        protocol INTEGER, flags TEXT, saddr TEXT, sport INTEGER, daddr TEXT, dport INTEGER,
        dname TEXT, uid INTEGER, data TEXT, allowed INTEGER, connection INTEGER, interactive INTEGER)"""),
    ("access", """CREATE TABLE access (
        ID INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER NOT NULL, version INTEGER NOT NULL,
        protocol INTEGER NOT NULL, daddr TEXT NOT NULL, dport INTEGER NOT NULL, time INTEGER NOT NULL,
        allowed INTEGER, block INTEGER NOT NULL, sent INTEGER, received INTEGER, connections INTEGER)"""),
    ("dns", """CREATE TABLE dns (
        ID INTEGER PRIMARY KEY AUTOINCREMENT, time INTEGER NOT NULL, qname TEXT NOT NULL,
        aname TEXT NOT NULL, resource TEXT NOT NULL, ttl INTEGER, uid INTEGER)"""),
    ("forward", """CREATE TABLE forward (
        ID INTEGER PRIMARY KEY AUTOINCREMENT, protocol INTEGER NOT NULL, dport INTEGER NOT NULL,
        raddr TEXT NOT NULL, rport INTEGER NOT NULL, ruid INTEGER NOT NULL)"""),
    ("app", """CREATE TABLE app (
        ID INTEGER PRIMARY KEY AUTOINCREMENT, package TEXT, label TEXT,
        system INTEGER NOT NULL, internet INTEGER NOT NULL, enabled INTEGER NOT NULL)"""),
]
INDEXES = [
    "CREATE UNIQUE INDEX idx_access ON access(uid, version, protocol, daddr, dport)",
    "CREATE INDEX idx_access_daddr ON access(daddr)",
    "CREATE INDEX idx_access_block ON access(block)",
    "CREATE UNIQUE INDEX idx_dns ON dns(qname, aname, resource)",
    "CREATE INDEX idx_dns_resource ON dns(resource)",
    "CREATE UNIQUE INDEX idx_package ON app(package)",
    "CREATE INDEX idx_log_time ON log(time)",
    "CREATE INDEX idx_log_dest ON log(daddr)",
    "CREATE INDEX idx_log_dname ON log(dname)",
    "CREATE INDEX idx_log_dport ON log(dport)",
    "CREATE INDEX idx_log_uid ON log(uid)",
]


def run(args, check=True, serial=None):
    cmd = ["adb"]
    if serial:
        cmd += ["-s", serial]
    cmd += args
    print("  $ " + " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"komenda zwróciła {r.returncode}: {r.stderr.strip() or r.stdout.strip()}")
    return r


def adb_shell(serial, cmd, check=True):
    return run(["shell", cmd], check=check, serial=serial)


def build_db(path, rules):
    """Generuje świeżą bazę Netguard (schemat v22) z regułami z `rules`."""
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    cur = con.cursor()
    for _, ddl in SCHEMA:
        cur.execute(ddl)
    for idx in INDEXES:
        cur.execute(idx)
    # reguły: package -> enabled (1/0). system/internet domyślnie 0 (NetGuard ustali sam przy skanie).
    for pkg, enabled in rules.items():
        cur.execute(
            "INSERT INTO app (package, label, system, internet, enabled) VALUES (?,?,?,?,?)",
            (pkg, pkg, 0, 1, 1 if enabled else 0),
        )
    cur.execute(f"PRAGMA user_version = {DB_VERSION}")
    con.commit()
    con.close()
    print(f"  baza: {len(rules)} reguł -> {os.path.basename(path)}")


def build_prefs(path, settings):
    """Generuje plik shared_prefs z ustawieniami globalnymi."""
    lines = ["<?xml version='1.0' encoding='utf-8' standalone='yes' ?>", "<map>"]
    for key, val in settings.items():
        if isinstance(val, bool):
            lines.append(f"    <boolean name=\"{key}\" value=\"{'true' if val else 'false'}\" />")
        elif isinstance(val, int):
            lines.append(f"    <int name=\"{key}\" value=\"{val}\" />")
        else:
            lines.append(f"    <string name=\"{key}\">{val}</string>")
    lines.append("</map>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  prefs: {len(settings)} ustawień -> {os.path.basename(path)}")


def main():
    ap = argparse.ArgumentParser(description="Wypycha konfigurację NetGuarda przez ADB.")
    ap.add_argument("config", help="plik JSON z konfiguracją")
    ap.add_argument("--serial", help="serial urządzenia ADB (domyślnie: jedyne podłączone)")
    ap.add_argument("--dry-run", action="store_true", help="tylko generuje pliki, nie wypycha")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)
    rules = cfg.get("rules", {})
    settings = cfg.get("settings", {})
    print(f"Konfiguracja: {cfg.get('name', args.config)} ({len(rules)} reguł, {len(settings)} ustawień)")

    tmp = tempfile.mkdtemp(prefix="ngcfg_")
    db_path = os.path.join(tmp, DB_NAME)
    prefs_path = os.path.join(tmp, PREFS_FILE)
    build_db(db_path, rules)
    build_prefs(prefs_path, settings)

    if args.dry_run:
        print(f"\n[dry-run] pliki wygenerowane w {tmp} — nie wypycham na urządzenie.")
        return

    # --- weryfikacja urządzenia ---
    if not args.serial:
        r = run(["devices"], check=False)
        lines = [l for l in r.stdout.splitlines()[1:] if l.strip() and "device" in l]
        if not lines:
            print("BŁĄD: brak podłączonych urządzeń ADB.", file=sys.stderr)
            sys.exit(1)
        args.serial = lines[0].split()[0]
    print(f"Urządzenie: {args.serial}")

    # czy run-as działa (czy to build debug)?
    t = adb_shell(args.serial, f"run-as {PKG} id", check=False)
    if t.returncode != 0:
        print("BŁĄD: run-as nie działa — zainstaluj build DEBUG NetGuarda (ten z tej strony).", file=sys.stderr)
        sys.exit(1)

    print("Wypycham konfigurację…")
    adb_shell(args.serial, f"am force-stop {PKG}")
    # pliki do /data/local/tmp (world-readable), potem run-as cp do katalogu aplikacji
    run(["push", db_path, "/data/local/tmp/ng.db"], serial=args.serial)
    run(["push", prefs_path, "/data/local/tmp/ng_prefs.xml"], serial=args.serial)
    adb_shell(args.serial, f"run-as {PKG} sh -c 'cp /data/local/tmp/ng.db databases/{DB_NAME} && chmod 600 databases/{DB_NAME}'")
    adb_shell(args.serial, f"run-as {PKG} sh -c 'cp /data/local/tmp/ng_prefs.xml shared_prefs/{PREFS_FILE}'")
    adb_shell(args.serial, "rm -f /data/local/tmp/ng.db /data/local/tmp/ng_prefs.xml", check=False)
    adb_shell(args.serial, f"am start -n {PKG}/.ActivityMain", check=False)

    shutil.rmtree(tmp, ignore_errors=True)
    print("\nGotowe. NetGuard uruchomiony z nową konfiguracją.")
    print("Sprawdź w aplikacji, czy reguły się zaaplikowały (lista aplikacji / przełączniki).")


if __name__ == "__main__":
    main()
