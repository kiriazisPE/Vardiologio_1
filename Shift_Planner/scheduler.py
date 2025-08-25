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
from typing import Dict, List, Tuple, Optional
from collections import defaultdict, Counter
import datetime as dt
import pandas as pd
from constants import DAYS, SHIFT_TIMES

__all__ = [
    "generate_schedule_v2",
    "auto_fix_schedule",
    "generate_schedule_opt",
    "check_violations",
]

# ----------------------------
# Helpers & Data structures
# ----------------------------

def _shift_len(shift: str) -> float:
    """Return the (positive) hours of a shift, handling wrap-around (e.g., 22→06)."""
    s, e = SHIFT_TIMES.get(shift, (9, 17))
    return (24 - s + e) if e < s else (e - s)


def _date(obj) -> dt.date:
    return pd.to_datetime(obj).date()


def _weekday_name(d: dt.date) -> str:
    return DAYS[d.weekday()]


def _shift_start_hour(shift: str) -> float:
    return SHIFT_TIMES.get(shift, (9, 17))[0]


def _shift_end_hour(shift: str) -> float:
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
    hours: float


# ----------------------------
# Rule key helpers
# ----------------------------

def _pick_rule(rules: Dict, key_5: str, key_6: str, key_7: str, work_model: str, default_5, default_6, default_7):
    wm = (work_model or "").strip()
    if wm == "5ήμερο":
        return type(default_5)(rules.get(key_5, default_5))
    if wm == "6ήμερο":
        return type(default_6)(rules.get(key_6, default_6))
    if wm == "7ήμερο":
        return type(default_7)(rules.get(key_7, default_7))
    # Fallback: treat unknown models like 5-day
    return type(default_5)(rules.get(key_5, default_5))


def _rest_hours_across_days(end_prev: float, next_start: float, min_daily_rest: int) -> float:
    """Compute rest from previous day's end hour (possibly ≥24) to next day's start.
    - If previous shift wraps past midnight, end_prev will be ≥24 (e.g., 31 for 23→07).
    - In that case rest is next_start - (end_prev % 24).
    - Otherwise rest is (24 - end_prev) + next_start.
    Returns a float for consistency with hour math elsewhere.
    """
    if end_prev >= 24:
        return float(next_start - (end_prev % 24))
    return float((24 - end_prev) + next_start)


# ----------------------------
# Rule checks
# ----------------------------

