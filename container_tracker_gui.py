#!/usr/bin/env python3
"""
Container Tracker
"""

__version__ = "1.0.0"

import json, os, sys, threading, logging, webbrowser, shutil, re
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    HAS_CTK = False
    import tkinter as tk
    from tkinter import ttk

from tkinter import messagebox, filedialog, END, StringVar
import tkinter.ttk as ttk_mod
import requests

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table, TableStyleInfo
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

try:
    import keyring
except ImportError:
    keyring = None


APP_NAME = "Container Tracker"
APP_SHORT_NAME = "ContainerTracker"
GITHUB_REPO = "m-mcohen/container-tracker"
# ─────────────────────────────────────────────────────────────────────────────
# Design system — palette, type scale, spacing, radius
# ─────────────────────────────────────────────────────────────────────────────

# Palette: navy + warm neutral. Semantic names; do not use raw hex elsewhere.
PALETTE_LIGHT = {
    "surface_base":    "#FAF8F3",  # warm bone — window background
    "surface_card":    "#FFFFFF",  # cards sit on this (outlined, no fill, so rarely used)
    "surface_subtle":  "#F1EDE4",  # log pane / table header — slightly darker than base
    "border":          "#D8D2C4",  # card / divider border (warm neutral)
    "border_subtle":   "#E7E2D6",  # hairline separators
    "text_primary":    "#1C1B17",  # deep warm charcoal
    "text_secondary":  "#5A5850",  # mid warm gray
    "text_tertiary":   "#8F8B82",  # hint / caption tertiary
    "accent":          "#1E3A5F",  # mid-dark navy — primary brand
    "accent_hover":    "#2A4D7A",  # lighter navy for button hover
    "accent_subtle":   "#E8EEF5",  # very light navy wash — ghost-button hover fill, banner bg
    "status_sailing":  "#4A7BA0",  # muted teal-blue
    "status_arrived":  "#5C8A5C",  # muted green
    "status_delayed":  "#B05A4D",  # muted rust
}
PALETTE_DARK = {
    "surface_base":    "#15171C",  # deep charcoal
    "surface_card":    "#1E2127",
    "surface_subtle":  "#191B20",
    "border":          "#383D48",  # nudged brighter so card edges stay visible on cards
    "border_subtle":   "#2E323B",
    "text_primary":    "#F0EDE5",  # warm off-white
    "text_secondary":  "#A8A59D",
    "text_tertiary":   "#6E6C66",
    "accent":          "#6B9DD4",  # brightened navy for dark-mode contrast
    "accent_hover":    "#84B0E0",
    "accent_subtle":   "#1C2836",
    "status_sailing":  "#6B9DD4",
    "status_arrived":  "#7FA87F",
    "status_delayed":  "#D48276",
}
ACCENT = PALETTE_LIGHT["accent"]  # kept for any legacy reference; theme-aware code uses self.T["green"]

# Typography — Segoe UI Variable ships with Windows 11; degrades to Segoe UI on Win10.
# Mono: Cascadia Code (ships with modern Windows), falls back via Tk to Consolas.
_FONT_FAMILY = "Segoe UI Variable"
_FONT_MONO   = "Cascadia Code"
FONTS = {
    "display":     (_FONT_FAMILY, 28, "bold"),    # stat-card numbers
    "heading":     (_FONT_FAMILY, 18, "bold"),    # page title / section heading
    "subheading":  (_FONT_FAMILY, 13, "bold"),    # primary CTA text, dialog field labels
    "body":        (_FONT_FAMILY, 12, "normal"),  # default label / row text
    "body_bold":   (_FONT_FAMILY, 12, "bold"),    # emphasized label
    "caption":     (_FONT_FAMILY, 11, "normal"),  # secondary labels, captions
    "hint":        (_FONT_FAMILY, 10, "normal"),  # muted hints, footer
    "mono":        (_FONT_MONO,   11, "normal"),  # activity log, monospace
}

# Spacing scale (px). Apply via dict lookup, no ad-hoc values.
SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}

# Corner-radius system.
RADIUS = {
    "input":    8,    # entries, combo boxes
    "btn":      8,    # secondary/ghost buttons
    "card":    12,    # outlined cards (stat cards, Excel card)
    "cta_pill": 19,   # primary CTAs (height 38 → radius 19 for true pill)
}

API_BASE = "https://api.shipsgo.com/v2"
KEYRING_SERVICE = f"{APP_SHORT_NAME}_shipsgo_api"
LEGACY_KEYRING_SERVICE = "KenGabbayTracker_shipsgo_api"
KEYRING_USER = "default"


def resource_path(rel: str) -> Path:
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return Path(base) / rel


LOGO_PATH = resource_path("app.ico")  # window icon only; not rendered in-app


def get_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".config"
    d = base / APP_SHORT_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


DATA_DIR = get_data_dir()
CONFIG_FILE = DATA_DIR / "config.json"
TRACKING_DB_FILE = DATA_DIR / "tracking_data.json"
LOG_FILE = DATA_DIR / "tracker.log"


def _migrate_data_folder(src: Path, dst: Path) -> int:
    """Move known data files from src → dst. Returns number of files moved. Removes src only if it emptied out."""
    if src is None or not src.exists() or src.resolve() == dst.resolve():
        return 0
    moved = 0
    for name in ("config.json", "tracking_data.json", "tracker.log"):
        s = src / name
        d = dst / name
        if s.exists() and not d.exists():
            try:
                shutil.move(str(s), str(d))
                moved += 1
            except Exception:
                pass
    if moved > 0:
        try:
            remaining = list(src.iterdir())
            if not remaining:
                src.rmdir()
                # Try to clean up KGC's company-level parent if it becomes empty.
                try:
                    parent = src.parent
                    appdata = Path(os.environ.get("APPDATA", "")) if sys.platform == "win32" else None
                    if parent.exists() and parent != appdata and not list(parent.iterdir()):
                        parent.rmdir()
                except Exception:
                    pass
        except Exception:
            pass
    return moved


# Migration chain: (i) next-to-exe/.py (oldest layout) and (ii) KGC-named APPDATA folder → DATA_DIR
_LEGACY_EXE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(os.path.dirname(os.path.abspath(__file__)))
_LEGACY_KGC_DIR = None
if sys.platform == "win32":
    _LEGACY_KGC_DIR = Path(os.environ.get("APPDATA", Path.home())) / "Ken Gabbay Coffee" / "KenGabbayTracker"

_migrate_data_folder(_LEGACY_EXE_DIR, DATA_DIR)
_migrate_data_folder(_LEGACY_KGC_DIR, DATA_DIR)

EST = timezone(timedelta(hours=-5))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.FileHandler(LOG_FILE)])
logger = logging.getLogger(__name__)


def get_api_token() -> str:
    if keyring is None:
        return ""
    try:
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USER) or ""
    except Exception as e:
        logger.info(f"keyring read failed: {e}")
        return ""


def set_api_token(token: str):
    if keyring is None:
        logger.info("keyring not installed; token not persisted")
        return
    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USER, token)
    except Exception as e:
        logger.info(f"keyring write failed: {e}")


def _migrate_keyring():
    if keyring is None:
        return
    try:
        old = keyring.get_password(LEGACY_KEYRING_SERVICE, KEYRING_USER)
    except Exception as e:
        logger.info(f"keyring legacy read failed: {e}")
        return
    if not old:
        return
    try:
        current = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:
        current = None
    if not current:
        try:
            keyring.set_password(KEYRING_SERVICE, KEYRING_USER, old)
            logger.info("migrated keyring entry to new service name")
        except Exception as e:
            logger.info(f"keyring migrate write failed: {e}")
            return
    try:
        keyring.delete_password(LEGACY_KEYRING_SERVICE, KEYRING_USER)
    except Exception as e:
        logger.info(f"keyring legacy delete failed: {e}")


_migrate_keyring()


def check_for_update_async(on_update):
    """Background GitHub Releases check. Calls on_update(tag, html_url) if a newer version is available."""
    def _go():
        try:
            if "<<" in GITHUB_REPO or "/" not in GITHUB_REPO:
                return
            r = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest", timeout=5)
            if r.status_code != 200:
                logger.info(f"update check: HTTP {r.status_code}")
                return
            data = r.json()
            tag = str(data.get("tag_name", "")).lstrip("v").strip()
            url = data.get("html_url", "")
            if not tag:
                return
            from packaging.version import parse as _parse
            if _parse(tag) > _parse(__version__):
                on_update(tag, url)
        except Exception as e:
            logger.info(f"update check failed: {e}")
    threading.Thread(target=_go, daemon=True).start()


