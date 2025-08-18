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
APP_ENV = os.getenv("APP_ENV", "dev")  # dev | prod
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
    "max_daily_overtime": 3,
    "min_daily_rest": 11,
    "weekly_hours_5days": 40,
    "weekly_hours_6days": 48,
    "weekly_max_with_overtime": 50,
    "weekly_rest_hours": 24,
    "monthly_hours": 160,
    "monthly_overtime": 12,
    "max_consecutive_days": 6,
    "work_model": "5ήμερο"
}

# ---------- Utility Functions ----------
def shift_duration(shift: str) -> int:
    """Return duration in hours, handling wrap-around shifts."""
    s, e = SHIFT_TIMES[shift]
    return (24 - s + e) if e < s else (e - s)

def shift_end_datetime(d: datetime, shift: str) -> datetime:
    """Compute end datetime for a shift that may cross midnight."""
    s, e = SHIFT_TIMES[shift]
    end_date = d + timedelta(days=1) if e < s else d
    return datetime.combine(end_date, time()) + timedelta(hours=e)
