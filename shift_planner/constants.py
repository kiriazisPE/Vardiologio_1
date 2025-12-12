# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, time
import os
import logging, sys

# ---------- Logging ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("shift_planner")

# ---------- App Config ----------
APP_ENV =  os.getenv("APP_ENV", "dev").lower()  # dev|prod  # dev|prod
DB_FILE = os.getenv("DB_FILE", "shifts.db")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8501"))
SESSION_TTL_MIN = int(os.getenv("SESSION_TTL_MIN", "240"))
TZ = os.getenv("TZ", "Europe/Athens")

# ---------- Domain Constants ----------
DAYS = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]

ALL_SHIFTS = ["Πρωί", "Απόγευμα", "Βράδυ"]

SHIFT_TIMES = {
    "Πρωί": (8, 16),
    "Απόγευμα": (16, 23),
    "Βράδυ": (23, 7)  # wraps to next day
}

DEFAULT_ROLES = ["Ταμείο", "Σερβιτόρος", "Μάγειρας", "Barista"]

EXTRA_ROLES = ["Υποδοχή", "Καθαριστής", "Λαντζέρης", "Οδηγός", "Manager"]

DEFAULT_RULES = {
    "max_daily_hours_5days": 8,
    "max_daily_hours_6days": 9,
    "max_daily_hours_7days": 9,
    "max_daily_overtime": 3,
    "min_daily_rest": 11,
    "weekly_hours_5days": 40,
    "weekly_hours_6days": 48,
    "weekly_hours_7days": 56,
    "weekly_rest_hours": 24,
    "monthly_hours": 160,
    "max_consecutive_days": 6,
    "work_model": "5ήμερο",
}


# ---------- Utility Functions ----------
def shift_duration(shift: str) -> int | None:
    """Return duration in hours, handling wrap-around shifts.
    Returns None if shift label is not in SHIFT_TIMES.
    """
    times = SHIFT_TIMES.get(shift)
    if not times:
        logger.info(f"Ignoring unknown shift label '{shift}'.")
        return None
    s, e = times
    return (24 - s + e) if e < s else (e - s)



def shift_end_datetime(d: datetime, shift: str) -> datetime | None:
    """Compute end datetime for a shift that may cross midnight.
    Returns None if shift label is unknown.
    """
    times = SHIFT_TIMES.get(shift)
    if not times:
        logger.warning(f"Unknown shift label '{shift}' – returning None.")
        return None

    s, e = times
    # If end < start, the shift wraps past midnight → next day
    end_date = d + timedelta(days=1) if e < s else d
    return datetime.combine(end_date, time(hour=e))




# Helper for rules
def get_rule(key: str, default=None):
    """Safe access to DEFAULT_RULES with optional fallback."""
    return DEFAULT_RULES.get(key, default)
