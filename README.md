# walitex-prox-lab

CI lane for **WA ProX** (the renamed, hardened WA LiteX clone) and for control builds of the shipped
WA LiteX itself. The emulator answers questions the phone cannot: on the S24 Ultra a bugreport's
`main` logcat buffer holds about one second, so anything the app logged a minute earlier is gone. An
emulator gives a live `adb logcat` for the whole run.

## What lives here

| path | what |
|---|---|
| `.github/workflows/emulator.yml` | boots an x86_64 or arm64 Android emulator, installs the APK from a URL input, runs a driver, uploads `out/` (screenshots, UI dumps, full logcat, crash buffer, socket samples) |
| `scripts/ui.py` | uiautomator helper: `list`, `tap <labels…>` (keyword priority, exact label beats substring, clickable beats plain text), `has <labels…>`, `shot`, `key`, `raw` |
| `scripts/probe.sh` | the linking driver: launch → clear the custom-ROM alert / EULA / permissions → phone-number screen → overflow menu (3 tries) → *Link as companion device*, or straight to the companion activity → 240 s watch |
| `scripts/drive_one.sh` | the same walk for one package, for A/B runs |
| `scripts/compare.sh` | untouched LiteX and the clone, same emulator, same minute |
| `scripts/ab_connect.sh` | launches each build and samples `/proc/net/tcp{,6}` by uid, to compare who keeps a socket to `:443` open |

## Notes that cost time to learn

* **Private repos on this GitHub account cannot run Actions** ("recent account payments have failed
  or your spending limit needs to be increased"), so this repo is public. No APK is stored here —
  the workflow pulls the build from the `apk_url` input at run time.
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
