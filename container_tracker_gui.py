#!/usr/bin/env python3
"""
Container ETA Tracker — Ken Gabbay Coffee
"""

import json, os, sys, threading, logging, base64, io
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

LOGO_B64 = "/9j/4AAQSkZJRgABAQAASABIAAD/4gHYSUNDX1BST0ZJTEUAAQEAAAHIbGNtcwIQAABtbnRyUkdCIFhZWiAH4gADABQACQAOAB1hY3NwTVNGVAAAAABzYXdzY3RybAAAAAAAAAAAAAAAAAAA9tYAAQAAAADTLWhhbmSdkQA9QICwPUB0LIGepSKOAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAAF9jcHJ0AAABDAAAAAx3dHB0AAABGAAAABRyWFlaAAABLAAAABRnWFlaAAABQAAAABRiWFlaAAABVAAAABRyVFJDAAABaAAAAGBnVFJDAAABaAAAAGBiVFJDAAABaAAAAGBkZXNjAAAAAAAAAAV1UkdCAAAAAAAAAAAAAAAAdGV4dAAAAABDQzAAWFlaIAAAAAAAAPNUAAEAAAABFslYWVogAAAAAAAAb6AAADjyAAADj1hZWiAAAAAAAABilgAAt4kAABjaWFlaIAAAAAAAACSgAAAPhQAAtsRjdXJ2AAAAAAAAACoAAAB8APgBnAJ1A4MEyQZOCBIKGAxiDvQRzxT2GGocLiBDJKwpai5+M+s5sz/WRldNNlR2XBdkHWyGdVZ+jYgskjacq6eMstu+mcrH12Xkd/H5////2wBDAAcHBwcHBwwHBwwRDAwMERcRERERFx4XFxcXFx4kHh4eHh4eJCQkJCQkJCQrKysrKysyMjIyMjg4ODg4ODg4ODj/2wBDAQkJCQ4NDhkNDRk7KCEoOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozv/wAARCAH0AfQDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD6RooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKqS3tnbcXE8cf++wH8zQBborFbxF4fj4fUbUfWZB/WmDxN4cJwNTtP8Av+n+NAG7RWXHrOjzcQ3sD/7sqn+RrQR0kXchDA9wcigCSiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAK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G5it165ldV/maAPMvAvgDV/DOqzavqF4krzoVdVBJbJySWOOcgGvXa801P4r+DtOBEVw924/hgQn/wAebC/ka4qT4o+K9fc2/hHSG5O3zWDSke/ACr+JIoA96lkjhjMsrBFUZLMcAD3NeaeIPiv4Z0cNFZOdQnHAWH7gPvJ0x9M1x8fw78ceKHE3jLUzHFnPkht5H0RcRr9RmvSNA+Hvhfw8VltLbzp16TTne+fUdlP0AoA8uP8Awsr4i/KR/Zemv1+8isv/AKG/6L9K9G8L/Dbw94aKXOz7Xdrz50oBwfVF6L9eT716JRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABWPqeh6Pq67NUtIrjjAMiAsPoeo/CtiigDyfUfg94RvMtarNaE9BE+Vz9HDfzFc23wh1zTSX8P648R6gEPFj/gSMf5V75RQB4F/Yfxn0zi11BLoD/por5/7+qKX+1/jVZ8TWKTY77Yzn/vhq98ooA8E/4TX4tR8PoSN7iCU/yek/4Tr4qnhdAXPvbzf/F175RQB4H/AMJT8YLniLSEj/7ZMP8A0J6P+L4XxxhbVT3/AHA/xavfKKAPAf8AhAviXqn/ACFdc8tG6qssh/8AHVAX9au2XwR0wN5mq6hPcMeT5arHk+5O417jRQBw+m/DrwfpOGg0+OVx/FNmU59cNkD8BXaRxpGgjjAVQMADgAfSpKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooA//9k="

