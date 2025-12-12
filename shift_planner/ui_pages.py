# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import datetime as dt
from datetime import date as dt_date, timedelta

from typing import Optional
from db import (
    get_all_companies, get_company, update_company, create_company,
    get_employees, add_employee, update_employee, delete_employee,
    # Visual builder + swaps:
    get_schedule_range, bulk_save_week_schedule, get_employee_id_by_name,
    create_swap_request, list_swap_requests, update_swap_status, apply_approved_swap,
)

from constants import DAYS, SHIFT_TIMES, ALL_SHIFTS, DEFAULT_ROLES, DEFAULT_RULES

# Import new analytics and export modules
try:
    from analytics import (
        show_detailed_analytics, render_kpi_cards, 
        render_employee_workload_comparison
    )
    from export_utils import show_export_dialog, show_import_dialog
    from calendar_view import render_calendar_view, render_weekly_timeline
    ADVANCED_FEATURES = True
except ImportError as e:
    ADVANCED_FEATURES = False
    import traceback
    print(f"Advanced features not available: {e}")
    traceback.print_exc()

# --- Optional import: auto-fix (may not exist in every deployment) ---
try:
    from scheduler import auto_fix_schedule as _auto_fix_schedule
except Exception:  # ImportError or AttributeError
    _auto_fix_schedule = None

from scheduler import check_violations


def page_business():
    st.title("⚙️ Business Configuration")
    st.caption("Configure your business settings, shifts, roles, and scheduling rules")

    # Require a selected company
    if "company" not in st.session_state or not st.session_state.get("company", {}):
        st.warning("⚠️ Please select a company from the sidebar.")
        return

    company = st.session_state.company
    company.setdefault("active_shifts", ALL_SHIFTS.copy())
    company.setdefault("roles", DEFAULT_ROLES.copy())
    company.setdefault("rules", DEFAULT_RULES.copy())
    company.setdefault("role_settings", {})
    company.setdefault("work_model", "5ήμερο")
    company.setdefault("active", True)

    # Basic Settings in clean card
    with st.container():
        st.subheader("🏢 Basic Information")
        col1, col2 = st.columns([3, 1])
        with col1:
            company["name"] = st.text_input(
                "Company Name", 
                company.get("name", ""),
                placeholder="Enter your company name"
            )
        with col2:
            options = ["5ήμερο", "6ήμερο", "7ήμερο"]
            current = company.get("work_model", "5ήμερο")
            idx = options.index(current) if current in options else 0
            company["work_model"] = st.selectbox("Work Model", options, index=idx)
        
        company["active"] = st.toggle("✅ Company Active", value=bool(company.get("active", True)))
    
    st.divider()

    # Shifts Configuration
    with st.expander("🕒 Shift Configuration", expanded=False):
        st.caption("Define the shifts available for scheduling")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            new_shift = st.text_input("Add New Shift", placeholder="e.g., Night Shift")
        with col2:
            st.write("")
            st.write("")
            if st.button("➕ Add", use_container_width=True) and new_shift:
                if new_shift not in company["active_shifts"]:
                    company["active_shifts"].append(new_shift)
                    st.success(f"Added: {new_shift}")
                    st.rerun()
        
        if st.button("↩️ Reset to Defaults", type="secondary"):
            company["active_shifts"] = ALL_SHIFTS.copy()
            st.rerun()
        
        st.write("**Active Shifts:**")
        for shift in company["active_shifts"]:
            cols = st.columns([4, 1])
            cols[0].markdown(f"• {shift}")
            if cols[1].button("🗑️", key=f"del_shift_{shift}"):
                company["active_shifts"].remove(shift)
                st.rerun()

    # Roles & Settings
    with st.expander("👔 Roles & Staffing Requirements", expanded=True):
        st.caption("Configure roles and their scheduling requirements")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            new_role = st.text_input("Add New Role", placeholder="e.g., Supervisor")
        with col2:
            st.write("")
            st.write("")
            if st.button("➕ Add Role", use_container_width=True) and new_role:
                if new_role not in company["roles"]:
                    company["roles"].append(new_role)
                    st.success(f"Added: {new_role}")
                    st.rerun()

        company.setdefault("role_settings", {})
        
        if company.get("roles"):
            st.write("")
            for r in company.get("roles", []):
                rs = company["role_settings"].setdefault(r, {})
                rs["priority"]        = int(rs.get("priority", 5))
                rs["min_per_shift"]   = int(rs.get("min_per_shift", 1))
                rs["max_per_shift"]   = int(rs.get("max_per_shift", 5))
                rs["max_hours_week"]  = int(rs.get("max_hours_week", 40))
                rs["cost"]            = float(rs.get("cost", 0.0))
                rs.setdefault("preferred_shifts", [])

                with st.container():
                    st.markdown(f"**{r}**")
                    col = st.columns([1, 1, 1])
                    rs["priority"]       = col[0].slider("Priority", 1, 10, rs["priority"], key=f"prio_{r}")
                    rs["min_per_shift"]  = col[1].number_input("Min", 0, 10, rs["min_per_shift"], key=f"min_{r}")
                    rs["max_per_shift"]  = col[2].number_input("Max", 1, 10, rs["max_per_shift"], key=f"max_{r}")
                    
                    rs["preferred_shifts"] = st.multiselect(
                        "Preferred Shifts",
                        company.get("active_shifts", []),
                        default=rs.get("preferred_shifts", []),
                        key=f"pref_{r}"
                    )
                    st.divider()

    # -------- Κανόνες --------
    with st.expander("⚖️ Κανόνες", expanded=False):
        rules = company.get("rules", {})
        rule_defs = {
            "max_daily_hours_5days": (6, 12, rules.get("max_daily_hours_5days", 8)),
            "max_daily_hours_6days": (6, 12, rules.get("max_daily_hours_6days", 9)),
            "max_daily_hours_7days": (6, 12, rules.get("max_daily_hours_7days", 9)),
            "max_daily_overtime":    (0, 6,  rules.get("max_daily_overtime", 3)),
            "min_daily_rest":        (8, 24, rules.get("min_daily_rest", 11)),
            "weekly_hours_5days":    (30, 50, rules.get("weekly_hours_5days", 40)),
            "weekly_hours_6days":    (30, 60, rules.get("weekly_hours_6days", 48)),
            "weekly_hours_7days":    (35, 70, rules.get("weekly_hours_7days", 56)),
            "monthly_hours":         (100, 300, rules.get("monthly_hours", 160)),
            "max_consecutive_days":  (3, 10, rules.get("max_consecutive_days", 6)),
        }
        for k, (mn, mx, dv) in rule_defs.items():
            rules[k] = st.number_input(k, mn, mx, dv)
        company["rules"] = rules

    # -------- Save --------
    if st.button("💾 Αποθήκευση Ρυθμίσεων", type="primary"):
        try:
            update_company(company["id"], company)
            st.success("✅ Αποθηκεύτηκε")
        except Exception as ex:
            st.error(f"Αποτυχία: {ex}")


