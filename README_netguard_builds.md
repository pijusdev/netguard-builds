# netguard_builds

## 0. CEL I STATUS

**CEL:** Strona dostępna po linku (trudna do odnalezienia), **prywatna**, z buildami
NetGuarda (bez Pro) + konfiguracjami urządzeń. Model: **prywatne repo GitHub + Cloudflare Pages**
(zgodnie z rekomendacją Gemini + decyzją Usera 2026-09-14).

| # | Zadanie | Status |
|---|---------|--------|
| 1 | Prywatne repo `pijusdev/netguard-builds` (buildy arm32/arm64, configs, site, CI) | ✅ |
| 2 | Ciemna strona (builds + status kompilacji z ETA + configs) | ✅ zwalidowana lokalnie |
| 3 | System konfiguracji: `apply_config.py` + 2 configi (prototyp) | ✅ |
| 4 | Konto **Cloudflare dla agenta (pius)** — e-mail `pijusejajus@gmail.com` | ⬜ |
| 5 | Podpięcie prywatnego repo pod **Cloudflare Pages** | ⬜ |
| 6 | Trudny do odgadnięcia URL + `<meta name="robots" content="noindex,nofollow">` | ⬜ |
| 7 | Plik akcji GitHub `build.yml` (token bez scope `workflow` → przez web UI) | ⬜ |
| 8 | Test buildu przez akcję (workflow_dispatch) | ⬜ |
| 9 | Finalny raport z linkiem do Usera | ⬜ |

> Hasło do konta Cloudflare (agenta): w `C:/bun/pi-agent/workspace/netguard_builds/.secrets.md`
> (plik z `.gitignore` — NIE trafia na GitHub).

---

Prywatne repo z **buildami NetGuarda skompilowanymi od źródła** — firewall dla Androida
z **odblokowanymi funkcjami Pro**, bez roota, w wersjach 32-bit i 64-bit. Do tego:
strona (GitHub Pages) do pobierania buildów + **system konfiguracji urządzeń** wypychany przez ADB.

> ⚠️ Repo jest **prywatne**. Strona jest dostępna tylko przez **tajny link GitHub Pages**
> (secret URL). Nie udostępniaj go publicznie.

---

## 1. Co to i jak to działa

**NetGuard** (open source, GPLv3, autor M66B) to firewall Androida działający przez lokalny
tunel VPN — blokuje internet dla wybranych aplikacji **bez roota**.

Wersje z Play Store mają funkcje Pro (dziennik, DNS, filtr ruchu, port forwarding) za opłatą.
**Mechanizm odblokowania** — bez żadnej modyfikacji kodu:

- W źródle NetGuarda (`IAB.java`) jest wbudowany backdoor:
  `IAB.isPurchased(...)` zwraca `true` (zakupione), gdy aplikacja jest **debuggable**
  (`Util.isDebuggable(context)`), chyba że w prefach `debug_iab` jest `true`.
- Build **debug** jest debuggable → **wszystkie funkcje Pro są odblokowane domyślnie**.

Dlatego kompilujemy po prostu `assembleDebug` — i mamy pełny NetGuard Pro, legalnie,
od źródła, bez kluczy i bez łajania kodu.

**Jedyna zmiana w źródle** (techniczna, nie funkcjonalna):
`compileSdkVersion = 36` → `compileSdk 36` (nowoczesna składnia Gradle). Reszta to oryginał.

---

## 2. Struktura repo

```
netguard_builds/
├── .github/workflows/build.yml   # Akcja GitHub: kompiluje NetGuarda na żądanie
├── build/
│   ├── VERSION                   # Pin wersji NetGuarda (2.337)
│   ├── build.sh                  # Logika budowania (SDK, patche, gradle)
│   ├── publish.py                # Po buildzie: aktualizuje builds.json + status.json
│   └── patches/                  # (rezerwa)
├── site/                         # Źródła strony (GitHub Pages, folder /site)
│   ├── index.html                # Ciemna, nowoczesna strona
│   ├── app.js                    # Frontend: lista buildów, polling statusu, ETA
│   ├── style.css                 # Motyw ciemny
│   ├── favicon.svg
│   ├── data/
│   │   ├── builds.json           # Lista buildów (wersja, ABI, size, sha256)
│   │   ├── configs.json          # Lista konfiguracji urządzeń
│   │   └── status.json           # Status kompilacji (idle/building/error) + ETA
│   └── dist/
│       ├── NetGuard-v2.337-arm32.apk
│       ├── NetGuard-v2.337-arm64.apk
│       └── configs/              # Pliki konfiguracji (.json)
├── tools/
│   └── apply_config.py           # Wypycha konfigurację na urządzenie przez ADB
└── README_netguard_builds.md     # Ten plik
```

---

## 3. Kompilacja

### Przez GitHub Actions (zalecane — "kliknij i skompiluje")
1. Otwórz repo → zakładka **Actions** → workflow **Build NetGuard** → **Run workflow**.
2. Akcja: JDK 21 + Android SDK (platform 36, NDK 25.2, CMake) → klonuje NetGuarda
   w wersji z `build/VERSION` → `assembleDebug` → wypycha APK do `site/dist/`.
