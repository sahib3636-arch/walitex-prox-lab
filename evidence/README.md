# Non-sensitive test evidence

- `premium-dialog-candidate-264207405.png` — screenshot from emulator run `41216388638` after tapping the “Disable calls and video calls” switch in diagnostic candidate `264207405`. It confirms that the Premium dialog still appears and the switch remains off.
- `premium-switch-transient-candidate-264207407.png` — screenshot from run `41218735895`: suppressing the dialog lets the switch appear on immediately after the tap, but it returns off after reopening the screen; the preference stays false. It contains no user chat or phone data.
- `dialog-callstack-candidate-264207406.txt` — stack trace pinpointing the native Premium-dialog callback.

All included evidence contains no user chat or phone data.

The full emulator outputs are available in the workspace under `/home/user/runs/mod9/`, `/home/user/runs/mod10/`, `/home/user/runs/mod11/`, and `/home/user/runs/mod12/`; their key results are summarized in `docs/PROJECT_STATUS.md` so they are not dependent on expiring Actions artifacts.