# ------------------------- Helpers ------------------------- #
def page_employees():
    back_to_company_selection("back_employees")
    st.subheader("👥 Υπάλληλοι")

    if "company" not in st.session_state:
        st.warning("Επιλέξτε επιχείρηση πρώτα.")
        return

    company = st.session_state.company
    st.session_state.setdefault("employees", [])

    # ---- Add new employee ----
    with st.form("add_emp"):
        name = st.text_input("Όνομα")
        roles = st.multiselect("Ρόλοι", company["roles"])
        availability = st.multiselect("Διαθεσιμότητα", company["active_shifts"])
        submitted = st.form_submit_button("➕ Προσθήκη")

    if submitted:
        errors = []
        if not name.strip():
            errors.append("Το όνομα είναι υποχρεωτικό.")
        if any(r not in company["roles"] for r in roles):
            errors.append("Μη έγκυρος ρόλος.")
        if any(s not in company["active_shifts"] for s in availability):
            errors.append("Μη έγκυρη βάρδια διαθεσιμότητας.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            # Re-validate company exists and not demo before DB write
            fresh = get_company(company.get("id"))
            if not fresh:
                st.error("Η επιχείρηση δεν υπάρχει πλέον. Παρακαλώ επέστρεψε στην επιλογή επιχείρησης.")
                st.session_state.pop("company", None)
                st.rerun()
            if fresh.get("id", 0) < 0:
                st.info("Demo εταιρεία: η προσθήκη υπαλλήλου δεν αποθηκεύεται στη ΒΔ.")
                st.stop()

            st.session_state.company = fresh
            company = fresh

            try:
                # DB expects lists (JSON stored)
                add_employee(company["id"], name.strip(), roles, availability)
                st.session_state.employees = get_employees(company["id"])
                st.success(f"✅ Προστέθηκε ο/η {name.strip()}")
                st.rerun()
            except Exception as ex:
                st.error(f"Αποτυχία προσθήκης: {ex}")

    employees = st.session_state.employees
    if not employees:
        _empty_state(
            "Δεν υπάρχουν ακόμα υπάλληλοι.",
            ["Προσθέστε προσωπικό για να ξεκινήσει η δημιουργία προγράμματος."],
            demo_button=True,
            on_demo=_demo_seed,
        )
        return

    # ---- List / edit employees ----
    for emp in employees:
        with st.expander(f"{emp['name']}"):
            c1, c2 = st.columns([0.65, 0.35])

            # LEFT: fields + missing helpers
            with c1:
                new_name = st.text_input("Όνομα", value=emp["name"], key=f"name_{emp['id']}")

                # Roles
                current_roles = _employee_roles(emp)
                role_options = company.get("roles", [])
                default_roles, missing_roles = _sanitize_default(role_options, current_roles)
                new_roles = st.multiselect("Ρόλοι", role_options, default=default_roles, key=f"roles_{emp['id']}")

                if missing_roles:
                    st.caption("⚠️ Αγνοήθηκαν ρόλοι: " + ", ".join(missing_roles))
                    if st.button("➕ Πρόσθεσέ τους", key=f"add_missing_roles_{emp['id']}"):
                        st.info("Πρόσθεσε νέους ρόλους από: ⚙️ Ρυθμίσεις Επιχείρησης. Δεν αλλάζουμε αυτόματα το παγκόσμιο schema από τη σελίδα Υπαλλήλων.")

                # Availability
                current_av = _availability_list(emp)
                shift_options = company.get("active_shifts", [])
                default_av, missing_av = _sanitize_default(shift_options, current_av)
                new_av = st.multiselect("Διαθεσιμότητα", shift_options, default=default_av, key=f"av_{emp['id']}")

                if missing_av:
                    st.caption("⚠️ Αγνοήθηκαν βάρδιες: " + ", ".join(missing_av))
                    if st.button("➕ Πρόσθεσέ τες", key=f"add_missing_shifts_{emp['id']}"):
                        st.info("Πρόσθεσε νέες βάρδιες από: ⚙️ Ρυθμίσεις Επιχείρησης. Δεν αλλάζουμε αυτόματα το παγκόσμιο schema από τη σελίδα Υπαλλήλων.")

            # RIGHT: save/delete
            with c2:
                st.write(" ")
                st.write(" ")

                if st.button("💾 Αποθήκευση", key=f"save_{emp['id']}"):
                    try:
                        # Validate against current company config
                        if any(r not in role_options for r in new_roles):
                            st.error("Μη έγκυρος ρόλος.")
                        elif any(s not in shift_options for s in new_av):
                            st.error("Μη έγκυρη βάρδια διαθεσιμότητας.")
                        else:
                            # DB expects roles: list, availability: list (JSON stored)
                            update_employee(emp["id"], new_name.strip(), new_roles, new_av)
                            st.session_state.employees = get_employees(company["id"])
                            st.success("✅ Αποθηκεύτηκε")
                            st.rerun()
                    except Exception as ex:
                        st.error(f"Αποτυχία αποθήκευσης: {ex}")

                if st.button("🗑️ Διαγραφή", key=f"del_{emp['id']}"):
                    st.session_state[f"confirm_del_{emp['id']}"] = True

                if st.session_state.get(f"confirm_del_{emp['id']}", False):
                    st.warning(f"Σίγουρα διαγραφή του/της **{emp['name']}**;", icon="⚠️")
                    cc1, cc2 = st.columns(2)
                    if cc1.button("❌ Ακύρωση", key=f"cancel_del_{emp['id']}"):
                        st.session_state[f"confirm_del_{emp['id']}"] = False
                    if cc2.button("✅ Επιβεβαίωση", key=f"confirm_btn_{emp['id']}"):
                        try:
                            delete_employee(emp["id"])
                            st.session_state[f"confirm_del_{emp['id']}"] = False
                            st.session_state.employees = get_employees(company["id"])
                            st.success("✅ Διαγράφηκε")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Αποτυχία διαγραφής: {ex}")


def _sanitize_default(options: list[str], default_vals: list[str]):
    opts = set(options or [])
    default_vals = default_vals or []
    valid = [v for v in default_vals if v in opts]
    missing = [v for v in default_vals if v not in opts]
    return valid, missing

def _shift_len(shift: str) -> int:
    s, e = SHIFT_TIMES.get(shift, (9, 17))
    return (24 - s + e) if e < s else (e - s)

def _ensure_schedule_df(df: pd.DataFrame | None) -> pd.DataFrame:
    cols = ["Ημέρα", "Ημερομηνία", "Βάρδια", "Υπάλληλος", "Ρόλος", "Ώρες"]
    if df is None or df.empty:
        out = pd.DataFrame(columns=cols)
        # keep Ώρες numeric (float to prevent truncation of e.g. 7.5)
        out["Ώρες"] = pd.Series([], dtype="float64")
        return out
    for c in cols:
        if c not in df.columns:
            df[c] = 0 if c == "Ώρες" else ""
    out = df[cols].copy()
    # enforce numeric for Ώρες (float to avoid type drift/truncation)
    out["Ώρες"] = pd.to_numeric(out["Ώρες"], errors="coerce").fillna(0).astype(float)
    return out

def _availability_list(emp) -> list[str]:
    """Normalize availability to a list of shift names."""
    av = emp.get("availability", [])
    if isinstance(av, dict):
        return [k for k, v in av.items() if v]
    if isinstance(av, list):
        return av
    return []

def _employee_roles(emp) -> list[str]:
    """Normalize roles to a list (DB stores list)."""
    roles = emp.get("roles", [])
    if isinstance(roles, list):
        return roles
    if isinstance(roles, str) and roles.strip():
        return [roles.strip()]
    return []


def generate_schedule(start_date, employees, active_shifts, roles, rules, role_settings, days_count):
    """
    Minimal, robust generator:
    - respects availability (per shift)
    - targets role minimums (min_per_shift)
    - simple round-robin with role priority
    Returns (schedule_df, missing_df)
    """
    if not employees:
        empty = _ensure_schedule_df(pd.DataFrame())
        return empty, pd.DataFrame(columns=["Ημέρα", "Ημερομηνία", "Βάρδια", "Ρόλος", "Λείπουν"])

    start_date = pd.to_datetime(start_date).date()
    rows, missing = [], []
    min_per = {r: max(0, int(role_settings.get(r, {}).get("min_per_shift", 1))) for r in roles}

    idx = 0
    order = list(employees)

    for d in range(days_count):
        day_dt = start_date + dt.timedelta(days=d)
        weekday_name = DAYS[day_dt.weekday()]
        for shift in active_shifts:
            need = dict(min_per)  # copy per shift
            for _ in range(len(order)):
                emp = order[idx % len(order)]
                idx += 1
                avail_list = _availability_list(emp)
                if shift not in avail_list:
                    continue
                eroles = _employee_roles(emp)
                if not eroles:
                    continue

                # Try by role priority (lower value = higher priority)
                placed = False
                for r in sorted(eroles, key=lambda x: role_settings.get(x, {}).get("priority", 5)):
                    if r not in roles:
                        continue
                    if need.get(r, 0) > 0:
                        rows.append({
                            "Ημέρα": weekday_name,
                            "Ημερομηνία": str(day_dt),
                            "Βάρδια": shift,
                            "Υπάλληλος": emp.get("name", ""),
                            "Ρόλος": r,
                            "Ώρες": float(_shift_len(shift)),
                        })
                        need[r] -= 1
                        placed = True
                        break
                if placed and all(v == 0 for v in need.values()):
                    break

            # Record any gaps left for this (date, shift)
            for r_name, left in need.items():
                if left > 0:
                    missing.append({
                        "Ημέρα": weekday_name,
                        "Ημερομηνία": str(day_dt),
                        "Βάρδια": shift,
                        "Ρόλος": r_name,
                        "Λείπουν": left,
                    })

    df = pd.DataFrame(rows, columns=["Ημέρα", "Ημερομηνία", "Βάρδια", "Υπάλληλος", "Ρόλος", "Ώρες"])
    missing_df = pd.DataFrame(missing, columns=["Ημέρα", "Ημερομηνία", "Βάρδια", "Ρόλος", "Λείπουν"])
    return _ensure_schedule_df(df), missing_df


def _empty_state(header: str, lines: list[str], demo_button: bool = False, on_demo=None):
    st.subheader(header)
    for line in lines:
        st.caption(line)
    if demo_button and on_demo:
        if st.button("✨ Συμπλήρωση demo δεδομένων"):
            on_demo()
            st.toast("Δημιουργήθηκαν demo δεδομένα", icon="✨")
            st.rerun()

def back_to_company_selection(key: str):
    if st.button("⬅️ Επιστροφή στην Επιλογή Επιχείρησης", key=key):
        for k in ("company", "employees", "schedule", "missing_staff"):
            st.session_state.pop(k, None)
        st.rerun()

def _demo_seed():
    st.session_state.company = {
        "id": -1,
        "name": "Demo Coffee",
        "work_model": "5ήμερο",
        "rules": {
            "max_daily_hours_5days": 8,
            "weekly_hours_5days": 40,
            "min_daily_rest": 11,
            "max_consecutive_days": 6
        },
        "roles": ["Barista", "Cashier"],
        "active_shifts": ["Πρωί", "Απόγευμα"],
        "role_settings": {
            "Barista": {"priority": 3, "min_per_shift": 1, "preferred_shifts": ["Πρωί"]},
            "Cashier": {"priority": 5, "min_per_shift": 1, "preferred_shifts": ["Απόγευμα"]},
        }
    }
    st.session_state.employees = [
        {"id": 1, "name": "Maria Papadopoulou", "roles": ["Barista"], "availability": ["Πρωί", "Απόγευμα"]},
        {"id": 2, "name": "Nikos Georgiou", "roles": ["Cashier"], "availability": ["Απόγευμα"]},
        {"id": 3, "name": "Eleni Kostopoulou", "roles": ["Barista", "Cashier"], "availability": ["Πρωί", "Απόγευμα"]},
    ]
    today = dt.date.today()
    rows = []
    for i in range(7):
        d = today + dt.timedelta(days=i)
        rows.append({"Ημέρα": DAYS[d.weekday()], "Ημερομηνία": str(d), "Βάρδια": "Πρωί", "Υπάλληλος": "Maria Papadopoulou", "Ρόλος": "Barista", "Ώρες": 8.0})
        rows.append({"Ημέρα": DAYS[d.weekday()], "Ημερομηνία": str(d), "Βάρδια": "Απόγευμα", "Υπάλληλος": "Nikos Georgiou", "Ρόλος": "Cashier", "Ώρες": 7.0})
    st.session_state.schedule = pd.DataFrame(rows)
    st.session_state.missing_staff = pd.DataFrame()

# ------------------------- Utility for grid ------------------------- #

def _week_dates(start_date: dt.date, days=7):
    return [start_date + dt.timedelta(days=i) for i in range(days)]

def _column_key(date: dt.date, shift: str) -> str:
    return f"{date.isoformat()}__{shift}"

def _parse_column_key(k: str):
    d, s = k.split("__", 1)
    return dt.date.fromisoformat(d), s

def _overlap(a_shift: str, b_shift: str) -> bool:
    sa, ea = SHIFT_TIMES.get(a_shift, (9, 17))
    sb, eb = SHIFT_TIMES.get(b_shift, (9, 17))
    def _range(s, e):
        if e < s:  # wrap at midnight
            return [(s, 24), (24, 24 + e)]
        return [(s, e)]
    ra, rb = _range(sa, ea), _range(sb, eb)
    for a1, a2 in ra:
        for b1, b2 in rb:
            if max(a1, b1) < min(a2, b2):
                return True
    return False

def _validate_no_double_bookings(grid_df) -> list[str]:
    errors = []
    for _, row in grid_df.iterrows():
        name = row["Υπάλληλος"]
        per_day = {}
        for col, val in row.items():
            if col == "Υπάλληλος" or not val or val == "— (καμία)":
                continue
            d, s = _parse_column_key(col)
            per_day.setdefault(d, []).append(s)
        for day, shifts in per_day.items():
            for i in range(len(shifts)):
                for j in range(i + 1, len(shifts)):
                    if _overlap(shifts[i], shifts[j]):
                        errors.append(f"Διπλοκράτηση: {name} την {day} ({shifts[i]} ↔ {shifts[j]})")
    return errors

def _grid_from_db_week(company_id: int, employees: list[dict], start_date: dt.date) -> "pd.DataFrame":
    dates = _week_dates(start_date)
    active_shifts = st.session_state.company.get("active_shifts", [])
    cols = ["Υπάλληλος"] + [_column_key(d, s) for d in dates for s in active_shifts]
    df = pd.DataFrame(columns=cols)
    df["Υπάλληλος"] = [e["name"] for e in employees]

    # Prefill all shift cells with "— (καμία)" so the editor shows the select properly
    for c in cols:
        if c != "Υπάλληλος":
            df[c] = "— (καμία)"

    # Overlay existing assignments from DB; show explicit placeholder for "assigned without role"
    existing = get_schedule_range(company_id, dates[0].isoformat(), dates[-1].isoformat())
    for row in existing:
        key = _column_key(dt.date.fromisoformat(row["date"]), row["shift"])
        value = row.get("role") if row.get("role") else "— (χωρίς ρόλο)"
        if key in df.columns:
            df.loc[df["Υπάλληλος"] == row["employee_name"], key] = value
    return df


def _assignments_from_grid(grid_df, employees, start_date: dt.date) -> list[dict]:
    name_to_id = {e["name"]: e["id"] for e in employees}
    valid_roles = set(st.session_state.company.get("roles", []))
    assignments = []
    for _, row in grid_df.iterrows():
        emp_name = row["Υπάλληλος"]
        emp_id = name_to_id.get(emp_name)
        if not emp_id:
            continue
        for col, val in row.items():
            if col == "Υπάλληλος" or not val or val == "— (καμία)":
                continue
            d, s = _parse_column_key(col)
            if val == "— (χωρίς ρόλο)":
                assignments.append({"employee_id": emp_id, "date": d.isoformat(), "shift": s, "role": None})
            elif val in valid_roles:
                assignments.append({"employee_id": emp_id, "date": d.isoformat(), "shift": s, "role": val})
    return assignments


# ------------------------- Pages ------------------------- #

def page_select_company():
    st.subheader("🏢 Επιλογή Επιχείρησης")

    companies = get_all_companies() or []
    if not companies:
        st.info("Δεν υπάρχουν εταιρείες. Δημιούργησα μια default.")
        create_company("Default Business")
        companies = get_all_companies() or []

    # Build select options
    options = {f"{c.get('name','?')} (ID:{c.get('id','?')})": c.get('id') for c in companies}
    if not options:
        st.error("Δεν βρέθηκαν εταιρείες (άδεια λίστα).")
        return

    selected_label = st.selectbox("Επιλογή", list(options.keys()))
    if st.button("✅ Άνοιγμα") and selected_label in options:
        company_id = options[selected_label]
        st.session_state.company = get_company(company_id) or {}
        # safe defaults
        st.session_state.company.setdefault("active_shifts", ALL_SHIFTS.copy())
        st.session_state.company.setdefault("roles", DEFAULT_ROLES.copy())
        st.session_state.company.setdefault("rules", DEFAULT_RULES.copy())
        st.session_state.company.setdefault("role_settings", {})
        st.session_state.company.setdefault("work_model", "5ήμερο")
        st.session_state.employees = get_employees(company_id)
        st.rerun()

    with st.expander("Δεν βλέπεις εταιρεία;"):
        if st.text_input("Όνομα νέας εταιρείας", key="new_co_name"):
            if st.button("➕ Δημιουργία"):
                create_company(st.session_state["new_co_name"].strip())
                st.success("Η εταιρεία δημιουργήθηκε.")
                st.rerun()


def page_schedule():
    st.title("📅 Schedule Management")
    st.caption("Create and manage employee schedules with AI-powered optimization")

    # ---- Guards & init ----
    st.session_state.setdefault("schedule", pd.DataFrame())
    st.session_state.setdefault("missing_staff", pd.DataFrame())
    st.session_state.setdefault("violations", pd.DataFrame())

    if "company" not in st.session_state or not st.session_state.get("company", {}).get("name"):
        st.warning("⚠️ Please select a company from the sidebar.")
        return
    if "employees" not in st.session_state or not st.session_state.employees:
        st.warning("⚠️ No employees found. Add employees to create schedules.")
        return

    company = st.session_state.company
    emps = st.session_state.employees

    # ====== AI Insights Panel ======
    with st.expander("🤖 AI Scheduling Insights", expanded=False):
        if st.button("🔍 Analyze Staffing with AI"):
            with st.spinner("AI analyzing your staffing situation..."):
                try:
                    from ai_scheduler import analyze_schedule_with_ai
                    
                    insights = analyze_schedule_with_ai(
                        emps,
                        company.get("active_shifts", []),
                        company.get("roles", []),
                        company.get("rules", {}),
                        company.get("role_settings", {}),
                        days_count=7,
                        work_model=company.get("work_model", "5ήμερο")
                    )
                    
                    if "error" not in insights:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("**📊 Staffing Analysis**")
                            st.info(insights.get("staffing_insights", "No insights available"))
                            
                            if insights.get("coverage_score"):
                                st.metric("Coverage Score", f"{insights['coverage_score']}/100")
                        
                        with col2:
                            st.markdown("**💡 Optimization Tips**")
                            for tip in insights.get("optimization_tips", []):
                                st.success(f"✓ {tip}")
                        
                        st.divider()
                        
                        if insights.get("predicted_conflicts"):
                            st.markdown("**⚠️ Predicted Conflicts**")
                            for conflict in insights["predicted_conflicts"]:
                                st.warning(conflict)
                        
                        if insights.get("recommended_actions"):
                            st.markdown("**🎯 Recommended Actions**")
                            for action in insights["recommended_actions"]:
                                st.markdown(f"• {action}")
                    else:
                        st.error(f"AI Analysis failed: {insights.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    st.error(f"AI features unavailable: {str(e)}")
                    st.caption("Make sure OpenAI API key is configured in .env file")

    # ====== Header controls ======
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        mode = st.radio("Schedule Duration", ["🗓️ Weekly (7 days)", "📅 Monthly (30 days)"], key="mode_sched")
    with col2:
        start_date = st.date_input("Start Date", dt_date.today(), key="start_sched")
    
    days_count = 7 if mode == "🗓️ Weekly (7 days)" else 30

    # Builder is weekly (7 days)
    week_len = 7
    dates = [start_date + timedelta(days=i) for i in range(week_len)]

    # ====== Generator / Auto-fix wires ======
    gen = generate_schedule  # (#15) Use local robust generator; remove undefined alias S

    # ====== Actions ======
    cgen, cfix = st.columns([0.35, 0.35])
    with cgen:
        generate_clicked = st.button("🛠 Δημιουργία", type="primary", key="btn_generate")
        if days_count == 30:
            st.caption("⚠️ Η δημιουργία για 30 ημέρες θα αντικαταστήσει όλο το διάστημα.")
            confirm_month = st.checkbox("Επιβεβαιώνω την αντικατάσταση όλων των 30 ημερών", key="confirm_month")
        else:
            confirm_month = True
    with cfix:
        refix_clicked = st.button("🧹 Επανέλεγχος & Αυτο-διόρθωση", help="Εφάρμοσε κανόνες στο τρέχον πρόγραμμα")

    # --- Generate schedule → optional auto-fix → persist to DB (week or month) ---
    if generate_clicked and confirm_month:
        df, missing_df = gen(
            start_date,
            emps,
            company.get("active_shifts", []),
            company.get("roles", []),
            company.get("rules", {}),
            company.get("role_settings", {}),
            days_count,
        )

        if callable(_auto_fix_schedule):  # (#16) only if imported & callable
            fixed_df, viols = _auto_fix_schedule(
                df, emps,
                company.get("active_shifts", []),
                company.get("roles", []),
                company.get("rules", {}),
                company.get("role_settings", {}),
                company.get("work_model", "5ήμερο"),
            )
        else:
            fixed_df = df
            viols = check_violations(df, company.get("rules", {}), company.get("work_model", "5ήμερο"))

        st.session_state.schedule = fixed_df
        st.session_state.missing_staff = missing_df
        st.session_state.violations = viols

        def _name_to_id(nm: str) -> Optional[int]:
            return get_employee_id_by_name(company["id"], nm)

        assignments = []
        period_start = start_date
        period_end = start_date + timedelta(days=days_count - 1)
        for _, r in fixed_df.iterrows():
            d = pd.to_datetime(r["Ημερομηνία"]).date()
            if period_start <= d <= period_end and r.get("Βάρδια") in company.get("active_shifts", []):
                eid = _name_to_id(r["Υπάλληλος"])
                if eid:
                    assignments.append({
                        "employee_id": eid,
                        "date": d.isoformat(),
                        "shift": r["Βάρδια"],
                        "role": r.get("Ρόλος") or None,
                    })
        if company.get("id", 0) < 0:
            st.info("Demo εταιρεία: δημιουργήθηκε πρόγραμμα, αλλά η αποθήκευση στη ΒΔ είναι απενεργοποιημένη.")
        else:
            bulk_save_week_schedule(company["id"], assignments, period_start.isoformat(), period_end.isoformat())
            st.success("✅ Δημιουργήθηκε και αποθηκεύτηκε πρόγραμμα για όλη την επιλεγμένη περίοδο.")
        st.rerun()
    elif generate_clicked and not confirm_month:
        st.warning("Χρειάζεται επιβεβαίωση για αποθήκευση ολόκληρου μήνα.")

    # --- Re-fix current in-memory schedule ---
    if refix_clicked and not st.session_state.schedule.empty:
        if callable(_auto_fix_schedule):
            fixed_df, viols = _auto_fix_schedule(
                st.session_state.schedule, emps,
                company.get("active_shifts", []),
                company.get("roles", []),
                company.get("rules", {}),
                company.get("role_settings", {}),
                company.get("work_model", "5ήμερο"),
            )
        else:
            fixed_df = st.session_state.schedule
            viols = check_violations(fixed_df, company.get("rules", {}), company.get("work_model", "5ήμερο"))
        st.session_state.schedule = fixed_df
        st.session_state.violations = viols
        st.success("🔧 Επανέλεγχος ολοκληρώθηκε.")
        st.rerun()

    # ====== Enhanced KPIs & Analytics ======
    sched = st.session_state.schedule.copy()
    st.divider()
    st.markdown("#### 📈 Επισκόπηση Προγράμματος")
    
    # Use advanced KPI cards if available
    if ADVANCED_FEATURES:
        render_kpi_cards(sched, emps, company, st.session_state.get("violations"))
    else:
        # Fallback to basic metrics
        c1, c2, c3, c4 = st.columns(4)
        if not sched.empty:
            try:
                dser = pd.to_datetime(sched["Ημερομηνία"], errors="coerce").dt.date
                c1.metric("Συνολικές βάρδιες", len(sched))
                c2.metric("Υπάλληλοι", len(emps))
                c3.metric("Ημέρες", len(set(dser)))
                c4.metric("Ρόλοι", len(company.get("roles", [])))
            except Exception:
                pass
        else:
            c1.metric("Συνολικές βάρδιες", 0)
            c2.metric("Υπάλληλοι", len(emps))
            c3.metric("Ημέρες", 0)
            c4.metric("Ρόλοι", len(company.get("roles", [])))
    
    # Add quick action buttons
    st.divider()
    col_act1, col_act2, col_act3, col_act4 = st.columns(4)
    
    with col_act1:
        if ADVANCED_FEATURES and st.button("📊 Αναλυτικά", use_container_width=True):
            if not sched.empty:
                show_detailed_analytics(sched, emps, company.get("active_shifts", []), company.get("roles", []))
            else:
                st.toast("Δεν υπάρχουν δεδομένα για ανάλυση", icon="⚠️")
    
    with col_act2:
        if ADVANCED_FEATURES and st.button("📥 Εξαγωγή", use_container_width=True):
            if not sched.empty:
                show_export_dialog(sched, company, emps, st.session_state.get("violations"))
            else:
                st.toast("Δεν υπάρχουν δεδομένα για εξαγωγή", icon="⚠️")
    
    with col_act3:
        if ADVANCED_FEATURES and st.button("📤 Εισαγωγή", use_container_width=True):
            show_import_dialog(company, emps)
    
    with col_act4:
        if ADVANCED_FEATURES and st.button("📅 Ημερολόγιο", use_container_width=True):
            st.session_state["show_calendar"] = not st.session_state.get("show_calendar", False)
            st.rerun()

    # ====== Calendar & Timeline Views ======
    if ADVANCED_FEATURES and st.session_state.get("show_calendar", False):
        st.divider()
        render_calendar_view(sched, company, emps)
        
        st.divider()
        render_weekly_timeline(sched, dates[0])
    
    # ====== Employee Workload Analysis ======
    if ADVANCED_FEATURES and not sched.empty:
        st.divider()
        render_employee_workload_comparison(sched, emps)
    
    # ====== Weekly Visual Builder ======
    st.divider()
    st.markdown("#### 🧱 Visual builder (εβδομαδιαίος πίνακας)")

    active_shifts = company.get("active_shifts", [])

    # Build initial grid from DB using unified helpers (#17)
    grid_df = _grid_from_db_week(company["id"], emps, dates[0])

    # Column labels for nicer headers
    col_labels = { _column_key(d, s): f"{DAYS[d.weekday()]} {d.strftime('%d/%m')} • {s}"
                   for d in dates for s in active_shifts }

    role_choices = ["— (καμία)", "— (χωρίς ρόλο)"] + company.get("roles", [])
    colcfg = {k: st.column_config.SelectboxColumn(label=col_labels.get(k, k), options=role_choices, default="— (καμία)")
              for k in grid_df.columns if k != "Υπάλληλος"}

    edited = st.data_editor(
        grid_df,
        column_config={"Υπάλληλος": st.column_config.TextColumn("Υπάλληλος", disabled=True), **colcfg},
        use_container_width=True, hide_index=True, num_rows="fixed"
    )

    cA, cB = st.columns([0.5, 0.5])
    with cA:
        if st.button(f"💾 Αποθήκευση εβδομάδας στη ΒΔ ({dates[0].isoformat()} → {dates[-1].isoformat()})", type="primary"):
            errs = _validate_no_double_bookings(edited)
            if errs:
                for e in errs:
                    st.error(e)
            else:
                assignments = _assignments_from_grid(edited, emps, dates[0])
                if company.get("id", 0) < 0:
                    st.info("Demo εταιρεία: η αποθήκευση στη ΒΔ είναι απενεργοποιημένη.")
                else:
                    bulk_save_week_schedule(company["id"], assignments, dates[0].isoformat(), dates[-1].isoformat())
                st.success("✅ Αποθηκεύτηκε το εβδομαδιαίο πρόγραμμα στη βάση.")
                st.rerun()
        if mode == "📅 Μηνιαίο":
            st.caption("Σημείωση: ο οπτικός επεξεργαστής αποθηκεύει **μόνο** την ορατή εβδομάδα. Για ολόκληρο μήνα, χρησιμοποίησε το κουμπί Δημιουργία (που αποθηκεύει 30 ημέρες).")
    with cB:
        if st.button("🔄 Φόρτωση από ΒΔ (εβδομάδα)"):
            st.rerun()

    # ====== SHIFT SWAPS ======
    st.divider()
    st.markdown("#### 🔁 Αιτήματα αλλαγής βάρδιας (ίδιο είδος βάρδιας)")  # (#19) clarify semantics

    with st.expander("📝 Υποβολή αιτήματος (εργαζόμενου)", expanded=False):
        st.caption("Ανταλλαγή γίνεται για **το ίδιο είδος βάρδιας** την ίδια ημέρα.")
        emp_names = [e["name"] for e in emps]
        req_emp = st.selectbox("Αιτών", emp_names, key="swap_req_emp")
        target_emp = st.selectbox("Συνάδελφος", [n for n in emp_names if n != req_emp], key="swap_target_emp")
        req_date = st.date_input("Ημερομηνία", dates[0], key="swap_date")
        req_shift = st.selectbox("Βάρδια", active_shifts, key="swap_shift")

        if st.button("📨 Υποβολή αιτήματος"):
            rid = get_employee_id_by_name(company["id"], req_emp)
            tid = get_employee_id_by_name(company["id"], target_emp)
            have = get_schedule_range(company["id"], req_date.isoformat(), req_date.isoformat())
            target_has = any(x["employee_id"] == tid and x["shift"] == req_shift for x in have)
            requester_has = any(x["employee_id"] == rid and x["shift"] == req_shift for x in have)
            if not requester_has:
                st.error("Ο αιτών δεν έχει αυτή τη βάρδια.")
            elif not target_has:
                st.error("Ο συνάδελφος δεν έχει αυτή τη βάρδια.")
            else:
                create_swap_request(company["id"], rid, tid, req_date.isoformat(), req_shift)
                st.success("✅ Καταχωρήθηκε αίτημα αλλαγής (pending).")

    with st.expander("📋 Εκκρεμή αιτήματα (manager)", expanded=True):
        pending = list_swap_requests(company["id"], status="pending")
        if not pending:
            st.info("Καμία εκκρεμότητα.")
        else:
            for r in pending:
                st.markdown(f"- **#{r['id']}** {r['date']} • *{r['shift']}* — {r['requester_name']} → {r['target_name']}")
                c1, c2, c3 = st.columns([0.2, 0.2, 0.6])
                note = c3.text_input("Σημείωση", key=f"note_{r['id']}")
                if c1.button("✅ Έγκριση", key=f"ok_{r['id']}"):
                    day_sched = get_schedule_range(company["id"], r["date"], r["date"])
                    req_has = any(x["employee_id"] == r["requester_id"] and x["shift"] == r["shift"] for x in day_sched)
                    target_has = any(x["employee_id"] == r["target_employee_id"] and x["shift"] == r["shift"] for x in day_sched)
                    if not (req_has and target_has):
                        st.error("Το ζεύγος βαρδιών δεν είναι έγκυρο πλέον.")
                    else:
                        update_swap_status(r["id"], "approved", note)
                        apply_approved_swap(company["id"], r["date"], r["shift"], r["requester_id"], r["target_employee_id"])
                        st.success("✅ Εφαρμόστηκε.")
                        st.rerun()
                if c2.button("⛔️ Απόρριψη", key=f"reject_{r['id']}"):
                    update_swap_status(r["id"], "rejected", note)
                    st.info("Απορρίφθηκε.")
                    st.rerun()
