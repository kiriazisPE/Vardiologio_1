# -*- coding: utf-8 -*-
"""
Advanced shift generator with scoring + rule checks and an auto-fix pass.
Designed to work with the Streamlit UI (DataFrame in session_state).

Public API:
  - generate_schedule_v2(...)
  - auto_fix_schedule(...)
  - generate_schedule_opt(...)
  - check_violations(...)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple
from collections import defaultdict, Counter
import datetime as dt
import pandas as pd
import re
from constants import DAYS, SHIFT_TIMES

# AI-powered scheduling
try:
    from ai_scheduler import (
        analyze_schedule_with_ai,
        optimize_employee_assignments_with_ai,
        resolve_conflicts_with_ai
    )
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    print("AI scheduler not available")

__all__ = [
    "generate_schedule_v2",
    "auto_fix_schedule",
    "generate_schedule_opt",
    "check_violations",
    "generate_schedule_smart",
    "generate_schedule",
]

# ----------------------------
# Helpers & Data structures
# ----------------------------

def generate_schedule_smart(
    start_date,
    employees,
    active_shifts,
    roles,
    rules,
    role_settings,
    days_count,
    work_model="5ήμερο",
    weights=None,
):
    """
    Prefer MILP optimizer if PuLP is available; otherwise fall back to the greedy v2.
    Also guards any optimizer build/solve exceptions to ensure a safe fallback.
    """
    try:
        import pulp  # noqa: F401
    except Exception as e:
        import traceback
        print("PuLP not importable; using greedy v2:", e)
        traceback.print_exc()
        return generate_schedule_v2(
            start_date, employees, active_shifts, roles, rules, role_settings, days_count, work_model
        )
    # PuLP present — attempt optimizer but guard failures explicitly
    try:
        return generate_schedule_opt(
            start_date, employees, active_shifts, roles, rules, role_settings, days_count, work_model, weights
        )
    except Exception as e:
        import traceback
        print("MILP scheduling raised; falling back to greedy v2:", e)
        traceback.print_exc()
        return generate_schedule_v2(
            start_date, employees, active_shifts, roles, rules, role_settings, days_count, work_model
        )



def _shift_len(shift: str) -> int:
    """Return the (positive) hours of a shift, handling wrap-around (e.g., 22→06)."""
    s, e = SHIFT_TIMES.get(shift, (9, 17))
    return (24 - s + e) if e < s else (e - s)

def _date(obj) -> dt.date:
    return pd.to_datetime(obj).date()

def _weekday_name(d: dt.date) -> str:
    return DAYS[d.weekday()]

def _shift_start_hour(shift: str) -> int:
    return SHIFT_TIMES.get(shift, (9, 17))[0]

def _shift_end_hour(shift: str) -> int:
    s, e = SHIFT_TIMES.get(shift, (9, 17))
    return e if e >= s else e + 24  # allow wrap past midnight (e.g., 02:00 → 26)

@dataclass(frozen=True)
class Employee:
    id: int
    name: str
    roles: List[str]
    availability: List[str]

@dataclass(frozen=True)
class Assignment:
    date: dt.date
    shift: str
    employee: str
    role: str
    hours: int


# ----------------------------
# Rule checks
# ----------------------------


def check_violations(schedule_df, rules: dict, work_model: str = "5ήμερο"):
    import pandas as pd
    from datetime import datetime, timedelta

    # --- Rule parameters (by work model) ---
    wm = (work_model or "").strip()
    if wm == "5ήμερο":
        max_daily_hours = int(rules.get("max_daily_hours_5days", 8))
        weekly_hours_cap = int(rules.get("weekly_hours_5days", 40))
    elif wm == "6ήμερο":
        max_daily_hours = int(rules.get("max_daily_hours_6days", 9))
        weekly_hours_cap = int(rules.get("weekly_hours_6days", 48))
    else:  # 7ήμερο
        max_daily_hours = int(rules.get("max_daily_hours_7days", 9))
        weekly_hours_cap = int(rules.get("weekly_hours_7days", 56))

    min_daily_rest = int(rules.get("min_daily_rest", 11))
    max_consecutive_days = int(rules.get("max_consecutive_days", 6))
    monthly_hours_cap = int(rules.get("monthly_hours", 160))

    # --- Normalize dates/hours ---
    df = schedule_df.copy()
    df["Ημερομηνία"] = pd.to_datetime(df["Ημερομηνία"]).dt.date
    if "Ώρες" not in df.columns:
        # Fallback if caller didn't include hours per row
        df["Ώρες"] = 0.0

    # De-duplicate exact duplicate assignment rows to avoid double-counting in aggregations
    df = df.drop_duplicates(subset=[c for c in ["Υπάλληλος","Ημερομηνία","Βάρδια","Ρόλος","Ώρες"] if c in df.columns])
    violations = []

    # --- A) Max daily hours per employee ---
    daily_hours = df.groupby(["Υπάλληλος", "Ημερομηνία"], as_index=False)["Ώρες"].sum()
    for _, row in daily_hours.iterrows():
        if row["Ώρες"] > max_daily_hours:
            violations.append({
                "Ημερομηνία": row["Ημερομηνία"],
                "Υπάλληλος": row["Υπάλληλος"],
                "Βάρδια": "",
                "Ρόλος": "",
                "Rule": "max_daily_hours",
                "Details": f"{row['Ώρες']}h > {max_daily_hours}h",
                "Severity": "high",
            })

    # --- B) Weekly hours cap (ISO week) ---
    dt_series = pd.to_datetime(df["Ημερομηνία"])
    df["_iso_year"] = dt_series.dt.isocalendar().year
    df["_iso_week"] = dt_series.dt.isocalendar().week
    weekly_hours = df.groupby(["Υπάλληλος", "_iso_year", "_iso_week"], as_index=False)["Ώρες"].sum()
    for _, row in weekly_hours.iterrows():
        if row["Ώρες"] > weekly_hours_cap:
            violations.append({
                "Ημερομηνία": None,
                "Υπάλληλος": row["Υπάλληλος"],
                "Βάρδια": "",
                "Ρόλος": "",
                "Rule": "weekly_hours_cap",
                "Details": f"{row['Ώρες']}h > {weekly_hours_cap}h (ISO week {int(row['_iso_week'])})",
                "Severity": "high",
            })

    # --- C) Monthly hours cap (calendar month) ---
    df["_month"] = pd.to_datetime(df["Ημερομηνία"]).dt.to_period("M")
    monthly_hours = df.groupby(["Υπάλληλος", "_month"], as_index=False)["Ώρες"].sum()
    for _, row in monthly_hours.iterrows():
        if row["Ώρες"] > monthly_hours_cap:
            violations.append({
                "Ημερομηνία": None,
                "Υπάλληλος": row["Υπάλληλος"],
                "Βάρδια": "",
                "Ρόλος": "",
                "Rule": "monthly_hours_cap",
                "Details": f"{row['Ώρες']}h > {monthly_hours_cap}h ({row['_month']})",
                "Severity": "medium",
            })

    # --- D) Max consecutive working days ---
    for emp, sub in df.groupby("Υπάλληλος"):
        worked_days = sorted(set(sub.loc[sub["Ώρες"] > 0, "Ημερομηνία"]))
        if not worked_days:
            continue
        streak = 1
        for i in range(1, len(worked_days)):
            if worked_days[i] == worked_days[i - 1] + timedelta(days=1):
                streak += 1
                if streak > max_consecutive_days:
                    violations.append({
                        "Ημερομηνία": worked_days[i],
                        "Υπάλληλος": emp,
                        "Βάρδια": "",
                        "Ρόλος": "",
                        "Rule": "max_consecutive_days",
                        "Details": f"{streak} days > {max_consecutive_days}",
                        "Severity": "medium",
                    })
            else:
                streak = 1

    # --- E) Min daily rest between shifts (if start/end columns exist) ---
    start_cols = [c for c in df.columns if c.lower() in ("start", "έναρξη", "starttime")]
    end_cols   = [c for c in df.columns if c.lower() in ("end", "τέλος", "endtime")]
    if start_cols and end_cols:
        s_col, e_col = start_cols[0], end_cols[0]

        # Expecting times as HH:MM or datetime; coerce to datetimes anchored on date
        def _coerce_dt(d, t):
            """Return (datetime_or_none, is_valid). Accepts:
            - 'HH:MM', 'H:MM', 'HH.MM', 'H.M', 'HH', 'H'
            - integers/floats (hours), strings with decimal separator '.' or ',' interpreted as hours (e.g., 9.5 => 09:30)
            - datetime
            If parsing fails or minutes are invalid, returns (None, False).
            """
            from datetime import datetime
            import math
            if pd.isna(t):
                return None, False
            if isinstance(t, datetime):
                return t, True
            try:
                # Numeric types (including strings like '9.5')
                if isinstance(t, (int, float)):
                    hh = int(math.floor(float(t)))
                    mm = int(round((float(t) - hh) * 60))
                    if mm == 60:
                        hh += 1; mm = 0
                    if not (0 <= hh <= 48 and 0 <= mm < 60):
                        return None, False
                    return datetime(d.year, d.month, d.day, int(hh) % 24, mm), True
                s = str(t).strip()
                s_num = s.replace(',', '.')
                # If purely numeric with optional decimal
                if re.fullmatch(r"\d+(?:[\.,]\d+)?", s):
                    val = float(s_num)
                    hh = int(math.floor(val))
                    mm = int(round((val - hh) * 60))
                    if mm == 60:
                        hh += 1; mm = 0
                    if not (0 <= hh <= 48 and 0 <= mm < 60):
                        return None, False
                    return datetime(d.year, d.month, d.day, int(hh) % 24, mm), True
                # Replace '.' with ':' if it's a separator variant like '9.00'
                s = s.replace('.', ':').replace(',', ':')
                parts = s.split(':')
                if len(parts) == 1:
                    hh, mm = int(parts[0]), 0
                else:
                    hh, mm = int(parts[0]), int(parts[1])
                if not (0 <= hh <= 48 and 0 <= mm < 60):  # basic sanity
                    return None, False
                return datetime(d.year, d.month, d.day, int(hh) % 24, mm), True
            except Exception:
                return None, False

        # Now check rest periods between consecutive shifts for each employee
        for emp, sub in df.groupby("Υπάλληλος"):
            sub_sorted = sub.sort_values("Ημερομηνία").copy()
            for i in range(len(sub_sorted) - 1):
                row1 = sub_sorted.iloc[i]
                row2 = sub_sorted.iloc[i + 1]
                
                end1, valid_e = _coerce_dt(row1["Ημερομηνία"], row1[e_col])
                start2, valid_s = _coerce_dt(row2["Ημερομηνία"], row2[s_col])
                
                if not (valid_e and valid_s):
                    continue
                
                # Handle shifts that span midnight
                if end1 and start2:
                    # If end time is in next day, adjust
                    if end1.time() < start2.time() and row2["Ημερομηνία"] == row1["Ημερομηνία"]:
                        end1 = end1 + timedelta(days=1)
                    
                    rest_hours = (start2 - end1).total_seconds() / 3600
                    
                    if rest_hours < min_daily_rest and rest_hours >= 0:
                        violations.append({
                            "Ημερομηνία": row2["Ημερομηνία"],
                            "Υπάλληλος": emp,
                            "Βάρδια": row2.get("Βάρδια", ""),
                            "Ρόλος": row2.get("Ρόλος", ""),
                            "Rule": "min_daily_rest",
                            "Details": f"{rest_hours:.1f}h rest < {min_daily_rest}h required",
                            "Severity": "high",
                        })

    # Return as DataFrame for UI consumption
    return pd.DataFrame(violations)


# ----------------------------
# Greedy generator (v2)
# ----------------------------

def generate_schedule_v2(
    start_date,
    employees: List[dict],
    active_shifts: List[str],
    roles: List[str],
    rules: Dict,
    role_settings: Dict,
    days_count: int,
    work_model: str = "5ήμερο",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Smart greedy scheduler with scoring:
      - honors availability/roles
      - respects daily/weekly limits and min rest while assigning
      - prioritizes role priority, preferred shifts, weekly fairness

    Returns (schedule_df, missing_df)
    """
    if not employees:
        raise ValueError("No employees to schedule.")
    if days_count <= 0:
        raise ValueError("days_count must be > 0.")

    start = _date(start_date)

    emps = [
        Employee(
            id=i,
            name=e["name"],
            roles=e.get("roles", []) or [],
            availability=e.get("availability", []) or [],
        )
        for i, e in enumerate(employees)
    ]

    min_per = {r: max(0, int(role_settings.get(r, {}).get("min_per_shift", 1))) for r in roles}
    role_prio = {r: int(role_settings.get(r, {}).get("priority", 5)) for r in roles}
    role_pref = {r: list(role_settings.get(r, {}).get("preferred_shifts", [])) for r in roles}

    assigned = []
    hours_by_emp_week: Dict[str, Counter] = defaultdict(Counter)
    last_shift_by_emp: Dict[str, tuple[dt.date, str]] = {}

    wm = work_model.strip()
    if wm == "5ήμερο":
        max_daily_hours = int(rules.get("max_daily_hours_5days", 8))
        weekly_hours_cap = int(rules.get("weekly_hours_5days", 40))
    elif wm == "6ήμερο":
        max_daily_hours = int(rules.get("max_daily_hours_6days", 9))
        weekly_hours_cap = int(rules.get("weekly_hours_6days", 48))
    else:  # 7ήμερο
        max_daily_hours = int(rules.get("max_daily_hours_7days", 9))
        weekly_hours_cap = int(rules.get("weekly_hours_7days", 56))
    min_daily_rest = int(rules.get("min_daily_rest", 11))
    max_consecutive_days = int(rules.get("max_consecutive_days", 6))

    def week_of_iso(d: dt.date) -> int:
        return d.isocalendar().week

    def can_assign(emp: Employee, d: dt.date, shift: str, role: str) -> bool:
        if shift not in emp.availability or role not in emp.roles:
            return False
        # daily cap
        cur_hours = sum(a.hours for a in assigned if a.employee == emp.name and a.date == d)
        if cur_hours + _shift_len(shift) > max_daily_hours:
            return False
        # weekly cap
        wk = week_of_iso(d)
        if hours_by_emp_week[emp.name][wk] + _shift_len(shift) > weekly_hours_cap:
            return False
        
        # min rest against previous day (compute precisely across midnight)
        if emp.name in last_shift_by_emp and last_shift_by_emp[emp.name][0] == d - dt.timedelta(days=1):
            prev_date, prev_shift = last_shift_by_emp[emp.name]
            end_h = _shift_end_hour(prev_shift)  # may be > 24 if wraps
            # Anchor end on previous date (add a day if it wraps past midnight)
            prev_end_dt = dt.datetime(prev_date.year, prev_date.month, prev_date.day, end_h % 24)
            if end_h >= 24:
                prev_end_dt += dt.timedelta(days=1)
            start_h = _shift_start_hour(shift)
            next_start_dt = dt.datetime(d.year, d.month, d.day, start_h)
            hours_rest = (next_start_dt - prev_end_dt).total_seconds() / 3600.0
            if hours_rest < min_daily_rest:
                return False

        return True

    def score(emp: Employee, d: dt.date, shift: str, role: str) -> float:
        # higher is better
        sc = 0.0
        # Role priority: lower number = more important
        sc += max(0, 10 - role_prio.get(role, 5))
        # Preferred shifts for that role
        if shift in role_pref.get(role, []):
            sc += 3.0
        # Weekly fairness (prefer lower current weekly hours)
        sc += max(0, 20 - hours_by_emp_week[emp.name][week_of_iso(d)]) * 0.2
        # Prefer employees not yet used that day
        if emp.name not in {a.employee for a in assigned if a.date == d}:
            sc += 1.0
        return sc

    missing_rows = []
    for i in range(days_count):
        d = start + dt.timedelta(days=i)
        day_label = _weekday_name(d)
        for shift in active_shifts:
            for role in roles:
                need = min_per.get(role, 0)
                if need <= 0:
                    continue
                picks = []
                for _ in range(need):
                    candidates = [e for e in emps if can_assign(e, d, shift, role)]
                    if not candidates:
                        missing_rows.append({
                            "Ημέρα": day_label,
                            "Ημερομηνία": str(d),
                            "Βάρδια": shift,
                            "Ρόλος": role,
                            "Λείπουν": max(1, need - len(picks)),
                        })
                        break
                    
                    # Use AI to select best employee if available
                    if AI_AVAILABLE and len(candidates) > 1:
                        try:
                            temp_df = pd.DataFrame([{
                                "Ημερομηνία": str(a.date),
                                "Βάρδια": a.shift,
                                "Υπάλληλος": a.employee,
                                "Ρόλος": a.role,
                                "Ώρες": a.hours
                            } for a in assigned])
                            
                            candidate_dicts = [
                                {"name": e.name, "roles": e.roles, "availability": e.availability}
                                for e in candidates
                            ]
                            
                            ai_selected = optimize_employee_assignments_with_ai(
                                d, shift, role, candidate_dicts, temp_df, rules, work_model
                            )
                            
                            # Find best from AI suggestions
                            best = next((e for e in candidates if e.name in ai_selected), None)
                            if not best:
                                best = max(candidates, key=lambda e: score(e, d, shift, role))
                        except Exception as e:
                            print(f"AI selection error: {e}")
                            best = max(candidates, key=lambda e: score(e, d, shift, role))
                    else:
                        best = max(candidates, key=lambda e: score(e, d, shift, role))
                    
                    hrs = _shift_len(shift)
                    assigned.append(Assignment(d, shift, best.name, role, hrs))
                    hours_by_emp_week[best.name][week_of_iso(d)] += hrs
                    last_shift_by_emp[best.name] = (d, shift)
                    picks.append(best.name)

    sched_df = pd.DataFrame(
        [{
            "Ημέρα": _weekday_name(a.date),
            "Ημερομηνία": str(a.date),
            "Βάρδια": a.shift,
            "Υπάλληλος": a.employee,
            "Ρόλος": a.role,
            "Ώρες": a.hours,
        } for a in assigned],
        columns=["Ημέρα", "Ημερομηνία", "Βάρδια", "Υπάλληλος", "Ρόλος", "Ώρες"],
    )

    missing_df = pd.DataFrame(missing_rows, columns=["Ημέρα", "Ημερομηνία", "Βάρδια", "Ρόλος", "Λείπουν"])
    return sched_df, missing_df


