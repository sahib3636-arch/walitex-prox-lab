# WA LiteX project status — Request 7

**Last updated:** 2026-11-01 (Asia/Karachi)
**Status:** active investigation; no new build is approved for general user installation. Candidate `264207411` is a local diagnostic build only.

## Goal and release gate

Improve the existing WA LiteX build the user installed and linked. Do not recreate the app or change its identity. A release is only acceptable when it meets all of these criteria:

1. Voice notes capture audible speech on the user's Samsung S24 Ultra.
2. The existing privacy switches stay enabled after leaving/reopening the sheet and restarting the app.
3. Premium-gated features are genuinely usable; merely changing a premium getter is not enough.
4. An update installs over package `com.whatsapp.litex` with the same signing identity, a higher `versionCode`, unchanged `versionName`, and preserved companion link/data.
5. Anti View Once still allows repeat viewing/download behavior while the sender receives an “Opened” receipt.

Do not claim any feature is fixed until its behavior is tested. Actual incoming-call rejection, candidate `264207411` switch persistence and in-place update, mic capture, sender-side receipt visibility, repeat-view/download behavior, and the real-device end-to-end update remain unverified.

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

### Candidate `264207409` in-place update test (emulator pass)

Workflow `41220850995` installed candidate `264207409` over the exact linked base with `adb install -r`, without uninstalling or clearing data. `IN_PLACE_INSTALL=PASS` and `PREFS_PRESERVED=PASS`; package stayed `com.whatsapp.litex`, versionName stayed `2.26.42.74`, versionCode advanced `264207400` → `264207409`, userId remained `10145`, firstInstallTime was unchanged, and rows 0 and 2 remained checked. The preference XML before and after was identical. See `evidence/in-place-update-candidate-264207409.txt` and `.png`.

This is emulator verification only; the existing companion link on the user's S24 Ultra still needs confirmation after any user-side update.

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
- Result: row 5 still remained off and displayed the same Premium dialog. The diagnostic tag `ProXCase22` was absent; a follow-up stack trace confirmed the dialog comes through `Extra.setPrmBanner` called by `Listener$Switch.onCheckedChanged`, not the `onCheckedCase22` replacement.
- Screenshot evidence: `evidence/premium-dialog-candidate-264207405.png`.

### Candidate `264207406` (dialog-call trace; not for user installation)

- APK SHA-256: `c87a16ebaaca455b6618e83aed8bf4f078beb9ad943c53355d87f2be898338c7`
- ZIP: `https://x0.at/U3mh.zip`
- Toggle run: `41217984667` (success)
- The `WaResources.getAlertDialog` stack trace identifies `Extra.setPrmBanner(Native Method)` called by `Listener$Switch.onCheckedChanged(Native Method)` as the actual Premium-dialog path. See `evidence/dialog-callstack-candidate-264207406.txt`.
- Row 5 still ended off. The temporary wrapper and native callback were diagnostic-only; this is not a release.

### Candidate `264207407` (local feature test; failed persistence)

- APK SHA-256: `8751725f01ccbd99a0c66517467e9feaba006f1d57758fcfafadf706f12f1b9f`
- ZIP: `https://x0.at/Hwfi.zip`
- It suppresses `Extra.setPrmBanner` for a local emulator test. The popup disappears and row 5 looks checked immediately after the tap, but after reopening the screen row 5 is off; `walitex_block_calls_check` remains false.
- Run `41218735895` completed successfully. The `ProXSetPrmBanner` tag confirms the intercepted callback ran. `final.txt` and `litex_prefs.xml` show the calls switch did not persist.
- Screenshot evidence: `evidence/premium-switch-transient-candidate-264207407.png`.

This proves popup suppression alone does not make the calls feature work. Candidate `264207407` is diagnostic-only and must not be installed on the user's phone.

### Diagnostic candidate `264207408` (write tracing; failed acceptance test)

