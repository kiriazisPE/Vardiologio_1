# -*- coding: utf-8 -*-
import datetime as dt
import streamlit as st
import pandas as pd
from datetime import date as dt_date, timedelta

from db import (
    get_all_companies,
    get_company,
    update_company,
    create_company,
    get_employees,
    add_employee,
    update_employee,
    delete_employee,
)
from constants import ALL_SHIFTS, DEFAULT_ROLES, DEFAULT_RULES, SHIFT_TIMES, DAYS
from scheduler import check_violations



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

def page_business():
    back_to_company_selection("back_business")
    st.subheader("⚙️ Ρυθμίσεις Επιχείρησης")
    company = st.session_state.company

    with st.container():
        st.subheader("Βασικά")
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            company["name"] = st.text_input("Όνομα", company.get("name", ""))
        with col2:
            options = ["5ήμερο", "6ήμερο", "7ήμερο"]
            current = company.get("work_model", "5ήμερο")
            try:
                idx = options.index(current)
            except ValueError:
                idx = 0
            company["work_model"] = st.selectbox("Μοντέλο", options, index=idx)

        with col3:
            company["active"] = st.toggle("Ενεργή", value=company.get("active", True))
        st.caption("Οι ρυθμίσεις αυτές επηρεάζουν τους ελέγχους συμμόρφωσης και τις προεπιλογές δημιουργίας.")

    with st.expander("🕒 Βάρδιες", expanded=False):
        new_shift = st.text_input("Νέα βάρδια")
        c1, c2 = st.columns(2)
        if c1.button("➕ Προσθήκη") and new_shift:
            if new_shift not in company["active_shifts"]:
                company["active_shifts"].append(new_shift)
        if c2.button("↩️ Προεπιλογές"):
            company["active_shifts"] = ALL_SHIFTS.copy()
        st.multiselect("Ενεργές", company["active_shifts"], default=company["active_shifts"], disabled=True)

    with st.expander("👔 Ρόλοι & Ρυθμίσεις", expanded=True):
        new_role = st.text_input("Νέος ρόλος")
        if st.button("➕ Προσθήκη Ρόλου") and new_role:
            if new_role not in company["roles"]:
                company["roles"].append(new_role)

        company.setdefault("role_settings", {})

        for r in company.get("roles", []):
            # Ensure dict exists and populate missing keys safely
            rs = company["role_settings"].setdefault(r, {})
            rs["priority"]        = int(rs.get("priority", 5))
            rs["min_per_shift"]   = int(rs.get("min_per_shift", 1))
            rs["max_per_shift"]   = int(rs.get("max_per_shift", 5))
            rs["max_hours_week"]  = int(rs.get("max_hours_week", 40))
            rs["cost"]            = float(rs.get("cost", 0))
            rs.setdefault("preferred_shifts", [])

            st.markdown(f"**{r}**")
            col = st.columns(3)
            rs["priority"]       = col[0].slider("Προτερ.", 1, 10, int(rs.get("priority", 5)), key=f"prio_{r}")
            rs["min_per_shift"]  = col[1].number_input("Min/shift", 0, 10, int(rs.get("min_per_shift", 1)), key=f"min_{r}")
            rs["max_per_shift"]  = col[2].number_input("Max/shift", 1, 10, int(rs.get("max_per_shift", 5)), key=f"max_{r}")
            rs["preferred_shifts"] = st.multiselect(
                "Προτιμώμενες",
                company.get("active_shifts", []),
                default=rs.get("preferred_shifts", []),
                key=f"pref_{r}"
            )



    with st.expander("⚖️ Κανόνες", expanded=False):
        rules = company.get("rules", {})
        rule_defs = {
            "max_daily_hours_5days": (6, 12, rules.get("max_daily_hours_5days", 8)),
            "max_daily_hours_6days": (6, 12, rules.get("max_daily_hours_6days", 9)),
            "max_daily_overtime": (0, 6, rules.get("max_daily_overtime", 3)),
            "min_daily_rest": (8, 24, rules.get("min_daily_rest", 11)),
            "weekly_hours_5days": (30, 50, rules.get("weekly_hours_5days", 40)),
            "weekly_hours_6days": (30, 60, rules.get("weekly_hours_6days", 48)),
            "monthly_hours": (100, 300, rules.get("monthly_hours", 160)),
            "max_consecutive_days": (3, 10, rules.get("max_consecutive_days", 6)),
        }
        for k, (mn, mx, dv) in rule_defs.items():
            rules[k] = st.number_input(k, mn, mx, dv)
        company["rules"] = rules

    if st.button("💾 Αποθήκευση Ρυθμίσεων", type="primary"):
        try:
            update_company(company["id"], company)
            st.success("✅ Αποθηκεύτηκε")
        except Exception as ex:
            st.error(f"Αποτυχία: {ex}")



