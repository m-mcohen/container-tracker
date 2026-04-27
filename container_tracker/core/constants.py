"""Shared constants. Pure data; no side effects on import."""

__version__ = "1.1.0"

APP_NAME = "Container Tracker"
APP_SHORT_NAME = "ContainerTracker"
GITHUB_REPO = "m-mcohen/container-tracker"
ACCENT = "#2563eb"

API_BASE = "https://api.shipsgo.com/v2"

CARRIER_SCAC_MAP = {
    "MAERSK": "MAEU", "MAERSK LINE": "MAEU", "MSC": "MSCU",
    "CMA CGM": "CMDU", "HAPAG LLOYD": "HLCU", "HAPAG-LLOYD": "HLCU",
    "COSCO": "COSU", "EVERGREEN": "EGLV", "ONE": "ONEY",
    "YANG MING": "YMLU", "ZIM": "ZIMU", "HMM": "HDMU",
    "OOCL": "OOLU", "PIL": "PILU",
}
CARRIER_NAMES = ["MAERSK LINE", "MSC", "CMA CGM", "HAPAG LLOYD", "COSCO",
                 "EVERGREEN", "ONE", "YANG MING", "ZIM", "HMM", "OOCL", "PIL", "OTHER"]

CONTAINER_COL_KEYWORDS = ["container", "cntr", "container #", "container number",
                          "container_number", "container no", "cntr #", "cntr no"]
