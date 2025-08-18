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
from typing import Dict, List, Tuple, Iterable
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


# ---------- Smart, self-healing generator ----------

from typing import Iterable

def _week_of(d: dt.date) -> int:
    return d.isocalendar().week

def _emp_obj_index(employees: List[dict]) -> Dict[str, Employee]:
    """Index employees by name as Employee objects."""
    idx = {}
    for i, e in enumerate(employees):
        roles = e.get("roles") or []
        avail = e.get("availability") or []
        idx[e["name"]] = Employee(i, e["name"], roles, avail)
    return idx

def _employee_can_take_slot(
    sched: pd.DataFrame,
    emp: Employee,
    d: dt.date,
    shift: str,
    role: str,
    rules: Dict,
    work_model: str,
) -> bool:
    """
    True if emp can take (d, shift, role) **without** breaking availability,
    roles, daily/weekly hour caps, rest (prev & next day), and duplicates.
    """
    # availability + role
    if shift not in (emp.availability or []): return False
    if role  not in (emp.roles or []):        return False

    df = sched.copy()
    df["Ημερομηνία"] = pd.to_datetime(df["Ημερομηνία"]).dt.date
    df["Ώρες"] = df["Ώρες"].astype(int)

    if work_model.strip() == "5ήμερο":
        max_daily = int(rules.get("max_daily_hours_5days", 8))
        max_week  = int(rules.get("weekly_hours_5days", 40))
    elif work_model.strip() == "7ήμερο":
        max_daily = int(rules.get("max_daily_hours_7days", 9))
        max_week  = int(rules.get("weekly_hours_7days", 56))  # set what you prefer
    else:  # "6ήμερο"
        max_daily = int(rules.get("max_daily_hours_6days", 9))
        max_week  = int(rules.get("weekly_hours_6days", 48))


    new_hours = _shift_len(shift)

    # daily cap
    day_hours = int(df[(df["Ημερομηνία"] == d) & (df["Υπάλληλος"] == emp.name)]["Ώρες"].sum())
    if day_hours + new_hours > max_daily:
        return False

    # weekly cap
    wk = _week_of(d)
    wk_hours = 0
    for dd in df[df["Υπάλληλος"] == emp.name]["Ημερομηνία"].unique():
        dd = dd if isinstance(dd, dt.date) else pd.to_datetime(dd).date()
        if _week_of(dd) == wk:
            wk_hours += int(df[(df["Ημερομηνία"] == dd) & (df["Υπάλληλος"] == emp.name)]["Ώρες"].sum())
    if wk_hours + new_hours > max_week:
        return False

    # min rest: previous day -> today
    prev = d - dt.timedelta(days=1)
    prev_rows = df[(df["Ημερομηνία"] == prev) & (df["Υπάλληλος"] == emp.name)]
    if not prev_rows.empty:
        start_next = SHIFT_TIMES.get(shift, (9, 17))[0]
        for _, r in prev_rows.iterrows():
            s, e = SHIFT_TIMES.get(r["Βάρδια"], (9, 17))
            end_prev = e if e >= s else e + 24
            prev_end_abs = end_prev if end_prev < 24 else end_prev - 24
            rest = (24 - prev_end_abs) + start_next
            if rest < min_rest:
                return False

    # min rest: today (this new) -> next day
    nextd = d + dt.timedelta(days=1)
    next_rows = df[(df["Ημερομηνία"] == nextd) & (df["Υπάλληλος"] == emp.name)]
    if not next_rows.empty:
        s, e = SHIFT_TIMES.get(shift, (9, 17))
        end_new = e if e >= s else e + 24
        for _, r in next_rows.iterrows():
            start_next = SHIFT_TIMES.get(r["Βάρδια"], (9, 17))[0]
            new_end_abs = end_new if end_new < 24 else end_new - 24
            rest = (24 - new_end_abs) + start_next
            if rest < min_rest:
                return False

    # no duplicate row for same (d, shift, emp)
    clash = ((df["Ημερομηνία"] == d) & (df["Βάρδια"] == shift) & (df["Υπάλληλος"] == emp.name)).any()
    if clash:
        return False

    return True

