# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import datetime as dt
from datetime import date as dt_date, timedelta

from db import (
    get_all_companies, get_company, update_company, create_company,
    get_employees, add_employee, update_employee, delete_employee,
    # Visual builder + swaps:
    get_schedule_range, bulk_save_week_schedule, get_employee_id_by_name,
    create_swap_request, list_swap_requests, update_swap_status, apply_approved_swap,
)

from constants import DAYS, SHIFT_TIMES, ALL_SHIFTS, DEFAULT_ROLES, DEFAULT_RULES

from scheduler import check_violations

def page_business():
    back_to_company_selection("back_business")
    st.subheader("⚙️ Ρυθμίσεις Επιχείρησης")

    # Require a selected company
    if "company" not in st.session_state or not st.session_state.get("company", {}):
        st.warning("🛈 Δεν έχει επιλεγεί επιχείρηση.")
        return

    company = st.session_state.company
    company.setdefault("active_shifts", ALL_SHIFTS.copy())
    company.setdefault("roles", DEFAULT_ROLES.copy())
    company.setdefault("rules", DEFAULT_RULES.copy())
    company.setdefault("role_settings", {})
    company.setdefault("work_model", "5ήμερο")
    company.setdefault("active", True)

    # -------- Βασικά --------
    with st.container():
        st.subheader("Βασικά")
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            company["name"] = st.text_input("Όνομα", company.get("name", ""))
        with col2:
            options = ["5ήμερο", "6ήμερο", "7ήμερο"]
            current = company.get("work_model", "5ήμερο")
            idx = options.index(current) if current in options else 0
            company["work_model"] = st.selectbox("Μοντέλο", options, index=idx)
        with col3:
            company["active"] = st.toggle("Ενεργή", value=bool(company.get("active", True)))
        st.caption("Οι ρυθμίσεις αυτές επηρεάζουν τους ελέγχους συμμόρφωσης και τις προεπιλογές δημιουργίας.")

    # -------- Βάρδιες --------
    with st.expander("🕒 Βάρδιες", expanded=False):
        new_shift = st.text_input("Νέα βάρδια")
        c1, c2 = st.columns(2)
        if c1.button("➕ Προσθήκη") and new_shift:
            if new_shift not in company["active_shifts"]:
                company["active_shifts"].append(new_shift)
        if c2.button("↩️ Προεπιλογές"):
            company["active_shifts"] = ALL_SHIFTS.copy()
        st.multiselect("Ενεργές", company["active_shifts"], default=company["active_shifts"], disabled=True)

    # -------- Ρόλοι & Ρυθμίσεις --------
    with st.expander("👔 Ρόλοι & Ρυθμίσεις", expanded=True):
        new_role = st.text_input("Νέος ρόλος")
        if st.button("➕ Προσθήκη Ρόλου") and new_role:
            if new_role not in company["roles"]:
                company["roles"].append(new_role)

        company.setdefault("role_settings", {})
        for r in company.get("roles", []):
            rs = company["role_settings"].setdefault(r, {})
            # defaults
            rs["priority"]        = int(rs.get("priority", 5))
            rs["min_per_shift"]   = int(rs.get("min_per_shift", 1))
            rs["max_per_shift"]   = int(rs.get("max_per_shift", 5))
            rs["max_hours_week"]  = int(rs.get("max_hours_week", 40))
            rs["cost"]            = float(rs.get("cost", 0.0))
            rs.setdefault("preferred_shifts", [])

            st.markdown(f"**{r}**")
            col = st.columns(3)
            rs["priority"]       = col[0].slider("Προτερ.", 1, 10, rs["priority"], key=f"prio_{r}")
            rs["min_per_shift"]  = col[1].number_input("Min/shift", 0, 10, rs["min_per_shift"], key=f"min_{r}")
            rs["max_per_shift"]  = col[2].number_input("Max/shift", 1, 10, rs["max_per_shift"], key=f"max_{r}")
            rs["preferred_shifts"] = st.multiselect(
                "Προτιμώμενες",
                company.get("active_shifts", []),
                default=rs.get("preferred_shifts", []),
                key=f"pref_{r}"
            )

    # -------- Κανόνες --------
    with st.expander("⚖️ Κανόνες", expanded=False):
        rules = company.get("rules", {})
        rule_defs = {
            "max_daily_hours_5days": (6, 12, rules.get("max_daily_hours_5days", 8)),
            "max_daily_hours_6days": (6, 12, rules.get("max_daily_hours_6days", 9)),
            "max_daily_overtime":    (0, 6,  rules.get("max_daily_overtime", 3)),
            "min_daily_rest":        (8, 24, rules.get("min_daily_rest", 11)),
            "weekly_hours_5days":    (30, 50, rules.get("weekly_hours_5days", 40)),
            "weekly_hours_6days":    (30, 60, rules.get("weekly_hours_6days", 48)),
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
                        company["roles"] = sorted(set(role_options) | set(missing_roles))
                        update_company(company["id"], company)
                        st.success("Προστέθηκαν οι ρόλοι.")
                        st.rerun()

                # Availability
                current_av = _availability_list(emp)
                shift_options = company.get("active_shifts", [])
                default_av, missing_av = _sanitize_default(shift_options, current_av)
                new_av = st.multiselect("Διαθεσιμότητα", shift_options, default=default_av, key=f"av_{emp['id']}")

                if missing_av:
                    st.caption("⚠️ Αγνοήθηκαν βάρδιες: " + ", ".join(missing_av))
                    if st.button("➕ Πρόσθεσέ τες", key=f"add_missing_shifts_{emp['id']}"):
                        company["active_shifts"] = sorted(set(shift_options) | set(missing_av))
                        update_company(company["id"], company)
                        st.success("Προστέθηκαν οι βάρδιες.")
                        st.rerun()

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
                            # DB expects roles: list, availability: list (JSON stored):contentReference[oaicite:1]{index=1}
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
        return pd.DataFrame(columns=cols)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols]

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
                            "Ώρες": _shift_len(shift),
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
        rows.append({"Ημέρα": DAYS[d.weekday()], "Ημερομηνία": str(d), "Βάρδια": "Πρωί", "Υπάλληλος": "Maria Papadopoulou", "Ρόλος": "Barista", "Ώρες": 8})
        rows.append({"Ημέρα": DAYS[d.weekday()], "Ημερομηνία": str(d), "Βάρδια": "Απόγευμα", "Υπάλληλος": "Nikos Georgiou", "Ρόλος": "Cashier", "Ώρες": 7})
    st.session_state.schedule = pd.DataFrame(rows)
    st.session_state.missing_staff = pd.DataFrame()

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

    # 🔧 Prefill all shift cells with "— (καμία)" so the editor shows the select properly
    for c in cols:
        if c != "Υπάλληλος":
            df[c] = "— (καμία)"

    # Overlay existing assignments from DB as "✅"
    existing = get_schedule_range(company_id, dates[0].isoformat(), dates[-1].isoformat())
    for row in existing:
        key = _column_key(dt.date.fromisoformat(row["date"]), row["shift"])
        df.loc[df["Υπάλληλος"] == row["employee_name"], key] = "✅"
    return df

