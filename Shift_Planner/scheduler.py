# scheduler.py
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

import math
import pandas as pd

# These come from your constants.py
# - DAYS: e.g. ["Δευ", "Τρι", "Τετ", "Πεμ", "Παρ", "Σαβ", "Κυρ"]
# - SHIFT_TIMES: {"Πρωί": (8.0, 16.0), "Απόγευμα": (16.0, 24.0), ...}
from constants import DAYS, SHIFT_TIMES  # type: ignore


# ---------------------------
# Utilities for shift handling
# ---------------------------

def _require_shift(shift: str, *, strict: bool = True) -> Optional[Tuple[float, float]]:
    """
    Return (start_hour, end_hour) from SHIFT_TIMES.
    - strict=True  -> raise on unknown key (useful for config validation)
    - strict=False -> return None (callers decide how to degrade gracefully)
    """
    if shift not in SHIFT_TIMES:
        if strict:
            known = ", ".join(sorted(SHIFT_TIMES.keys()))
            raise KeyError(f"Unknown shift key '{shift}'. Valid keys: {known}")
        return None
    return SHIFT_TIMES[shift]


def _shift_len(shift: str) -> float:
    """Return the (positive) hours of a shift, handling wrap-around. Unknown→0.0h."""
    se = _require_shift(shift, strict=False)
    if not se:
        return 0.0
    s, e = se
    return (24 - s + e) if e < s else (e - s)


def _shift_start_hour(shift: str) -> Optional[float]:
    se = _require_shift(shift, strict=False)
    return None if not se else se[0]


def _shift_end_hour(shift: str) -> Optional[float]:
    se = _require_shift(shift, strict=False)
    if not se:
        return None
    s, e = se
    return e if e >= s else e + 24  # allow wrap past midnight


def _iso_week_key(d: date) -> Tuple[int, int]:
    iso = d.isocalendar()
    return iso[0], iso[1]  # (year, week)


def _rest_between(prev_date: date, prev_end_hour: float, next_date: date, next_start_hour: float) -> float:
    """
    Hours of rest from (prev_date @ prev_end_hour) to (next_date @ next_start_hour).
    End hour may be >=24 to indicate wrap.
    """
    prev_dt = datetime.combine(prev_date, datetime.min.time()) + timedelta(hours=prev_end_hour)
    next_dt = datetime.combine(next_date, datetime.min.time()) + timedelta(hours=next_start_hour)
    return max(0.0, (next_dt - prev_dt).total_seconds() / 3600.0)


# ---------------------------
# Rules & defaults
# ---------------------------

def _pick_rule(
    rules: Dict,
    key_5: str, key_6: str, key_7: str,
    work_model: str,
    default_5, default_6, default_7
):
    """
    Pick value from rules with sensible defaults per work model.
    Work model expected values: "5ήμερο", "6ήμερο", "7ήμερο".
    """
    wm = (work_model or "").strip()
    if wm == "5ήμερο":
        return type(default_5)(rules.get(key_5, default_5))
    if wm == "6ήμερο":
        return type(default_6)(rules.get(key_6, default_6))
    if wm == "7ήμερο":
        return type(default_7)(rules.get(key_7, default_7))
    # Unknown → pick 5-day by default
    return type(default_5)(rules.get(key_5, default_5))


# UI-aligned default caps (single source of truth fallback)
# - daily: 5d/6d/7d = 8/9/9
# - weekly: 5d/6d/7d = 40/48/56

def _rule_caps(rules: Dict, work_model: str) -> Tuple[float, float]:
    max_daily_hours = _pick_rule(
        rules,
        "max_daily_hours_5days",
        "max_daily_hours_6days",
        "max_daily_hours_7days",
        work_model,
        8, 9, 9,
    )
    weekly_hours_cap = _pick_rule(
        rules,
        "weekly_hours_5days",
        "weekly_hours_6days",
        "weekly_hours_7days",
        work_model,
        40, 48, 56,
    )
    return float(max_daily_hours), float(weekly_hours_cap)



