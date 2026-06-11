// Generates delivery/ContainerTracker_Getting_Started.docx — the client-facing
// setup guide. Regenerate after UI or flow changes (update the version string
// in the subtitle below first):
//
//   npm install -g docx
//   $env:NODE_PATH = npm root -g
//   node tools\client_guide.js delivery\ContainerTracker_Getting_Started.docx
//
// delivery/ is gitignored; the .docx/.pdf are send-to-client artifacts, not
// source. Convert to PDF by opening in Word (or any docx-to-pdf tool).

const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        Header, Footer, AlignmentType, LevelFormat, ExternalHyperlink,
        TabStopType, TabStopPosition, HeadingLevel, BorderStyle, WidthType,
        ShadingType, PageNumber } = require("docx");

const ACCENT = "1F4E79";   // deep navy — matches the app's Excel header brand
const LIGHT  = "EAF1F8";   // pale blue fill for callouts
const WARN   = "FDF3D7";   // pale amber fill for the SmartScreen warning
const MUTE   = "6B7280";

const border = { style: BorderStyle.SINGLE, size: 1, color: "C9D4E0" };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 100, bottom: 100, left: 140, right: 140 };

function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] });
}
function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] });
}
function p(runs, opts = {}) {
  if (typeof runs === "string") runs = [new TextRun(runs)];
  return new Paragraph({ children: runs, spacing: { after: 120 }, ...opts });
}
function step(ref, runs) {
  if (typeof runs === "string") runs = [new TextRun(runs)];
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    children: runs,
    spacing: { after: 100 },
  });
}
function bullet(runs) {
  if (typeof runs === "string") runs = [new TextRun(runs)];
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children: runs,
    spacing: { after: 100 },
  });
}
function bold(t) { return new TextRun({ text: t, bold: true }); }
function plain(t) { return new TextRun(t); }
function link(text, url) {
  return new ExternalHyperlink({
    children: [new TextRun({ text, style: "Hyperlink" })],
    link: url,
  });
}
function callout(fill, paragraphs) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [new TableRow({
      children: [new TableCell({
        borders, width: { size: 9360, type: WidthType.DXA },
        shading: { fill, type: ShadingType.CLEAR },
        margins: cellMargins,
        children: paragraphs,
      })],
    })],
  });
}

const numberingConfigs = ["part1", "part2", "part3"].map(ref => ({
  reference: ref,
  levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 540, hanging: 360 } } } }],
}));
numberingConfigs.push({
  reference: "bullets",
  levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 540, hanging: 360 } } } }],
});

function statusRow(cells, isHeader = false) {
  const widths = [2200, 7160];
  return new TableRow({
    children: cells.map((c, i) => new TableCell({
      borders, width: { size: widths[i], type: WidthType.DXA },
      shading: isHeader ? { fill: ACCENT, type: ShadingType.CLEAR } : undefined,
      margins: cellMargins,
      children: [new Paragraph({ children: [new TextRun({ text: c, bold: isHeader, color: isHeader ? "FFFFFF" : undefined })] })],
    })),
  });
}