3. Strona pokazuje na żywo status (krok + szacowany czas) — odpytuje `status.json`.
4. Gotowe APK pojawia się na stronie w sekcji **Do pobrania**.

Czas: ~15–20 min (pobranie NDK + kompilacja native + APK).

### Lokalnie
```bash
# wymaga JDK 21 + ANDROID_HOME (platform 36, build-tools 36, NDK 25.2.9519653, cmake)
export ANDROID_HOME=/sciezka/do/sdk
./build/build.sh            # wersja z build/VERSION
# APK w build/out/: NetGuard-v<ver>-arm32.apk, -arm64.apk, -universal.apk
```

---

## 4. Strona (GitHub Pages)

- Ciemna, prosta, czytelna. Pokazuje: jak to działa, status kompilacji (z ETA),
  listę buildów (wersja + procesor + size + sha256 + pobierz), konfiguracje urządzeń.
- **Tajny link**: repo prywatne → w ustawieniach Pages jest **Secret URL**
  (losowy adres `*.pages.github.net`) — ten link działa bez logowania. To JEDYNY
  adres do udostępniania.
- Frontend odpytuje `data/status.json` co 30 s — gdy akcja buduje, widać krok i
  szacowany czas do końca (na podstawie czasu ostatniego builda).

---

## 5. Konfiguracje urządzeń (część 2)

### Jak NetGuard przechowuje konfigurację (research)
- **Reguły** (która appa ma internet): baza SQLite `databases/Netguard`, tabela `app`
  — kolumna `enabled` = 1 dozwolona / 0 zablokowana. Schemat `DB_VERSION = 22`
  (wersja 2.337). Tabele: `log`, `access`, `dns`, `forward`, `app`.
- **Ustawienia globalne** (filtrowanie, logowanie, DNS, watchdog…):
  `shared_prefs/eu.faircode.netguard_preferences.xml` (klucze: `filter`, `log`, `dns`,
  `pcap`, `auto_enable`, `watchdog`, `stats_frequency`, …).
- NetGuard ma wbudowany **eksport do XML** (`ActivitySettings`), ale **import jest
  wywoływany z UI (SAF)** — trudno to zautomatyzować przez ADB.

### Nasze podejście: wypychanie przez ADB + run-as
Bo build **debug jest debuggable**, `adb shell run-as eu.faircode.netguard` ma dostęp
do plików aplikacji. `tools/apply_config.py`:
1. generuje świeżą bazę `Netguard` (schemat v22, `PRAGMA user_version=22`) z regułami,
2. generuje plik preferencji z ustawieniami,
3. `am force-stop` → `adb push` do `/data/local/tmp` → `run-as cp` do katalogu app,
4. uruchamia NetGuarda.

Efekt: **pełna, powtarzalna konfiguracja** na urządzeniu, bez dotykania UI.

### Format konfiguracji (JSON)
```json
{
  "name": "Nazwa profilu",
  "device": "Opis urządzenia",
  "desc": "Co robi",
  "settings": { "filter": true, "log": true, "dns": false },
  "rules": { "com.example.ad": 0, "com.example.good": 1 }
}
```
`rules`: package → `1` dozwolona / `0` zablokowana. `settings`: klucz → wartość
(bool/int/string) — odpowiadają kluczen w `shared_prefs`.

### Użycie
```bash
adb devices                                   # sprawdź, czy urządzenie jest widoczne
python3 tools/apply_config.py dist/configs/towinger_q13w.json
python3 tools/apply_config.py dist/configs/block_ads.json --dry-run   # tylko generuje pliki
```

### Rozwijanie
Konfiguracje leżą w `site/dist/configs/` (pobieralne ze strony) i są listowane w
`site/data/configs.json`. Aby dodać nową: wrzuć `.json` do `dist/configs/`, dodaj
wpis do `configs.json`, commit + push (strona się odświeży).

> ⚠️ Skrypt `apply_config.py` jest **prototypem** — wygenerowany na podstawie schematu
> z źródła 2.337. Przed użyciem na ważnym urządzeniu zrób backup bazy NetGuarda
> (`adb shell run-as eu.faircode.netguard cat databases/Netguard > backup.db`).

---

## 6. Prywatność i bezpieczeństwo — co NIE ma w tym repo

Zgodnie z zasadą **zero rzeczy prywatnych na GitHubie**:
- ❌ brak prywatnych kluczy podpisujących (używamy standardowego klucza debug Androida),
- ❌ brak tokenów API, haseł, danych logowania,
- ❌ brak prywatnych adresów IP / URL-i wewnętrznych,
- ❌ brak handoffów, notatek z danymi osobowymi,
- ✅ jedyne "sekrety" to standardowy `debug.keystore` (publiczny, znany wszystkim).

Pamiętaj: **nie commituj** niczego prywatnego do historii — historia commitów też jest
prywatna, ale lepiej nie ryzykować.

---

## 7. Utrzymanie

- Zmiana wersji NetGuarda: edytuj `build/VERSION` (i ewentualnie schemat bazy w
  `apply_config.py`, jeśli `DB_VERSION` się zmieni).
- Dodanie architektury (np. x86_64): rozszerz `splits.abi.include` w `build/build.sh`
  i mapę `ABI_MAP`.
- Logi akcji: zakładka **Actions** w repo.
