# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Tuple, Union, Iterable
from datetime import timedelta
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

# ---------- Helpers (env parsing) ----------
def _get_int_env(name: str, default: int) -> int:
    """Parse an int env var with fallback and logging on invalid values."""
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        logger.warning("Invalid %s=%r; falling back to %s", name, raw, default)
        return int(default)

# ---------- App Config ----------
APP_ENV = os.getenv("APP_ENV", "dev")  # dev | prod
DB_FILE = os.getenv("DB_FILE", "shifts.db")
SERVER_PORT = _get_int_env("SERVER_PORT", 8501)
SESSION_TTL_MIN = _get_int_env("SESSION_TTL_MIN", 240)
TZ = os.getenv("TZ", "Europe/Athens") or "Europe/Athens"  # kept as a simple string for display/logging

# ---------- Domain Constants ----------
DAYS: list[str] = [
    "Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"
]

# Default built-in shifts
ALL_SHIFTS: list[str] = ["Πρωί", "Απόγευμα", "Βράδυ"]



# Shift bounds (start_hour, end_hour) as floats; 7.5 == 07:30
_SHIFT_TIMES: Dict[str, Tuple[float, float]] = {
    "Πρωί": (8.0, 16.0),
    "Απόγευμα": (16.0, 23.0),
    "Βράδυ": (23.0, 7.0),  # wraps to next day
}

SHIFT_TIMES = _SHIFT_TIMES 


def register_shift(name: str, start_hour: float, end_hour: float) -> None:
    """
    Register or update a shift's start/end wall-clock hours.
    Example: register_shift("Split", 12.0, 20.0)
    """
    if not name or not isinstance(name, str):
        raise ValueError("Shift name must be a non-empty string")
    try:
        s = float(start_hour); e = float(end_hour)
    except (TypeError, ValueError):
        raise ValueError("start_hour and end_hour must be numbers")
    _SHIFT_TIMES[name] = (s, e)

def shift_bounds(shift: str) -> Tuple[float, float]:
    """Return (start_hour, end_hour). Raises KeyError for unknown names."""
    try:
        return _SHIFT_TIMES[shift]
    except KeyError as e:
        raise KeyError(f"Unknown shift name: {shift}") from e

def shift_duration(shift: str) -> float:
    """Return duration in hours (supports fractional hours), handling wrap-around."""
    s, e = shift_bounds(shift)
    return (24.0 - s + e) if e < s else (e - s)

def safe_shift_duration(shift: str, default_hours: float = 0.0) -> float:
    """
    Like shift_duration(), but returns a default if the shift is unknown.
    (The UI can call register_shift() once to avoid falling back.)
    """
    try:
        return shift_duration(shift)
    except KeyError:
        logger.warning("Unknown shift '%s' requested; returning default=%.2f h", shift, default_hours)
        return float(default_hours)

def is_known_shift(shift: str) -> bool:
    return shift in _SHIFT_TIMES

def shift_times_snapshot() -> Dict[str, Tuple[float, float]]:
    """Read-only snapshot for external modules (avoid accidental mutation)."""
    return dict(_SHIFT_TIMES)

# Unified Greek labels for a polished UI
DEFAULT_ROLES = ["Ταμείο", "Σερβιτόρος", "Μάγειρας", "Μπαρίστα"]
# NOTE: Removed EXTRA_ROLES (legacy/unused)

# ---------- Labor Rules (single source of truth) ----------
# Common limits used across models
RULES_COMMON: Dict[str, float] = {
    "max_daily_overtime": 3.0,  # hours of OT allowed in a single day
    "min_daily_rest": 11.0,     # minimum rest between shifts in hours
    "weekly_rest_hours": 24.0,  # weekly continuous rest
    "monthly_hours": 160.0,     # nominal monthly target
}

# Per-work-model limits (picked by get_rules())
# NOTE: max_consecutive_days is an INT by design; hour caps are floats.
RULES_BY_MODEL: Dict[str, Dict[str, Union[float, int]]] = {
    "5ήμερο": {
        "max_daily_hours": 8.0,
        "weekly_hours": 40.0,
        "max_consecutive_days": 6,
    },
    "6ήμερο": {
        "max_daily_hours": 9.0,
        "weekly_hours": 48.0,
        "max_consecutive_days": 6,
    },
    # Align with UI: 7 × 8h nominal cap → 56.0h
    "7ήμερο": {
        "max_daily_hours": 9.0,
        "weekly_hours": 56.0,   # was 63.0; unified with UI defaults
        "max_consecutive_days": 6,
    },
}

# Default work model for new companies/tenants
DEFAULT_WORK_MODEL = os.getenv("DEFAULT_WORK_MODEL", "5ήμερο")

def get_rules(work_model: str | None = None) -> Dict[str, Union[float, int, str]]:
    """
    Canonical merged rule set for a given work model.
    Engines (validators/generators) should call this to avoid key mismatches.
    Unknown models fall back to DEFAULT_WORK_MODEL.
    """
    model = (work_model or DEFAULT_WORK_MODEL).strip()
    if model not in RULES_BY_MODEL:
        logger.warning("Unknown work model '%s'; falling back to %s", model, DEFAULT_WORK_MODEL)
        model = DEFAULT_WORK_MODEL
    merged = {**RULES_COMMON, **RULES_BY_MODEL[model]}
    return {**merged, "work_model": model}

def rules_flat(work_model: str | None = None) -> Dict[str, Union[float, int, str]]:
    """
    UI/back-compat: flatten get_rules() into the legacy key shape the old UI expects.
    Prefer using get_rules() in new code.
    """
    model = (work_model or DEFAULT_WORK_MODEL).strip()
    base = get_rules(model)
    return {
        "max_daily_hours_5days": RULES_BY_MODEL["5ήμερο"]["max_daily_hours"],
        "max_daily_hours_6days": RULES_BY_MODEL["6ήμερο"]["max_daily_hours"],
        "max_daily_hours_7days": RULES_BY_MODEL["7ήμερο"]["max_daily_hours"],
        "max_daily_overtime": base["max_daily_overtime"],
        "min_daily_rest": base["min_daily_rest"],
        "weekly_hours_5days": RULES_BY_MODEL["5ήμερο"]["weekly_hours"],
        "weekly_hours_6days": RULES_BY_MODEL["6ήμερο"]["weekly_hours"],
        "weekly_hours_7days": RULES_BY_MODEL["7ήμερο"]["weekly_hours"],
        "weekly_rest_hours": base["weekly_rest_hours"],
        "monthly_hours": base["monthly_hours"],
        "max_consecutive_days": RULES_BY_MODEL["5ήμερο"]["max_consecutive_days"],
        "work_model": model,
    }

# Convenience: one flat blob for the default model (for older imports that want a constant)
DEFAULT_RULES_FLAT = rules_flat(DEFAULT_WORK_MODEL)

# ---------- Public API ----------
__all__: Iterable[str] = (
    # App
    "APP_ENV", "DB_FILE", "SERVER_PORT", "SESSION_TTL_MIN", "TZ",
    # Domain
    "DAYS", "ALL_SHIFTS",
    "register_shift", "shift_bounds", "shift_duration", "safe_shift_duration",
    "is_known_shift", "shift_times_snapshot",
    "DEFAULT_ROLES",
    "SHIFT_TIMES",                 # <-- add this
    # Rules
    "RULES_COMMON", "RULES_BY_MODEL", "DEFAULT_WORK_MODEL",
    "get_rules", "rules_flat", "DEFAULT_RULES_FLAT",
)