def _min_daily_rest_rule(rules: Dict) -> float:
    """Return minimum daily rest hours; accepts both 'min_daily_rest_hours' and legacy 'min_daily_rest'."""
    try:
        # Prefer the explicit key, but fall back to legacy naming or default 11h
        return float(rules.get("min_daily_rest_hours", rules.get("min_daily_rest", 11)))
    except Exception:
        return 11.0

@dataclass
class Assignment:
    date: date
    shift: str
    employee: str
    role: str
    hours: float


# ---------------------------
# Requirements extraction (robust to various structures)
# ---------------------------

def _day_label(d: date) -> str:
    # Monday=0..Sunday=6 mapping to Greek short labels assumed in DAYS
    return DAYS[d.weekday() % len(DAYS)]


def _extract_need(
    role_settings: Dict,
    d: date,
    shift: str,
    role: str
) -> int:
    """
    Accepts multiple shapes for role_settings; tries the most specific first.
    Supported (examples):
      role_settings = {
        "per_day": {"Δευ": {"Πρωί": {"Ταμίας": 2}}},
        "per_shift": {"Πρωί": {"Ταμίας": 2}},
        "min_per": {"Ταμίας": 2}
      }
    Returns 0 if not defined.
    """
    if not isinstance(role_settings, dict):
        return 0

    dl = _day_label(d)
    # 1) per_day[day][shift][role]
    per_day = role_settings.get("per_day", {})
    need = per_day.get(dl, {}).get(shift, {}).get(role)
    if isinstance(need, int) and need >= 0:
        return need

    # 2) per_shift[shift][role]
    per_shift = role_settings.get("per_shift", {})
    need = per_shift.get(shift, {}).get(role)
    if isinstance(need, int) and need >= 0:
        return need

    # 3) min_per[role]
    min_per = role_settings.get("min_per", {})
    need = min_per.get(role)
    if isinstance(need, int) and need >= 0:
        return need

    return 0


def _employee_available(emp: Dict, d: date, shift: str) -> bool:
    """
    Best-effort availability check.
    Supports:
      - emp["unavailable_days"] : Iterable[int] with 0=Mon
      - emp["available_days"]   : Iterable[int] with 0=Mon
      - emp["unavailable"]      : {"Δευ": ["Πρωί", ...], ...}
      - emp["available"]        : {"Δευ": ["Πρωί", ...], ...}
    If no info -> assume available.
    """
    w = d.weekday()

    # Blocked weekday
    if isinstance(emp.get("unavailable_days"), Iterable):
        if w in set(emp["unavailable_days"]):
            return False

    # Allowed weekday only
    if isinstance(emp.get("available_days"), Iterable):
        if w not in set(emp["available_days"]):
            return False

    dl = _day_label(d)

    # Blocked specific (day, shift)
    if isinstance(emp.get("unavailable"), dict):
        if shift in set(emp["unavailable"].get(dl, [])):
            return False

    # Allowed specific (day, shift)
    if isinstance(emp.get("available"), dict):
        allowed = set(emp["available"].get(dl, []))
        # If the day is present and the shift not in the set, then not available
        if dl in emp["available"] and shift not in allowed:
            return False

    return True


# ---------------------------
# Violations
# ---------------------------

