"""ShipsGo API v2 client and response parsing.

Pure logic. Constructing a client does not make a network call.
"""
from __future__ import annotations


CARRIER_SCAC_MAP: dict[str, str] = {
    "MAERSK":       "MAEU",
    "MAERSK LINE":  "MAEU",
    "MSC":          "MSCU",
    "CMA CGM":      "CMDU",
    "HAPAG LLOYD":  "HLCU",
    "HAPAG-LLOYD":  "HLCU",
    "COSCO":        "COSU",
    "EVERGREEN":    "EGLV",
    "ONE":          "ONEY",
    "YANG MING":    "YMLU",
    "ZIM":          "ZIMU",
    "HMM":          "HDMU",
    "OOCL":         "OOLU",
    "PIL":          "PILU",
}

CARRIER_NAMES: list[str] = [
    "MAERSK LINE", "MSC", "CMA CGM", "HAPAG LLOYD", "COSCO",
    "EVERGREEN", "ONE", "YANG MING", "ZIM", "HMM", "OOCL", "PIL", "OTHER",
]


def resolve_scac(line: str) -> str:
    """Resolve a shipping-line name to a SCAC code.

    Known names map via CARRIER_SCAC_MAP. A four-letter input is assumed to
    already be a SCAC. Otherwise the uppercased input is returned unchanged.
    """
    upper = line.strip().upper()
    return CARRIER_SCAC_MAP.get(upper, upper)
