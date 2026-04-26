# v1.1.0 Build Log — 2026-04-25

## Artifacts

- `dist/ContainerTracker.exe` — 48.9 MB (51,280,440 bytes; PyInstaller --onefile --windowed)
- `dist/installer/ContainerTracker_Setup_v1.1.0.exe` — 50.3 MB (52,772,848 bytes; Inno Setup)

## Build environment

- Python: 3.14.2
- PyInstaller: 6.20.0
- Inno Setup: 6.7.1 (`C:\Users\emine\AppData\Local\Programs\Inno Setup 6\ISCC.exe`)
- OS: Windows 11 Pro 10.0.26200

## Spec optimization — what actually shipped

The Phase 7 finish session was prompted to do a fresh `.spec` rewrite that
swapped the existing PyInstaller-bundled-hook + `excludes` approach for
`collect_all('PySide6')` + a hiddenimports filter. That rewrite was
**not applied**: the prior commit `77e45fc` ("build: slim PyInstaller bundle
by excluding unused PySide6 modules") had already shrunk the exe from 266 MB
to 48.9 MB using a different mechanism, and the rewrite would have:

- excluded `PySide6.QtNetwork` (the prior commit message explicitly noted
  the app references QtNetwork — risk of runtime breakage)
- dropped the existing `numpy`, `PIL`, `pytest`, `_pytest`, `setuptools`,
  `pip` excludes that the current spec uses to keep transitive bloat out

Decision: keep the committed approach in `77e45fc`. The 48.9 MB exe already
beat the 60–100 MB target the prompt aimed at. Posterity: the shipped
`.spec` reflects `77e45fc`, not the rewrite drafted in the Phase 7 finish
prompt.

## Smoke test results

### Standalone .exe (`dist/ContainerTracker.exe`)

- Bootloader PID: 35220 (Start-Process handle — exits after spawning child)
- Window-owning PID: 38424 (looked up via `Get-Process ContainerTracker`)
- Window title: `Container Tracker v1.1.0`
- Window handle: 1115562
- Cold-start time to window: 2.3 s
- Exit on WM_CLOSE: clean (window closed and process tree cleaned up)

Note: the first smoke-test invocation tracked the bootloader PID returned
by `Start-Process -PassThru`, which exits before the child registers a
window — so the window check kept failing on a process that no longer had
one. Switched to looking up the live process by name (`Get-Process
ContainerTracker | Where-Object { $_.MainWindowHandle -ne 0 }`), which
captured the window in 2.3 s. The exe itself was never the problem.

### Installed .exe (silent upgrade from v1.0.0)

- Installer exit code: 0
- Installed path: `%LOCALAPPDATA%\Programs\ContainerTracker\ContainerTracker.exe`
- Installed size: 48.9 MB (replaced the v1.0.0 binary at 266 MB / 278,787,530 bytes)
- `config.json` preserved: yes (100 B before, 100 B after, byte-identical)
- `tracking_data.json` preserved: yes (file does not exist on this machine; both pre and post comparisons returned `$null` — the byte-identical check still holds)
- Bootloader PID: 20492
- Window-owning PID: 10560
- Launch title: `Container Tracker v1.1.0`
- Window handle: 9899202
- Cold-start time to window: 2.3 s
- Exit on WM_CLOSE: clean
- Backup `%APPDATA%\ContainerTracker.phase7-backup`: cleaned up after all checks passed

## Ready to ship

- AppId unchanged (`867023ab-b5bc-48d0-8093-961789d93187`) → Windows recognized v1.1.0 install as an upgrade over v1.0.0.
- `ATTRIBUTIONS.md` bundled.
- `README_CLIENT.md` bundled (isreadme).
- User data migration: none needed — v1.0.0 config format matches v1.1.0.
- Per-user install (`PrivilegesRequired=lowest`) — no UAC prompt required.

**Upload to GitHub Releases: pending user approval.**
