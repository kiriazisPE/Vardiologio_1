# -*- coding: utf-8 -*-
"""
Centralized constants & small utilities for the scheduling app.

Changes in this version:
- Reintroduced DEFAULT_RULES as a compatibility alias so legacy imports don’t break.
- Normalize rule keys by work model (5/6/7-day) and remove unused/ambiguous keys.
- Provide a helper `get_rules(work_model)` to fetch the correct rules for engines.
- Make time calculations float-friendly (supports 7.5h etc.).
- Align type hints to float where fractional hours are possible.
"""
from __future__ import annotations
from datetime import datetime, timedelta, time
from typing import Dict, Tuple
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
DAYS = [
    "Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"
]

ALL_SHIFTS = ["Πρωί", "Απόγευμα", "Βράδυ"]

# Start/end expressed as clock hours (can be fractional)
# e.g., 7.5 means 07:30
SHIFT_TIMES: Dict[str, Tuple[float, float]] = {
    "Πρωί": (8.0, 16.0),
    "Απόγευμα": (16.0, 23.0),
    "Βράδυ": (23.0, 7.0),  # wraps to next day
}

DEFAULT_ROLES = ["Ταμείο", "Σερβιτόρος", "Μάγειρας", "Barista"]
EXTRA_ROLES = ["Υποδοχή", "Καθαριστής", "Λαντζέρης", "Οδηγός", "Manager"]

# ---------- Labor Rules ----------
# Common limits used across models
RULES_COMMON: Dict[str, float] = {
    "max_daily_overtime": 3.0,  # hours of OT allowed in a single day
    "min_daily_rest": 11.0,     # minimum rest between shifts in hours
    "weekly_rest_hours": 24.0,  # weekly continuous rest
    "monthly_hours": 160.0,     # nominal monthly target
}

# Per-work-model limits (picked by get_rules())
RULES_BY_MODEL: Dict[str, Dict[str, float]] = {
    # 5-day week
    "5ήμερο": {
        "max_daily_hours": 8.0,
        "weekly_hours": 40.0,
        "max_consecutive_days": 6.0,
    },
    # 6-day week
    "6ήμερο": {
        "max_daily_hours": 9.0,
        "weekly_hours": 48.0,
        "max_consecutive_days": 6.0,
    },
    # 7-day rota (coverage every day; each employee still must get weekly rest)
    "7ήμερο": {
        "max_daily_hours": 9.0,
        "weekly_hours": 56.0,  # 7 × 8h typical cap; adjust as needed
        "max_consecutive_days": 6.0,
    },
}

# Default work model for new companies/tenants
DEFAULT_WORK_MODEL = os.getenv("DEFAULT_WORK_MODEL", "5ήμερο")


def get_rules(work_model: str | None = None) -> Dict[str, float]:
    """Return the merged rule set for the given work model.

    Engines (validators/generators) should call this to avoid key mismatches.
    Unknown models fall back to DEFAULT_WORK_MODEL.
    """
    model = (work_model or DEFAULT_WORK_MODEL).strip()
    if model not in RULES_BY_MODEL:
        logger.warning("Unknown work model '%s'; falling back to %s", model, DEFAULT_WORK_MODEL)
        model = DEFAULT_WORK_MODEL
    merged: Dict[str, float] = {**RULES_COMMON, **RULES_BY_MODEL[model]}
    merged_with_model = {**merged, "work_model": model}
    return merged_with_model

# Back-compat layer: expose DEFAULT_RULES with the same keys older code expected.
# Maps the selected model into a flat dictionary resembling the older structure.
# Note: Prefer get_rules() going forward.
DEFAULT_RULES: Dict[str, float] = {
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

# ---------- Utility Functions (float-aware) ----------

def shift_bounds(shift: str) -> Tuple[float, float]:
    """Return (start_hour, end_hour) as floats.
    Example: (23.0, 7.0) means 23:00 → 07:00 next day.
    """
    try:
        return SHIFT_TIMES[shift]
    except KeyError as e:
        raise KeyError(f"Unknown shift name: {shift}") from e


def shift_duration(shift: str) -> float:
    """Return duration in hours (supports fractional hours), handling wrap-around.
    """
    s, e = shift_bounds(shift)
    return (24.0 - s + e) if e < s else (e - s)


def shift_end_datetime(d: datetime, shift: str) -> datetime:
    """Compute end datetime for a shift that may cross midnight.

    Uses float hours; timedelta accepts fractional hours.
    """
    s, e = shift_bounds(shift)
    end_date = d + timedelta(days=1) if e < s else d
    # Combine at midnight and add e hours
    return datetime.combine(end_date, time()) + timedelta(hours=e)
