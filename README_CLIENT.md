# Container Tracker

**Version 1.1.0**

## What This App Does

Container Tracker keeps an eye on your shipping containers across the major ocean carriers — MSC, Maersk, CMA CGM, Hapag-Lloyd, COSCO, Evergreen, ONE, ZIM, and more — and writes the latest status, ETA, vessel, and route information straight into your Excel file every time you click Refresh. You keep working in Excel; the app keeps Excel up to date.

## Installing

1. Run `ContainerTracker_Setup_v1.1.0.exe` and follow the prompts. No admin rights are needed — it installs to your user folder.
2. Launch **Container Tracker** from the desktop shortcut or Start menu.
3. The first time it opens, a Welcome dialog asks for three things:
   - **Company name** — whatever you'd like the app to display.
   - **ShipsGo API key** — paste your token from [shipsgo.com](https://shipsgo.com) → Dashboard → Integrations → ShipsGo API. It looks like a long string of letters, numbers, and dashes.
   - **Contact email** — your support address.
4. Click Save. Your API key is stored in Windows Credential Manager (not in any plain-text file), and these settings are remembered going forward.

## Daily Use

### Linking an Excel file

Open Settings (the gear icon ⚙ in the top-right) and either browse to your existing tracking spreadsheet or click **Create Template** to make a new one. The app needs a column whose header contains the word *Container*, *Cntr*, or *Container #* — that's the only requirement. Everything else (Status, ETA, Vessel, Route, Delay, Transit %) is added automatically the first time the app writes to the file.

You can also click **Open in Excel** at the top of the window any time to open the linked file.

### Refreshing

Click **Refresh** in the top-right. The app pulls the latest information from the carriers and writes it to your linked Excel file. The "Last refreshed" timestamp updates when it's done. Refreshes are unlimited and free — you only spend ShipsGo credits when you add a brand-new container.

### Adding a container

Click **+ Add container**, paste the container number, choose the carrier, and confirm. This is the one action that costs a ShipsGo credit. From then on, refreshes are free.

### Archiving containers

Once a container has been delivered (or is otherwise no longer worth tracking), select it in the table and click **Archive selected**. Archived containers are removed from your Excel file but kept in the app's history. You can review them any time by clicking the **Archived** filter at the top of the table.

### Filtering the table

Use the chips above the table — **All**, **Delayed**, **Sailing**, **Arrived**, **Booked**, **Archived** — to show just the containers you care about right now.

## What the Excel File Looks Like

The app works with any spreadsheet that has a column for container numbers. The first time it writes to a new file, it adds (or updates) these columns alongside your existing data:

- **Status** — Booked, Sailing, Arrived, Discharged, Delayed
- **Original ETA** and **Current ETA**
- **Delay** — "+6 days", "On time", "-2 days (early)", etc.
- **Route** — port of loading → port of discharge
- **Vessel** — current vessel name
- **Transit %** — how far along the journey

Status cells are color-coded; delays are red, on-time is normal, early is green. If the app finds containers in your spreadsheet that it doesn't know about yet, it asks before adding them (since adding consumes ShipsGo credits).

## Troubleshooting

### "Linked Excel file not found"

This banner appears at the top of the app when the spreadsheet you linked has been moved, renamed, or deleted. Click **Open Settings** in the banner and link the file again. Refreshes still update the app's internal data while the file is missing — you just need to re-link before the next write to Excel will work.

### "Excel write skipped"

This means the spreadsheet is open in Excel and locked for editing. Tracking data was still updated inside the app — close the workbook in Excel and click **Refresh** again to sync the changes to the file. Click **Dismiss** to clear the banner once you've handled it.

### "Not enough ShipsGo credits"

Adding a new container costs one ShipsGo credit. If you see this error, top up your ShipsGo account at [shipsgo.com](https://shipsgo.com) and try the Add again. Refreshing existing containers never costs credits.

### Anything else

Open `%APPDATA%\ContainerTracker\` (paste that into the Windows Explorer address bar) and look for `tracker.log`. It records what the app was doing when something went wrong. If you can't figure it out from there, send the log file to Michael.

## Updating

When a new version of Container Tracker is released, a banner appears at the top of the app on launch. Click it to open the download page, run the new installer over your existing one, and you're done — your data, settings, and Excel link are preserved.

## Where Your Data Lives

`%APPDATA%\ContainerTracker\` holds your `config.json`, `tracking_data.json`, and `tracker.log`. Your linked Excel file stays wherever you put it. Your ShipsGo API key lives in Windows Credential Manager and never touches a plain-text file.

---
<a href="https://www.flaticon.com/free-icons/container" title="container icons">Container icons created by Iconjam - Flaticon</a>