def page_schedule():

    back_to_company_selection("back_schedule")
    st.subheader("📅 Πρόγραμμα")

    # Init state
    st.session_state.setdefault("schedule", pd.DataFrame())
    st.session_state.setdefault("missing_staff", pd.DataFrame())
    st.session_state.setdefault("violations", pd.DataFrame())

    # Guards
    if "company" not in st.session_state or not st.session_state.get("company", {}).get("name"):
        _empty_state("Δεν έχει επιλεγεί επιχείρηση.", ["Επιλέξτε επιχείρηση για να συνεχίσετε."], demo_button=True, on_demo=_demo_seed)
        return
    if "employees" not in st.session_state or not st.session_state.employees:
        _empty_state("Δεν υπάρχουν υπάλληλοι.", ["Προσθέστε προσωπικό για να δημιουργηθεί πρόγραμμα."], demo_button=True, on_demo=_demo_seed)
        return

    company = st.session_state.company

    # KPI strip
    sched = _ensure_schedule_df(st.session_state.get("schedule"))
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Ημέρες", int(sched["Ημερομηνία"].nunique()) if not sched.empty else 0)
    with c2: st.metric("Αναθέσεις", len(sched) if not sched.empty else 0)
    with c3: st.metric("Άτομα", int(sched["Υπάλληλος"].nunique()) if not sched.empty else 0)
    with c4: st.metric("Ρόλοι", int(sched["Ρόλος"].nunique()) if not sched.empty else 0)

    # Options
    mode = st.radio("Τύπος", ["🗓️ Εβδομαδιαίο", "📅 Μηνιαίο"], key="mode_sched")
    days_count = 7 if mode == "🗓️ Εβδομαδιαίο" else 30
    start_date = st.date_input("Έναρξη", dt.date.today(), key="start_sched")

    # Generate
    if st.button("🛠 Δημιουργία", type="primary", key="btn_generate"):
        df, conflicts, viols = gen(
            start_date,
            st.session_state.employees,
            company.get("active_shifts", []),
            company.get("roles", []),
            company.get("rules", {}),
            company.get("role_settings", {}),
            days_count,
            company.get("work_model", "5ήμερο"),
        )
        st.session_state.schedule = _ensure_schedule_df(df)
        st.session_state.missing_staff = conflicts
        st.session_state.violations = viols
        st.success("✅ Δημιουργήθηκε πρόγραμμα.")

    st.divider()

    # Editor + filters
    if not st.session_state.schedule.empty:
        sched = st.session_state.schedule.copy()

        employees = sorted({e.get("name", "") for e in st.session_state.employees})
        roles = company.get("roles", [])
        shifts = company.get("active_shifts", [])

        c1, c2, c3, c4, c5 = st.columns([1.1, 1.1, 1.1, 1, 1.2])
        role_f    = c1.multiselect("Φίλτρο Ρόλου", roles, key="f_role")
        shift_f   = c2.multiselect("Φίλτρο Βάρδιας", shifts, key="f_shift")
        emp_f     = c3.multiselect("Φίλτρο Υπαλλήλου", employees, key="f_emp")
        date_from = c4.date_input("Από", pd.to_datetime(sched["Ημερομηνία"]).min().date(), key="f_from")
        date_to   = c5.date_input("Έως", pd.to_datetime(sched["Ημερομηνία"]).max().date(), key="f_to")

        mask = (
            (pd.to_datetime(sched["Ημερομηνία"]) >= pd.to_datetime(date_from)) &
            (pd.to_datetime(sched["Ημερομηνία"]) <= pd.to_datetime(date_to))
        )
        if role_f:  mask &= sched["Ρόλος"].isin(role_f)
        if shift_f: mask &= sched["Βάρδια"].isin(shift_f)
        if emp_f:   mask &= sched["Υπάλληλος"].isin(emp_f)

        view = sched[mask].reset_index(drop=True)
        view["Ημερομηνία"] = pd.to_datetime(view["Ημερομηνία"], errors="coerce").dt.date

        # Quick row status
        def row_status(row):
            if not str(row.get("Υπάλληλος", "")).strip():
                return "Κενό"
            try:
                hrs = int(row.get("Ώρες", 0))
            except Exception:
                hrs = 0
            return "OK" if 1 <= hrs <= 12 else "Λάθος ώρες"

        view["Κατάσταση"] = view.apply(row_status, axis=1)

        col_cfg = {
            "Ημέρα": st.column_config.TextColumn("Ημέρα", disabled=True),
            "Ημερομηνία": st.column_config.DateColumn("Ημερομηνία", format="YYYY-MM-DD"),
            "Βάρδια": st.column_config.SelectboxColumn("Βάρδια", options=shifts, width="large"),
            "Υπάλληλος": st.column_config.SelectboxColumn("Υπάλληλος", options=employees),
            "Ρόλος": st.column_config.SelectboxColumn("Ρόλος", options=roles),
            "Ώρες": st.column_config.NumberColumn("Ώρες", min_value=1, max_value=12, step=1),
            "Κατάσταση": st.column_config.TextColumn("Κατάσταση", help="Γρήγορος έλεγχος", width="medium"),
        }

        left, right = st.columns([0.67, 0.33])

        with left:
            edited = st.data_editor(
                view,
                num_rows="dynamic",
                use_container_width=True,
                column_config=col_cfg,
                hide_index=True,
                key="editor_schedule",
            )

            # Save edited subset back into full schedule
            st.session_state.setdefault("_last_schedule", None)
            b1, b2, b3 = st.columns(3)
            if b1.button("💾 Αποθήκευση Αλλαγών", key="save_sched"):
                st.session_state["_last_schedule"] = st.session_state.schedule.copy()
                untouched = sched[~mask]
                st.session_state.schedule = (
                    pd.concat([untouched, edited.drop(columns=["Κατάσταση"])], ignore_index=True)
                      .sort_values(["Ημερομηνία", "Βάρδια", "Ρόλος", "Υπάλληλος"])
                      .reset_index(drop=True)
                )
                st.success("✅ Οι αλλαγές αποθηκεύτηκαν!")

            if b2.button("↩️ Αναίρεση τελευταίας αποθήκευσης", disabled=st.session_state["_last_schedule"] is None):
                st.session_state.schedule = _ensure_schedule_df(st.session_state["_last_schedule"].copy())
                st.session_state["_last_schedule"] = None
                st.toast("Επαναφορά πραγματοποιήθηκε.", icon="↩️")
                st.rerun()

            csv = st.session_state.schedule.to_csv(index=False).encode("utf-8-sig")
            b3.download_button("⬇️ Εξαγωγή CSV", data=csv, file_name="schedule.csv", mime="text/csv", key="dl_sched")

        with right:
            st.markdown("#### 📊 Σύνοψη")
            if not edited.empty:
                emp_hours = edited.groupby("Υπάλληλος")["Ώρες"].sum().sort_values(ascending=False)
                for n, h in emp_hours.items():
                    st.write(f"**{n}** — {int(h)} ώρες")

            # One-click self-heal after manual edits
            if st.button("🧹 Επανέλεγχος & Αυτο-διόρθωση", help="Εφάρμοσε όλους τους κανόνες στο τρέχον πρόγραμμα"):
                # derive span & start from current schedule
                cur = st.session_state.schedule.copy()
                cur["Ημερομηνία"] = pd.to_datetime(cur["Ημερομηνία"], errors="coerce").dt.date
                start = cur["Ημερομηνία"].min() if not cur.empty else dt.date.today()
                span = len(cur["Ημερομηνία"].unique()) if not cur.empty else 7
                fixed_df, conflicts, viols = gen(
                    start,
                    st.session_state.employees,
                    company.get("active_shifts", []),
                    company.get("roles", []),
                    company.get("rules", {}),
                    company.get("role_settings", {}),
                    span,
                    company.get("work_model", "5ήμερο"),
                )
                st.session_state.schedule = _ensure_schedule_df(fixed_df)
                st.session_state.missing_staff = conflicts
                st.session_state.violations = viols
                st.success("🔧 Έγινε επανέλεγχος & διόρθωση.")
                st.rerun()

    # Missing coverage
    miss = st.session_state.get("missing_staff", pd.DataFrame())
    if miss is not None and not miss.empty:
        st.divider()
        st.markdown("#### Ελλείψεις στελέχωσης")
        try:
            st.dataframe(miss, use_container_width=True, hide_index=True)
        except TypeError:
            st.dataframe(miss.style.hide(axis="index"), use_container_width=True)

    # Violations
    viols = st.session_state.get("violations", pd.DataFrame())
    if viols is not None and not viols.empty:
        st.divider()
        st.markdown("#### ⚠️ Παραβιάσεις Κανόνων (μετά την αυτο-διόρθωση)")
        try:
            st.dataframe(viols, use_container_width=True, hide_index=True)
        except TypeError:
            st.dataframe(viols.style.hide(axis="index"), use_container_width=True)