def check_violations(
    sched: pd.DataFrame,
    *,
    rules: Dict,
    work_model: str,
) -> pd.DataFrame:
    """
    Validate schedule and return a DataFrame of violations with columns:
      ["Είδος", "Υπάλληλος", "Ημερομηνία", "Λεπτομέρειες"]

    Expected sched columns:
      - "Ημερομηνία": date or iso string
      - "Βάρδια": shift key
      - "Υπάλληλος": employee name
      - "Ρόλος": role name
      - "Ώρες": float
    """
    if sched.empty:
        return pd.DataFrame(columns=["Είδος", "Υπάλληλος", "Ημερομηνία", "Λεπτομέρειες"])

    # Normalize date
    if not pd.api.types.is_datetime64_any_dtype(sched["Ημερομηνία"]):
        sched = sched.copy()
        sched["Ημερομηνία"] = pd.to_datetime(sched["Ημερομηνία"]).dt.date

    max_daily_hours, weekly_hours_cap = _rule_caps(rules, work_model)
    min_daily_rest = _min_daily_rest_rule(rules)

    viols: List[Dict] = []

    # Daily cap
    daily = (
        sched.groupby(["Υπάλληλος", "Ημερομηνία"])["Ώρες"]
        .sum()
        .reset_index()
    )
    for _, r in daily.iterrows():
        if float(r["Ώρες"]) > max_daily_hours + 1e-6:
            viols.append({
                "Είδος": "Υπέρβαση ημερήσιων ωρών",
                "Υπάλληλος": r["Υπάλληλος"],
                "Ημερομηνία": r["Ημερομηνία"],
                "Λεπτομέρειες": f"{float(r['Ώρες']):.2f}h > {max_daily_hours}h",
            })

    # Weekly cap
    sched["_week"] = sched["Ημερομηνία"].apply(_iso_week_key)
    weekly = (
        sched.groupby(["Υπάλληλος", "_week"])["Ώρες"]
        .sum()
        .reset_index()
    )
    for _, r in weekly.iterrows():
        if float(r["Ώρες"]) > weekly_hours_cap + 1e-6:
            wk = r["_week"]
            viols.append({
                "Είδος": "Υπέρβαση εβδομαδιαίων ωρών",
                "Υπάλληλος": r["Υπάλληλος"],
                "Ημερομηνία": f"ISO week {wk[1]} ({wk[0]})",
                "Λεπτομέρειες": f"{float(r['Ώρες']):.2f}h > {weekly_hours_cap}h",
            })

    # Daily rest (across consecutive days)
    for emp, g in sched.groupby("Υπάλληλος"):
        g = g.sort_values(["Ημερομηνία", "Βάρδια"])
        by_date = defaultdict(list)
        for _, row in g.iterrows():
            by_date[row["Ημερομηνία"]].append(row["Βάρδια"])
        dates = sorted(by_date.keys())
        for i, d in enumerate(dates[:-1]):
            dn = dates[i + 1]
            # next-day earliest start (skip unknown shifts)
            next_starts = [sh for sh in (_shift_start_hour(s) for s in by_date[dn]) if sh is not None]
            if not next_starts:
                continue
            next_start = min(next_starts)
            # previous-day latest end (skip unknown shifts)
            prev_ends = [eh for eh in (_shift_end_hour(s) for s in by_date[d]) if eh is not None]
            prev_end = max(prev_ends) if prev_ends else 0.0
            rest = _rest_between(d, prev_end, dn, next_start)
            if rest < min_daily_rest:
                viols.append({
                    "Είδος": "Ανεπαρκής ημερήσια ανάπαυση",
                    "Υπάλληλος": emp,
                    "Ημερομηνία": f"{d} → {dn}",
                    "Λεπτομέρειες": f"{rest:.2f}h < {min_daily_rest}h",
                })

    out = pd.DataFrame(viols, columns=["Είδος", "Υπάλληλος", "Ημερομηνία", "Λεπτομέρειες"])
    return out


# ---------------------------
# Generators
# ---------------------------

def _score_candidate(
    emp: Dict,
    role: str,
    d: date,
    shift: str,
    assigned_hours_today: float,
    assigned_hours_week: float,
    max_daily_hours: float,
    weekly_hours_cap: float,
) -> float:
    """
    Simple heuristic:
      + Prefer lower weekly hours first (fairness)
      + Avoid hitting daily cap
    """
    if assigned_hours_today >= max_daily_hours - 1e-6:
        return -math.inf
    if assigned_hours_week >= weekly_hours_cap - 1e-6:
        return -math.inf
    base = -assigned_hours_week  # fewer hours → higher score
    # Light bonus if specifically skilled for role; assume emp["roles"] optional
    if role and (emp.get("role") == role or role in set(emp.get("roles", []))):
        base += 0.25
    return base


def _iter_days(start_date: date, days_count: int) -> Iterable[date]:
    for i in range(days_count):
        yield start_date + timedelta(days=i)