function fixRow(cells, isHeader = false) {
  const widths = [3120, 6240];
  return new TableRow({
    children: cells.map((c, i) => new TableCell({
      borders, width: { size: widths[i], type: WidthType.DXA },
      shading: isHeader ? { fill: ACCENT, type: ShadingType.CLEAR } : undefined,
      margins: cellMargins,
      children: [new Paragraph({ children: [new TextRun({ text: c, bold: isHeader, color: isHeader ? "FFFFFF" : undefined })] })],
    })),
  });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } }, // 11pt
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: "000000" },
        paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0,
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: ACCENT, space: 2 } } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: "000000" },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: "Subtitle2", name: "Subtitle2", basedOn: "Normal",
        run: { size: 22, color: MUTE },
        paragraph: { spacing: { after: 360 } } },
      { id: "TitleBig", name: "TitleBig", basedOn: "Normal",
        run: { size: 52, bold: true, color: "000000" },
        paragraph: { spacing: { before: 120, after: 80 } } },
    ],
  },
  numbering: { config: numberingConfigs },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
        children: [
          new TextRun({ text: "Container Tracker — Getting Started Guide", color: MUTE, size: 18 }),
          new TextRun({ text: "\t", color: MUTE, size: 18 }),
          new TextRun({ children: ["Page ", PageNumber.CURRENT], color: MUTE, size: 18 }),
        ],
      })] }),
    },
    children: [
      // ── Title ──
      new Paragraph({ style: "TitleBig", children: [new TextRun("Container Tracker")] }),
      new Paragraph({ style: "Subtitle2", children: [
        new TextRun("Getting Started Guide • Version 1.2.0 • June 2026"),
      ] }),

      p([plain("Container Tracker watches your ocean shipments for you. Give it your container numbers and it keeps an eye on every ship — where it is, when it will arrive, and whether it is running late — and writes everything into your Excel file automatically. One-time setup takes about ten minutes; after that, day-to-day use is a single click.")]),

      callout(LIGHT, [
        p([bold("What you’ll need:"), plain(" a Windows PC, Microsoft Excel, your business email address, and about 10 minutes. The app and the ShipsGo account are free to set up; tracking a new container costs one ShipsGo credit (updates after that are free and unlimited).")],
          { spacing: { after: 0 } }),
      ]),
      p(""),

      // ── Part 1 ──
      h1("Part 1 — Create your free ShipsGo account"),
      p([plain("ShipsGo is the service that does the actual ship tracking. The app needs your personal ShipsGo “API key” — think of it as the password that connects the app to your account.")]),
      step("part1", [plain("Go to "), link("shipsgo.com", "https://shipsgo.com"), plain(" and click "), bold("Sign Up"), plain(". The account is free.")]),
      step("part1", "Use your business email, and click the link in the confirmation email when it arrives."),
      step("part1", [plain("Log in to the ShipsGo dashboard. In the left sidebar, open the "), bold("Integration"), plain(" section, then "), bold("ShipsGo API"), plain(".")]),
      step("part1", [plain("Generate your "), bold("API key"), plain(" and copy it — a long string of letters and numbers. Treat it like a password: don’t email or text it to anyone.")]),
      step("part1", [plain("About cost: tracking a "), bold("new"), plain(" container uses 1 ShipsGo credit; after that, all updates on it are free. If your account has no credits, you can buy a bundle in the dashboard — they go a long way.")]),

      // ── Part 2 ──
      h1("Part 2 — Install the app"),
      step("part2", [plain("Open this link: "), link("github.com/m-mcohen/container-tracker/releases/latest", "https://github.com/m-mcohen/container-tracker/releases/latest")]),
      step("part2", [plain("Under “Assets,” click "), bold("ContainerTracker_Setup_v1.2.0.exe"), plain(" to download it.")]),
      step("part2", "Run the downloaded file."),
      step("part2", [plain("Click through the installer (leave "), bold("Create a desktop shortcut"), plain(" checked). The app opens when it finishes.")]),
      p(""),
      callout(WARN, [
        p([bold("Windows will warn you — that’s expected."), plain(" The app isn’t from a big software company, so Windows doesn’t recognize it:")], { spacing: { after: 80 } }),
        bullet([plain("If the browser says the file “isn’t commonly downloaded,” choose "), bold("Keep"), plain(".")]),
        bullet([plain("If a blue “Windows protected your PC” box appears, click "), bold("More info"), plain(", then "), bold("Run anyway"), plain(".")]),
      ]),

      // ── Part 3 ──
      h1("Part 3 — Connect the app to your account"),
      p("The app won’t track anything until it has your API key — it will remind you with a welcome message on first launch."),
      step("part3", [plain("Click "), bold("Open Settings"), plain(" on the welcome message (or the gear icon, top right).")]),
      step("part3", [plain("Enter your "), bold("company name"), plain(" and "), bold("contact email"), plain(", and paste your "), bold("API key"), plain(" from Part 1 into the API key box. Click "), bold("Test"), plain(" to confirm it works, then "), bold("Save changes"), plain(".")]),
      step("part3", [plain("Under "), bold("Linked spreadsheet"), plain(", pick one:  already have an Excel file with a “Container” column? Click "), bold("Change…"), plain(" and select it.  Starting fresh? Click "), bold("Create template"), plain(" and save the file somewhere easy, like Documents.")]),
      step("part3", "Click the back arrow to return to the main screen. Setup is done — you never repeat this."),

      // ── Everyday use ──
      h1("Everyday use"),
      bullet([bold("Add container"), plain(" (top right): type the container number — 11 characters, like MSKU1234567 — pick the shipping line, click "), bold("Add & track"), plain(". This is the step that uses 1 credit.")]),
      bullet([bold("Refresh"), plain(" (the blue button): pulls the latest status for everything and updates your Excel file automatically. Free and unlimited — click it as often as you like.")]),
      bullet([plain("You can also type new container numbers "), bold("straight into your Excel file"), plain(" — on the next Refresh, the app spots them and offers to track them.")]),
      bullet([plain("Done with a delivered shipment? Click the "), bold("⋯"), plain(" on its row, then "), bold("Archive"), plain(". It moves out of view (and out of Excel) but is never deleted — find it under the Archived tab.")]),
      bullet([bold("Close Excel before clicking Refresh."), plain(" If the file is open, the app tells you and simply catches up on the next refresh. Nothing is lost.")]),

      h2("What the screen is telling you"),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2200, 7160],
        rows: [
          statusRow(["You see", "It means"], true),
          statusRow(["Sailing (blue)", "On the water and on schedule. The Transit bar shows how far along the voyage is."]),
          statusRow(["Delayed (red)", "Running late — the Delay column shows how many days behind the original ETA. “+7 days” in red means a week late; green “(early)” means ahead of schedule."]),
          statusRow(["Arrived (green)", "Reached the destination port (or discharged/delivered)."]),
          statusRow(["Booked (yellow)", "Registered with the carrier but not yet sailed."]),
        ],
      }),
      p(""),

      // ── Updates ──
      h1("Updates"),
      p([plain("When a new version of the app is released, a banner appears at the top of the main screen. Click "), bold("Download update"), plain(", run the installer over the old version, and you’re done. Your settings, tracked containers, and Excel file are never touched by an update.")]),

      // ── Help ──
      h1("If something looks wrong"),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3120, 6240],
        rows: [
          fixRow(["What you see", "What to do"], true),
          fixRow(["“Excel write skipped”", "The spreadsheet was open in Excel during a refresh. Close the workbook and click Refresh again."]),
          fixRow(["“Linked Excel file not found”", "The file was moved or renamed. Open Settings and re-link it with Change…"]),
          fixRow(["“New containers found in your spreadsheet”", "You added container numbers in Excel. Click Register to start tracking them (1 credit each), or Skip."]),
          fixRow(["“Not enough credits”", "Your ShipsGo account is out of credits — top up in the ShipsGo dashboard."]),
          fixRow(["Anything else", "Open the Activity log at the bottom of the main screen and send me a screenshot."]),
        ],
      }),
    ],
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(process.argv[2] || "ContainerTracker_Getting_Started.docx", buf);
  console.log("written");
});
