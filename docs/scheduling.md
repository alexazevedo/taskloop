# Scheduling orc

## macOS — launchd

Create `~/Library/LaunchAgents/com.orc.nightrun.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.orc.nightrun</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/bin/orc</string>
    <string>run</string>
    <string>--night</string>
    <string>--repo</string>
    <string>/path/to/repo</string>
    <string>--config</string>
    <string>/path/to/repo/orchestrator.toml</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>22</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>/tmp/orc-night.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/orc-night.err</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.orc.nightrun.plist
```

## Linux — cron

```cron
# Run nightly at 22:00
0 22 * * * /usr/local/bin/orc run --night \
  --repo /path/to/repo \
  --config /path/to/repo/orchestrator.toml \
  >> /var/log/orc-night.log 2>&1
```

Add via `crontab -e`.

## Notes

- `orc run --night` respects `night_wallclock_minutes` from config; it stops pulling new tickets when the budget is exhausted.
- The run lock (`tasks/.orc.lock`) prevents two simultaneous instances. If cron fires while a previous run is still active, the new invocation exits cleanly with a non-zero code.
- Logs: human-readable output goes to stdout/stderr; structured telemetry to `tasks/.telemetry.jsonl`.