def generate_schedule_v2(
    start_date: date,
    employees: List[Dict],
    active_shifts: List[str],
    roles: List[str],
    rules: Dict,
    role_settings: Dict,
    days_count: int,
    work_model: str,
):
    """
    Greedy generator with rest/daily/weekly caps.
    Returns (schedule_df, missing_df)
    """
    max_daily_hours, weekly_hours_cap = _rule_caps(rules, work_model)
    min_daily_rest = _min_daily_rest_rule(rules)

    assigned: List[Assignment] = []
    missing_rows: List[Dict] = []

    # tracking
    last_work_by_emp: Dict[str, Tuple[date, float]] = {}  # name -> (date, end_hour)
    daily_hours: Dict[Tuple[str, date], float] = defaultdict(float)
    weekly_hours: Dict[Tuple[str, Tuple[int, int]], float] = defaultdict(float)

    # Normalized employee list
    emps = []
    for e in employees:
        name = e.get("name") or e.get("Νομ/Επ") or e.get("employee") or "?"
        main_role = e.get("role") or e.get("Ρόλος")
        roles_set = set(e.get("roles", []))
        if main_role:
            roles_set.add(main_role)
        emps.append({**e, "name": name, "role": main_role, "roles": list(roles_set)})

    for d in _iter_days(start_date, days_count):
        day_label = _day_label(d)
        for shift in active_shifts:
            # Soft-validate unknown shifts: skip fill and record missing needs
            if _require_shift(shift, strict=False) is None:
                for role in roles:
                    need = max(0, _extract_need(role_settings, d, shift, role))
                    if need > 0:
                        missing_rows.append({
                            "Ημέρα": day_label, "Ημερομηνία": str(d), "Βάρδια": shift,
                            "Ρόλος": role, "Λείπουν": need, "Αιτία": "Άγνωστη βάρδια (χωρίς ώρες)"
                        })
                continue

            for role in roles:
                need = int(max(0, _extract_need(role_settings, d, shift, role)))
                if need <= 0:
                    continue

                already = sum(1 for a in assigned if a.date == d and a.shift == shift and a.role == role)
                remaining = max(0, need - already)
                if remaining == 0:
                    continue

                # Candidate pool
                candidates = [
                    e for e in emps
                    if (role in set(e.get("roles", [])) or e.get("role") == role)
                    and _employee_available(e, d, shift)
                ]
                # Greedy picks
                for _ in range(remaining):
                    best = None
                    best_score = -math.inf
                    for e in candidates:
                        # Rest check
                        start_hr = _shift_start_hour(shift)
                        end_hr = _shift_end_hour(shift)
                        if start_hr is None or end_hr is None:
                            continue  # unknown shift would have been gated earlier

                        if e["name"] in last_work_by_emp:
                            prev_date, prev_end = last_work_by_emp[e["name"]]
                            rest = _rest_between(prev_date, prev_end, d, start_hr)
                            if rest < min_daily_rest:
                                continue

                        hrs_today = daily_hours[(e["name"], d)]
                        hrs_week = weekly_hours[(e["name"], _iso_week_key(d))]
                        score = _score_candidate(
                            e, role, d, shift,
                            hrs_today, hrs_week,
                            max_daily_hours, weekly_hours_cap
                        )
                        if score > best_score:
                            best = e
                            best_score = score

                    if best is None:
                        # Couldn't fill this slot
                        missing_rows.append({
                            "Ημέρα": day_label, "Ημερομηνία": str(d), "Βάρδια": shift,
                            "Ρόλος": role, "Λείπουν": 1, "Αιτία": "Μη διαθέσιμο προσωπικό ή περιορισμοί ωρών/ανάπαυσης"
                        })
                        continue

                    hrs = float(_shift_len(shift))
                    asg = Assignment(d, shift, best["name"], role, hrs)
                    assigned.append(asg)

                    # update trackers
                    last_work_by_emp[best["name"]] = (d, _shift_end_hour(shift) or 0.0)
                    daily_hours[(best["name"], d)] += hrs
                    weekly_hours[(best["name"], _iso_week_key(d))] += hrs

    df = pd.DataFrame([{
        "Ημερομηνία": a.date,
        "Βάρδια": a.shift,
        "Υπάλληλος": a.employee,
        "Ρόλος": a.role,
        "Ώρες": a.hours,
    } for a in assigned])

    missing_df = pd.DataFrame(missing_rows, columns=["Ημέρα", "Ημερομηνία", "Βάρδια", "Ρόλος", "Λείπουν", "Αιτία"])
    return df, missing_df