API_KEY_PATTERN = re.compile(r"^[0-9a-fA-F\-]{30,40}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def open_in_explorer(path: Path):
    try:
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            import subprocess; subprocess.Popen(["open", str(path)])
        else:
            import subprocess; subprocess.Popen(["xdg-open", str(path)])
    except Exception as e:
        logger.info(f"open_in_explorer failed: {e}")

def now_est():
    return datetime.now(EST).strftime("%Y-%m-%d %I:%M %p EST")

def now_est_short():
    return datetime.now(EST).strftime("%I:%M %p")

def _theme_from_palette(P):
    """Map the semantic palette onto the legacy theme keys so the rest of the app
    (which reads self.T[...]) picks up the new values without further refactor."""
    return {
        "bg":          P["surface_base"],
        "card":        "transparent",          # outlined cards — no fill
        "input":       P["surface_base"],      # inputs blend with bg; border provides the frame
        "primary":     P["text_primary"],
        "secondary":   P["text_secondary"],
        "muted":       P["text_secondary"],
        "hint":        P["text_tertiary"],
        "border":      P["border"],
        "green":       P["accent"],            # primary accent (key name kept for minimal churn)
        "green_dark":  P["accent_hover"],
        "green_light": P["accent_subtle"],
        "blue":        P["status_sailing"],
        "blue_light":  P["accent_subtle"],
        "btn_bg":      P["surface_base"],      # ghost-button idle fg
        "btn_text":    P["text_secondary"],
        "thead":       P["surface_subtle"],
        "log_bg":      P["surface_subtle"],
        "sail_bg":     P["accent_subtle"],
        "sail_fg":     P["accent"],
        "disc_bg":     P["accent_subtle"],
        "disc_fg":     P["status_arrived"],
        "stat_bg":     "transparent",          # outlined stat cards — no fill
        "dropdown_bg": P["surface_card"],      # real fill — popup menus/dropdowns reject transparent
        "status_sailing": P["status_sailing"],
        "status_arrived": P["status_arrived"],
        "status_delayed": P["status_delayed"],
    }
LIGHT = _theme_from_palette(PALETTE_LIGHT)
DARK  = _theme_from_palette(PALETTE_DARK)

CARRIER_SCAC_MAP = {
    "MAERSK": "MAEU", "MAERSK LINE": "MAEU", "MSC": "MSCU",
    "CMA CGM": "CMDU", "HAPAG LLOYD": "HLCU", "HAPAG-LLOYD": "HLCU",
    "COSCO": "COSU", "EVERGREEN": "EGLV", "ONE": "ONEY",
    "YANG MING": "YMLU", "ZIM": "ZIMU", "HMM": "HDMU", "OOCL": "OOLU", "PIL": "PILU"}
CARRIER_NAMES = ["MAERSK LINE","MSC","CMA CGM","HAPAG LLOYD","COSCO",
                 "EVERGREEN","ONE","YANG MING","ZIM","HMM","OOCL","PIL","OTHER"]
CONTAINER_COL_KEYWORDS = ["container","cntr","container #","container number",
                          "container_number","container no","cntr #","cntr no"]

def resolve_scac(line):
    u = line.strip().upper()
    return CARRIER_SCAC_MAP.get(u, u if len(u)==4 else u)

def load_json(fp, default=None):
    p = Path(fp)
    if p.exists():
        with open(p) as f: return json.load(f)
    return default if default is not None else {}
def save_json(fp, data):
    with open(fp,"w") as f: json.dump(data,f,indent=2,default=str)
def load_config():
    return load_json(CONFIG_FILE, {"company_name":"","contact_email":"","excel_path":"","dark_mode":False,"dismissed":[]})
def save_config(c):
    save_json(CONFIG_FILE,c)

def migrate_token_from_config(cfg: dict) -> bool:
    """If config.json contains a legacy token field, move it to keyring. Returns True if migrated."""
    changed = False
    for key in ("shipsgo_api_token", "api_key"):
        if key in cfg:
            tok = str(cfg.pop(key) or "").strip()
            if tok:
                set_api_token(tok)
                logger.info(f"migrated {key} from config.json to keyring")
            changed = True
    return changed


def is_first_run(cfg: dict) -> bool:
    return not cfg.get("company_name") and not get_api_token()


def validate_setup_fields(company: str, api_key: str, email: str) -> str | None:
    if not company.strip():
        return "Company name is required."
    if not api_key.strip():
        return "ShipsGo API key is required."
    if not API_KEY_PATTERN.match(api_key.strip()):
        return "That API key doesn't look right — check for extra spaces or missing characters."
    if not email.strip() or not EMAIL_PATTERN.match(email.strip()):
        return "Enter a valid email address."
    return None


class SetupDialog:
    """Modal first-run / settings editor for company_name + api_key + contact_email."""
    def __init__(self, parent, initial_company="", initial_api_key="", initial_email="",
                 mode="first_run", extra_info=None):
        """
        mode: 'first_run' (blocking, no cancel, × quits app) or 'settings' (has Save + Cancel).
        extra_info: optional dict with keys version, data_dir (Path), github_repo — shown read-only in settings.
        """
        self.mode = mode
        self.result = None  # dict or None on cancel
        self.parent = parent
        self._build(initial_company, initial_api_key, initial_email, extra_info or {})

    def _build(self, company, api_key, email, extra):
        title = "Welcome to Container Tracker" if self.mode == "first_run" else "Settings"
        if HAS_CTK:
            self.win = ctk.CTkToplevel(self.parent)
        else:
            self.win = tk.Toplevel(self.parent)
        self.win.title(title)
        self.win.resizable(False, False)
        self.win.transient(self.parent)
        try:
            self.win.iconbitmap(str(LOGO_PATH))
        except Exception:
            pass

        # × handler
        if self.mode == "first_run":
            self.win.protocol("WM_DELETE_WINDOW", self._exit_app)
        else:
            self.win.protocol("WM_DELETE_WINDOW", self._on_cancel)

        body = ctk.CTkFrame(self.win, fg_color="transparent") if HAS_CTK else tk.Frame(self.win)
        body.pack(padx=24, pady=20, fill="both", expand=True)

        if self.mode == "first_run":
            intro = "Let's get you set up. You can change these later in Settings."
        else:
            intro = "Update your company info and API credentials."
        (ctk.CTkLabel(body, text=intro, font=FONTS["body"], justify="left") if HAS_CTK
         else tk.Label(body, text=intro, font=FONTS["hint"], justify="left")).pack(anchor="w", pady=(0, 14))

        self.company_var = StringVar(value=company)
        self.api_var = StringVar(value=api_key)
        self.email_var = StringVar(value=email)

        self._field(body, "Company name", self.company_var, width=360)
        self._field(body, "ShipsGo API key", self.api_var, width=360, mono=True,
                    hint="Find your key at shipsgo.com \u2192 Dashboard \u2192 Integrations \u2192 ShipsGo API")
        self._field(body, "Contact email", self.email_var, width=360)

        for v in (self.company_var, self.api_var, self.email_var):
            v.trace_add("write", lambda *_: self._update_save_state())

        if extra:
            sep = (ctk.CTkFrame(body, height=1, fg_color="#CCCCCC") if HAS_CTK
                   else tk.Frame(body, height=1, bg="#CCCCCC"))
            sep.pack(fill="x", pady=(12, 10))
            self._info_row(body, "App version", extra.get("version", ""))
            dd = extra.get("data_dir")
            if dd:
                self._info_row(body, "Data folder", str(dd), clickable=lambda: open_in_explorer(dd))
            self._info_row(body, "GitHub repo", extra.get("github_repo", ""))

        # Error label
        self.err_var = StringVar(value="")
        err = (ctk.CTkLabel(body, textvariable=self.err_var, text_color="#D32F2F",
                            font=FONTS["caption"], justify="left") if HAS_CTK
               else tk.Label(body, textvariable=self.err_var, fg="#D32F2F", font=FONTS["hint"], justify="left"))
        err.pack(anchor="w", pady=(6, 0))

        # Buttons
        btns = ctk.CTkFrame(body, fg_color="transparent") if HAS_CTK else tk.Frame(body)
        btns.pack(fill="x", pady=(14, 0))

        if self.mode == "settings":
            if HAS_CTK:
                self.cancel_btn = ctk.CTkButton(btns, text="Cancel", width=100, command=self._on_cancel,
                                                fg_color="#DDDBD5", text_color="#333333", hover_color="#C7C4BD")
            else:
                self.cancel_btn = tk.Button(btns, text="Cancel", width=12, command=self._on_cancel)
            self.cancel_btn.pack(side="right", padx=(8, 0))

        if HAS_CTK:
            self.save_btn = ctk.CTkButton(btns, text="Save", width=120, command=self._on_save,
                                          fg_color=ACCENT, hover_color="#1D4ED8", text_color="white",
                                          font=FONTS["subheading"])
        else:
            self.save_btn = tk.Button(btns, text="Save", width=14, command=self._on_save,
                                      bg=ACCENT, fg="white")
        self.save_btn.pack(side="right")

        self._update_save_state()
        self.win.update_idletasks()
        self._center()
        self.win.grab_set()
        self.win.focus_force()

    def _field(self, parent, label, var, width=340, mono=False, hint=None):
        (ctk.CTkLabel(parent, text=label, font=FONTS["subheading"], anchor="w") if HAS_CTK
         else tk.Label(parent, text=label, font=FONTS["body_bold"], anchor="w")).pack(anchor="w", pady=(4, 2))
        font = ("Consolas", 12) if mono else FONTS["body"]
        if HAS_CTK:
            entry = ctk.CTkEntry(parent, textvariable=var, width=width, font=font, corner_radius=RADIUS["input"])
        else:
            entry = tk.Entry(parent, textvariable=var, width=width // 8, font=font)
        entry.pack(anchor="w", pady=(0, 2))
        if hint:
            (ctk.CTkLabel(parent, text=hint, font=FONTS["hint"], text_color="#666666", anchor="w") if HAS_CTK
             else tk.Label(parent, text=hint, font=FONTS["hint"], fg="#666666", anchor="w")).pack(anchor="w", pady=(0, 8))
        else:
            (ctk.CTkFrame(parent, height=4, fg_color="transparent") if HAS_CTK
             else tk.Frame(parent, height=4)).pack(pady=(0, 4))

    def _info_row(self, parent, label, value, clickable=None):
        row = ctk.CTkFrame(parent, fg_color="transparent") if HAS_CTK else tk.Frame(parent)
        row.pack(anchor="w", fill="x", pady=1)
        (ctk.CTkLabel(row, text=label + ":", font=FONTS["body_bold"], width=110, anchor="w") if HAS_CTK
         else tk.Label(row, text=label + ":", font=FONTS["hint"], width=14, anchor="w")).pack(side="left")
        text_color = ACCENT if clickable else "#333333"
        cursor = "hand2" if clickable else ""
        if HAS_CTK:
            lbl = ctk.CTkLabel(row, text=value, font=FONTS["hint"], text_color=text_color,
                               cursor=cursor, anchor="w")
        else:
            lbl = tk.Label(row, text=value, font=FONTS["hint"], fg=text_color, cursor=cursor, anchor="w")
        lbl.pack(side="left")
        if clickable:
            lbl.bind("<Button-1>", lambda _e: clickable())

    def _center(self):
        self.win.update_idletasks()
        w = self.win.winfo_width(); h = self.win.winfo_height()
        sw = self.win.winfo_screenwidth(); sh = self.win.winfo_screenheight()
        x = (sw - w) // 2; y = (sh - h) // 3
        self.win.geometry(f"+{x}+{y}")

    def _update_save_state(self):
        valid = (self.company_var.get().strip() and self.api_var.get().strip() and self.email_var.get().strip()
                 and API_KEY_PATTERN.match(self.api_var.get().strip())
                 and EMAIL_PATTERN.match(self.email_var.get().strip()))
        state = "normal" if valid else "disabled"
        try:
            if HAS_CTK:
                self.save_btn.configure(state=state)
            else:
                self.save_btn.config(state=state)
        except Exception:
            pass

    def _on_save(self):
        err = validate_setup_fields(self.company_var.get(), self.api_var.get(), self.email_var.get())
        if err:
            self.err_var.set(err); return
        self.result = {
            "company_name": self.company_var.get().strip(),
            "api_key": self.api_var.get().strip(),
            "contact_email": self.email_var.get().strip(),
        }
        self.win.grab_release(); self.win.destroy()

    def _on_cancel(self):
        self.result = None
        self.win.grab_release(); self.win.destroy()

    def _exit_app(self):
        # First-run × quits app cleanly.
        try:
            self.win.grab_release(); self.win.destroy()
        except Exception:
            pass
        try:
            self.parent.destroy()
        except Exception:
            pass
        sys.exit(0)

class ShipsGoClient:
    def __init__(self, token):
        self.session = requests.Session()
        self.session.headers.update({"Accept":"application/json","Content-Type":"application/json",
                                     "X-Shipsgo-User-Token":token})
    def create_shipment(self, container_number="", carrier_scac=""):
        payload = {}
        if container_number: payload["container_number"]=container_number.strip().upper()
        if carrier_scac: payload["carrier_scac"]=carrier_scac.strip().upper()
        r = self.session.post(f"{API_BASE}/ocean/shipments",json=payload,timeout=30)
        if r.status_code==409: return {"already_exists":True}
        if r.status_code==402: return {"error":"NOT_ENOUGH_CREDITS"}
        r.raise_for_status(); return r.json()
    def list_shipments(self, take=100):
        r = self.session.get(f"{API_BASE}/ocean/shipments",params={"take":take},timeout=30)
        r.raise_for_status(); d=r.json()
        return d.get("shipments",d.get("data",[])) if isinstance(d,dict) else d
    def get_shipment(self, sid):
        r = self.session.get(f"{API_BASE}/ocean/shipments/{sid}",timeout=30)
        r.raise_for_status(); return r.json()
    def delete_shipment(self, sid):
        r = self.session.delete(f"{API_BASE}/ocean/shipments/{sid}",timeout=30)
        r.raise_for_status(); return r.json()

def extract_fields(shipment):
    if "shipment" in shipment and isinstance(shipment["shipment"],dict):
        shipment=shipment["shipment"]
    f = {"status":"","vessel":"","pol":"","pod":"","eta":"","etd":"",
         "carrier":"","transit_pct":"","original_eta":"","delay_days":""}
    f["status"]=shipment.get("status","")
    cr=shipment.get("carrier") or {}
    if isinstance(cr,dict): f["carrier"]=cr.get("name",cr.get("scac",""))
    route=shipment.get("route") or {}
    pol=route.get("port_of_loading") or route.get("origin") or {}
    pl=pol.get("location") or {}
    f["pol"]=pl.get("name","")
    f["etd"]=pol.get("date_of_loading",pol.get("date_of_dep",""))
    pod=route.get("port_of_discharge") or route.get("destination") or {}
    dl=pod.get("location") or {}
    f["pod"]=dl.get("name","")
    f["eta"]=pod.get("date_of_discharge",pod.get("date_of_eta",""))
    f["original_eta"]=pod.get("date_of_discharge_initial",pod.get("date_of_eta_initial",""))
    f["transit_pct"]=route.get("transit_percentage","")
    try:
        es=str(f["eta"]).split("T")[0] if f["eta"] else ""
        os_=str(f["original_eta"]).split("T")[0] if f["original_eta"] else ""
        if es and os_:
            ed=datetime.strptime(es,"%Y-%m-%d"); od=datetime.strptime(os_,"%Y-%m-%d")
            diff=(ed-od).days
            if diff>0: f["delay_days"]=f"+{diff} days"
            elif diff<0: f["delay_days"]=f"{diff} days (early)"
            else: f["delay_days"]="On time"
    except: pass
    containers=shipment.get("containers") or []
    if containers and isinstance(containers[0],dict):
        for m in reversed(containers[0].get("movements") or []):
            if isinstance(m,dict) and m.get("vessel"):
                v=m["vessel"]
                if isinstance(v,dict) and v.get("name"): f["vessel"]=v["name"]; break
    for k in ("eta","etd","original_eta"):
        if f[k] and "T" in str(f[k]): f[k]=str(f[k]).split("T")[0]
    return f

TRACKING_COL_MAP = {"Carrier":"carrier","Status":"status","ETA":"eta",
    "Original ETA":"original_eta","Delay":"delay_days",
    "Port of Loading":"pol","Port of Discharge":"pod",
    "Vessel":"vessel","Transit %":"transit_pct","Last Refreshed":"last_refreshed"}

def find_container_column(ws):
    for c in range(1,ws.max_column+1):
        h=str(ws.cell(row=1,column=c).value or "").strip().lower()
        if h in CONTAINER_COL_KEYWORDS: return c
    for c in range(1,ws.max_column+1):
        h=str(ws.cell(row=1,column=c).value or "").strip().lower()
        if "container" in h or "cntr" in h: return c
    return None

def find_or_create_tracking_columns(ws):
    existing={}
    for c in range(1,ws.max_column+1):
        h=str(ws.cell(row=1,column=c).value or "").strip()
        if h: existing[h.lower()]=c
    fm={}; nc=ws.max_column+1
    hf=Font(name="Calibri",bold=True,size=11,color="FFFFFF")
    hfill=PatternFill(start_color="1F4E79",end_color="1F4E79",fill_type="solid")
    ha=Alignment(horizontal="center",vertical="center")
    for hn,fk in TRACKING_COL_MAP.items():
        fc=existing.get(hn.lower())
        if fc: fm[fk]=fc
        else:
            c=ws.cell(row=1,column=nc,value=hn); c.font=hf; c.fill=hfill; c.alignment=ha
            fm[fk]=nc; nc+=1
    return fm

def read_containers_from_excel(path):
    wb=load_workbook(str(path),data_only=True); ws=wb.active
    cc=find_container_column(ws)
    if cc is None: wb.close(); return []
    out=[]
    for r in range(2,ws.max_row+1):
        v=ws.cell(row=r,column=cc).value
        if v:
            cn=str(v).strip().upper()
            if len(cn)>=10: out.append(cn)
    wb.close(); return out

def update_excel_with_tracking(path, data):
    wb=load_workbook(str(path)); ws=wb.active
    cc=find_container_column(ws)
    if cc is None: wb.close(); raise ValueError("No Container column found.")
    fm=find_or_create_tracking_columns(ws)
    sc={"sailing":"D6EAF8","en_route":"D6EAF8","arrived":"D5F5E3",
        "discharged":"ABEBC6","delivered":"82E0AA","booked":"FCF3CF",
        "new":"FCF3CF","untracked":"F2F3F4"}
    count=0; ts=now_est()
    for r in range(2,ws.max_row+1):
        cv=ws.cell(row=r,column=cc).value
        if not cv: continue
        cn=str(cv).strip().upper()
        if cn in data:
            rec=data[cn]
            for fk,col in fm.items():
                val=rec.get(fk,"")
                if fk=="transit_pct" and val!="": val=f"{val}%"
                if fk=="last_refreshed": val=ts
                ws.cell(row=r,column=col,value=val)
            scol=fm.get("status")
            if scol:
                cell=ws.cell(row=r,column=scol)
                sl=str(cell.value or "").lower().replace(" ","_")
                for sk,color in sc.items():
                    if sk in sl: cell.fill=PatternFill(start_color=color,fill_type="solid"); break
            dcol=fm.get("delay_days")
            if dcol:
                dc=ws.cell(row=r,column=dcol); dv=str(dc.value or "")
                if dv.startswith("+"):
                    dc.fill=PatternFill(start_color="FADBD8",fill_type="solid")
                    dc.font=Font(color="C0392B")
                elif "early" in dv:
                    dc.fill=PatternFill(start_color="D5F5E3",fill_type="solid")
                    dc.font=Font(color="27AE60")
                elif "On time" in dv: dc.font=Font(color="27AE60")
            count+=1
    # Append containers in tracker but not yet in Excel
    existing_containers=set()
    for r in range(2,ws.max_row+1):
        cv=ws.cell(row=r,column=cc).value
        if cv: existing_containers.add(str(cv).strip().upper())
    appended=0
    for cn,rec in data.items():
        if cn not in existing_containers and rec.get("status"):
            nr=ws.max_row+1
            ws.cell(row=nr,column=cc,value=cn)
            for fk,col in fm.items():
                val=rec.get(fk,"")
                if fk=="transit_pct" and val!="": val=f"{val}%"
                if fk=="last_refreshed": val=ts
                ws.cell(row=nr,column=col,value=val)
            appended+=1; count+=1
    for fk,col in fm.items():
        ml=max((len(str(ws.cell(row=r,column=col).value or "")) for r in range(1,ws.max_row+1)),default=10)
        ws.column_dimensions[get_column_letter(col)].width=min(ml+4,30)
    wb.save(str(path)); wb.close(); return count

def create_template_excel(path):
    wb=Workbook(); ws=wb.active; ws.title="Container Tracking"
    headers=["Container #","PO / Reference","Notes","Carrier","Status","ETA","Original ETA",
             "Delay","Port of Loading","Port of Discharge","Vessel","Transit %","Last Refreshed"]
    for col,h in enumerate(headers,1):
        ws.cell(row=1,column=col,value=h)
    for ri,(cn,ref,n) in enumerate([("MSKU1234567","PO-2024-001","Sample - replace"),("MSCU7654321","PO-2024-002","")],2):
        ws.cell(row=ri,column=1,value=cn)
        ws.cell(row=ri,column=2,value=ref)
        ws.cell(row=ri,column=3,value=n)
    lc=get_column_letter(len(headers))
    tbl=Table(displayName="ContainerTracking",ref=f"A1:{lc}3")
    tbl.tableStyleInfo=TableStyleInfo(name="TableStyleMedium2",showFirstColumn=False,
        showLastColumn=False,showRowStripes=True,showColumnStripes=False)
    ws.add_table(tbl)
    for i,w in enumerate([18,18,25,16,14,14,14,14,20,20,20,12,22],1):
        ws.column_dimensions[get_column_letter(i)].width=w
    ws.freeze_panes="A2"; wb.save(str(path)); wb.close(); return str(path)


_BaseRoot = ctk.CTk if HAS_CTK else tk.Tk


class ContainerTrackerApp(_BaseRoot):
    def __init__(self):
        if HAS_CTK:
            ctk.set_appearance_mode("light")
        super().__init__()

        self.wm_attributes('-alpha', 0.0)

        self.update_idletasks()

        self.root = self  # alias so the rest of the class can keep using self.root.*

        self.config=load_config()
        if migrate_token_from_config(self.config):
            save_config(self.config)
        self.is_dark=self.config.get("dark_mode",False)
        self.T=DARK if self.is_dark else LIGHT
        self.db=load_json(TRACKING_DB_FILE,{})
        self.client=None; self.themed_widgets=[]
        self.update_banner=None

        if HAS_CTK:
            self.configure(fg_color=self.T["bg"])
        else:
            self.configure(bg=self.T["bg"])
        self.title(APP_NAME)

        # Geometry is deferred to the reveal block below — calling self.geometry() on a
        # CTk root in 'withdrawn' state (CTk's default) is a silent no-op. minsize is fine
        # to set here; it just constrains future resize operations.
        self.minsize(860,650)

        if LOGO_PATH.exists() and LOGO_PATH.suffix.lower() == ".ico":
            def _set_icon():
                try: self.iconbitmap(str(LOGO_PATH))
                except Exception: pass
            self.after(200, _set_icon)
            self.after(600, _set_icon)
            self.after(1200, _set_icon)

        first_run = is_first_run(self.config)
        if first_run:
            dlg = SetupDialog(self, mode="first_run")
            self.wait_window(dlg.win)
            if not dlg.result:
                self.destroy()
                sys.exit(0)
            self.config["company_name"] = dlg.result["company_name"]
            self.config["contact_email"] = dlg.result["contact_email"]
            save_config(self.config)
            set_api_token(dlg.result["api_key"])
            self.api_key_cached = dlg.result["api_key"]
        else:
            self.api_key_cached = get_api_token()

        self._apply_window_title()
        self.build_ui(); self.load_table_data(); self.update_stats()

        # Reveal. Order matters: deiconify flips WM state 'withdrawn' → 'normal', so
        # geometry/alpha calls that follow actually take effect against a mapped window.
        self.deiconify()

        self.geometry("1020x800")

        self.wm_attributes('-alpha', 1.0)

        self.lift()
        self.update_idletasks()

        check_for_update_async(lambda tag, url: self.after(0, lambda: self.show_update_banner(tag, url)))

    def _apply_window_title(self):
        company = self.config.get("company_name", "").strip()
        self.root.title(f"{APP_NAME} \u2014 {company}" if company else APP_NAME)

    def show_update_banner(self, new_version: str, release_url: str):
        if self.update_banner is not None:
            return
        T=self.T
        if HAS_CTK:
            bar=ctk.CTkFrame(self.root, fg_color=T["sail_bg"], corner_radius=0, height=34)
            bar.pack(fill="x", side="top", before=self.root.winfo_children()[0])
            msg=ctk.CTkLabel(bar, text=f"Version {new_version} available \u2014 click to download",
                             text_color=T["sail_fg"], font=FONTS["subheading"], cursor="hand2",
                             fg_color="transparent")
            msg.pack(side="left", padx=12, pady=4)
            close=ctk.CTkButton(bar, text="\u00d7", width=28, height=24, corner_radius=RADIUS["btn"],
                                fg_color="transparent", hover_color=T["border"],
                                text_color=T["sail_fg"], font=FONTS["body_bold"],
                                command=self._dismiss_update_banner)
            close.pack(side="right", padx=6, pady=4)
        else:
            bar=tk.Frame(self.root, bg=T["sail_bg"])
            bar.pack(fill="x", side="top", before=self.root.winfo_children()[0])
            msg=tk.Label(bar, text=f"Version {new_version} available \u2014 click to download",
                         bg=T["sail_bg"], fg=T["sail_fg"], font=FONTS["body_bold"], cursor="hand2")
            msg.pack(side="left", padx=12, pady=4)
            close=tk.Button(bar, text="\u00d7", bg=T["sail_bg"], fg=T["sail_fg"],
                            relief="flat", command=self._dismiss_update_banner)
            close.pack(side="right", padx=6, pady=2)
        msg.bind("<Button-1>", lambda _e: webbrowser.open(release_url))
        self.update_banner=bar

    def _dismiss_update_banner(self):
        if self.update_banner is not None:
            try: self.update_banner.destroy()
            except Exception: pass
            self.update_banner=None

    def _reg(self,w,role):
        self.themed_widgets.append((w,role)); return w

    def apply_theme(self):
        T=self.T
        for w,role in self.themed_widgets:
            try:
                if not HAS_CTK: continue
                m={"bg":{"fg_color":T["bg"]},"card":{"fg_color":T["card"],"border_color":T["border"]},
                   "stat_card":{"fg_color":T["stat_bg"],"border_color":T["border"]},
                   "input":{"fg_color":T["input"],"border_color":T["border"],"text_color":T["primary"]},
                   "label_primary":{"text_color":T["primary"]},"label_secondary":{"text_color":T["secondary"]},
                   "label_muted":{"text_color":T["muted"]},"label_hint":{"text_color":T["hint"]},
                   "label_green":{"text_color":T["green"]},
                   "btn":{"fg_color":T["btn_bg"],"text_color":T["btn_text"],"hover_color":T["border"]},
                   "btn_outline":{"fg_color":"transparent","border_color":T["green"],"text_color":T["green"],"hover_color":T["green_light"]},
                   "btn_green":{"fg_color":T["green"],"hover_color":T["green_dark"]},
                   "btn_red":{"fg_color":"#D32F2F","hover_color":"#B71C1C"},
                   "log":{"fg_color":T["log_bg"],"text_color":T["secondary"],"border_color":T["border"]},
                   "combo":{"fg_color":T["input"],"border_color":T["border"],"button_color":T["green"],
                            "button_hover_color":T["green_dark"],
                            "dropdown_fg_color":T["dropdown_bg"],"text_color":T["primary"]},
                   "stat_value":{"text_color":T["primary"]},"stat_label":{"text_color":T["muted"]}}
                if role in m: w.configure(**m[role])
            except: pass
        if HAS_CTK: self.root.configure(fg_color=T["bg"])
        s=ttk_mod.Style()
        s.configure("Custom.Treeview",background=T["bg"],fieldbackground=T["bg"],
                    foreground=T["primary"],rowheight=40,font=FONTS["body"],borderwidth=0)
        s.configure("Custom.Treeview.Heading",background=T["thead"],foreground=T["secondary"],
                    font=FONTS["hint"],borderwidth=0,relief="flat")
        s.map("Custom.Treeview",background=[("selected",T["green_light"])],
              foreground=[("selected",T["primary"])])

    def toggle_theme(self):
        self.is_dark=not self.is_dark; self.T=DARK if self.is_dark else LIGHT
        self.config["dark_mode"]=self.is_dark; save_config(self.config)
        self.apply_theme()
        if HAS_CTK:
            if self.is_dark: self.theme_switch.select()
            else: self.theme_switch.deselect()

    def _f(self,p,role="bg"):
        w=ctk.CTkFrame(p,fg_color="transparent") if HAS_CTK else tk.Frame(p,bg=self.T["bg"])
        return self._reg(w,role)
    def _card(self,p):
        w=ctk.CTkFrame(p,fg_color=self.T["card"],corner_radius=RADIUS["card"],border_width=1,border_color=self.T["border"]) if HAS_CTK else tk.Frame(p,bg=self.T["card"],bd=1,relief="solid")
        return self._reg(w,"card")
    def _l(self,p,text,role="label_primary",size=13,bold=False):
        wt="bold" if bold else "normal"
        cm={"label_primary":"primary","label_secondary":"secondary","label_muted":"muted","label_hint":"hint","label_green":"green"}
        c=self.T[cm.get(role,"primary")]
        w=ctk.CTkLabel(p,text=text,text_color=c,font=(_FONT_FAMILY, size, wt),fg_color="transparent") if HAS_CTK else tk.Label(p,text=text,fg=c,bg=self.T["bg"],font=(_FONT_FAMILY, size, wt))
        return self._reg(w,role)
    def _btn(self,p,text,cmd,role="btn"):
        if HAS_CTK:
            kw={"text":text,"command":cmd,"corner_radius":RADIUS["btn"]}
            if role=="btn_green":
                # Primary CTA — solid navy, pill shape
                kw.update(fg_color=self.T["green"],hover_color=self.T["green_dark"],text_color="white",font=FONTS["subheading"],height=38,corner_radius=RADIUS["cta_pill"])
            elif role=="btn_outline":
                # Primary-weight ghost — pill to match primary
                kw.update(fg_color="transparent",hover_color=self.T["green_light"],text_color=self.T["green"],border_width=1,border_color=self.T["green"],font=FONTS["body"],height=34,corner_radius=RADIUS["cta_pill"])
            elif role=="btn_red":
                kw.update(fg_color="#B05A4D",hover_color="#94483D",text_color="white",font=FONTS["caption"],height=30,width=100)
            else:
                # Ghost / tertiary button — transparent with hairline border
                kw.update(fg_color="transparent",hover_color=self.T["green_light"],text_color=self.T["btn_text"],border_width=1,border_color=self.T["border"],font=FONTS["body"],height=34)
            w=ctk.CTkButton(p,**kw)
        else:
            bg=self.T["green"] if role=="btn_green" else ("#D32F2F" if role=="btn_red" else self.T["btn_bg"])
            fg="white" if role in ("btn_green","btn_red") else self.T["btn_text"]
            w=tk.Button(p,text=text,command=cmd,bg=bg,fg=fg,font=FONTS["caption"],relief="flat",padx=12,pady=4)
        return self._reg(w,role)
    def _e(self,p,**kw):
        w=ctk.CTkEntry(p,fg_color=self.T["input"],border_color=self.T["border"],text_color=self.T["primary"],corner_radius=RADIUS["input"],**kw) if HAS_CTK else tk.Entry(p,bg=self.T["input"],fg=self.T["primary"],relief="solid",bd=1)
        return self._reg(w,"input")

    def build_ui(self):
        T=self.T
        # Header
        hdr=self._f(self.root); hdr.pack(fill="x",padx=SPACING["xl"],pady=(SPACING["lg"], SPACING["sm"]))
        left=self._f(hdr); left.pack(side="left")
        tf=self._f(left); tf.pack(side="left")
        self._l(tf,APP_NAME,size=18,bold=True).pack(anchor="w")
        company=self.config.get("company_name","").strip()
        self.company_label=self._l(tf, company, role="label_muted", size=11)
        self.company_label.pack(anchor="w")
        rt=self._f(hdr); rt.pack(side="right")
        self.status_label=self._l(rt,"",role="label_green",size=11)
        self.status_label.pack(side="left",padx=(0,14))
        if HAS_CTK:
            self.theme_switch=ctk.CTkSwitch(rt,text="",width=44,command=self.toggle_theme,
                fg_color=T["border"],progress_color=T["green"],button_color="#FFF",button_hover_color="#EEE")
            if self.is_dark: self.theme_switch.select()
            self.theme_switch.pack(side="left")
            self.settings_btn=ctk.CTkButton(rt, text="\u2699", width=32, height=32, corner_radius=RADIUS["btn"],
                fg_color="transparent", hover_color=T["border"], text_color=T["secondary"],
                font=(_FONT_FAMILY, 18), command=self.open_settings)
            self.settings_btn.pack(side="left", padx=(10, 0))
        else:
            self.settings_btn=tk.Button(rt, text="\u2699", command=self.open_settings,
                font=FONTS["body_bold"], relief="flat", bg=T["bg"], fg=T["secondary"])
            self.settings_btn.pack(side="left", padx=(10, 0))

        # Excel card
        ec=self._card(self.root); ec.pack(fill="x",padx=SPACING["xl"],pady=(SPACING["sm"], SPACING["sm"]))
        ei=self._f(ec,role="card"); ei.pack(fill="x",padx=SPACING["lg"], pady=SPACING["lg"])
        if HAS_CTK: ei.configure(fg_color=T["card"])
        self._l(ei,"Linked spreadsheet",role="label_muted",size=11).pack(anchor="w",pady=(0,4))
        er=self._f(ei,role="card"); er.pack(fill="x")
        if HAS_CTK: er.configure(fg_color=T["card"])
        self.excel_display=self._l(er,self.config.get("excel_path","") or "No file linked",role="label_green",size=11)
        self.excel_display.pack(side="left",padx=(0,12))
        self._btn(er,"Browse...",self.browse_excel).pack(side="left",padx=3)
        self._btn(er,"Create Template",self.create_template).pack(side="left",padx=3)
        self._btn(er,"Open in Excel",self.open_excel).pack(side="left",padx=3)

        # Summary cards
        sf=self._f(self.root); sf.pack(fill="x",padx=SPACING["xl"],pady=(SPACING["sm"], SPACING["sm"]))
        self.stat_frames={}
        for key,label in [("total","Tracked"),("sailing","Sailing"),("arrived","Arrived"),("delayed","Delayed")]:
            card=ctk.CTkFrame(sf,fg_color=T["stat_bg"],corner_radius=RADIUS["card"],border_width=1,border_color=T["border"],height=72) if HAS_CTK else tk.Frame(sf,bg=T["stat_bg"],bd=1,relief="solid")
            self._reg(card,"stat_card")
            card.pack(side="left",fill="x",expand=True,padx=(0 if key=="total" else 4,0))
            sl=self._l(card,label,role="stat_label",size=10); sl.pack(anchor="w",padx=12,pady=(8,0))
            color=T["primary"]
            if key=="sailing": color=T["blue"]
            elif key=="arrived": color=T["green"]
            elif key=="delayed": color="#D32F2F"
            sv=ctk.CTkLabel(card,text="0",text_color=color,font=FONTS["display"],fg_color="transparent") if HAS_CTK else tk.Label(card,text="0",fg=color,bg=T["stat_bg"],font=FONTS["display"])
            sv.pack(anchor="w",padx=12,pady=(0, SPACING["md"]))
            self.stat_frames[key]=sv

        # Actions
        af=self._f(self.root); af.pack(fill="x",padx=SPACING["xl"],pady=(SPACING["sm"], SPACING["sm"]))
        self.refresh_btn=self._btn(af,"  Refresh All ETAs & Update Excel  ",self.refresh_data,role="btn_green")
        self.refresh_btn.pack(side="left",padx=(0,8))
        self._btn(af,"Remove Selected",self.remove_container,role="btn_red").pack(side="left",padx=(0,16))
        self._l(af,"Add:",role="label_muted",size=11).pack(side="left",padx=(12,4))
        self.container_var=StringVar()
        self._e(af,textvariable=self.container_var,width=130).pack(side="left",padx=(0,4))
        self.carrier_var=StringVar(value="MAERSK LINE")
        if HAS_CTK:
            cc=ctk.CTkComboBox(af,values=CARRIER_NAMES,variable=self.carrier_var,width=130,
                fg_color=T["input"],border_color=T["border"],
                button_color=T["green"],button_hover_color=T["green_dark"],
                dropdown_fg_color=T["dropdown_bg"],text_color=T["primary"],corner_radius=RADIUS["input"])
            self._reg(cc,"combo")
        else: cc=ttk.Combobox(af,textvariable=self.carrier_var,values=CARRIER_NAMES,width=14,state="readonly")
        cc.pack(side="left",padx=(0,4))
        self._btn(af,"Add & Track",self.add_container,role="btn_outline").pack(side="left")

        # Table
        tbf=self._f(self.root); tbf.pack(fill="both",expand=True,padx=SPACING["xl"],pady=(SPACING["sm"],SPACING["sm"]))
        s=ttk_mod.Style(); s.theme_use("clam")
        s.configure("Custom.Treeview",background=T["bg"],fieldbackground=T["bg"],
                    foreground=T["primary"],rowheight=40,font=FONTS["body"],borderwidth=0)
        s.configure("Custom.Treeview.Heading",background=T["thead"],foreground=T["secondary"],
                    font=FONTS["hint"],borderwidth=0,relief="flat")
        s.map("Custom.Treeview",background=[("selected",T["green_light"])],foreground=[("selected",T["primary"])])
        cols=("container","carrier","status","orig_eta","eta","delay","route","vessel","transit")
        self.tree=ttk_mod.Treeview(tbf,columns=cols,show="headings",height=8,style="Custom.Treeview")
        for cid,hd,w in [("container","Container #",115),("carrier","Carrier",90),("status","Status",90),
            ("orig_eta","Original ETA",90),("eta","Current ETA",90),("delay","Delay",80),
            ("route","Route",180),("vessel","Vessel",120),("transit","Transit",60)]:
            self.tree.heading(cid,text=hd); self.tree.column(cid,width=w,minwidth=45)
        # Semantic row tags: status column text color conveys state without a filled cell.
        self.tree.tag_configure("status_sailing",  foreground=T["status_sailing"])
        self.tree.tag_configure("status_arrived",  foreground=T["status_arrived"])
        self.tree.tag_configure("status_delayed",  foreground=T["status_delayed"])
        self.tree.tag_configure("status_neutral",  foreground=T["primary"])
        if HAS_CTK:
            sb=ctk.CTkScrollbar(tbf,command=self.tree.yview,fg_color="transparent",
                button_color=T["border"],button_hover_color=T["muted"])
        else:
            sb=ttk_mod.Scrollbar(tbf,orient="vertical",command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left",fill="both",expand=True); sb.pack(side="right",fill="y")

        # Log
        lf=self._f(self.root); lf.pack(fill="x",padx=SPACING["xl"],pady=(SPACING["xs"], SPACING["xs"]))
        self._l(lf,"Activity log",role="label_hint",size=10).pack(anchor="w",pady=(0,2))
        if HAS_CTK:
            self.log_text=ctk.CTkTextbox(self.root,height=80,fg_color=T["log_bg"],text_color=T["secondary"],
                font=FONTS["mono"],corner_radius=RADIUS["input"],border_width=1,border_color=T["border"],
                scrollbar_button_color=T["border"],scrollbar_button_hover_color=T["muted"])
            self._reg(self.log_text,"log")
        else:
            self.log_text=tk.Text(self.root,height=4,font=FONTS["mono"],bg=T["log_bg"],fg=T["secondary"],relief="solid",bd=1)
        self.log_text.pack(fill="x",padx=SPACING["xl"],pady=(0, SPACING["md"]))

        # Footer
        ff=self._f(self.root); ff.pack(fill="x",padx=SPACING["xl"],pady=(0, SPACING["md"]))
        self._l(ff,"Powered by ShipsGo API",role="label_hint",size=9).pack(side="left")
        self._l(ff,"Refreshes are free & unlimited \u2022 All times EST",role="label_hint",size=9).pack(side="right")

    def log(self,msg):
        self.log_text.insert(END,f"[{now_est_short()}] {msg}\n"); self.log_text.see(END); logger.info(msg)
    def set_status(self,msg):
        if HAS_CTK: self.status_label.configure(text=msg)
        else: self.status_label.config(text=msg)
        self.root.update_idletasks()
    def _dis(self):
        if HAS_CTK: self.refresh_btn.configure(state="disabled")
        else: self.refresh_btn.config(state="disabled")
    def _en(self):
        if HAS_CTK: self.refresh_btn.configure(state="normal")
        else: self.refresh_btn.config(state="normal")

    def update_stats(self):
        total=len(self.db); sailing=0; arrived=0; delayed=0
        for _,r in self.db.items():
            st=str(r.get("status","")).upper()
            dd=str(r.get("delay_days",""))
            if st=="SAILING": sailing+=1
            elif st in ("ARRIVED","DISCHARGED","DELIVERED","GATE_OUT"): arrived+=1
            if dd.startswith("+") and st=="SAILING": delayed+=1
        for k,v in [("total",total),("sailing",sailing),("arrived",arrived),("delayed",delayed)]:
            if HAS_CTK: self.stat_frames[k].configure(text=str(v))
            else: self.stat_frames[k].config(text=str(v))

    def load_table_data(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for key,rec in sorted(self.db.items()):
            tp=rec.get("transit_pct","")
            if tp!="": tp=f"{tp}%"
            pol=rec.get("pol",""); pod=rec.get("pod","")
            route=f"{pol} \u2192 {pod}" if pol and pod else pol or pod or ""
            status_str=str(rec.get("status","")).upper()
            delay_str=str(rec.get("delay_days",""))
            if delay_str.startswith("+") and status_str=="SAILING":
                tag="status_delayed"
            elif status_str in ("ARRIVED","DISCHARGED","DELIVERED","GATE_OUT"):
                tag="status_arrived"
            elif status_str=="SAILING":
                tag="status_sailing"
            else:
                tag="status_neutral"
            self.tree.insert("",END,iid=key,values=(
                rec.get("container_number") or key, rec.get("carrier",rec.get("shipping_line","")),
                rec.get("status",""), rec.get("original_eta",""), rec.get("eta",""),
                rec.get("delay_days",""), route, rec.get("vessel",""), tp),
                tags=(tag,))
        self.update_stats()

    def open_settings(self):
        extra = {"version": __version__, "data_dir": DATA_DIR, "github_repo": GITHUB_REPO}
        dlg = SetupDialog(self.root,
                          initial_company=self.config.get("company_name",""),
                          initial_api_key=self.api_key_cached or get_api_token(),
                          initial_email=self.config.get("contact_email",""),
                          mode="settings",
                          extra_info=extra)
        self.root.wait_window(dlg.win)
        if not dlg.result:
            return
        self.config["company_name"] = dlg.result["company_name"]
        self.config["contact_email"] = dlg.result["contact_email"]
        save_config(self.config)
        if dlg.result["api_key"] != self.api_key_cached:
            set_api_token(dlg.result["api_key"])
            self.api_key_cached = dlg.result["api_key"]
            self.client = None  # force rebuild with new token
        self._apply_window_title()
        company = self.config.get("company_name", "").strip()
        try:
            if HAS_CTK: self.company_label.configure(text=company)
            else: self.company_label.config(text=company)
        except Exception: pass
        self.log("Settings updated.")

    def get_client(self):
        key=(self.api_key_cached or get_api_token()).strip()
        if not key:
            messagebox.showwarning("Missing API Key","Open Settings (\u2699) and enter your ShipsGo API key.\n\n1. Go to shipsgo.com\n2. Dashboard > Integrations > ShipsGo API\n3. Copy your token"); return None
        if self.client is None: self.client=ShipsGoClient(key)
        return self.client

    def browse_excel(self):
        p=filedialog.askopenfilename(title="Select spreadsheet",filetypes=[("Excel","*.xlsx"),("All","*.*")])
        if p:
            self.config["excel_path"]=p; save_config(self.config)
            if HAS_CTK: self.excel_display.configure(text=p)
            else: self.excel_display.config(text=p)
            self.log(f"Linked: {Path(p).name}")
    def create_template(self):
        p=filedialog.asksaveasfilename(title="Save template",defaultextension=".xlsx",initialfile="Container_Tracking.xlsx",filetypes=[("Excel","*.xlsx")])
        if p:
            try:
                create_template_excel(p); self.config["excel_path"]=p; save_config(self.config)
                if HAS_CTK: self.excel_display.configure(text=p)
                else: self.excel_display.config(text=p)
                self.log(f"Template created: {Path(p).name}")
                messagebox.showinfo("Template Created","Template saved as an Excel Table.\n\nReplace samples with real containers, then Refresh.\nNew rows auto-inherit table formatting.")
                os.startfile(p)
            except Exception as e: messagebox.showerror("Error",str(e))
    def open_excel(self):
        p=self.config.get("excel_path","")
        if p and Path(p).exists(): os.startfile(p)
        else: messagebox.showinfo("No File","No Excel file linked.\n\nClick 'Browse...' or 'Create Template'.")

    def remove_container(self):
        sel=self.tree.selection()
        if not sel: messagebox.showinfo("No Selection","Select a container in the table first."); return
        cn=sel[0]
        rec=self.db.get(cn,{})
        status=str(rec.get("status","")).upper()
        is_done=status in ("DISCHARGED","DELIVERED","GATE_OUT","ARRIVED")

        if is_done:
            if not messagebox.askyesno("Remove Completed Shipment",
                f"Remove {cn}?\n\nStatus: {status}\n\n"
                "This shipment is complete. It will be permanently\n"
                "dismissed and won't reappear on future refreshes.\n\n"
                "It will remain in your Excel file."): return
            # Add to permanent dismissed list
            if "dismissed" not in self.config: self.config["dismissed"]=[]
            if cn not in self.config["dismissed"]:
                self.config["dismissed"].append(cn)
            save_config(self.config)
            if cn in self.db: del self.db[cn]
            save_json(TRACKING_DB_FILE,self.db); self.load_table_data()
            self.log(f"Dismissed {cn} (completed shipment, won't reappear)")
        else:
            if not messagebox.askyesno("Remove Active Shipment",
                f"Remove {cn} from the app?\n\nStatus: {status}\n\n"
                "This shipment is still active on ShipsGo.\n"
                "It WILL reappear on the next refresh.\n\n"
                "To permanently stop tracking, wait until\n"
                "the shipment is discharged, then remove it."): return
            if cn in self.db: del self.db[cn]
            save_json(TRACKING_DB_FILE,self.db); self.load_table_data()
            self.log(f"Removed {cn} from display (will reappear on next refresh)")

    def add_container(self):
        client=self.get_client()
        if not client: return
        cn=self.container_var.get().strip().upper(); cl=self.carrier_var.get().strip()
        if not cn: messagebox.showwarning("Missing","Enter a container number."); return
        if len(cn)!=11:
            if not messagebox.askyesno("Check Container #",f"Usually 11 chars (4 letters + 7 digits).\nYours: {cn} ({len(cn)} chars)\n\nContinue?"): return
        scac=resolve_scac(cl)
        if not messagebox.askyesno("Confirm Registration",
            f"Register {cn} with ShipsGo?\n\n"
            f"This will use 1 tracking credit (~$2 USD).\n"
            f"Credits are one-time per shipment \u2014 all future\n"
            f"refreshes are free and unlimited.\n\n"
            f"If the container is already tracked, no credit\n"
            f"will be charged."): return
        def _go():
            # Un-dismiss if previously removed
            dismissed=self.config.get("dismissed",[])
            if cn in dismissed:
                dismissed.remove(cn); self.config["dismissed"]=dismissed; save_config(self.config)
                self.log(f"Re-activated {cn} (was previously dismissed)")
            self.set_status("Registering..."); self.log(f"Adding {cn} ({cl})...")
            try:
                r=client.create_shipment(container_number=cn,carrier_scac=scac)
                if r.get("error")=="NOT_ENOUGH_CREDITS":
                    self.log(f"Not enough credits for {cn}")
                    self.root.after(0,lambda:messagebox.showerror("No Credits",
                        "Not enough ShipsGo credits.\n\n"
                        "To purchase more credits:\n"
                        "1. Go to shipsgo.com\n"
                        "2. Log into your dashboard\n"
                        "3. Click 'Buy Now' (starts at $20 for 10 credits)\n\n"
                        "Then come back and try again."))
                elif r.get("already_exists"):
                    self.log(f"{cn} already tracked on ShipsGo")
                    # Still add to local DB so it shows in app
                    if cn not in self.db:
                        self.db[cn]={"container_number":cn,"carrier":cl,"last_refreshed":None}
                        save_json(TRACKING_DB_FILE,self.db)
                else:
                    self.log(f"{cn} registered (1 credit used)")
                    # Add to local DB immediately so it shows in app
                    self.db[cn]={"container_number":cn,"carrier":cl,
                                 "shipment_id":r.get("id",""),"last_refreshed":None}
                    save_json(TRACKING_DB_FILE,self.db)
                    self.root.after(0,lambda:messagebox.showinfo("Added",
                        f"{cn} registered successfully.\n\n"
                        f"Full tracking data may take a few hours to appear.\n"
                        f"The container will be added to your Excel file on\n"
                        f"the next refresh."))
                self._do_refresh()
            except requests.ConnectionError:
                self.log("Connection error"); self.root.after(0,lambda:messagebox.showerror("No Connection","Check your internet connection."))
            except Exception as e:
                self.log(f"Error: {e}"); self.root.after(0,lambda:messagebox.showerror("Error",str(e)))
            finally: self.set_status(""); self.root.after(0,self._en)
        self._dis(); threading.Thread(target=_go,daemon=True).start()

    def refresh_data(self):
        if not self.get_client(): return
        def _t(): self._do_refresh(); self.set_status(""); self.root.after(0,self._en)
        self._dis(); threading.Thread(target=_t,daemon=True).start()

    def _do_refresh(self):
        client=self.get_client()
        if not client: return
        self.set_status("Fetching..."); self.log("Refreshing...")
        try:
            ships=client.list_shipments(); ac=len(ships)
            self.log(f"Found {ac} shipments on ShipsGo")
            if ac==0:
                self.log("WARNING: No shipments on your account")
                self.root.after(0,lambda:messagebox.showwarning("No Shipments","No shipments on ShipsGo.\n\nUse 'Add & Track' to register containers (1 credit each)."))
                return
            smap={}
            for s in ships:
                if not isinstance(s,dict): continue
                sid=s.get("id")
                if sid: smap[str(sid)]=s
                cn=(s.get("container_number") or "").upper()
                if cn: smap[cn]=s
            ep=self.config.get("excel_path","")
            if ep and Path(ep).exists():
                try:
                    ec=read_containers_from_excel(ep); self.log(f"Read {len(ec)} containers from Excel")
                    if len(ec)==0: self.log("WARNING: No containers found in spreadsheet")
                    dismissed=self.config.get("dismissed",[])
                    for c in ec:
                        if c not in self.db and c not in dismissed:
                            self.db[c]={"container_number":c,"last_refreshed":None}
                except PermissionError:
                    self.log("ERROR: Excel open - close it first")
                    self.root.after(0,lambda:messagebox.showerror("File In Use","Close Excel first, then Refresh.")); return
                except Exception as e: self.log(f"Excel read error: {e}")
            if not self.db and smap:
                dismissed=self.config.get("dismissed",[])
                for s in ships:
                    if not isinstance(s,dict): continue
                    cn=(s.get("container_number") or "").upper()
                    if not cn or cn in dismissed: continue
                    cr=s.get("carrier") or {}
                    self.db[cn]={"container_number":cn,"shipping_line":cr.get("name","") if isinstance(cr,dict) else "","shipment_id":s.get("id",""),"last_refreshed":None}
            matched=0; unmatched=0; delayed_sailing=0; unmatched_list=[]
            for key,rec in self.db.items():
                sid=str(rec.get("shipment_id","")); cn=rec.get("container_number","").upper()
                sh=smap.get(sid) or smap.get(cn)
                if sh:
                    fid=sh.get("id")
                    if fid:
                        try: self.set_status(f"Fetching {cn}..."); sh=client.get_shipment(fid); rec["shipment_id"]=fid
                        except: pass
                    fe=extract_fields(sh); rec.update(fe); rec["last_refreshed"]=now_est()
                    dd=fe.get("delay_days",""); st=fe.get("status","").upper()
                    delay_info=f" | DELAYED {dd}" if dd.startswith("+") else ""
                    if dd.startswith("+") and st=="SAILING": delayed_sailing+=1
                    self.log(f"  {cn}: {fe['status']} | ETA: {fe['eta']} | {fe['pol']} -> {fe['pod']}{delay_info}")
                    matched+=1
                else:
                    rec["last_refreshed"]=now_est(); self.log(f"  {cn}: not on ShipsGo yet")
                    unmatched+=1; unmatched_list.append(cn)
            save_json(TRACKING_DB_FILE,self.db); self.root.after(0,self.load_table_data)
            eu=0
            if ep and Path(ep).exists():
                try:
                    self.set_status("Updating Excel..."); eu=update_excel_with_tracking(ep,self.db)
                    self.log(f"Updated {eu} rows in Excel")
                except PermissionError:
                    self.log("Excel open - close it first")
                    self.root.after(0,lambda:messagebox.showwarning("File In Use","Close Excel, then Refresh."))
                except Exception as e: self.log(f"Excel error: {e}")
            self.log(f"--- DONE: {matched} matched, {unmatched} unmatched, {delayed_sailing} actively delayed, {eu} Excel rows updated ---")
            self.set_status(f"Refreshed {matched} containers \u2014 {now_est_short()} EST")

            # Show unmatched containers popup with option to register
            if unmatched_list:
                ul=list(unmatched_list)  # capture for lambda
                self.root.after(0, lambda: self._prompt_register_unmatched(ul))
            elif delayed_sailing>0:
                self.root.after(0,lambda:messagebox.showinfo("Delays Detected",f"{delayed_sailing} container(s) currently sailing are delayed.\n\nCheck the Delay column for details."))
        except requests.ConnectionError:
            self.log("Connection error"); self.root.after(0,lambda:messagebox.showerror("No Connection","Check your internet."))
        except requests.HTTPError as e:
            if "401" in str(e):
                self.log("Auth failed"); self.root.after(0,lambda:messagebox.showerror("Invalid API Key","API key rejected.\n\nRe-copy from shipsgo.com > Dashboard > Integrations."))
            else: self.log(f"API error: {e}"); self.root.after(0,lambda:messagebox.showerror("Error",str(e)))
        except Exception as e:
            self.log(f"Failed: {e}"); self.root.after(0,lambda:messagebox.showerror("Error",str(e)))

    def _prompt_register_unmatched(self, containers):
        """Show popup listing unmatched containers with option to register them."""
        container_list = "\n".join(f"  \u2022 {c}" for c in containers[:15])
        if len(containers) > 15:
            container_list += f"\n  ... and {len(containers)-15} more"

        result = messagebox.askyesno(
            f"{len(containers)} New Container(s) Found",
            f"The following containers are in your spreadsheet but not yet "
            f"tracked on ShipsGo:\n\n{container_list}\n\n"
            f"Would you like to register them now?\n\n"
            f"Cost: 1 credit per container (~$2 USD each)\n"
            f"Credits are one-time per shipment \u2014 all future\n"
            f"refreshes are free and unlimited.\n\n"
            f"Total: {len(containers)} credit(s) will be used.")

        if result:
            self._dis()
            threading.Thread(target=self._register_unmatched, args=(containers,), daemon=True).start()

    def _register_unmatched(self, containers):
        """Register unmatched containers with ShipsGo in background."""
        client = self.get_client()
        if not client:
            self._en(); return

        registered = 0; failed = 0; out_of_credits = False
        self.log(f"Registering {len(containers)} new containers...")

        for cn in containers:
            self.set_status(f"Registering {cn}...")
            try:
                r = client.create_shipment(container_number=cn)
                if r.get("error") == "NOT_ENOUGH_CREDITS":
                    out_of_credits = True
                    self.log(f"  {cn}: out of credits")
                    remaining = len(containers) - registered - failed
                    self.root.after(0, lambda rem=remaining: messagebox.showwarning(
                        "Out of Credits",
                        f"You ran out of ShipsGo credits.\n\n"
                        f"Registered: {registered}\n"
                        f"Remaining: {rem}\n\n"
                        f"To purchase more credits:\n"
                        f"1. Go to shipsgo.com\n"
                        f"2. Log into your dashboard\n"
                        f"3. Click 'Buy Now' (starts at $20 for 10 credits)\n\n"
                        f"Then come back and click Refresh to register\n"
                        f"the remaining containers."))
                    break
                elif r.get("already_exists"):
                    self.log(f"  {cn}: already on ShipsGo")
                    registered += 1
                else:
                    self.log(f"  {cn}: registered (1 credit)")
                    registered += 1
            except Exception as e:
                self.log(f"  {cn}: error - {e}")
                failed += 1

        if not out_of_credits:
            self.log(f"Registration complete: {registered} registered, {failed} failed")
            if registered > 0:
                self.root.after(0, lambda: messagebox.showinfo(
                    "Registration Complete",
                    f"{registered} container(s) registered successfully.\n\n"
                    f"Full tracking data may take a few hours to appear.\n"
                    f"Click Refresh periodically to check."))

        # Refresh to pick up newly registered containers
        self.log("Refreshing after registration...")
        self._do_refresh()
        self.root.after(0, self._en)

    def run(self): self.root.mainloop()

if __name__=="__main__": ContainerTrackerApp().run()