def check_violations(
    df: pd.DataFrame,
    rules: Dict,
    work_model: str = "5ήμερο",
) -> pd.DataFrame:
    """
    Validate a schedule DataFrame against labor rules.

    Expected columns in df:
      ["Ημέρα","Ημερομηνία","Βάρδια","Υπάλληλος","Ρόλος","Ώρες"]

    Rules (with defaults):
      - max_daily_hours_5days / _6days / _7days   (default 8 / 9 / 8)
      - weekly_hours_5days / _6days / _7days      (default 40 / 48 / 56)
      - min_daily_rest                             (default 11)
      - max_consecutive_days                       (default 6)

    Returns:
      DataFrame columns: ["Ημερομηνία","Υπάλληλος","Βάρδια","Ρόλος","Rule","Details","Severity"]
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["Ημερομηνία","Υπάλληλος","Βάρδια","Ρόλος","Rule","Details","Severity"])

    req_cols = {"Ημερομηνία", "Βάρδια", "Υπάλληλος", "Ρόλος", "Ώρες"}
    missing = req_cols - set(df.columns)
    if missing:
        raise ValueError(f"Schedule is missing required columns: {missing}")

    # Normalize (keep hours as float — do NOT truncate)
    sched = df.copy()
    sched["Ημερομηνία"] = pd.to_datetime(sched["Ημερομηνία"]).dt.date
    sched["Ώρες"] = sched["Ώρες"].astype(float)

    # Rule parameters (5/6/7-day models)
    max_daily_hours = _pick_rule(
        rules,
        "max_daily_hours_5days",
        "max_daily_hours_6days",
        "max_daily_hours_7days",
        work_model,
        8,
        9,
        8,
    )
    weekly_hours_cap = _pick_rule(
        rules,
        "weekly_hours_5days",
        "weekly_hours_6days",
        "weekly_hours_7days",
        work_model,
        40,
        48,
        56,
    )
    min_daily_rest = int(rules.get("min_daily_rest", 11))
    max_consecutive_days = int(rules.get("max_consecutive_days", 6))

    viols = []

    # A) Max daily hours
    daily = sched.groupby(["Υπάλληλος", "Ημερομηνία"])["Ώρες"].sum().reset_index()
    for _, row in daily.iterrows():
        if float(row["Ώρες"]) > float(max_daily_hours):
            viols.append({
                "Ημερομηνία": row["Ημερομηνία"],
                "Υπάλληλος": row["Υπάλληλος"],
                "Βάρδια": "",
                "Ρόλος": "",
                "Rule": "max_daily_hours",
                "Details": f"{row['Ώρες']}h > {max_daily_hours}h",
                "Severity": "high",
            })

    # B) Max weekly hours
    def week_of(d: dt.date) -> int:
        return d.isocalendar().week

    sched["_week"] = sched["Ημερομηνία"].apply(week_of)
    weekly = sched.groupby(["Υπάλληλος", "_week"])["Ώρες"].sum().reset_index()
    for _, row in weekly.iterrows():
        if float(row["Ώρες"]) > float(weekly_hours_cap):
            viols.append({
                "Ημερομηνία": pd.NaT,  # whole-week violation
                "Υπάλληλος": row["Υπάλληλος"],
                "Βάρδια": "",
                "Ρόλος": "",
                "Rule": "weekly_hours_cap",
                "Details": f"{row['Ώρες']}h > {weekly_hours_cap}h (week {row['_week']})",
                "Severity": "high",
            })

    # C) Rest time (no close→open below min rest)
    for emp, g in sched.groupby("Υπάλληλος"):
        g = g.sort_values(["Ημερομηνία", "Βάρδια"])
        by_date = defaultdict(list)
        for _, r in g.iterrows():
            by_date[r["Ημερομηνία"]].append(r["Βάρδια"])
        dates = sorted(by_date.keys())
        for i, d in enumerate(dates[:-1]):
            dn = dates[i + 1]
            # earliest next-day start
            if by_date[dn]:
                next_start = min(_shift_start_hour(s) for s in by_date[dn])
            else:
                continue
            for s_prev in by_date[d]:
                end_prev = _shift_end_hour(s_prev)
                rest = _rest_hours_across_days(end_prev, next_start, min_daily_rest)
                if rest < min_daily_rest:
                    viols.append({
                        "Ημερομηνία": dn,
                        "Υπάλληλος": emp,
                        "Βάρδια": "",
                        "Ρόλος": "",
                        "Rule": "min_daily_rest",
                        "Details": f"rest {rest:.1f}h < {min_daily_rest}h (prev: {s_prev})",
                        "Severity": "medium",
                    })
                    break  # one violation per pair of days is enough

    # D) Max consecutive days
    for emp, g in sched.groupby("Υπάλληλος"):
        days = sorted(set(g["Ημερομηνία"]))
        streak = 0
        last = None
        for d in days:
            if last is None or d == last + dt.timedelta(days=1):
                streak += 1
            else:
                streak = 1
            if streak > max_consecutive_days:
                viols.append({
                    "Ημερομηνία": d,
                    "Υπάλληλος": emp,
                    "Βάρδια": "",
                    "Ρόλος": "",
                    "Rule": "max_consecutive_days",
                    "Details": f"{streak} consecutive days > {max_consecutive_days}",
                    "Severity": "medium",
                })
            last = d

    return pd.DataFrame(
        viols,
        columns=["Ημερομηνία", "Υπάλληλος", "Βάρδια", "Ρόλος", "Rule", "Details", "Severity"],
    )


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

    assigned: List[Assignment] = []
    hours_by_emp_week: Dict[str, Counter] = defaultdict(Counter)
    last_shift_by_emp: Dict[str, Tuple[dt.date, str]] = {}

    max_daily_hours = _pick_rule(
        rules,
        "max_daily_hours_5days",
        "max_daily_hours_6days",
        "max_daily_hours_7days",
        work_model,
        8,
        9,
        8,
    )
    weekly_hours_cap = _pick_rule(
        rules,
        "weekly_hours_5days",
        "weekly_hours_6days",
        "weekly_hours_7days",
        work_model,
        40,
        48,
        56,
    )
    min_daily_rest = int(rules.get("min_daily_rest", 11))

    def week_of(d: dt.date) -> int:
        return d.isocalendar().week

    def can_assign(emp: Employee, d: dt.date, shift: str, role: str) -> bool:
        if shift not in emp.availability or role not in emp.roles:
            return False
        # daily cap
        cur_hours = sum(a.hours for a in assigned if a.employee == emp.name and a.date == d)
        if cur_hours + _shift_len(shift) > max_daily_hours:
            return False
        # weekly cap
        wk = week_of(d)
        if hours_by_emp_week[emp.name][wk] + _shift_len(shift) > weekly_hours_cap:
            return False
        # min rest against previous day
        if emp.name in last_shift_by_emp and last_shift_by_emp[emp.name][0] == d - dt.timedelta(days=1):
            end_h = _shift_end_hour(last_shift_by_emp[emp.name][1])
            next_start = _shift_start_hour(shift)
            rest = _rest_hours_across_days(end_h, next_start, min_daily_rest)
            if rest < min_daily_rest:
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
        sc += max(0, 20 - hours_by_emp_week[emp.name][week_of(d)]) * 0.2
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
                    best = max(candidates, key=lambda e: score(e, d, shift, role))
                    hrs = float(_shift_len(shift))
                    assigned.append(Assignment(d, shift, best.name, role, hrs))
                    hours_by_emp_week[best.name][week_of(d)] += hrs
                    last_shift_by_emp[best.name] = (d, shift)
                    picks.append(best.name)

    sched_df = pd.DataFrame(
        [{
            "Ημέρα": _weekday_name(a.date),
            "Ημερομηνία": str(a.date),
            "Βάρδια": a.shift,
            "Υπάλληλος": a.employee,
            "Ρόλος": a.role,
            "Ώρες": float(a.hours),
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
    # Keep float — do not coerce to int
    sched["Ώρες"] = sched["Ώρες"].astype(float)

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

                    def emp_load(e: Employee) -> Tuple[float, float]:
                        day_load = float(sched[(sched["Ημερομηνία"] == d) &
                                              (sched["Υπάλληλος"] == e.name)]["Ώρες"].sum())
                        week = d.isocalendar().week
                        wk_load = 0.0
                        for dd in sched["Ημερομηνία"].unique():
                            dd_date = dd if isinstance(dd, dt.date) else dt.date.fromisoformat(str(dd))
                            if dd_date.isocalendar().week == week:
                                wk_load += float(sched[(sched["Ημερομηνία"] == dd_date) &
                                                      (sched["Υπάλληλος"] == e.name)]["Ώρες"].sum())
                        return (day_load, wk_load)

                    best = sorted(candidates, key=lambda e: emp_load(e))[0]
                    rows_to_add.append({
                        "Ημέρα": DAYS[d.weekday()],
                        "Ημερομηνία": d,
                        "Βάρδια": shift,
                        "Υπάλληλος": best.name,
                        "Ρόλος": role,
                        "Ώρες": float(_shift_len(shift)),
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
    weights: Optional[Dict] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    MILP-based scheduler using PuLP (CBC). Falls back to generate_schedule_v2 if PuLP is
    unavailable.

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
    Emps: List[Employee] = []
    for i, e in enumerate(employees):
        av = e.get("availability") or []
        if isinstance(av, dict):
            av = [k for k, v in av.items() if v]
        Emps.append(Employee(id=i, name=e["name"], roles=e.get("roles", []) or [], availability=av))

    # Helpers
    def shift_len(s: str) -> float:
        return _shift_len(s)

    def shift_start(s: str) -> float:
        return _shift_start_hour(s)

    def shift_end(s: str) -> float:
        return _shift_end_hour(s)

    # Rules
    max_daily_hours = _pick_rule(
        rules,
        "max_daily_hours_5days",
        "max_daily_hours_6days",
        "max_daily_hours_7days",
        work_model,
        8,
        9,
        8,
    )
    weekly_hours_cap = _pick_rule(
        rules,
        "weekly_hours_5days",
        "weekly_hours_6days",
        "weekly_hours_7days",
        work_model,
        40,
        48,
        56,
    )
    min_daily_rest = int(rules.get("min_daily_rest", 11))

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
    week_of = lambda d: d.isocalendar().week
    weeks = sorted({week_of(d) for d in dates})
    H = {(e.name, w): pulp.LpVariable(f"H_{e.id}_w{w}", lowBound=0) for e in Emps for w in weeks}
    Devp = {(e.name, w): pulp.LpVariable(f"Devp_{e.id}_w{w}", lowBound=0) for e in Emps for w in weeks}
    Devn = {(e.name, w): pulp.LpVariable(f"Devn_{e.id}_w{w}", lowBound=0) for e in Emps for w in weeks}

    # --- Constraints ---

    # Coverage with slacks
    for d in dates:
        for s in active_shifts:
            for r in roles:
                m += (pulp.lpSum(x[(e.name, d, s, r)] for e in Emps) + o[(d, s, r)] - u[(d, s, r)] == min_per.get(r, 0))
                # Optional cap with soft overage
                m += (pulp.lpSum(x[(e.name, d, s, r)] for e in Emps) <= max_per.get(r, 9999) + o[(d, s, r)])

    # At most one role per employee per (date, shift)
    for e in Emps:
        for d in dates:
            for s in active_shifts:
                m += pulp.lpSum(x[(e.name, d, s, r)] for r in roles) <= 1

    # Daily hours cap
    for e in Emps:
        for d in dates:
            m += pulp.lpSum(shift_len(s) * pulp.lpSum(x[(e.name, d, s, r)] for r in roles) for s in active_shifts) <= max_daily_hours

    # Weekly hours cap + define H(e, week)
    for e in Emps:
        for w in weeks:
            relevant_dates = [d for d in dates if week_of(d) == w]
            m += H[(e.name, w)] == pulp.lpSum(
                shift_len(s) * pulp.lpSum(x[(e.name, d, s, r)] for r in roles)
                for d in relevant_dates for s in active_shifts
            )
            m += H[(e.name, w)] <= weekly_hours_cap

    # Min daily rest: forbid specific (prev, next) shift pairs across consecutive days
    for e in Emps:
        for i, d in enumerate(dates[:-1]):
            dn = dates[i + 1]
            for s_prev in active_shifts:
                for s_next in active_shifts:
                    end_prev = shift_end(s_prev)
                    start_next = shift_start(s_next)
                    rest_hours = _rest_hours_across_days(end_prev, start_next, min_daily_rest)
                    if rest_hours < min_daily_rest:
                        m += (
                            pulp.lpSum(x[(e.name, d, s_prev, r)] for r in roles) +
                            pulp.lpSum(x[(e.name, dn, s_next, r)] for r in roles)
                            <= 1
                        )

    # Fairness targets per week (simple heuristic)
    T: Dict[int, float] = {}
    for w in weeks:
        relevant_dates = [d for d in dates if week_of(d) == w]
        req_hours = sum(min_per.get(r, 0) * shift_len(s) for d in relevant_dates for s in active_shifts for r in roles)
        T[w] = req_hours / max(1, len(Emps))

    for e in Emps:
        for w in weeks:
            m += H[(e.name, w)] - T[w] == Devp[(e.name, w)] - Devn[(e.name, w)]

    # --- Objective ---
    obj = 0
    obj += 100.0 * pulp.lpSum(u.values()) + 5.0 * pulp.lpSum(o.values())

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
        obj += -2.0 * pulp.lpSum(pref_terms)
    if prio_terms:
        obj += -1.0 * pulp.lpSum(prio_terms)

    obj += 0.5 * (pulp.lpSum(Devp.values()) + pulp.lpSum(Devn.values()))
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
                        "Ώρες": float(shift_len(s)),
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