def auto_fix_schedule(
    schedule_df: pd.DataFrame,
    start_date: date,
    employees: List[Dict],
    active_shifts: List[str],
    roles: List[str],
    rules: Dict,
    role_settings: Dict,
    days_count: int,
    work_model: str,
):
    """
    Attempts to fill gaps in an existing schedule without breaking constraints.
    Returns (fixed_df, missing_df, violations_df)
    """
    max_daily_hours, weekly_hours_cap = _rule_caps(rules, work_model)
    min_daily_rest = _min_daily_rest_rule(rules)

    # Normalize existing schedule
    sched = schedule_df.copy()
    if sched.empty:
        sched = pd.DataFrame(columns=["Ημερομηνία", "Βάρδια", "Υπάλληλος", "Ρόλος", "Ώρες"])
    if "Ώρες" not in sched.columns:
        sched["Ώρες"] = 0.0
    if not pd.api.types.is_datetime64_any_dtype(sched["Ημερομηνία"]):
        sched["Ημερομηνία"] = pd.to_datetime(sched["Ημερομηνία"]).dt.date

    # Fast lookup of existing counts per (date, shift, role)
    existing_counts = sched.groupby(["Ημερομηνία", "Βάρδια", "Ρόλος"])["Υπάλληλος"].count().to_dict()

    # trackers
    last_work_by_emp: Dict[str, Tuple[date, float]] = {}
    daily_hours: Dict[Tuple[str, date], float] = defaultdict(float)
    weekly_hours: Dict[Tuple[str, Tuple[int, int]], float] = defaultdict(float)

    # Seed trackers from existing schedule
    for _, r in sched.iterrows():
        nm = r["Υπάλληλος"]
        d = r["Ημερομηνία"]
        sh = r["Βάρδια"]
        hrs = float(r.get("Ώρες", _shift_len(sh)))
        daily_hours[(nm, d)] += hrs
        weekly_hours[(nm, _iso_week_key(d))] += hrs
        end_hr = _shift_end_hour(sh)
        if end_hr is not None:
            prev = last_work_by_emp.get(nm)
            if prev is None or (datetime.combine(d, datetime.min.time()) + timedelta(hours=end_hr)) > \
                    (datetime.combine(prev[0], datetime.min.time()) + timedelta(hours=prev[1])):
                last_work_by_emp[nm] = (d, end_hr)

    # Normalized employees
    emps = []
    for e in employees:
        name = e.get("name") or e.get("Νομ/Επ") or e.get("employee") or "?"
        main_role = e.get("role") or e.get("Ρόλος")
        roles_set = set(e.get("roles", []))
        if main_role:
            roles_set.add(main_role)
        emps.append({**e, "name": name, "role": main_role, "roles": list(roles_set)})

    missing_rows: List[Dict] = []
    day0 = start_date

    for d in _iter_days(day0, days_count):
        day_label = _day_label(d)
        for shift in active_shifts:
            # Skip unknown shifts but surface needs
            if _require_shift(shift, strict=False) is None:
                for role in roles:
                    need = int(max(0, _extract_need(role_settings, d, shift, role)))
                    cur = existing_counts.get((d, shift, role), 0)
                    gap = max(0, need - cur)
                    if gap > 0:
                        missing_rows.append({
                            "Ημέρα": day_label, "Ημερομηνία": str(d), "Βάρδια": shift,
                            "Ρόλος": role, "Λείπουν": gap, "Αιτία": "Άγνωστη βάρδια (χωρίς ώρες)"
                        })
                continue

            for role in roles:
                need = int(max(0, _extract_need(role_settings, d, shift, role)))
                cur = int(existing_counts.get((d, shift, role), 0))
                gap = max(0, need - cur)
                if gap == 0:
                    continue

                # Candidate pool
                candidates = [
                    e for e in emps
                    if (role in set(e.get("roles", [])) or e.get("role") == role)
                    and _employee_available(e, d, shift)
                ]

                for _ in range(gap):
                    best = None
                    best_score = -math.inf
                    start_hr = _shift_start_hour(shift)
                    end_hr = _shift_end_hour(shift)
                    if start_hr is None or end_hr is None:
                        break

                    for e in candidates:
                        if e["name"] in set(sched["Υπάλληλος"]):
                            # allow multiple assignments across days; no per-day duplicates check here
                            pass
                        # Rest check
                        if e["name"] in last_work_by_emp:
                            prev_date, prev_end = last_work_by_emp[e["name"]]
                            rest = _rest_between(prev_date, prev_end, d, start_hr)
                            if rest < min_daily_rest:
                                continue

                        hrs_today = daily_hours[(e["name"], d)]
                        hrs_week = weekly_hours[(e["name"], _iso_week_key(d))]
                        score = _score_candidate(
                            e, role, d, shift,
                            hrs_today, hrs_week,
                            max_daily_hours, weekly_hours_cap
                        )
                        if score > best_score:
                            best = e
                            best_score = score

                    if best is None:
                        missing_rows.append({
                            "Ημέρα": day_label, "Ημερομηνία": str(d), "Βάρδια": shift,
                            "Ρόλος": role, "Λείπουν": 1, "Αιτία": "Μη διαθέσιμο προσωπικό ή περιορισμοί ωρών/ανάπαυσης"
                        })
                        continue

                    hrs = float(_shift_len(shift))
                    new_row = {
                        "Ημερομηνία": d, "Βάρδια": shift, "Υπάλληλος": best["name"], "Ρόλος": role, "Ώρες": hrs
                    }
                    sched = pd.concat([sched, pd.DataFrame([new_row])], ignore_index=True)

                    existing_counts[(d, shift, role)] = existing_counts.get((d, shift, role), 0) + 1
                    last_work_by_emp[best["name"]] = (d, end_hr or 0.0)
                    daily_hours[(best["name"], d)] += hrs
                    weekly_hours[(best["name"], _iso_week_key(d))] += hrs

    violations = check_violations(sched, rules=rules, work_model=work_model)
    missing_df = pd.DataFrame(
        missing_rows, columns=["Ημέρα", "Ημερομηνία", "Βάρδια", "Ρόλος", "Λείπουν", "Αιτία"]
    )
    return sched, missing_df, violations


