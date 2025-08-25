# -*- coding: utf-8 -*-

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict, Tuple, Union, Iterable
import os
import logging, sys
from zoneinfo import ZoneInfo

# ---------- Logging ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("shift_planner")

# ---------- Helpers (env parsing) ----------

def _get_int_env(name: str, default: int) -> int:
    """Parse an int env var with fallback and logging on invalid values.

    Prevents import-time crashes if the environment variable is present but not an int.
    """
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        logger.warning("Invalid %s=%r; falling back to %s", name, raw, default)
        return int(default)

def _get_tz(name_or_obj: Union[str, ZoneInfo, None]) -> ZoneInfo:
    """Return a ZoneInfo from a tz name or pass through an existing ZoneInfo.

    Falls back to Europe/Athens if nothing valid is provided.
    """
    if isinstance(name_or_obj, ZoneInfo):
        return name_or_obj
    tz_name = (name_or_obj or "Europe/Athens") or "Europe/Athens"
    try:
        return ZoneInfo(tz_name)
    except Exception:  # pragma: no cover (defensive)
        logger.warning("Unknown timezone %r; falling back to Europe/Athens", tz_name)
        return ZoneInfo("Europe/Athens")

# ---------- App Config ----------
APP_ENV = os.getenv("APP_ENV", "dev")  # dev | prod
DB_FILE = os.getenv("DB_FILE", "shifts.db")
SERVER_PORT = _get_int_env("SERVER_PORT", 8501)
SESSION_TTL_MIN = _get_int_env("SESSION_TTL_MIN", 240)
TZ = os.getenv("TZ", "Europe/Athens") or "Europe/Athens"
TZINFO: ZoneInfo = _get_tz(TZ)  # single source of truth for tz usage

# ---------- Domain Constants ----------
DAYS: list[str] = [
    "Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"
]

ALL_SHIFTS: list[str] = ["Πρωί", "Απόγευμα", "Βράδυ"]

# Start/end expressed as clock hours (can be fractional)
# e.g., 7.5 means 07:30
SHIFT_TIMES: Dict[str, Tuple[float, float]] = {
    "Πρωί": (8.0, 16.0),
    "Απόγευμα": (16.0, 23.0),
    "Βράδυ": (23.0, 7.0),  # wraps to next day
}
# Public set of known shift keys for validation in other modules
KNOWN_SHIFTS = set(SHIFT_TIMES.keys())

# Unified Greek labels for a polished UI
DEFAULT_ROLES = ["Ταμείο", "Σερβιτόρος", "Μάγειρας", "Μπαρίστα"]
# Legacy/unused in UI; retained for back-compat. Safe to remove once callers stop importing it.
EXTRA_ROLES = ["Υποδοχή", "Καθαριστής", "Λαντζέρης", "Οδηγός", "Υπεύθυνος"]

# ---------- Labor Rules ----------
# Common limits used across models
RULES_COMMON: Dict[str, float] = {
    "max_daily_overtime": 3.0,  # hours of OT allowed in a single day
    "min_daily_rest": 11.0,     # minimum rest between shifts in hours
    "weekly_rest_hours": 24.0,  # weekly continuous rest
    "monthly_hours": 160.0,     # nominal monthly target
}

# Per-work-model limits (picked by get_rules())
# NOTE: max_consecutive_days is an INT by design; other hour caps are floats.
RULES_BY_MODEL: Dict[str, Dict[str, Union[float, int]]] = {
    # 5-day week
    "5ήμερο": {
        "max_daily_hours": 8.0,
        "weekly_hours": 40.0,
        "max_consecutive_days": 6,  # int
    },
    # 6-day week
    "6ήμερο": {
        "max_daily_hours": 9.0,
        "weekly_hours": 48.0,
        "max_consecutive_days": 6,  # int
    },
    # 7-day rota (coverage every day; each employee still must get weekly rest)
    # Engine default: 9.0h daily. Weekly cap is nominal 7 × 9 = 63.0h.
    "7ήμερο": {
        "max_daily_hours": 9.0,
        "weekly_hours": 63.0,
        "max_consecutive_days": 6,  # int
    },
}

# Default work model for new companies/tenants
DEFAULT_WORK_MODEL = os.getenv("DEFAULT_WORK_MODEL", "5ήμερο")

