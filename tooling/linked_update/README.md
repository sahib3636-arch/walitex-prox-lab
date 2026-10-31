# In-place linked-base update builder

These are the source and helper modules for producing a successor to the user's exact linked `mf9mic` APK. The builder modifies the existing package; it does not create a new app. Its normal output keeps `com.whatsapp.litex`, `versionName=2.26.42.74`, the same signer/lineage, and requires an explicit higher `TARGET_VERSION`.

## Private inputs

The public repo deliberately does **not** contain the linked APK, keystore, key lineage, or key password. Keep those in the authorized private working directory. The known linked base has SHA-256 `068e77c5573570e99baee67129c47419c7b5e5cec6c91f529f23be8db365fa08` and `versionCode=264207400`.

Typical local setup (paths may be overridden):

```sh
export PROX_BUILD_DIR="$HOME/prox-build"
export PROX_BASE_APK="$PROX_BUILD_DIR/incoming/mf9mic-signed.apk"
# Load PROX_KEY_PASS from a secure local secret store; do not put it in shell history or Git.
TARGET_VERSION=264207407 python3 tooling/linked_update/update_linked.py
```

Dependencies include Python 3, Java, the Android SDK `aapt`, `zipalign`, and `apksigner`, `zip`, Capstone, and the Debian baksmali/smali jars used by the build. The builder fails if the input version is not lower than the target, the APK identity changes, an unexpected archive entry changes, or signing/zipalign verification fails.

## Diagnostic flags

- `PROX_DIAG_TOGGLE=1` adds preference-read and switch-constructor logging.
- `PROX_TRACE_DIALOGS=1` replaces `WaResources.getAlertDialog` with a temporary stack-tracing wrapper.
- `PROX_SUPPRESS_PRM_BANNER=1` suppresses `Extra.setPrmBanner` for a local calls-switch test; this only removes the popup and does not prove the feature works.
- `PROX_DIAG_SET_BOOLEAN=1` replaces the native Boolean writer with a direct SharedPreferences writer and logs every key/value write.
- `PROX_DIAG_GET_PRM=1` logs premium getter IDs while preserving the local `getPrm` return values.

Both are **diagnostic-only** and must be disabled for any release build unless the underlying behavior is independently validated and the patch is deliberately retained.

The local builder writes APKs/reports under `$PROX_BUILD_DIR/artifacts` and `$PROX_BUILD_DIR/report`, outside the repository. Never commit those files or any signing material.