# ---------------------------
# MILP optimizer (optional)
# ---------------------------

def generate_schedule_opt(
    start_date: date,
    employees: List[Dict],
    active_shifts: List[str],
    roles: List[str],
    rules: Dict,
    role_settings: Dict,
    days_count: int,
    work_model: str,
):
    """
    MILP optimizer if pulp is available; otherwise falls back to generate_schedule_v2.
    Returns (schedule_df, missing_df)
    """
    try:
        import pulp  # type: ignore
    except Exception:
        # Fallback
        return generate_schedule_v2(
            start_date, employees, active_shifts, roles, rules, role_settings, days_count, work_model
        )

    max_daily_hours, weekly_hours_cap = _rule_caps(rules, work_model)
    min_daily_rest = _min_daily_rest_rule(rules)

    # Soft-skip unknown shifts entirely (they'll show as missing)
    known_shifts = [s for s in active_shifts if _require_shift(s, strict=False) is not None]

    # Build index sets
    days = list(_iter_days(start_date, days_count))
    E = []
    for e in employees:
        name = e.get("name") or e.get("Νομ/Επ") or e.get("employee") or "?"
        main_role = e.get("role") or e.get("Ρόλος")
        roles_set = set(e.get("roles", []))
        if main_role:
            roles_set.add(main_role)
        E.append({**e, "name": name, "role": main_role, "roles": list(roles_set)})

    # Decision vars: x[d, s, r, e] ∈ {0,1}
    prob = pulp.LpProblem("schedule", pulp.LpMaximize)
    X = {}
    for d in days:
        for s in known_shifts:
            for r in roles:
                for e in E:
                    feas = (r in set(e["roles"]) or e["role"] == r) and _employee_available(e, d, s)
                    X[(d, s, r, e["name"])] = pulp.LpVariable(
                        f"x_{d}_{s}_{r}_{e['name']}", lowBound=0, upBound=1, cat="Binary"
                    ) if feas else None

    # Objective: cover as many required slots as possible
    prob += pulp.lpSum(
        X[(d, s, r, e["name"])]
        for d in days for s in known_shifts for r in roles for e in E
        if X[(d, s, r, e["name"])] is not None
    )

    # Coverage constraints
    for d in days:
        for s in known_shifts:
            for r in roles:
                need = int(max(0, _extract_need(role_settings, d, s, r)))
                if need <= 0:
                    continue
                prob += (
                    pulp.lpSum(
                        X[(d, s, r, e["name"])] for e in E
                        if X[(d, s, r, e["name"])] is not None
                    ) <= need
                )

    # Daily & weekly hour caps
    for e in E:
        for d in days:
            prob += (
                pulp.lpSum(
                    X[(d, s, r, e["name"])] * _shift_len(s)
                    for s in known_shifts for r in roles
                    if X[(d, s, r, e["name"])] is not None
                ) <= max_daily_hours
            )
        # Weekly caps (by ISO week)
        weeks = defaultdict(list)
        for d in days:
            weeks[_iso_week_key(d)].append(d)
        for wk, dlist in weeks.items():
            prob += (
                pulp.lpSum(
                    X[(dd, s, r, e["name"])] * _shift_len(s)
                    for dd in dlist for s in known_shifts for r in roles
                    if X[(dd, s, r, e["name"])] is not None
                ) <= weekly_hours_cap
            )

    # Daily rest between consecutive days (only partial: forbid assignments that would violate rest)
    for e in E:
        for i in range(len(days) - 1):
            d = days[i]
            dn = days[i + 1]
            for s_prev in known_shifts:
                for s_next in known_shifts:
                    end_prev = _shift_end_hour(s_prev)
                    start_next = _shift_start_hour(s_next)
                    if end_prev is None or start_next is None:
                        continue
                    if _rest_between(d, end_prev, dn, start_next) < min_daily_rest:
                        for r_prev in roles:
                            for r_next in roles:
                                v1 = X.get((d, s_prev, r_prev, e["name"]))
                                v2 = X.get((dn, s_next, r_next, e["name"]))
                                if v1 is not None and v2 is not None:
                                    prob += v1 + v2 <= 1

    # Solve
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    assigned: List[Assignment] = []
    for (d, s, r, en), var in X.items():
        if var is not None and var.value() and var.value() > 0.5:
            assigned.append(Assignment(d, s, en, r, _shift_len(s)))

    df = pd.DataFrame([{
        "Ημερομηνία": a.date,
        "Βάρδια": a.shift,
        "Υπάλληλος": a.employee,
        "Ρόλος": a.role,
        "Ώρες": a.hours,
    } for a in assigned])

    # Build missing_df from unmet needs
    missing_rows: List[Dict] = []
    for d in days:
        dl = _day_label(d)
        for s in active_shifts:
            if s not in known_shifts:
                for r in roles:
                    need = int(max(0, _extract_need(role_settings, d, s, r)))
                    if need > 0:
                        missing_rows.append({
                            "Ημέρα": dl, "Ημερομηνία": str(d), "Βάρδια": s,
                            "Ρόλος": r, "Λείπουν": need, "Αιτία": "Άγνωστη βάρδια (χωρίς ώρες)"
                        })
                continue
            for r in roles:
                need = int(max(0, _extract_need(role_settings, d, s, r)))
                have = int(((df["Ημερομηνία"] == d) & (df["Βάρδια"] == s) & (df["Ρόλος"] == r)).sum())
                gap = max(0, need - have)
                if gap > 0:
                    missing_rows.append({
                        "Ημέρα": dl, "Ημερομηνία": str(d), "Βάρδια": s,
                        "Ρόλος": r, "Λείπουν": gap, "Αιτία": "Μη διαθέσιμο προσωπικό ή περιορισμοί"
                    })

    missing_df = pd.DataFrame(missing_rows, columns=["Ημέρα", "Ημερομηνία", "Βάρδια", "Ρόλος", "Λείπουν", "Αιτία"])
    return df, missing_df