def _fill_coverage_gaps(
    sched: pd.DataFrame,
    employees: List[dict],
    active_shifts: List[str],
    roles: List[str],
    role_settings: Dict,
    rules: Dict,
    work_model: str,
) -> pd.DataFrame:
    """
    Ensure min_per_shift coverage per (date, shift, role) by assigning eligible
    employees with least (day_load, week_load).
    """
    df = sched.copy()
    df["Ημερομηνία"] = pd.to_datetime(df["Ημερομηνία"]).dt.date
    df["Ώρες"] = df["Ώρες"].astype(int)

    emp_idx = _emp_obj_index(employees)
    min_per = {r: max(0, int(role_settings.get(r, {}).get("min_per_shift", 1))) for r in roles}

    all_dates = sorted(df["Ημερομηνία"].unique())
    for d in all_dates:
        for s in active_shifts:
            for r in roles:
                have = int(((df["Ημερομηνία"] == d) & (df["Βάρδια"] == s) & (df["Ρόλος"] == r)).sum())
                need = max(0, min_per.get(r, 0) - have)
                while need > 0:
                    cands: List[Employee] = []
                    for name, emp in emp_idx.items():
                        if not _employee_can_take_slot(df, emp, d, s, r, rules, work_model):
                            continue
                        cands.append(emp)
                    if not cands:
                        break

                    def load_key(e: Employee) -> tuple[int, int]:
                        day_h = int(df[(df["Ημερομηνία"] == d) & (df["Υπάλληλος"] == e.name)]["Ώρες"].sum())
                        wk = _week_of(d)
                        wk_h = 0
                        for dd in df[df["Υπάλληλος"] == e.name]["Ημερομηνία"].unique():
                            dd = dd if isinstance(dd, dt.date) else pd.to_datetime(dd).date()
                            if _week_of(dd) == wk:
                                wk_h += int(df[(df["Ημερομηνία"] == dd) & (df["Υπάλληλος"] == e.name)]["Ώρες"].sum())
                        return (day_h, wk_h)

                    best = sorted(cands, key=load_key)[0]
                    df.loc[len(df)] = [DAYS[d.weekday()], d, s, best.name, r, _shift_len(s)]
                    need -= 1
    return df

def _try_reassign_one(
    sched: pd.DataFrame,
    employees: List[dict],
    viol_row: dict,
    rules: Dict,
    work_model: str,
    active_shifts: List[str],
    roles: List[str],
) -> tuple[pd.DataFrame, bool]:
    """
    Local fix for a single violation by reassigning ONE implicated row.
    Returns (new_df, changed?).
    """
    df = sched.copy()
    df["Ημερομηνία"] = pd.to_datetime(df["Ημερομηνία"]).dt.date
    df["Ώρες"] = df["Ώρες"].astype(int)
    emp_idx = _emp_obj_index(employees)

    rule = viol_row.get("Rule")
    emp  = viol_row.get("Υπάλληλος", "")
    date = viol_row.get("Ημερομηνία", None)
    if isinstance(date, str):
        date = pd.to_datetime(date).date()

    def candidates_for_slot(d: dt.date, shift: str, role: str, exclude: Iterable[str]) -> List[Employee]:
        cands = []
        for e in emp_idx.values():
            if e.name in exclude: continue
            if _employee_can_take_slot(df, e, d, shift, role, rules, work_model):
                cands.append(e)
        return cands

    def pick_heaviest(emp_name: str, on_date: dt.date | None = None) -> int | None:
        subset = df[df["Υπάλληλος"] == emp_name]
        if on_date: subset = subset[subset["Ημερομηνία"] == on_date]
        if subset.empty: return None
        return subset.sort_values("Ώρες", ascending=False).index[0]

    changed = False

    if rule == "max_daily_hours" and date is not None and emp:
        row_idx = pick_heaviest(emp, on_date=date)
        if row_idx is not None:
            row = df.loc[row_idx]
            d, s, r = row["Ημερομηνία"], row["Βάρδια"], row["Ρόλος"]
            cands = candidates_for_slot(d, s, r, exclude=[emp])
            if cands:
                df.loc[row_idx, "Υπάλληλος"] = cands[0].name
                changed = True
            else:
                df = df.drop(index=row_idx).reset_index(drop=True)
                changed = True

    elif rule == "weekly_hours_cap" and emp:
        row_idx = pick_heaviest(emp)
        if row_idx is not None:
            row = df.loc[row_idx]
            d, s, r = row["Ημερομηνία"], row["Βάρδια"], row["Ρόλος"]
            cands = candidates_for_slot(d, s, r, exclude=[emp])
            if cands:
                df.loc[row_idx, "Υπάλληλος"] = cands[0].name
                changed = True
            else:
                df = df.drop(index=row_idx).reset_index(drop=True)
                changed = True

    elif rule == "min_daily_rest" and emp and date is not None:
        # Violation reported on next day; move earliest shift on that next day
        next_rows = df[(df["Ημερομηνία"] == date) & (df["Υπάλληλος"] == emp)]
        if not next_rows.empty:
            next_rows = next_rows.sort_values(by="Βάρδια", key=lambda s: [SHIFT_TIMES.get(x, (9,17))[0] for x in s])
            row_idx = next_rows.index[0]
            row = df.loc[row_idx]
            d, s, r = row["Ημερομηνία"], row["Βάρδια"], row["Ρόλος"]
            cands = candidates_for_slot(d, s, r, exclude=[emp])
            if cands:
                df.loc[row_idx, "Υπάλληλος"] = cands[0].name
                changed = True
            else:
                df = df.drop(index=row_idx).reset_index(drop=True)
                changed = True

    elif rule == "max_consecutive_days" and emp and date is not None:
        rows = df[(df["Ημερομηνία"] == date) & (df["Υπάλληλος"] == emp)]
        if not rows.empty:
            row_idx = rows.index[0]
            row = df.loc[row_idx]
            d, s, r = row["Ημερομηνία"], row["Βάρδια"], row["Ρόλος"]
            cands = candidates_for_slot(d, s, r, exclude=[emp])
            if cands:
                df.loc[row_idx, "Υπάλληλος"] = cands[0].name
                changed = True
            else:
                df = df.drop(index=row_idx).reset_index(drop=True)
                changed = True

    return df, changed