def _assignments_from_grid(grid_df, employees, start_date: dt.date) -> list[dict]:
    name_to_id = {e["name"]: e["id"] for e in employees}
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
            assignments.append({"employee_id": emp_id, "date": d.isoformat(), "shift": s})
    return assignments







def page_schedule():
    back_to_company_selection("back_schedule")
    st.subheader("📅 Πρόγραμμα")

    # ---- Guards & init ----
    st.session_state.setdefault("schedule", pd.DataFrame())
    st.session_state.setdefault("missing_staff", pd.DataFrame())
    st.session_state.setdefault("violations", pd.DataFrame())

    if "company" not in st.session_state or not st.session_state.get("company", {}).get("name"):
        st.warning("🛈 Δεν έχει επιλεγεί επιχείρηση.")
        return
    if "employees" not in st.session_state or not st.session_state.employees:
        st.warning("🛈 Δεν υπάρχουν υπάλληλοι. Προσθέστε για να δημιουργηθεί πρόγραμμα.")
        return

    company = st.session_state.company
    emps = st.session_state.employees

    # ---- Επιλογές δημιουργίας ----
    mode = st.radio("Τύπος", ["🗓️ Εβδομαδιαίο", "📅 Μηνιαίο"], key="mode_sched")
    days_count = 7 if mode == "🗓️ Εβδομαδιαίο" else 30
    start_date = st.date_input("Έναρξη", dt_date.today(), key="start_sched")

    week_len = 7  # ο builder είναι εβδομαδιαίος
    dates = [start_date + timedelta(days=i) for i in range(week_len)]

    # ---- Generator / Auto-fix (προαιρετικά, αν υπάρχουν στο scheduler.py) ----
    import scheduler as S
    gen = getattr(S, "generate_schedule_smart", None) or \
          getattr(S, "generate_schedule_opt", None)   or \
          S.generate_schedule_v2
    from scheduler import check_violations
    try:
        from scheduler import auto_fix_schedule
    except Exception:
        auto_fix_schedule = None

    cgen, cfix = st.columns([0.25, 0.35])
    with cgen:
        generate_clicked = st.button("🛠 Δημιουργία", type="primary", key="btn_generate")
    with cfix:
        refix_clicked = st.button("🧹 Επανέλεγχος & Αυτο-διόρθωση", help="Εφάρμοσε κανόνες στο τρέχον πρόγραμμα")

    if generate_clicked:
        df, missing_df = gen(
            start_date,
            st.session_state.employees,
            company.get("active_shifts", []),
            company.get("roles", []),
            company.get("rules", {}),
            company.get("role_settings", {}),
            days_count,
            company.get("work_model", "5ήμερο"),
        )
        if auto_fix_schedule:
            fixed_df, viols = auto_fix_schedule(
                df,
                st.session_state.employees,
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
        st.success("✅ Δημιουργήθηκε πρόγραμμα.")

    if refix_clicked and not st.session_state.schedule.empty:
        if auto_fix_schedule:
            fixed_df, viols = auto_fix_schedule(
                st.session_state.schedule,
                st.session_state.employees,
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
        st.success("🔧 Έγινε επανέλεγχος & διόρθωση.")
        st.rerun()

    # ====== KPIs ======
    sched = st.session_state.schedule.copy()
    st.divider()
    st.markdown("#### 📈 KPIs Προγράμματος")
    c1, c2, c3, c4 = st.columns(4)
    if not sched.empty:
        try:
            dser = pd.to_datetime(sched["Ημερομηνία"], errors="coerce").dt.date
        except Exception:
            dser = sched["Ημερομηνία"]
        with c1: st.metric("Ημέρες", int(pd.Series(dser).nunique()))
        with c2: st.metric("Αναθέσεις", int(len(sched)))
        with c3: st.metric("Άτομα", int(sched["Υπάλληλος"].nunique()))
        with c4: st.metric("Ρόλοι", int(sched["Ρόλος"].nunique()))
    else:
        with c1: st.metric("Ημέρες", 0)
        with c2: st.metric("Αναθέσεις", 0)
        with c3: st.metric("Άτομα", 0)
        with c4: st.metric("Ρόλοι", 0)

    # ====== VISUAL BUILDER (weekly) ======
    st.divider()
    st.markdown("#### 🧱 Visual builder (εβδομαδιαίος πίνακας)")

    active_shifts = company.get("active_shifts", [])
    col_labels = {_column_key(d, s): f"{DAYS[d.weekday()][:3]} {d.strftime('%d/%m')} • {s}"
                  for d in dates for s in active_shifts}

    grid_df = _grid_from_db_week(company["id"], emps, dates[0])

    colcfg = {}
    choices = ["— (καμία)"] + company.get("roles", []) + ["✅"]
    for k, label in col_labels.items():
        colcfg[k] = st.column_config.SelectboxColumn(label=label, options=choices, default="— (καμία)")

    # Ensure no NaN/None values remain for select columns
    for c in grid_df.columns:
        if c != "Υπάλληλος":
            grid_df[c] = grid_df[c].fillna("— (καμία)")
    edited = st.data_editor(
        grid_df,
        column_config={"Υπάλληλος": st.column_config.TextColumn("Υπάλληλος", disabled=True), **colcfg},
        use_container_width=True, hide_index=True, num_rows="fixed"
    )

    cA, cB = st.columns([0.5, 0.5])
    with cA:
        if st.button("💾 Αποθήκευση εβδομάδας στη ΒΔ", type="primary"):
            errs = _validate_no_double_bookings(edited)
            if errs:
                for e in errs: st.error(e)
            else:
                assignments = _assignments_from_grid(edited, emps, dates[0])
                bulk_save_week_schedule(company["id"], assignments, dates[0].isoformat(), dates[-1].isoformat())
                st.success("✅ Αποθηκεύτηκε το εβδομαδιαίο πρόγραμμα στη βάση.")
    with cB:
        if st.button("🔄 Φόρτωση από ΒΔ (εβδομάδα)"):
            st.rerun()

    # ====== SHIFT SWAPS ======
    st.divider()
    st.markdown("#### 🔁 Αιτήματα αλλαγής βάρδιας")

    with st.expander("📝 Υποβολή αιτήματος (εργαζόμενου)", expanded=False):
        emp_names = [e["name"] for e in emps]
        req_emp = st.selectbox("Αιτών", emp_names, key="swap_req_emp")
        target_emp = st.selectbox("Συνάδελφος", [n for n in emp_names if n != req_emp], key="swap_target_emp")
        req_date = st.date_input("Ημερομηνία", dates[0], key="swap_date")
        req_shift = st.selectbox("Βάρδια", active_shifts, key="swap_shift")

        if st.button("📨 Υποβολή αιτήματος"):
            rid = get_employee_id_by_name(company["id"], req_emp)
            tid = get_employee_id_by_name(company["id"], target_emp)
            have = get_schedule_range(company["id"], req_date.isoformat(), req_date.isoformat())
            target_has = any(r["employee_id"] == tid and r["shift"] == req_shift for r in have)
            if target_has:
                st.error("Ο συνάδελφος έχει ήδη την ίδια βάρδια εκείνη την ημέρα.")
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
                    tgt_has = any(x["employee_id"] == r["target_employee_id"] and x["shift"] == r["shift"] for x in day_sched)
                    if not req_has:
                        st.error("Ο αιτών δεν έχει αυτή τη βάρδια για να την αλλάξει.")
                    elif tgt_has:
                        st.error("Ο στόχος έχει ήδη την ίδια βάρδια (δε γίνεται αλλαγή).")
                    else:
                        apply_approved_swap(company["id"], r["date"], r["shift"], r["requester_id"], r["target_employee_id"])
                        update_swap_status(r["id"], "approved", note)
                        st.success("✅ Εγκεκριμένο & ενημερώθηκε το πρόγραμμα στη ΒΔ.")
                        st.rerun()
                if c2.button("❌ Απόρριψη", key=f"rej_{r['id']}"):
                    update_swap_status(r["id"], "rejected", note)
                    st.warning("⛔ Απορρίφθηκε.")
                    st.rerun()

    # ====== Ελλείψεις / Παραβιάσεις ======
    miss = st.session_state.get("missing_staff", pd.DataFrame())
    if miss is not None and not miss.empty:
        with st.expander("🧩 Ελλείψεις στελέχωσης", expanded=False):
            try:
                st.dataframe(miss, use_container_width=True, hide_index=True)
            except TypeError:
                st.dataframe(miss.style.hide(axis="index"), use_container_width=True)

    viols = st.session_state.get("violations", pd.DataFrame())
    with st.expander("⚠️ Παραβιάσεις Κανόνων (μετά την αυτο-διόρθωση)", expanded=False):
        if viols is None or viols.empty:
            st.success("Δεν εντοπίστηκαν παραβιάσεις.")
        else:
            try:
                st.dataframe(viols, use_container_width=True, hide_index=True)
            except TypeError:
                st.dataframe(viols.style.hide(axis="index"), use_container_width=True)
