# Container Tracker

## What This App Does

Tracks your shipping containers across MSC, Maersk, CMA CGM, Hapag-Lloyd, and other major carriers, and writes up-to-date ETAs directly to Excel.

## First-Time Setup

1. Run the Setup file (`ContainerTracker_Setup_v1.0.0.exe`) and follow the prompts.
2. Launch Container Tracker from your desktop or Start menu.
3. A Welcome dialog will ask for three things:
   - **Company name** — whatever you'd like the app to display.
   - **ShipsGo API key** — paste your UUID-format v2 token. Find it at [shipsgo.com](https://shipsgo.com) under Dashboard → Integrations → ShipsGo API.
   - **Contact email** — your support/contact address.
4. Click Save. These values are stored securely (the API key goes into Windows Credential Manager, never a plain-text file) and the app remembers them going forward.

## Daily Use

1. Open the app.
2. Click **Refresh All ETAs & Update Excel** to pull the latest status from the carriers and write it to your linked spreadsheet.
3. Use the **Add** field and carrier dropdown to track new containers.
4. Use the **Linked spreadsheet** section to choose, create, or open your Excel file.

Refreshes are unlimited and free — you only consume ShipsGo credits when adding a new container for the first time.

## Updating Your Settings

Click the gear icon (⚙) in the top-right of the main window to edit your company name, API key, or contact email.

## Where Your Data Lives

All your configuration, tracking data, and logs are stored in:

`%APPDATA%\ContainerTracker\`

You can paste that path directly into the Windows Explorer address bar to open the folder.

## Getting Updates

When a new version is available, a banner appears at the top of the app. Click it to open the download page, run the new installer over your existing installation, and you're done. Your data and settings are preserved.

## If Something Breaks

Open the data folder above and check the file called `tracker.log` — it records what the app was doing when the problem occurred. If you can't figure it out from there, send the log file to Michael.

---
<a href="https://www.flaticon.com/free-icons/container" title="container icons">Container icons created by Iconjam - Flaticon</a>