API_BASE = "https://api.shipsgo.com/v2"
APP_DIR = Path(os.path.dirname(os.path.abspath(sys.argv[0])))
CONFIG_FILE = APP_DIR / "config.json"
TRACKING_DB_FILE = APP_DIR / "tracking_data.json"
LOG_FILE = APP_DIR / "tracker.log"
EST = timezone(timedelta(hours=-5))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.FileHandler(LOG_FILE)])
logger = logging.getLogger(__name__)

def now_est():
    return datetime.now(EST).strftime("%Y-%m-%d %I:%M %p EST")

def now_est_short():
    return datetime.now(EST).strftime("%I:%M %p")

LIGHT = {
    "bg": "#ECEAE5", "card": "#FFFFFF", "input": "#F7F6F3",
    "primary": "#111111", "secondary": "#333333", "muted": "#666666",
    "hint": "#999999", "border": "#D0CEC8",
    "green": "#3EA652", "green_dark": "#2D8A42", "green_light": "#E0F2E5",
    "blue": "#1565C0", "blue_light": "#E3F2FD",
    "btn_bg": "#DDDBD5", "btn_text": "#333333",
    "thead": "#F2F0EC", "log_bg": "#FFFFFF",
    "sail_bg": "#E3F2FD", "sail_fg": "#0D47A1",
    "disc_bg": "#E0F2E5", "disc_fg": "#1B5E20",
    "stat_bg": "#FFFFFF",
}
DARK = {
    "bg": "#1A1A1F", "card": "#242429", "input": "#1E1E24",
    "primary": "#F0EDE8", "secondary": "#CCCCCC", "muted": "#909090",
    "hint": "#606060", "border": "#3A3A42",
    "green": "#3EA652", "green_dark": "#2D8A42", "green_light": "#1A3A24",
    "blue": "#64B5F6", "blue_light": "#1A2A3A",
    "btn_bg": "#333338", "btn_text": "#CCCCCC",
    "thead": "#1E1E24", "log_bg": "#1E1E24",
    "sail_bg": "#1A2A3A", "sail_fg": "#64B5F6",
    "disc_bg": "#1A3A24", "disc_fg": "#66BB6A",
    "stat_bg": "#242429",
}

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
    return load_json(CONFIG_FILE, {"api_key":"","excel_path":"","dark_mode":False,"dismissed":[]})
def save_config(c):
    save_json(CONFIG_FILE,c)

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


