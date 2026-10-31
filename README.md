# walitex-prox-lab

Ongoing engineering work on the **existing WA LiteX app** the user installed and linked. The app's
original package identity (`com.whatsapp.litex`) and its current signing identity must be preserved;
this repository is not a replacement product or a renamed-clone release path. Some historical
notes/scripts from earlier clone experiments remain for reference, but they are not authority to
change the current app identity. See [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) for the live
acceptance criteria, verified results, and unresolved issues.

The emulator answers questions the phone cannot: on the S24 Ultra a bugreport's `main` logcat buffer
holds about one second, so anything the app logged a minute earlier is gone. An emulator gives a
live `adb logcat` for the whole run. Emulator success is not treated as proof of S24 Ultra behavior.

## What lives here

| path | what |
|---|---|
| `docs/PROJECT_STATUS.md` | current user acceptance criteria, exact base identity, verified update results, failures, and open tests |
| `docs/REPO_HYGIENE.md` | what belongs in the public repo and how to keep APKs, credentials, and signing material out |
| `tooling/linked_update/` | linked-base in-place patch/build sources; requires the private base APK and signing identity outside Git |
| `.github/workflows/emulator.yml` | boots an x86_64 or arm64 Android emulator, installs the APK from a URL input, runs a driver, uploads `out/` (screenshots, UI dumps, full logcat, crash buffer, socket samples) |
| `scripts/ui.py` | uiautomator helper: `list`, `tap <labels…>` (keyword priority, exact label beats substring, clickable beats plain text), `has <labels…>`, `shot`, `key`, `raw` |
| `scripts/probe.sh` | the linking driver: launch → clear the custom-ROM alert / EULA / permissions → phone-number screen → overflow menu (3 tries) → *Link as companion device*, or straight to the companion activity → 240 s watch |
| `scripts/upgrade_probe.sh` | verifies an `adb install -r` update over the exact linked base and checks package identity/preferences |
| `scripts/mod_toggles.sh` | taps every privacy switch, captures persistence/modal screenshots, and preserves diagnostic log traces |
| `scripts/drive_one.sh` | the same walk for one package, for A/B runs |
| `scripts/compare.sh` | historical control/clone comparison helper; not the current release path |
| `scripts/ab_connect.sh` | launches builds and samples `/proc/net/tcp{,6}` by uid, for connection diagnostics |

## Notes that cost time to learn

* **Private repos on this GitHub account cannot run Actions** ("recent account payments have failed
  or your spending limit needs to be increased"), so this repo is public. No APK or signing material
  is stored here — the workflow pulls the test build from `apk_url`, and the private linked base/key
  stay in the authorized local build environment.
* **API level matters for the ABI**: the APK ships arm64 libraries only. `api-level: 33`,
  target `google_apis` has no ARM translation and fails with
  `INSTALL_FAILED_NO_MATCHING_ABIS`; **api 30/31 google_apis x86_64** do translate ARM and the app
  installs and runs (`abis=x86_64,arm64-v8a`).
* **The overflow menu does not open on the phone-number screen** in the emulator (three taps, no
  popup), while the same icon opens it on the EULA screen. mf7 and the control builds therefore
  start the companion activity from `RegisterPhone.onCreate`, with exactly the intent the menu item
  builds: `entry_point = "entry_phone_reg"`.
* `curl` against the file host needs `--retry-all-errors`: long transfers get cut and `--retry`
  alone does not resume them.
* Concurrency groups must include every input that changes the job, or a second dispatch cancels the
  first.

## Inputs

| input | meaning |
|---|---|
| `apk_url` | APK or a zip containing one |
| `apk_sha256` | optional expected hash (leave blank unless you mean it — a stale default fails the run) |
| `original_url` | optional untouched WA LiteX APK, for the A/B drivers |
| `api_level`, `arch` | emulator image (`31` + `x86_64` is what works for this APK) |
| `driver`, `clone_pkg`, `ipv6` | script to run, package under test, `off` to disable IPv6 on the emulator |
