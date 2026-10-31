# walitex-prox-lab

CI lane for **WA ProX** (the renamed, hardened WA LiteX clone, package `com.whatsapp.litey`).

What lives here:

| path | what |
|---|---|
| `.github/workflows/emulator.yml` | boots an x86_64 Android emulator on a GitHub runner, installs the APK from a release asset, runs a driver script, uploads `out/` (screenshots, UI dumps, full logcat, crash buffer) |
| `scripts/probe.sh` | the driver: launch → clear EULA/permission screens → overflow menu → *Link as companion device* → watch, capture |
| `scripts/ui.py` | uiautomator helper: `list`, `tap <labels…>`, `shot`, `key`, `raw` |

APKs are attached as **release assets**, never committed (124 MB each). The workflow pulls them with
the repo's own `GITHUB_TOKEN`, so no secrets are stored in the repo.

## Why this exists

The phone-side bugreport channel is useless for this question: on the S24U the bugreport's `main`
logcat buffer covers **about one second**, so anything the app logged a minute earlier is gone.
An emulator gives a live `adb logcat`, which the diagnostic builds need.

## Builds under test

* `mf3` — the clone, blank-screen crash fixed
* `mf4dbg` — mf3 + WhatsApp's internal log level forced to 5 (logcat mirror)
* `mf5dbg` — mf4dbg + 9 breadcrumbs through the companion-linking flow and a 40 s watchdog that
  throws `RuntimeException("PROX-PROBE path: …")` when the QR payload never arrives

## Running

Manual: Actions → *emulator-probe* → Run workflow, pick the release `tag`.

The first question the lane answers: does the companion-linking flow behave the same on a clean
emulator as on the Samsung, and if it fails, what does the app itself say about it.
