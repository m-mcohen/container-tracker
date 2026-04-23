# Ken Gabbay Container Tracker

## What This App Does

Tracks your shipping containers across MSC, Maersk, CMA CGM, Hapag-Lloyd, and other major carriers, and writes up-to-date ETAs directly to Excel.

## First-Time Setup

1. Run the Setup file (`KenGabbayTracker_Setup_v1.0.0.exe`) and follow the prompts.
2. Launch the app from your desktop or Start menu.
3. When prompted, paste in your ShipsGo API key. You only do this once — the key is stored securely in Windows Credential Manager and never asked for again.

## Daily Use

1. Open the app.
2. Click **Refresh** to pull the latest status from the carriers.
3. Click **Export to Excel** to save the updated data to your spreadsheet.

That's it.

## Where Your Data Lives

All your configuration, tracking data, and logs are stored in:

`%APPDATA%\Ken Gabbay Coffee\KenGabbayTracker\`

You can paste that path directly into the Windows Explorer address bar to open the folder.

## Getting Updates

When a new version is available, a banner appears at the top of the app. Click it to download the new installer, run it over the existing installation, and you're done. Your data and settings are preserved.

## If Something Breaks

Open the data folder above and check the file called `tracker.log` — it records what the app was doing when the problem occurred. If you can't figure it out from there, send the log file to Michael and he'll take a look.
