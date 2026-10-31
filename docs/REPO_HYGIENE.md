# Repository recovery and hygiene

This public repository is the durable record for project source scripts, decisions, test summaries, hashes, and non-sensitive evidence. Continue committing meaningful updates as work progresses.

## Keep out of Git

- APK/AAB files, expansion archives, Android data directories, and emulator output dumps.
- The exact linked-base APK and its contents.
- Signing keystores, signing passwords, key lineages, private keys, access tokens, and private config payloads.
- Real user phone numbers, message content, chats, or user-device identifiers.

The repository ignores common APK/signing outputs. Before every commit, review `git status --short` and scan staged files for tokens and private-key markers. Never print or copy the authenticated Git remote URL into a tracked file.

## Preserve durably

- Source/patch scripts and their validation checks.
- Current acceptance criteria, build identity, hashes, and concise test results.
- Run IDs and the exact paths/links for raw artifacts while they remain available.
- Small screenshots that demonstrate a defect, after confirming they contain no personal data.

Actions artifacts expire. When a result matters, record it in `docs/PROJECT_STATUS.md` before that happens.

## Recovery caveat

A same-signing-key in-place update requires the original private keystore. It must remain private, backed up securely outside this public repository, and available to the authorized owner. A new key cannot install over the already-linked app. The local working copy currently keeps the exact base APK and signing material outside `/home/user/lab`; their hashes and purpose are documented, not the key files themselves.