def repair_schedule(
    df: pd.DataFrame,
    employees: List[dict],
    active_shifts: List[str],
    roles: List[str],
    rules: Dict,
    role_settings: Dict,
    work_model: str = "5ήμερο",
    max_passes: int = 8,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Iteratively fix all violations (reassign or drop illegal rows), then backfill
    to meet min_per. Returns (fixed_schedule_df, remaining_violations_df).
    """
    sched = df.copy()
    sched["Ημερομηνία"] = pd.to_datetime(sched["Ημερομηνία"]).dt.date
    sched["Ώρες"] = sched["Ώρες"].astype(int)

    for _ in range(max_passes):
        viols = check_violations(sched, rules, work_model)
        if viols.empty:
            break
        changed_any = False
        order = {"high": 0, "medium": 1, "": 2}
        viols = viols.sort_values(by=["Severity", "Rule"], key=lambda s: [order.get(x, 2) for x in s])
        for _, v in viols.iterrows():
            sched, changed = _try_reassign_one(
                sched, employees, v.to_dict(), rules, work_model, active_shifts, roles
            )
            changed_any = changed_any or changed
        # always backfill coverage after each pass
        sched = _fill_coverage_gaps(sched, employees, active_shifts, roles, role_settings, rules, work_model)
        if not changed_any:
            break

    final_viol = check_violations(sched, rules, work_model)
    return sched.reset_index(drop=True), final_viol.reset_index(drop=True)

def generate_schedule_smart(
    start_date,
    employees: List[dict],
    active_shifts: List[str],
    roles: List[str],
    rules: Dict,
    role_settings: Dict,
    days_count: int,
    work_model: str = "5ήμερο",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    1) Build initial plan (MILP if available, else greedy v2)
    2) Repair iteratively until no violations or fixed-point
    3) Return (schedule_df, missing_df, violations_df)
    """
    # initial plan (prefer MILP)
    try:
        sched_df, missing_df = generate_schedule_opt(
            start_date, employees, active_shifts, roles, rules, role_settings, days_count, work_model
        )
    except Exception:
        sched_df, missing_df = generate_schedule_v2(
            start_date, employees, active_shifts, roles, rules, role_settings, days_count, work_model
        )

    fixed_df, viols_df = repair_schedule(
        sched_df, employees, active_shifts, roles, rules, role_settings, work_model
    )

    # recompute remaining missing coverage after repair
    min_per = {r: max(0, int(role_settings.get(r, {}).get("min_per_shift", 1))) for r in roles}
    fixed = fixed_df.copy()
    if not fixed.empty:
        fixed["Ημερομηνία"] = pd.to_datetime(fixed["Ημερομηνία"]).dt.date

    missing_rows = []
    if not fixed.empty:
        all_dates = sorted(fixed["Ημερομηνία"].unique())
        for d in all_dates:
            for s in active_shifts:
                for r in roles:
                    cur = int(((fixed["Ημερομηνία"] == d) & (fixed["Βάρδια"] == s) & (fixed["Ρόλος"] == r)).sum())
                    need = max(0, min_per.get(r, 0) - cur)
                    if need > 0:
                        missing_rows.append({
                            "Ημέρα": DAYS[d.weekday()],
                            "Ημερομηνία": str(d),
                            "Βάρδια": s,
                            "Ρόλος": r,
                            "Λείπουν": need
                        })
    missing_df = pd.DataFrame(missing_rows, columns=["Ημέρα","Ημερομηνία","Βάρδια","Ρόλος","Λείπουν"])

    # normalize types for UI
    fixed_df = fixed_df.copy()
    if not fixed_df.empty:
        fixed_df["Ημερομηνία"] = fixed_df["Ημερομηνία"].astype(str)

    return fixed_df.reset_index(drop=True), missing_df.reset_index(drop=True), viols_df.reset_index(drop=True)


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
      - max_daily_hours_5days / max_daily_hours_6days   (default 8 / 9)
      - weekly_hours_5days / weekly_hours_6days         (default 40 / 48)
      - min_daily_rest                                  (default 11)
      - max_consecutive_days                            (default 6)

    Returns:
      DataFrame columns: ["Ημερομηνία","Υπάλληλος","Βάρδια","Ρόλος","Rule","Details","Severity"]
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["Ημερομηνία","Υπάλληλος","Βάρδια","Ρόλος","Rule","Details","Severity"])

    req_cols = {"Ημερομηνία", "Βάρδια", "Υπάλληλος", "Ρόλος", "Ώρες"}
    missing = req_cols - set(df.columns)
    if missing:
        raise ValueError(f"Schedule is missing required columns: {missing}")

    # Normalize
    sched = df.copy()
    sched["Ημερομηνία"] = pd.to_datetime(sched["Ημερομηνία"]).dt.date
    sched["Ώρες"] = sched["Ώρες"].astype(int)

    # Rule parameters
    if work_model.strip() == "5ήμερο":
        max_daily_hours = int(rules.get("max_daily_hours_5days", 8))
        weekly_hours_cap = int(rules.get("weekly_hours_5days", 40))
    else:
        max_daily_hours = int(rules.get("max_daily_hours_6days", 9))
        weekly_hours_cap = int(rules.get("weekly_hours_6days", 48))
    min_daily_rest = int(rules.get("min_daily_rest", 11))
    max_consecutive_days = int(rules.get("max_consecutive_days", 6))

    viols: List[Dict] = []

    # A) Max daily hours
    daily = sched.groupby(["Υπάλληλος", "Ημερομηνία"])["Ώρες"].sum().reset_index()
    for _, row in daily.iterrows():
        if row["Ώρες"] > max_daily_hours:
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
        if row["Ώρες"] > weekly_hours_cap:
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
    # For each employee, check any shift on day d and the earliest shift on d+1.
    for emp, g in sched.groupby("Υπάλληλος"):
        g = g.sort_values(["Ημερομηνία", "Βάρδια"])
        # Build map date -> list of shifts
        by_date: Dict[dt.date, List[str]] = defaultdict(list)
        for _, r in g.iterrows():
            by_date[r["Ημερομηνία"]].append(r["Βάρδια"])
        dates = sorted(by_date.keys())
        for i, d in enumerate(dates[:-1]):
            dn = dates[i + 1]
            # For all prev shifts vs earliest next shift
            next_start = None
            if by_date[dn]:
                next_start = min(_shift_start_hour(s) for s in by_date[dn])
            if next_start is None:
                continue
            for s_prev in by_date[d]:
                end_prev = _shift_end_hour(s_prev)
                prev_end_abs = end_prev if end_prev < 24 else end_prev - 24
                rest = (24 - prev_end_abs) + next_start
                if rest < min_daily_rest:
                    viols.append({
                        "Ημερομηνία": dn,
                        "Υπάλληλος": emp,
                        "Βάρδια": "",
                        "Ρόλος": "",
                        "Rule": "min_daily_rest",
                        "Details": f"rest {int(rest)}h < {min_daily_rest}h (prev: {s_prev})",
                        "Severity": "medium",
                    })
                    # one violation per pair of days is enough
                    break

    # D) Max consecutive days
    for emp, g in sched.groupby("Υπάλληλος"):
        days = sorted(set(g["Ημερομηνία"]))
        streak = 0
        last: dt.date | None = None
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
# Greedy generator
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
    last_shift_by_emp: Dict[str, tuple[dt.date, str]] = {}

    max_daily_hours = int(rules.get("max_daily_hours_5days", 8 if work_model == "5ήμερο" else 9))
    weekly_hours_cap = int(rules.get("weekly_hours_5days", 40 if work_model == "5ήμερο" else 48))
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
            prev_end_abs = end_h if end_h < 24 else end_h - 24
            rest = (24 - prev_end_abs) + next_start
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

    missing_rows: List[Dict] = []
    for i in range(days_count):
        d = start + dt.timedelta(days=i)
        day_label = _weekday_name(d)
        for shift in active_shifts:
            for role in roles:
                need = min_per.get(role, 0)
                if need <= 0:
                    continue
                picks: List[str] = []
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
                    hrs = _shift_len(shift)
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

    rows_to_add: List[Dict] = []
    all_dates = sorted(sched["Ημερομηνία"].unique())
    for d in all_dates:
        for shift in active_shifts:
            for role in roles:
                cur = existing.get((d, shift, role), 0)
                need = max(0, min_per.get(role, 0) - cur)
                for _ in range(need):
                    # Eligible candidates
                    candidates: List[Employee] = []
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
# MILP Optimizer (PuLP)
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

    # Normalize employees
    Emps: List[Employee] = []
    for i, e in enumerate(employees):
        av = e.get("availability") or []
        if isinstance(av, dict):  # support legacy dict format
            av = [k for k, v in av.items() if v]
        Emps.append(Employee(id=i, name=e["name"], roles=e.get("roles", []) or [], availability=av))

    # Parameters / helpers
    def shift_len(s: str) -> int:
        return _shift_len(s)

    def shift_start(s: str) -> int:
        return _shift_start_hour(s)

    def shift_end(s: str) -> int:
        return _shift_end_hour(s)

    # Rules
    if work_model.strip() == "5ήμερο":
        max_daily_hours = int(rules.get("max_daily_hours_5days", 8))
        weekly_hours_cap = int(rules.get("weekly_hours_5days", 40))
    else:
        max_daily_hours = int(rules.get("max_daily_hours_6days", 9))
        weekly_hours_cap = int(rules.get("weekly_hours_6days", 48))
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
    x: Dict[tuple, pulp.LpVariable] = {}
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
                    prev_end_abs = end_prev if end_prev < 24 else end_prev - 24
                    rest_hours = (24 - prev_end_abs) + start_next
                    if rest_hours < min_daily_rest:
                        m += (
                            pulp.lpSum(x[(e.name, d, s_prev, r)] for r in roles) +
                            pulp.lpSum(x[(e.name, dn, s_next, r)] for r in roles)
                            <= 1
                        )

    # Fairness targets per week (simple heuristic)
    T = {}
    for w in weeks:
        relevant_dates = [d for d in dates if week_of(d) == w]
        req_hours = sum(min_per.get(r, 0) * shift_len(s) for d in relevant_dates for s in active_shifts for r in roles)
        T[w] = req_hours / max(1, len(Emps))

    for e in Emps:
        for w in weeks:
            m += H[(e.name, w)] - T[w] == Devp[(e.name, w)] - Devn[(e.name, w)]

    # --- Objective ---
    obj = W["pen_under"] * pulp.lpSum(u.values()) + W["pen_over"] * pulp.lpSum(o.values())

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
    rows: List[Dict] = []
    missing_rows: List[Dict] = []
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
                        "Ώρες": shift_len(s),
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