- APK SHA-256: `08b40a530163798784e5cd32565a29825e3e1b6433294256cd6a5c54a4f148e5`
- ZIP: `https://x0.at/elaN.zip` (SHA-256 `13c24339ed55b0796dec257fc1ad5cecebaa47f7f45584227b05ea9f15f3989d`)
- Workflow `41219372357` completed, but the calls-switch test failed. Logcat recorded `getPrm(55501)`, then `walitex_block_calls_check=true`, immediately followed by `...=false`, then the banner callback. After reopening, row 5 was off and the preference remained false; rows 0–4 persisted.
- Evidence: `evidence/calls-toggle-native-reset-candidate-264207408.txt`.
- Native disassembly identifies the second false write at VA `0x6ff60`: `sturb wzr, [x29, #-0x28]`. The same JNI boolean slot had first been loaded from the checked state at `0x6fe08` (`sturb w21, [x29, #-0x28]`). This is the specific reset site to test; it is not evidence that the paid feature is unlocked.

### Diagnostic candidate `264207409` (native reset-site persistence test passed; feature unverified)

- APK SHA-256: `b6aec8055a8902c7386514cd0f38096e51b92e83e1e5fbe8a1bc865e1f8c4587`
- Diagnostic ZIP: `https://x0.at/Z009.zip` (SHA-256 `a6e6cda5e0c778eee5322054c002f3893e862f1bd9a02f92f1d39684271ae056`)
- Workflow `41220312147` completed successfully. The trace shows `getPrm(55501)`, followed by two `walitex_block_calls_check=true` writes and no false reset. After reopening, row 5 remained checked and the preference remained true; rows 0–4 also remained checked. `SoLoader` confirms the emulator loaded the patched `/lib/arm64` native library.
- Run `41220244459` failed before emulator startup due to a test-workflow self-move when a ZIP member was already named `app.apk`; fixed in commit `981d5ae`. The corrected rerun is `41220312147`.
- Screenshot and exact evidence: `evidence/calls-switch-persistent-candidate-264207409.png` and `.txt`.
- This is still a diagnostic candidate, not approved for user installation. It suppresses the Premium banner and instruments preferences. Persistence is verified; actual call blocking and legitimate Premium entitlement are not.
- The separate in-place-update probe over the original linked base passed in workflow `41220850995`; details and evidence are recorded above. The candidate remains diagnostic-only because actual call blocking is unverified.

### Candidate `264207410` (native writer and banner retained; persistence passes, feature remains gated)

- APK SHA-256: `bdba36bd7bf2b61619a3ec0c83a746d4145f4e1e71e8ac95c4e0dc7fe48415f2`
- ZIP: `https://x0.at/f5pP.zip` (SHA-256 `705b7cd34bf9d1e751de16bab7225916e7c97a5df4ef200cad811f8ccde93f8b`)
- Emulator workflow `41221349558` completed successfully. This build keeps the native `WaResources.setBoolean` writer and original Premium banner; only the guarded `0x6ff60` reset store is NOPed. The calls preference was true and row 5 stayed checked after cold reopen.
- The Premium dialog still appears on tap, and while it is open the switch looks off. After closing/reopening the screen, the persisted preference displays on. Screenshots and details: `evidence/calls-switch-native-writer-candidate-264207410.txt` and two `.png` files.
- This confirms persistence through the original native writer, **not** that incoming calls are blocked. The UI still presents the feature as Premium, so this candidate is not an unlock and is not approved for user installation.

### Candidate `264207411` (local test; static call path found, dynamic checks pending)

- APK SHA-256: `955ba44f2bf5828038b7ca3d829b09a0f8d99279968855154d65103bd1ba0179`; size 123,703,596 bytes.
- Test ZIP: `https://x0.at/FV9w.zip` (SHA-256 `54d209df09ec30bda0f41c604c69875744ed8ccb385a3fa5d87cc8e8e8f4cb7a`). The ZIP was downloaded again and its hash matched; `unzip -t` passed.
- Identity: package `com.whatsapp.litex`, versionCode `264207411`, versionName `2.26.42.74`, signer `CN=ProX Mod (a)` (certificate SHA-256 matches the known base signer). `aapt dump badging`, `zipalign -c`, `apksigner verify` (v1/v2/v3), and APK ZIP integrity checks passed. It was built from the exact linked base with the native preference writer retained, the guarded `0x6ff60` false-reset store NOPed, and `Extra.setPrmBanner` suppressed solely for local feature testing.
- Static DEX/native tracing found a path from the `walitex_block_calls_check` preference through `LX/CMk.handleMessage` and `PrivacyActivity.getPrivacyCalls` to a `RunnableTask` mode 6 that calls `Voip.rejectCall(String,String,int)`. The native path also reads `walitex_block_calls_mode` and `walitex_blocked_country_prefixes`, builds per-number preference names, and contains a prefix `startsWith` check. Evidence and offsets: `evidence/calls-block-static-trace-candidate-264207411.txt`.
- This materially improves the static understanding, but it is **not a behavior test**. Candidate 411 has not been emulator-tested for switch persistence, real call rejection, or `adb install -r` over the exact base. The S24 Ultra has not been tested. The banner suppression is not a Premium entitlement; this build remains diagnostic-only and is not approved as a release.