class ContainerTrackerApp:
    def __init__(self):
        self.config=load_config()
        self.is_dark=self.config.get("dark_mode",False)
        self.T=DARK if self.is_dark else LIGHT
        self.db=load_json(TRACKING_DB_FILE,{})
        self.client=None; self.themed_widgets=[]

        if HAS_CTK:
            ctk.set_appearance_mode("light")
            self.root=ctk.CTk(); self.root.configure(fg_color=self.T["bg"])
        else:
            self.root=tk.Tk(); self.root.configure(bg=self.T["bg"])
        self.root.title("Container Tracking \u2014 Ken Gabbay Coffee")
        self.root.geometry("1020x800"); self.root.minsize(860,650)

        # Set window icon from embedded logo
        self.logo_image=None; self.logo_icon=None
        if HAS_PIL:
            try:
                d=base64.b64decode(LOGO_B64)
                img=Image.open(io.BytesIO(d))
                self.logo_image=ctk.CTkImage(img.resize((50,50),Image.LANCZOS),size=(50,50)) if HAS_CTK else ImageTk.PhotoImage(img.resize((50,50),Image.LANCZOS))
                # Save as temp .ico and set as window icon
                import tempfile
                self._icon_path=os.path.join(tempfile.gettempdir(),"kgc_tracker.ico")
                icon_sizes=[(16,16),(32,32),(48,48)]
                icon_imgs=[img.resize(s,Image.LANCZOS) for s in icon_sizes]
                icon_imgs[0].save(self._icon_path,format="ICO",sizes=icon_sizes,append_images=icon_imgs[1:])
                def _set_icon():
                    try: self.root.iconbitmap(self._icon_path)
                    except: pass
                self.root.after(200, _set_icon)
                self.root.after(600, _set_icon)
                self.root.after(1200, _set_icon)
            except Exception: pass

        self.build_ui(); self.load_table_data(); self.update_stats()

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
                   "combo":{"fg_color":T["input"],"border_color":T["border"],"button_color":T["btn_bg"],
                            "dropdown_fg_color":T["card"],"text_color":T["primary"]},
                   "stat_value":{"text_color":T["primary"]},"stat_label":{"text_color":T["muted"]}}
                if role in m: w.configure(**m[role])
            except: pass
        if HAS_CTK: self.root.configure(fg_color=T["bg"])
        s=ttk_mod.Style()
        s.configure("Custom.Treeview",background=T["card"],fieldbackground=T["card"],
                    foreground=T["primary"],rowheight=34,font=("Segoe UI",11),borderwidth=0)
        s.configure("Custom.Treeview.Heading",background=T["thead"],foreground=T["muted"],
                    font=("Segoe UI",10),borderwidth=0,relief="flat")
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
        w=ctk.CTkFrame(p,fg_color=self.T["card"],corner_radius=12,border_width=1,border_color=self.T["border"]) if HAS_CTK else tk.Frame(p,bg=self.T["card"],bd=1,relief="solid")
        return self._reg(w,"card")
    def _l(self,p,text,role="label_primary",size=13,bold=False):
        wt="bold" if bold else "normal"
        cm={"label_primary":"primary","label_secondary":"secondary","label_muted":"muted","label_hint":"hint","label_green":"green"}
        c=self.T[cm.get(role,"primary")]
        w=ctk.CTkLabel(p,text=text,text_color=c,font=("Segoe UI",size,wt),fg_color="transparent") if HAS_CTK else tk.Label(p,text=text,fg=c,bg=self.T["bg"],font=("Segoe UI",size,wt))
        return self._reg(w,role)
    def _btn(self,p,text,cmd,role="btn"):
        if HAS_CTK:
            kw={"text":text,"command":cmd,"corner_radius":8}
            if role=="btn_green": kw.update(fg_color=self.T["green"],hover_color=self.T["green_dark"],text_color="white",font=("Segoe UI",13,"bold"),height=38)
            elif role=="btn_outline": kw.update(fg_color="transparent",hover_color=self.T["green_light"],text_color=self.T["green"],border_width=1,border_color=self.T["green"],font=("Segoe UI",12),height=34)
            elif role=="btn_red": kw.update(fg_color="#D32F2F",hover_color="#B71C1C",text_color="white",font=("Segoe UI",11),height=30,width=100)
            else: kw.update(fg_color=self.T["btn_bg"],hover_color=self.T["border"],text_color=self.T["btn_text"],font=("Segoe UI",12),height=34)
            w=ctk.CTkButton(p,**kw)
        else:
            bg=self.T["green"] if role=="btn_green" else ("#D32F2F" if role=="btn_red" else self.T["btn_bg"])
            fg="white" if role in ("btn_green","btn_red") else self.T["btn_text"]
            w=tk.Button(p,text=text,command=cmd,bg=bg,fg=fg,font=("Segoe UI",11),relief="flat",padx=12,pady=4)
        return self._reg(w,role)
    def _e(self,p,**kw):
        w=ctk.CTkEntry(p,fg_color=self.T["input"],border_color=self.T["border"],text_color=self.T["primary"],corner_radius=8,**kw) if HAS_CTK else tk.Entry(p,bg=self.T["input"],fg=self.T["primary"],relief="solid",bd=1)
        return self._reg(w,"input")

    def build_ui(self):
        T=self.T
        # Header
        hdr=self._f(self.root); hdr.pack(fill="x",padx=20,pady=(14,6))
        left=self._f(hdr); left.pack(side="left")
        if self.logo_image:
            (ctk.CTkLabel(left,image=self.logo_image,text="",fg_color="transparent") if HAS_CTK
             else tk.Label(left,image=self.logo_image,bg=T["bg"])).pack(side="left",padx=(0,14))
        tf=self._f(left); tf.pack(side="left")
        self._l(tf,"Container Tracking",size=18,bold=True).pack(anchor="w")
        self._l(tf,"Ken Gabbay Coffee",role="label_muted",size=11).pack(anchor="w")
        rt=self._f(hdr); rt.pack(side="right")
        self.status_label=self._l(rt,"",role="label_green",size=11)
        self.status_label.pack(side="left",padx=(0,14))
        if HAS_CTK:
            self.theme_switch=ctk.CTkSwitch(rt,text="",width=44,command=self.toggle_theme,
                fg_color=T["border"],progress_color=T["green"],button_color="#FFF",button_hover_color="#EEE")
            if self.is_dark: self.theme_switch.select()
            self.theme_switch.pack(side="left")

        # API Key
        kf=self._f(self.root); kf.pack(fill="x",padx=20,pady=(2,4))
        self._l(kf,"API key",role="label_muted",size=11).pack(side="left",padx=(0,8))
        self.api_key_var=StringVar(value=self.config.get("api_key",""))
        self._e(kf,textvariable=self.api_key_var,show="*",width=340).pack(side="left",padx=(0,6))
        self._btn(kf,"Save",self.save_api_key).pack(side="left")

        # Excel card
        ec=self._card(self.root); ec.pack(fill="x",padx=20,pady=(4,4))
        ei=self._f(ec,role="card"); ei.pack(fill="x",padx=16,pady=12)
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
        sf=self._f(self.root); sf.pack(fill="x",padx=20,pady=(6,4))
        self.stat_frames={}
        for key,label in [("total","Tracked"),("sailing","Sailing"),("arrived","Arrived"),("delayed","Delayed")]:
            card=ctk.CTkFrame(sf,fg_color=T["stat_bg"],corner_radius=10,border_width=1,border_color=T["border"],height=60) if HAS_CTK else tk.Frame(sf,bg=T["stat_bg"],bd=1,relief="solid")
            self._reg(card,"stat_card")
            card.pack(side="left",fill="x",expand=True,padx=(0 if key=="total" else 4,0))
            sl=self._l(card,label,role="stat_label",size=10); sl.pack(anchor="w",padx=12,pady=(8,0))
            color=T["primary"]
            if key=="sailing": color=T["blue"]
            elif key=="arrived": color=T["green"]
            elif key=="delayed": color="#D32F2F"
            sv=ctk.CTkLabel(card,text="0",text_color=color,font=("Segoe UI",22,"bold"),fg_color="transparent") if HAS_CTK else tk.Label(card,text="0",fg=color,bg=T["stat_bg"],font=("Segoe UI",22,"bold"))
            sv.pack(anchor="w",padx=12,pady=(0,8))
            self.stat_frames[key]=sv

        # Actions
        af=self._f(self.root); af.pack(fill="x",padx=20,pady=(6,4))
        self.refresh_btn=self._btn(af,"  Refresh All ETAs & Update Excel  ",self.refresh_data,role="btn_green")
        self.refresh_btn.pack(side="left",padx=(0,8))
        self._btn(af,"Remove Selected",self.remove_container,role="btn_red").pack(side="left",padx=(0,16))
        self._l(af,"Add:",role="label_muted",size=11).pack(side="left",padx=(12,4))
        self.container_var=StringVar()
        self._e(af,textvariable=self.container_var,width=130).pack(side="left",padx=(0,4))
        self.carrier_var=StringVar(value="MAERSK LINE")
        if HAS_CTK:
            cc=ctk.CTkComboBox(af,values=CARRIER_NAMES,variable=self.carrier_var,width=130,
                fg_color=T["input"],border_color=T["border"],button_color=T["btn_bg"],
                dropdown_fg_color=T["card"],text_color=T["primary"],corner_radius=8)
            self._reg(cc,"combo")
        else: cc=ttk.Combobox(af,textvariable=self.carrier_var,values=CARRIER_NAMES,width=14,state="readonly")
        cc.pack(side="left",padx=(0,4))
        self._btn(af,"Add & Track",self.add_container,role="btn_outline").pack(side="left")

        # Table
        tbf=self._f(self.root); tbf.pack(fill="both",expand=True,padx=20,pady=(4,4))
        s=ttk_mod.Style(); s.theme_use("clam")
        s.configure("Custom.Treeview",background=T["card"],fieldbackground=T["card"],
                    foreground=T["primary"],rowheight=34,font=("Segoe UI",11),borderwidth=0)
        s.configure("Custom.Treeview.Heading",background=T["thead"],foreground=T["muted"],
                    font=("Segoe UI",10),borderwidth=0,relief="flat")
        s.map("Custom.Treeview",background=[("selected",T["green_light"])],foreground=[("selected",T["primary"])])
        cols=("container","carrier","status","orig_eta","eta","delay","route","vessel","transit")
        self.tree=ttk_mod.Treeview(tbf,columns=cols,show="headings",height=8,style="Custom.Treeview")
        for cid,hd,w in [("container","Container #",115),("carrier","Carrier",90),("status","Status",90),
            ("orig_eta","Original ETA",90),("eta","Current ETA",90),("delay","Delay",80),
            ("route","Route",180),("vessel","Vessel",120),("transit","Transit",60)]:
            self.tree.heading(cid,text=hd); self.tree.column(cid,width=w,minwidth=45)
        if HAS_CTK:
            sb=ctk.CTkScrollbar(tbf,command=self.tree.yview,fg_color="transparent",
                button_color=T["border"],button_hover_color=T["muted"])
        else:
            sb=ttk_mod.Scrollbar(tbf,orient="vertical",command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left",fill="both",expand=True); sb.pack(side="right",fill="y")

        # Log
        lf=self._f(self.root); lf.pack(fill="x",padx=20,pady=(2,2))
        self._l(lf,"Activity log",role="label_hint",size=10).pack(anchor="w",pady=(0,2))
        if HAS_CTK:
            self.log_text=ctk.CTkTextbox(self.root,height=80,fg_color=T["log_bg"],text_color=T["secondary"],
                font=("Consolas",11),corner_radius=8,border_width=1,border_color=T["border"])
            self._reg(self.log_text,"log")
        else:
            self.log_text=tk.Text(self.root,height=4,font=("Consolas",9),bg=T["log_bg"],fg=T["secondary"],relief="solid",bd=1)
        self.log_text.pack(fill="x",padx=20,pady=(0,8))

        # Footer
        ff=self._f(self.root); ff.pack(fill="x",padx=20,pady=(0,8))
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
            self.tree.insert("",END,iid=key,values=(
                rec.get("container_number") or key, rec.get("carrier",rec.get("shipping_line","")),
                rec.get("status",""), rec.get("original_eta",""), rec.get("eta",""),
                rec.get("delay_days",""), route, rec.get("vessel",""), tp))
        self.update_stats()

    def save_api_key(self):
        key=self.api_key_var.get().strip()
        if not key: messagebox.showwarning("Missing Key","Please enter your ShipsGo API key."); return
        self.config["api_key"]=key; save_config(self.config); self.client=None
        self.log("API key saved."); messagebox.showinfo("Saved","API key saved.")
    def get_client(self):
        key=self.api_key_var.get().strip()
        if not key:
            messagebox.showwarning("Missing API Key","Enter your ShipsGo API key first.\n\n1. Go to shipsgo.com\n2. Dashboard > Integrations > ShipsGo API\n3. Copy your token"); return None
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