# ----------------------------
# Auto-fix pass
# ----------------------------

def auto_fix_schedule(
    df: pd.DataFrame,
    employees: List[dict],
    active_shifts: List[str],
    roles: List[str],
    rules: Dict,
    role_settings: Dict,
    work_model: str = "5ήμερο",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Attempts to fill under-staffed (date,shift,role) slots by choosing eligible,
    low-load employees; then re-runs rule checks.
    """
    if df is None or df.empty:
        return df, pd.DataFrame()

    sched = df.copy()
    sched["Ημερομηνία"] = pd.to_datetime(sched["Ημερομηνία"]).dt.date
    sched["Ώρες"] = sched["Ώρες"].astype(int)

    emps = [
        Employee(
            id=i,
            name=e["name"],
            roles=e.get("roles", []) or [],
            availability=e.get("availability", []) or [],
        )
        for i, e in enumerate(employees)
    ]

    min_per = {r: max(0, int(role_settings.get(r, {}).get("min_per_shift", 1))) for r in roles}
    grouped = sched.groupby(["Ημερομηνία", "Βάρδια", "Ρόλος"]).size().reset_index(name="count")
    existing = {(r["Ημερομηνία"], r["Βάρδια"], r["Ρόλος"]): r["count"] for _, r in grouped.iterrows()}

    rows_to_add = []
    all_dates = sorted(sched["Ημερομηνία"].unique())
    for d in all_dates:
        for shift in active_shifts:
            for role in roles:
                cur = existing.get((d, shift, role), 0)
                need = max(0, min_per.get(role, 0) - cur)
                for _ in range(need):
                    # Eligible candidates
                    candidates = []
                    for e in emps:
                        if shift not in e.availability or role not in e.roles:
                            continue
                        clash = ((sched["Ημερομηνία"] == d) &
                                 (sched["Βάρδια"] == shift) &
                                 (sched["Υπάλληλος"] == e.name)).any()
                        if clash:
                            continue
                        candidates.append(e)
                    if not candidates:
                        continue

                    def emp_load(e: Employee) -> Tuple[int, int]:
                        day_load = int(sched[(sched["Ημερομηνία"] == d) &
                                             (sched["Υπάλληλος"] == e.name)]["Ώρες"].sum())
                        week = d.isocalendar().week
                        wk_load = 0
                        for dd in sched["Ημερομηνία"].unique():
                            dd_date = dd if isinstance(dd, dt.date) else dt.date.fromisoformat(str(dd))
                            if dd_date.isocalendar().week == week:
                                wk_load += int(sched[(sched["Ημερομηνία"] == dd_date) &
                                                     (sched["Υπάλληλος"] == e.name)]["Ώρες"].sum())
                        return (day_load, wk_load)

                    best = sorted(candidates, key=lambda e: emp_load(e))[0]
                    rows_to_add.append({
                        "Ημέρα": DAYS[d.weekday()],
                        "Ημερομηνία": d,
                        "Βάρδια": shift,
                        "Υπάλληλος": best.name,
                        "Ρόλος": role,
                        "Ώρες": _shift_len(shift),
                    })

    if rows_to_add:
        sched = pd.concat([sched, pd.DataFrame(rows_to_add)], ignore_index=True)

    viols = check_violations(sched, rules, work_model)
    sched["Ημερομηνία"] = sched["Ημερομηνία"].astype(str)
    return sched.reset_index(drop=True), viols.reset_index(drop=True)


# ----------------------------
# MILP Optimizer (PuLP) — optional
# ----------------------------

def generate_schedule_opt(
    start_date,
    employees: List[dict],
    active_shifts: List[str],
    roles: List[str],
    rules: Dict,
    role_settings: Dict,
    days_count: int,
    work_model: str = "5ήμερο",
    weights: Dict | None = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    MILP-based scheduler using PuLP (CBC). Falls back to generate_schedule_v2 if PuLP is unavailable.

    Hard constraints: availability, roles, daily/weekly hours, min rest, min coverage.
    Soft objectives: under/over coverage, role preferred shifts, role priority, fairness.

    Returns (schedule_df, missing_df).
    """
    try:
        import pulp
    except Exception:
        # Graceful fallback to greedy
        return generate_schedule_v2(
            start_date, employees, active_shifts, roles, rules, role_settings, days_count, work_model
        )

    start = pd.to_datetime(start_date).date()
    dates = [start + dt.timedelta(days=i) for i in range(days_count)]

    # Normalize employees (accept legacy availability dict format)
    Emps = []
    for i, e in enumerate(employees):
        av = e.get("availability") or []
        if isinstance(av, dict):
            av = [k for k, v in av.items() if v]
        Emps.append(Employee(id=i, name=e["name"], roles=e.get("roles", []) or [], availability=av))

    # Helpers (distinct local names to avoid confusion with module-level helpers)
    def _slen(s: str) -> int:
        return _shift_len(s)

    def _sstart(s: str) -> int:
        return _shift_start_hour(s)

    def _send(s: str) -> int:
        return _shift_end_hour(s)

    # Rules by work model
    wm = (work_model or "").strip()
    if wm == "5ήμερο":
        max_daily_hours = int(rules.get("max_daily_hours_5days", 8))
        weekly_hours_cap = int(rules.get("weekly_hours_5days", 40))
    elif wm == "6ήμερο":
        max_daily_hours = int(rules.get("max_daily_hours_6days", 9))
        weekly_hours_cap = int(rules.get("weekly_hours_6days", 48))
    else:
        max_daily_hours = int(rules.get("max_daily_hours_7days", 9))
        weekly_hours_cap = int(rules.get("weekly_hours_7days", 56))
    min_daily_rest = int(rules.get("min_daily_rest", 11))
    max_consecutive_days = int(rules.get("max_consecutive_days", 6))

    # Role settings
    min_per = {r: max(0, int(role_settings.get(r, {}).get("min_per_shift", 1))) for r in roles}
    max_per = {r: int(role_settings.get(r, {}).get("max_per_shift", 9999)) for r in roles}
    role_prio = {r: int(role_settings.get(r, {}).get("priority", 5)) for r in roles}
    role_pref = {r: list(role_settings.get(r, {}).get("preferred_shifts", [])) for r in roles}

    # Weights
    W = {
        "pen_under": 100.0,
        "pen_over": 5.0,
        "w_pref": 2.0,
        "w_prio": 1.0,
        "w_fair": 0.5,
    }
    if weights:
        W.update(weights)

    # Model
    m = pulp.LpProblem("ShiftScheduling", pulp.LpMinimize)

    # Variables
    x = {}
    for e in Emps:
        for d in dates:
            for s in active_shifts:
                for r in roles:
                    feasible = (r in e.roles) and (s in e.availability)
                    lb, ub = (0, 1) if feasible else (0, 0)
                    x[(e.name, d, s, r)] = pulp.LpVariable(f"x_{e.id}_{d}_{s}_{r}", lb, ub, cat="Binary")

    # Under/over staffing slack per (d,s,r)
    u = {(d, s, r): pulp.LpVariable(f"under_{d}_{s}_{r}", lowBound=0) for d in dates for s in active_shifts for r in roles}
    o = {(d, s, r): pulp.LpVariable(f"over_{d}_{s}_{r}",  lowBound=0) for d in dates for s in active_shifts for r in roles}

    # Fairness vars per employee-week
    week_of_iso = lambda d: d.isocalendar().week
    weeks = sorted({week_of_iso(d) for d in dates})
    H = {(e.name, w): pulp.LpVariable(f"H_{e.id}_w{w}", lowBound=0) for e in Emps for w in weeks}
    Devp = {(e.name, w): pulp.LpVariable(f"Devp_{e.id}_w{w}", lowBound=0) for e in Emps for w in weeks}
    Devn = {(e.name, w): pulp.LpVariable(f"Devn_{e.id}_w{w}", lowBound=0) for e in Emps for w in weeks}

    # --- Constraints ---

    # Coverage with slacks (and soft cap via 'o')
    for d in dates:
        for s in active_shifts:
            for r in roles:
                m += (pulp.lpSum(x[(e.name, d, s, r)] for e in Emps) + o[(d, s, r)] - u[(d, s, r)] == min_per.get(r, 0))
                m += (pulp.lpSum(x[(e.name, d, s, r)] for e in Emps) <= max_per.get(r, 9999) + o[(d, s, r)])

    # At most one role per employee per (date, shift)
    for e in Emps:
        for d in dates:
            for s in active_shifts:
                m += pulp.lpSum(x[(e.name, d, s, r)] for r in roles) <= 1

    # Daily hours cap
    for e in Emps:
        for d in dates:
            m += pulp.lpSum(_slen(s) * pulp.lpSum(x[(e.name, d, s, r)] for r in roles) for s in active_shifts) <= max_daily_hours

    # Weekly hours cap + define H(e, week)
    for e in Emps:
        for w in weeks:
            relevant_dates = [d for d in dates if week_of_iso(d) == w]
            m += H[(e.name, w)] == pulp.lpSum(
                _slen(s) * pulp.lpSum(x[(e.name, d, s, r)] for r in roles)
                for d in relevant_dates for s in active_shifts
            )
            m += H[(e.name, w)] <= weekly_hours_cap

    # Min daily rest: forbid specific (prev, next) shift pairs across consecutive days
    for e in Emps:
        for i, d in enumerate(dates[:-1]):
            dn = dates[i + 1]
            for s_prev in active_shifts:
                for s_next in active_shifts:
                    end_prev = _send(s_prev)
                    start_next = _sstart(s_next)
                    prev_end_abs = end_prev if end_prev < 24 else end_prev - 24
                    rest_hours = (24 - prev_end_abs) + start_next
                    if rest_hours < min_daily_rest:
                        m += (
                            pulp.lpSum(x[(e.name, d, s_prev, r)] for r in roles) +
                            pulp.lpSum(x[(e.name, dn, s_next, r)] for r in roles)
                            <= 1
                        )

    # Max consecutive days: in any (K+1)-day sliding window, at most K worked days
    K = max_consecutive_days
    if K > 0 and len(dates) >= K + 1:
        for i in range(0, len(dates) - K):
            window = dates[i:i + K + 1]
            for e in Emps:
                m += pulp.lpSum(
                    pulp.lpSum(
                        pulp.lpSum(x[(e.name, d, s, r)] for r in roles)
                        for s in active_shifts
                    )
                    for d in window
                ) <= K

    # Fairness targets per week (simple heuristic)
    T = {}
    for w in weeks:
        relevant_dates = [d for d in dates if week_of_iso(d) == w]
        req_hours = sum(min_per.get(r, 0) * _slen(s) for d in relevant_dates for s in active_shifts for r in roles)
        T[w] = req_hours / max(1, len(Emps))
    for e in Emps:
        for w in weeks:
            m += H[(e.name, w)] - T[w] == Devp[(e.name, w)] - Devn[(e.name, w)]

    # --- Objective ---
    obj = 0
    obj += W["pen_under"] * pulp.lpSum(u.values()) + W["pen_over"] * pulp.lpSum(o.values())

    pref_terms = []
    prio_terms = []
    for e in Emps:
        for d in dates:
            for s in active_shifts:
                for r in roles:
                    if s in role_pref.get(r, []):
                        pref_terms.append(x[(e.name, d, s, r)])
                    prio_terms.append((10 - role_prio.get(r, 5)) * x[(e.name, d, s, r)])

    if pref_terms:
        obj += -W["w_pref"] * pulp.lpSum(pref_terms)
    if prio_terms:
        obj += -W["w_prio"] * pulp.lpSum(prio_terms)

    obj += W["w_fair"] * (pulp.lpSum(Devp.values()) + pulp.lpSum(Devn.values()))
    m.setObjective(obj)

    # Solve
    m.solve(pulp.PULP_CBC_CMD(msg=False))

    # Build schedule + missing
    rows = []
    missing_rows = []
    for d in dates:
        for s in active_shifts:
            for r in roles:
                assigned_names = [e.name for e in Emps if x[(e.name, d, s, r)].value() >= 0.5]
                for name in assigned_names:
                    rows.append({
                        "Ημέρα": DAYS[d.weekday()],
                        "Ημερομηνία": str(d),
                        "Βάρδια": s,
                        "Υπάλληλος": name,
                        "Ρόλος": r,
                        "Ώρες": _slen(s),
                    })
                under = u[(d, s, r)].value()
                if under and under > 1e-6:
                    missing_rows.append({
                        "Ημέρα": DAYS[d.weekday()],
                        "Ημερομηνία": str(d),
                        "Βάρδια": s,
                        "Ρόλος": r,
                        "Λείπουν": int(round(under)),
                    })

    sched_df = pd.DataFrame(rows, columns=["Ημέρα", "Ημερομηνία", "Βάρδια", "Υπάλληλος", "Ρόλος", "Ώρες"])
    missing_df = pd.DataFrame(missing_rows, columns=["Ημέρα", "Ημερομηνία", "Βάρδια", "Ρόλος", "Λείπουν"])
    return sched_df, missing_df
