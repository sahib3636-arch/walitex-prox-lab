# WA LiteX project status — Request 7

**Last updated:** 2026-10-31 (Asia/Karachi)
**Status:** active investigation; no new build is approved for user installation.

## Goal and release gate

Improve the existing WA LiteX build the user installed and linked. Do not recreate the app or change its identity. A release is only acceptable when it meets all of these criteria:

1. Voice notes capture audible speech on the user's Samsung S24 Ultra.
2. The existing privacy switches stay enabled after leaving/reopening the sheet and restarting the app.
3. Premium-gated features are genuinely usable; merely changing a premium getter is not enough.
4. An update installs over package `com.whatsapp.litex` with the same signing identity, a higher `versionCode`, unchanged `versionName`, and preserved companion link/data.
5. Anti View Once still allows repeat viewing/download behavior while the sender receives an “Opened” receipt.

Do not claim any feature is fixed until its behavior is tested. Mic capture, sender-side receipt visibility, repeat-view/download behavior, and the real-device end-to-end update remain unverified.

## Identity and known-good base

- User-installed and linked base build: `mf9mic`
- Package: `com.whatsapp.litex`
- `versionCode`: `264207400`
- `versionName`: `2.26.42.74`
- Base APK SHA-256: `068e77c5573570e99baee67129c47419c7b5e5cec6c91f529f23be8db365fa08`
- Base archive: `https://x0.at/UW0H.zip`
- Existing signer: `CN=ProX Mod (a)` (certificate SHA-256 `2805279da0b0d8c73e4dcbbbc66d87617a16ead435c9e0090aaea9091ecfe209`)

Never change the package, authorities, permissions, or `versionName`. Never uninstall/clear data on the user's linked phone. Keep signing material private and outside this public repository.

## Verified in-place update test

Run `41215960864` used the corrected `scripts/upgrade_probe.sh`, installing candidate `264207404` over the exact `264207400` base on an Android API 31 x86_64 emulator. The workflow completed successfully.

- `adb install -r`: **Success**
- Probe result: `IN_PLACE_INSTALL=PASS`, `PREFS_PRESERVED=PASS`
- Package stayed `com.whatsapp.litex`; `versionName` stayed `2.26.42.74`.
- `versionCode`: `264207400` → `264207404`.
- Package `userId` stayed `10145`; `firstInstallTime` was unchanged; `lastUpdateTime` advanced. This is an in-place update, not an uninstall/reinstall.
- The tested privacy preferences matched before/after. The tested rows 0 and 2 remained checked after the update.

Evidence is in `/home/user/runs/mod9/` while that workspace is available. The concise probe output is also recorded in this document so the result does not depend on the temporary Actions artifact.

## Premium toggle: latest findings

The privacy screen has six switches in the emulator test. Rows 0–4 are ordinary toggles; row 5 is “Disable calls and video calls” and is marked Premium.

### Candidate `264207404`

- APK SHA-256: `7b93efdda62ddd06e9f614d48cdd5429f621e4effd33817a12f2ec6466a41e05`
- ZIP: `https://x0.at/hRov.zip`
- Toggle run: `41215902278` (success)
- Result: rows 0–4 could be enabled, but row 5 remained off. Tapping it displayed the Premium dialog. `walitex_block_calls_check` remained false.
- In-place update test: `41215960864` (success; details above).

The `getPrm(55501/55502)` return-value hypothesis and a local replacement for `Listener$Switch.onCheckedCase22` did **not** unlock this row. Do not ship candidate `264207404` as the fix.

### Diagnostic candidate `264207405` (not for user installation)

- APK SHA-256: `5114346a5ae0eff8d326ce2315fe982fc1442196614c70be135344335f9658df`
- ZIP: `https://x0.at/vZ3C.zip`
- Toggle run: `41216388638` (success)
- Result: row 5 still remained off and displayed the same Premium dialog. The diagnostic tag `ProXCase22` was not present in the captured logcat. This suggests that the replacement did not reach its logging branch; the exact caller/argument path is still being traced, so this absence alone is not treated as conclusive proof that the Java callback is never invoked.
- Screenshot evidence: `evidence/premium-dialog-candidate-264207405.png`.

This candidate contains experimental tracing and is not a user-ready release. The next diagnostic should capture the Java stack at `WaResources.getAlertDialog` while leaving the native callback behavior intact, then identify the specific gate responsible for the modal.

## Earlier useful results

- Candidate `264207403` was installed over the linked base by run `41215277866` (`adb install -r` succeeded). The first workflow reported failure only because the probe mixed XML and assertion text into one file. The probe was corrected and pushed as commit `f064eae`.
- Candidate `264207403` did not unlock the Premium calls switch; the dialog remained. It should not be treated as a fix.
- Earlier tests showed privacy rows 0–4 could be persisted through the SharedPreferences-backed path; the previous “saveEnabled”-only change was insufficient.
- The QR/link regression was caused by changing the package identity. The corrected `mf9mic` base restored the original package and the user successfully linked it. No package rename is allowed going forward.

## Mic and Anti View Once

- Mic: the phone reports voice notes are silence/static. AudioSource variants 5, 6, 7, and 9 did not restore capture. The current linked-base patch changes the S24 Ultra non-Pixel branch to use `AudioSource.CAMCORDER`, but this is **not verified on the phone**.
- Anti View Once: the candidate patch permits the ordinary open/read-receipt path while leaving retention/display behavior in place. Repeat-view/download behavior and the sender’s visible “Opened” status are **not verified**.

## Test/build policy

- Emulator runs are diagnostics, not proof of success on the S24 Ultra.
- Always test updates with `adb install -r` over the exact linked base and record package, version, signer, user ID, first-install time, and preferences.
- Increment `versionCode` for every candidate; do not give the user an unvalidated diagnostic APK.
- Do not put APKs, signing keystores, private credentials, or real user/device identifiers in this public repo. Store source, patch scripts, hashes, test summaries, and non-sensitive screenshots instead.
- The GitHub Actions artifacts expire; preserve important outcomes in committed docs/evidence rather than relying on the Actions UI alone.