def get_rules(work_model: str | None = None) -> Dict[str, Union[float, int, str]]:
    """Return the merged rule set for the given work model.

    Engines (validators/generators) should call this to avoid key mismatches.
    Unknown models fall back to DEFAULT_WORK_MODEL.
    """
    model = (work_model or DEFAULT_WORK_MODEL).strip()
    if model not in RULES_BY_MODEL:
        logger.warning("Unknown work model '%s'; falling back to %s", model, DEFAULT_WORK_MODEL)
        model = DEFAULT_WORK_MODEL
    merged: Dict[str, Union[float, int]] = {**RULES_COMMON, **RULES_BY_MODEL[model]}
    # Include the selected work model label in the returned mapping.
    merged_with_model: Dict[str, Union[float, int, str]] = {**merged, "work_model": model}
    return dict(merged_with_model)  # return a copy to prevent accidental mutation

# Back-compat layer: expose DEFAULT_RULES with the same keys older code expected.
# NOTE: Prefer get_rules() going forward; this alias remains to avoid breaking legacy imports.
DEFAULT_RULES: Dict[str, Union[float, int, str]] = {
    "max_daily_hours_5days": RULES_BY_MODEL["5ήμερο"]["max_daily_hours"],
    "max_daily_hours_6days": RULES_BY_MODEL["6ήμερο"]["max_daily_hours"],
    "max_daily_hours_7days": RULES_BY_MODEL["7ήμερο"]["max_daily_hours"],
    "max_daily_overtime": RULES_COMMON["max_daily_overtime"],
    "min_daily_rest": RULES_COMMON["min_daily_rest"],
    "weekly_hours_5days": RULES_BY_MODEL["5ήμερο"]["weekly_hours"],
    "weekly_hours_6days": RULES_BY_MODEL["6ήμερο"]["weekly_hours"],
    "weekly_hours_7days": RULES_BY_MODEL["7ήμερο"]["weekly_hours"],
    "weekly_rest_hours": RULES_COMMON["weekly_rest_hours"],
    "monthly_hours": RULES_COMMON["monthly_hours"],
    "max_consecutive_days": RULES_BY_MODEL["5ήμερο"]["max_consecutive_days"],  # consistent default
    "work_model": DEFAULT_WORK_MODEL,
}

# ---------- Utility Functions (float- & tz-aware) ----------

def shift_bounds(shift: str) -> Tuple[float, float]:
    """Return (start_hour, end_hour) as floats.
    Example: (23.0, 7.0) means 23:00 → 07:00 next day.
    """
    try:
        return SHIFT_TIMES[shift]
    except KeyError as e:
        raise KeyError(f"Unknown shift name: {shift}") from e

def shift_duration(shift: str) -> float:
    """Return duration in hours (supports fractional hours), handling wrap-around."""
    s, e = shift_bounds(shift)
    return (24.0 - s + e) if e < s else (e - s)

def is_known_shift(shift: str) -> bool:
    """Fast membership check for valid shift keys."""
    return shift in KNOWN_SHIFTS

def shift_end_datetime(d: datetime, shift: str) -> datetime:
    """Compute end datetime for a shift that may cross midnight, timezone-aware.

    Behavior:
    - If `d` is naive, it is interpreted in the app's configured TZ (TZINFO).
    - If `d` is aware, it is converted to the configured TZ *date* before computing.
    - SHIFT_TIMES are wall‑clock hours. On DST transition days, elapsed seconds may differ
      from `shift_duration(shift) * 3600` even though the wall‑clock span matches.
    """
    # normalize input date to configured tz at local midnight
    if d.tzinfo is None:
        d_local = datetime(d.year, d.month, d.day, tzinfo=TZINFO)
    else:
        d_local = d.astimezone(TZINFO).replace(hour=0, minute=0, second=0, microsecond=0)

    start_hour, _ = shift_bounds(shift)
    start_dt = d_local + timedelta(hours=start_hour)
    return start_dt + timedelta(hours=shift_duration(shift))

# ---------- Public API ----------
__all__: Iterable[str] = (
    "APP_ENV",
    "DB_FILE",
    "SERVER_PORT",
    "SESSION_TTL_MIN",
    "TZ",
    "TZINFO",
    "DAYS",
    "ALL_SHIFTS",
    "SHIFT_TIMES",
    "KNOWN_SHIFTS",
    "DEFAULT_ROLES",
    "EXTRA_ROLES",
    "RULES_COMMON",
    "RULES_BY_MODEL",
    "DEFAULT_WORK_MODEL",
    "DEFAULT_RULES",
    "get_rules",
    "shift_bounds",
    "shift_duration",
    "is_known_shift",
    "shift_end_datetime",
)