## Earlier useful results

- Candidate `264207403` was installed over the linked base by run `41215277866` (`adb install -r` succeeded). The first workflow reported failure only because the probe mixed XML and assertion text into one file. The probe was corrected and pushed as commit `f064eae`.
- Candidate `264207403` did not unlock the Premium calls switch; the dialog remained. It should not be treated as a fix.
- Earlier tests showed privacy rows 0–4 could be persisted through the SharedPreferences-backed path; the previous “saveEnabled”-only change was insufficient.
- The QR/link regression was caused by changing the package identity. The corrected `mf9mic` base restored the original package and the user successfully linked it. No package rename is allowed going forward.

## Mic and Anti View Once

- Mic: the phone reports voice notes are silence/static. AudioSource variants 5, 6, 7, and 9 did not restore capture. The current linked-base patch changes the S24 Ultra non-Pixel branch to use `AudioSource.CAMCORDER`, but this is **not verified on the phone**.
- Anti View Once: the candidate patch permits the ordinary open/read-receipt path while leaving retention/display behavior in place. Repeat-view/download behavior and the sender’s visible “Opened” status are **not verified**.

## Durable project files

- `tooling/linked_update/` contains `update_linked.py`, its `build_apk.py`, `mic_patch.py`, and `axml.py` helpers; the exact base APK, signing keystore, lineage, and passwords remain outside Git.
- The builder keeps the exact existing `P06_NEW` implementation. Logging remains isolated in `P06_DIAG_NEW` and is selected only with its diagnostic flag.
- `scripts/upgrade_probe.sh` is the corrected in-place update probe; commit `f064eae` fixed its earlier output-path false negative.
- `scripts/mod_toggles.sh` now keeps full dialog-stack and toggle-state trace excerpts from diagnostic runs.
- `evidence/premium-dialog-candidate-264207405.png` preserves the earlier Premium-dialog failure screenshot.
- `evidence/calls-toggle-native-reset-candidate-264207408.txt` records the exact setter order, final false preference, and the guarded native reset-site hypothesis.
- `evidence/calls-switch-persistent-candidate-264207409.txt` and `.png` record the successful emulator persistence test while clearly distinguishing it from actual call-block verification.
- `evidence/in-place-update-candidate-264207409.txt` and `.png` record the exact `adb install -r` update and preserved preferences on API 31.
- `evidence/calls-switch-native-writer-candidate-264207410.txt` and screenshots show that native preferences persist while the Premium dialog remains visible.
- `evidence/calls-block-static-trace-candidate-264207411.txt` records the DEX/native route from the calls preference to the WhatsApp `rejectCall` API, with explicit caveats that dynamic call-blocking and candidate-411 update tests remain undone.

## Test/build policy

- Emulator runs are diagnostics, not proof of success on the S24 Ultra.
- Always test updates with `adb install -r` over the exact linked base and record package, version, signer, user ID, first-install time, and preferences.
- Increment `versionCode` for every candidate; do not give the user an unvalidated diagnostic APK.
- Do not put APKs, signing keystores, private credentials, or real user/device identifiers in this public repo. Store source, patch scripts, hashes, test summaries, and non-sensitive screenshots instead.
- The GitHub Actions artifacts expire; preserve important outcomes in committed docs/evidence rather than relying on the Actions UI alone.
