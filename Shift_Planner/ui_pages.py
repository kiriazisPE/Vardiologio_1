# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import datetime as dt
from datetime import date as dt_date, timedelta
from typing import List, Optional, Tuple, Dict, Any
import inspect

# ---------- Imports (robust to package/non-package layout) ----------
try:
    from .constants import DAYS, SHIFT_TIMES, ALL_SHIFTS, DEFAULT_ROLES
except Exception:  # pragma: no cover
    from constants import DAYS, SHIFT_TIMES, ALL_SHIFTS, DEFAULT_ROLES  # type: ignore

# Core DB API (guaranteed)
try:
    try:
        from .db import (
            get_all_companies, get_company, update_company, create_company,
            get_employees, add_employee, update_employee, delete_employee,
        )
    except Exception:  # pragma: no cover
        from db import (  # type: ignore
            get_all_companies, get_company, update_company, create_company,
            get_employees, add_employee, update_employee, delete_employee,
        )
    _DB_OK = True
except Exception:
    _DB_OK = False
    get_all_companies = get_company = update_company = create_company = None  # type: ignore
    get_employees = add_employee = update_employee = delete_employee = None  # type: ignore

# Optional DB helpers (may not exist or may have different signatures)
def _maybe_get(name: str):
    for modname in (".db", "db"):
        try:
            if modname == ".db":
                from . import db as _db  # type: ignore
            else:
                import db as _db  # type: ignore
            return getattr(_db, name, None)
        except Exception:
            continue
    return None

get_schedule_range = _maybe_get("get_schedule_range")
bulk_save_week_schedule = _maybe_get("bulk_save_week_schedule")
get_employee_id_by_name = _maybe_get("get_employee_id_by_name")
create_swap_request = _maybe_get("create_swap_request")
list_swap_requests = _maybe_get("list_swap_requests")
update_swap_status = _maybe_get("update_swap_status")
apply_approved_swap = _maybe_get("apply_approved_swap")

# --- Optional import: validator / auto-fix ---
try:
    try:
        from .scheduler import check_violations
        try:
            from .scheduler import auto_fix_schedule as _auto_fix_schedule
        except Exception:
            _auto_fix_schedule = None
    except Exception:  # pragma: no cover
        from scheduler import check_violations  # type: ignore
        try:
            from scheduler import auto_fix_schedule as _auto_fix_schedule  # type: ignore
        except Exception:
            _auto_fix_schedule = None
except Exception:  # ultimate fallback
    def check_violations(df, rules, work_model="5ήμερο"):
        return pd.DataFrame()
    _auto_fix_schedule = None

# ===== Local safe fallback to replace removed DEFAULT_RULES =====
# (You removed DEFAULT_RULES previously; keep UI resilient)
DEFAULT_RULES_FALLBACK = {
    "max_daily_hours_5days": 8,
    "max_daily_hours_6days": 9,
    "max_daily_hours_7days": 9,
    "max_daily_overtime": 3,
    "min_daily_rest": 11,
    "weekly_hours_5days": 40,
    "weekly_hours_6days": 48,
    "weekly_hours_7days": 56,
    "monthly_hours": 160,
    "max_consecutive_days": 6,
}

# ======================== THEME & GLOBAL STYLE ========================
def _apply_global_style():
    """Theme-aware CSS: respects Streamlit theme tokens (no hardcoded colors)."""
    if st.session_state.get("_styled_once"):
        return
    st.markdown(
        """
        <style>
        /* Tighten vertical rhythm */
        .block-container { padding-top: 1.2rem; padding-bottom: 2.4rem; }
        section[data-testid="stSidebar"] .block-container { padding-top: 0.8rem; }

        /* Cards/expanders polish */
        .stMetric { border-radius: 16px; padding: 0.4rem 0.6rem; }
        div[data-testid="stExpander"] > details { border-radius: 14px; }
        div[data-testid="stExpander"] summary { font-weight: 600; }

        /* Data editor header wrap + denser rows */
        div[data-testid="stDataFrame"] .st-emotion-cache-1yycgf0 { white-space: normal !important; }
        div[data-testid="stDataFrame"] .row_heading { font-weight: 600; }
        div[data-testid="stDataFrame"] .blank { color: var(--text-color); }

        /* Primary buttons a bit rounded */
        .stButton>button, .stDownloadButton>button {
          border-radius: 12px;
          padding: 0.45rem 0.9rem;
          font-weight: 600;
        }
        /* Soft badge button */
        .btn-soft>button {
          background: color-mix(in srgb, var(--primary-color) 16%, transparent);
          color: var(--primary-color);
          border: 1px solid color-mix(in srgb, var(--primary-color) 30%, transparent);
        }

        /* Use theme variables so dark/light works */
        :root, [data-theme="dark"] {
          --kpi-bg: color-mix(in srgb, var(--background-color) 85%, var(--primary-color) 15%);
        }
        .kpi-card { background: var(--kpi-bg); border-radius: 16px; padding: .8rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state["_styled_once"] = True

# ======================== CACHING HELPERS ========================
# Cache lightweight reads; callers can still force-refresh with st.rerun().
if hasattr(st, "cache_data"):
    cache_data = st.cache_data
else:  # Streamlit < 1.18 fallback
    def cache_data(func=None, **_):
        return func

@cache_data(show_spinner=False)
def _cached_companies():
    return get_all_companies() if callable(get_all_companies) else []

@cache_data(show_spinner=False)
def _cached_employees(company_id: int):
    return get_employees(company_id) if callable(get_employees) else []

@cache_data(show_spinner=False)
def _cached_schedule(company_id: int, start_iso: str, end_iso: str):
    if callable(get_schedule_range):
        return get_schedule_range(company_id, start_iso, end_iso) or []
    return []

# ======================== PAGES ========================

def page_select_company():
    """Company selection page."""
    st.subheader("🏢 Επιλογή Επιχείρησης")

    companies = get_all_companies()() if False else (get_all_companies() if callable(get_all_companies) else [])
    if not companies:
        if callable(create_company) and callable(get_all_companies):
            st.info("Δεν υπάρχουν εταιρείες. Δημιούργησα μια default.")
            create_company("Default Business")
            companies = get_all_companies() or []
        else:
            st.info("Λειτουργία επίδειξης: η ΒΔ δεν είναι διαθέσιμη.")
            companies = [{"id": -1, "name": "Demo Business"}]

    options = {f"{c.get('name','?')} (ID:{c.get('id','?')})": c.get('id') for c in companies}
    if not options:
        st.error("Δεν βρέθηκαν εταιρείες (άδεια λίστα).")
        return

    selected_label = st.selectbox("Επιλογή", list(options.keys()))
    if st.button("✅ Άνοιγμα") and selected_label in options:
        company_id = options[selected_label]
        st.session_state.company = get_company(company_id) if callable(get_company) else {"id": -1, "name": "Demo"}
        st.session_state.company.setdefault("active_shifts", ALL_SHIFTS.copy())
        st.session_state.company.setdefault("roles", DEFAULT_ROLES.copy())
        st.session_state.company.setdefault("rules", DEFAULT_RULES_FALLBACK.copy())
        st.session_state.company.setdefault("role_settings", {})
        st.session_state.company.setdefault("work_model", "5ήμερο")
        st.session_state.employees = get_employees(company_id) if callable(get_employees) else []
        st.rerun()

    with st.expander("Δεν βλέπεις εταιρεία;"):
        if st.text_input("Όνομα νέας εταιρείας", key="new_co_name"):
            if st.button("➕ Δημιουργία"):
                if callable(create_company):
                    create_company(st.session_state["new_co_name"].strip())
                    st.success("Η εταιρεία δημιουργήθηκε.")
                    st.rerun()
                else:
                    st.info("Λειτουργία επίδειξης: η ΒΔ δεν είναι διαθέσιμη.")



def page_business():
    """Company settings page (polished)."""
    _apply_global_style()
    back_to_company_selection("back_business")
    st.subheader("⚙️ Ρυθμίσεις Επιχείρησης")

    if "company" not in st.session_state or not st.session_state.get("company", {}):
        st.warning("Δεν έχει επιλεγεί επιχείρηση.")
        return

    company = st.session_state.company
    company.setdefault("active_shifts", ALL_SHIFTS.copy())
    company.setdefault("roles", DEFAULT_ROLES.copy())
    company.setdefault("rules", DEFAULT_RULES_FALLBACK.copy())
    company.setdefault("role_settings", {})
    company.setdefault("work_model", "5ήμερο")

    with st.container():
        st.subheader("Βασικά")
        col1, col2 = st.columns([2, 1])
        with col1:
            company["name"] = st.text_input("Όνομα επιχείρησης", company.get("name", ""))
        with col2:
            options = ["5ήμερο", "6ήμερο", "7ήμερο"]
            current = company.get("work_model", "5ήμερο")
            idx = options.index(current) if current in options else 0
            company["work_model"] = st.selectbox("Μοντέλο εργασίας", options, index=idx, help="Χρησιμοποιείται στους ελέγχους συμμόρφωσης.")

    with st.expander("🕒 Βάρδιες", expanded=False):
        new_shift = st.text_input("Προσθήκη νέας βάρδιας")
        c1, c2 = st.columns(2)
        if c1.button("➕ Προσθήκη"):
            if new_shift and new_shift not in company["active_shifts"]:
                company["active_shifts"].append(new_shift)
                st.toast("Προστέθηκε βάρδια.")
        if c2.button("↩️ Επαναφορά προεπιλογών"):
            company["active_shifts"] = ALL_SHIFTS.copy()
        st.multiselect("Ενεργές βάρδιες", company["active_shifts"], default=company["active_shifts"], disabled=True)

    with st.expander("👔 Ρόλοι & Ρυθμίσεις", expanded=True):
        new_role = st.text_input("Νέος ρόλος")
        cols = st.columns([0.28, 0.28, 0.44])
        if cols[0].button("➕ Προσθήκη Ρόλου", use_container_width=True):
            if new_role and new_role not in company["roles"]:
                company["roles"].append(new_role)
                st.toast("Προστέθηκε ρόλος.")
        cols[1].button("📦 Προεπιλεγμένοι ρόλοι", help="Δεν τροποποιεί τους τρέχοντες ρόλους — μόνο ενημέρωση.", use_container_width=True)
        cols[2].empty()

        company.setdefault("role_settings", {})
        for r in company.get("roles", []):
            rs = company["role_settings"].setdefault(r, {})
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
                "Προτιμώμενες βάρδιες",
                company.get("active_shifts", []),
                default=rs.get("preferred_shifts", []),
                key=f"pref_{r}"
            )

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

    st.divider()
    if st.button("💾 Αποθήκευση Ρυθμίσεων", type="primary"):
        try:
            if _DB_OK and callable(update_company):
                update_company(company["id"], company)
                st.success("Αποθηκεύτηκε.")
            else:
                st.info("Λειτουργία επίδειξης: η ΒΔ δεν είναι διαθέσιμη.")
        except Exception as ex:
            st.error(f"Αποτυχία: {ex}")

# ------------------------- Employees ------------------------- #
def page_employees():
    _apply_global_style()
    back_to_company_selection("back_employees")
    st.subheader("👥 Υπάλληλοι")

    if "company" not in st.session_state:
        st.warning("Επιλέξτε επιχείρηση πρώτα.")
        return

    company = st.session_state.company
    st.session_state.setdefault("employees", _cached_employees(company.get("id", -1)))

    with st.form("add_emp", clear_on_submit=True):
        st.markdown("##### ➕ Προσθήκη")
        name = st.text_input("Όνομα")
        roles = st.multiselect("Ρόλοι", company.get("roles", []))
        availability = st.multiselect("Διαθεσιμότητα", company.get("active_shifts", []))
        submitted = st.form_submit_button("Προσθήκη", use_container_width=True)
    if submitted:
        _add_employee_handler(company, name, roles, availability)

    employees = st.session_state.employees
    if not employees:
        _empty_state(
            "Δεν υπάρχουν ακόμα υπάλληλοι.",
            ["Προσθέστε προσωπικό για να ξεκινήσει η δημιουργία προγράμματος."],
            demo_button=True,
            on_demo=_demo_seed,
        )
        return

    for emp in employees:
        with st.expander(f"{emp['name']}"):
            c1, c2 = st.columns([0.65, 0.35])
            with c1:
                new_name = st.text_input("Όνομα", value=emp["name"], key=f"name_{emp['id']}")
                current_roles = _employee_roles(emp)
                role_options = company.get("roles", [])
                default_roles, missing_roles = _sanitize_default(role_options, current_roles)
                new_roles = st.multiselect("Ρόλοι", role_options, default=default_roles, key=f"roles_{emp['id']}")
                if missing_roles:
                    st.caption("⚠️ Αγνοήθηκαν ρόλοι: " + ", ".join(missing_roles))

                current_av = _availability_list(emp)
                shift_options = company.get("active_shifts", [])
                default_av, missing_av = _sanitize_default(shift_options, current_av)
                new_av = st.multiselect("Διαθεσιμότητα", shift_options, default=default_av, key=f"av_{emp['id']}")
                if missing_av:
                    st.caption("⚠️ Αγνοήθηκαν βάρδιες: " + ", ".join(missing_av))
            with c2:
                st.write(" ")
                st.write(" ")
                if st.button("💾 Αποθήκευση", key=f"save_{emp['id']}"):
                    _save_employee_handler(emp, new_name, new_roles, new_av, role_options, shift_options)
                if st.button("🗑️ Διαγραφή", key=f"del_{emp['id']}"):
                    st.session_state[f"confirm_del_{emp['id']}"] = True
                if st.session_state.get(f"confirm_del_{emp['id']}", False):
                    st.warning(f"Σίγουρα διαγραφή του/της **{emp['name']}**;", icon="⚠️")
                    cc1, cc2 = st.columns(2)
                    if cc1.button("❌ Ακύρωση", key=f"cancel_del_{emp['id']}"):
                        st.session_state[f"confirm_del_{emp['id']}"] = False
                    if cc2.button("✅ Επιβεβαίωση", key=f"confirm_btn_{emp['id']}"):
                        _delete_employee_handler(emp)

# ------------------------- Schedule ------------------------- #
def page_schedule():
    _apply_global_style()
    back_to_company_selection("back_schedule")
    st.subheader("📅 Πρόγραμμα")

    st.session_state.setdefault("schedule", pd.DataFrame())
    st.session_state.setdefault("missing_staff", pd.DataFrame())
    st.session_state.setdefault("violations", pd.DataFrame())

    if "company" not in st.session_state or not st.session_state.get("company", {}).get("name"):
        st.warning("Δεν έχει επιλεγεί επιχείρηση.")
        return
    if "employees" not in st.session_state or not st.session_state.employees:
        st.warning("Δεν υπάρχουν υπάλληλοι. Προσθέστε για να δημιουργηθεί πρόγραμμα.")
        return

    company = st.session_state.company
    emps = st.session_state.employees

    tabs = st.tabs(["⚙️ Δημιουργία", "🧱 Visual builder", "🔁 Αιτήματα αλλαγής"])
    with tabs[0]:
        _tab_generate(company, emps)
    with tabs[1]:
        _tab_visual_builder(company, emps)
    with tabs[2]:
        _tab_swaps(company, emps)

# ======================== Tab: Generate ========================
def _tab_generate(company: Dict[str, Any], emps: List[Dict[str, Any]]):
    col_hdr1, col_hdr2, col_hdr3, col_hdr4 = st.columns(4)
    sched = st.session_state.schedule.copy()
    if not sched.empty:
        try:
            dser = pd.to_datetime(sched["Ημερομηνία"], errors="coerce").dt.date
            col_hdr1.metric("Συνολικές βάρδιες", len(sched))
            col_hdr2.metric("Υπάλληλοι", len(emps))
            col_hdr3.metric("Ημέρες", len(set(dser)))
            col_hdr4.metric("Ρόλοι", len(company.get("roles", [])))
        except Exception:
            pass
    else:
        col_hdr1.metric("Συνολικές βάρδιες", 0)
        col_hdr2.metric("Υπάλληλοι", len(emps))
        col_hdr3.metric("Ημέρες", 0)
        col_hdr4.metric("Ρόλοι", len(company.get("roles", [])))

    st.divider()
    mode = st.radio("Εμβέλεια", ["🗓️ Εβδομαδιαίο", "📅 Μηνιαίο"], horizontal=True, key="mode_sched")
    days_count = 7 if mode == "🗓️ Εβδομαδιαίο" else 30
    start_date = st.date_input("Έναρξη", dt_date.today(), key="start_sched")

    colb1, colb2 = st.columns([0.35, 0.35])
    with colb1:
        generate_clicked = st.button("🛠 Δημιουργία", type="primary", key="btn_generate")
        if days_count == 30:
            st.caption("⚠️ Η δημιουργία για 30 ημέρες θα αντικαταστήσει όλο το διάστημα.")
            confirm_month = st.checkbox("Επιβεβαιώνω την αντικατάσταση όλων των 30 ημερών", key="confirm_month")
        else:
            confirm_month = True
    with colb2:
        refix_clicked = st.button("🧹 Επανέλεγχος & Auto‑διόρθωση", help="Εφάρμοσε κανόνες στο τρέχον πρόγραμμα")

    if generate_clicked and confirm_month:
        _generate_and_save(company, emps, start_date, days_count)
    elif generate_clicked and not confirm_month:
        st.warning("Χρειάζεται επιβεβαίωση για αποθήκευση ολόκληρου μήνα.")

    if refix_clicked and not st.session_state.schedule.empty:
        _refix_current(company, emps)

# ======================== Tab: Visual Builder ========================
def _tab_visual_builder(company: Dict[str, Any], emps: List[Dict[str, Any]]):
    st.caption("Ο πίνακας αφορά στην **ορατή εβδομάδα**. Για ολόκληρο μήνα χρησιμοποίησε τη Δημιουργία.")
    start_date = st.date_input("Έναρξη εβδομάδας", dt_date.today(), key="vb_start")
    dates = [start_date + timedelta(days=i) for i in range(7)]

    active_shifts = company.get("active_shifts", [])
    grid_df = _grid_from_db_week(company["id"], emps, dates[0])

    col_labels = { _column_key(d, s): f"{DAYS[d.weekday()]} {d.strftime('%d/%m')} • {s}"
                   for d in dates for s in active_shifts }

    role_choices = ["— (καμία)", "— (χωρίς ρόλο)"] + company.get("roles", [])
    colcfg = {k: st.column_config.SelectboxColumn(label=col_labels.get(k, k), options=role_choices, default="— (καμία)")
              for k in grid_df.columns if k != "Υπάλληλος"}

    edited = st.data_editor(
        grid_df,
        column_config={"Υπάλληλος": st.column_config.TextColumn("Υπάλληλος", disabled=True), **colcfg},
        use_container_width=True, hide_index=True, num_rows="fixed", key="vb_editor", height=360
    )

    colA, colB = st.columns([0.5, 0.5])
    with colA:
        if st.button(f"💾 Αποθήκευση εβδομάδας ({dates[0].isoformat()} → {dates[-1].isoformat()})", type="primary"):
            errs = _validate_no_double_bookings(edited)
            if errs:
                for e in errs: st.error(e)
            else:
                assignments = _assignments_from_grid(edited, emps, dates[0])
                if company.get("id", 0) < 0:
                    st.info("Demo εταιρεία: η αποθήκευση στη ΒΔ είναι απενεργοποιημένη.")
                else:
                    if callable(bulk_save_week_schedule):
                        bulk_save_week_schedule(company["id"], assignments)  # 2‑arg signature
                        st.success("Αποθηκεύτηκε το εβδομαδιαίο πρόγραμμα.")
                    else:
                        st.info("Η αποθήκευση εβδομάδας δεν είναι διαθέσιμη (λείπει bulk_save_week_schedule).")
                st.rerun()
    with colB:
        if st.button("🔄 Φόρτωση από ΒΔ"):
            st.cache_data.clear()
            st.rerun()

# ======================== Tab: Swaps ========================
def _tab_swaps(company: Dict[str, Any], emps: List[Dict[str, Any]]):
    def _has_sig(fn, min_params):
        try:
            return callable(fn) and len(inspect.signature(fn).parameters) >= min_params
        except Exception:
            return False

    SWAPS_OK = (
        _has_sig(create_swap_request, 5) and
        _has_sig(list_swap_requests, 1) and
        _has_sig(update_swap_status, 2) and
        _has_sig(apply_approved_swap, 5) and
        _has_sig(get_schedule_range, 3) and
        _has_sig(get_employee_id_by_name, 2)
    )
    if not SWAPS_OK:
        st.info("Η ενότητα είναι απενεργοποιημένη: τα DB helpers δεν είναι πλήρως συμβατά.")
        return

    with st.expander("📝 Υποβολή αιτήματος (εργαζόμενου)", expanded=False):
        st.caption("Ανταλλαγή για **το ίδιο είδος βάρδιας** την ίδια ημέρα.")
        emp_names = [e["name"] for e in emps]
        req_emp = st.selectbox("Αιτών", emp_names, key="swap_req_emp")
        target_emp = st.selectbox("Συνάδελφος", [n for n in emp_names if n != req_emp], key="swap_target_emp")
        req_date = st.date_input("Ημερομηνία", dt_date.today(), key="swap_date")
        req_shift = st.selectbox("Βάρδια", company.get("active_shifts", []), key="swap_shift")

        if st.button("📨 Υποβολή αιτήματος"):
            rid = get_employee_id_by_name(company["id"], req_emp)
            tid = get_employee_id_by_name(company["id"], target_emp)
            have = get_schedule_range(company["id"], req_date.isoformat(), req_date.isoformat())
            target_has = any(x.get("employee_id") == tid and x.get("shift") == req_shift for x in (have or []))
            requester_has = any(x.get("employee_id") == rid and x.get("shift") == req_shift for x in (have or []))
            if not requester_has:
                st.error("Ο αιτών δεν έχει αυτή τη βάρδια.")
            elif not target_has:
                st.error("Ο συνάδελφος δεν έχει αυτή τη βάρδια.")
            else:
                create_swap_request(company["id"], rid, tid, req_date.isoformat(), req_shift)
                st.success("Καταχωρήθηκε αίτημα (pending).")

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
                    req_has = any(x.get("employee_id") == r["requester_id"] and x.get("shift") == r["shift"] for x in (day_sched or []))
                    target_has = any(x.get("employee_id") == r["target_employee_id"] and x.get("shift") == r["shift"] for x in (day_sched or []))
                    if not (req_has and target_has):
                        st.error("Το ζεύγος βαρδιών δεν είναι έγκυρο πλέον.")
                    else:
                        update_swap_status(r["id"], "approved", note)
                        apply_approved_swap(company["id"], r["date"], r["shift"], r["requester_id"], r["target_employee_id"])
                        st.success("Εφαρμόστηκε.")
                        st.rerun()
                if c2.button("⛔️ Απόρριψη", key=f"reject_{r['id']}"):
                    update_swap_status(r["id"], "rejected", note)
                    st.info("Απορρίφθηκε.")
                    st.rerun()

# ------------------------- Handlers ------------------------- #
def _add_employee_handler(company, name, roles, availability):
    errors = []
    if not name.strip():
        errors.append("Το όνομα είναι υποχρεωτικό.")
    if any(r not in company.get("roles", []) for r in roles):
        errors.append("Μη έγκυρος ρόλος.")
    if any(s not in company.get("active_shifts", []) for s in availability):
        errors.append("Μη έγκυρη βάρδια διαθεσιμότητας.")
    if errors:
        for e in errors: st.error(e)
        return

    fresh = get_company(company.get("id")) if callable(get_company) else company
    if not fresh:
        st.error("Η επιχείρηση δεν υπάρχει πλέον.")
        st.session_state.pop("company", None)
        st.rerun()
    if fresh.get("id", 0) < 0:
        st.info("Demo εταιρεία: η προσθήκη υπαλλήλου δεν αποθηκεύεται στη ΒΔ.")
        st.stop()

    try:
        if callable(add_employee):
            add_employee(fresh["id"], name.strip(), roles, availability)
            st.session_state.employees = _cached_employees.clear() or _cached_employees(fresh["id"])
            st.success(f"Προστέθηκε ο/η {name.strip()}")
            st.rerun()
        else:
            st.info("Λειτουργία επίδειξης: η ΒΔ δεν είναι διαθέσιμη.")
    except Exception as ex:
        st.error(f"Αποτυχία προσθήκης: {ex}")

def _save_employee_handler(emp, new_name, new_roles, new_av, role_options, shift_options):
    if any(r not in role_options for r in new_roles):
        st.error("Μη έγκυρος ρόλος.")
        return
    if any(s not in shift_options for s in new_av):
        st.error("Μη έγκυρη βάρδια διαθεσιμότητας.")
        return
    try:
        if callable(update_employee) and callable(get_employees):
            update_employee(emp["id"], new_name.strip(), new_roles, new_av)
            st.session_state.employees = _cached_employees.clear() or _cached_employees(st.session_state.company["id"])
            st.success("Αποθηκεύτηκε.")
            st.rerun()
        else:
            st.info("Λειτουργία επίδειξης: η ΒΔ δεν είναι διαθέσιμη.")
    except Exception as ex:
        st.error(f"Αποτυχία αποθήκευσης: {ex}")

def _delete_employee_handler(emp):
    try:
        if callable(delete_employee) and callable(get_employees):
            delete_employee(emp["id"])
            st.session_state[f"confirm_del_{emp['id']}"] = False
            st.session_state.employees = _cached_employees.clear() or _cached_employees(st.session_state.company["id"])
            st.success("Διαγράφηκε.")
            st.rerun()
        else:
            st.info("Λειτουργία επίδειξης: η ΒΔ δεν είναι διαθέσιμη.")
    except Exception as ex:
        st.error(f"Αποτυχία διαγραφής: {ex}")

# ------------------------- Core Scheduling Helpers ------------------------- #
def _sanitize_default(options: List[str], default_vals: List[str]) -> Tuple[List[str], List[str]]:
    opts = set(options or [])
    default_vals = default_vals or []
    valid = [v for v in default_vals if v in opts]
    missing = [v for v in default_vals if v not in opts]
    return valid, missing

def _shift_len(shift: str) -> int:
    s, e = SHIFT_TIMES.get(shift, (9, 17))
    return (24 - s + e) if e < s else (e - s)

def _ensure_schedule_df(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    cols = ["Ημέρα", "Ημερομηνία", "Βάρδια", "Υπάλληλος", "Ρόλος", "Ώρες"]
    if df is None or df.empty:
        out = pd.DataFrame(columns=cols)
        out["Ώρες"] = pd.Series([], dtype="float64")
        return out
    for c in cols:
        if c not in df.columns:
            df[c] = 0 if c == "Ώρες" else ""
    out = df[cols].copy()
    out["Ώρες"] = pd.to_numeric(out["Ώρες"], errors="coerce").fillna(0).astype(float)
    return out

def _availability_list(emp: Dict[str, Any]) -> List[str]:
    av = emp.get("availability", [])
    if isinstance(av, dict):
        return [k for k, v in av.items() if v]
    if isinstance(av, list):
        return av
    return []

def _employee_roles(emp: Dict[str, Any]) -> List[str]:
    roles = emp.get("roles", [])
    if isinstance(roles, list):
        return roles
    if isinstance(roles, str) and roles.strip():
        return [roles.strip()]
    return []

def generate_schedule(start_date, employees, active_shifts, roles, rules, role_settings, days_count):
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
            need = dict(min_per)
            for _ in range(len(order)):
                emp = order[idx % len(order)]
                idx += 1
                avail_list = _availability_list(emp)
                if shift not in avail_list:
                    continue
                eroles = _employee_roles(emp)
                if not eroles:
                    continue

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

def _empty_state(header: str, lines: List[str], demo_button: bool = False, on_demo=None):
    st.subheader(header)
    for line in lines:
        st.caption(line)
    if demo_button and on_demo:
        if st.button("✨ Συμπλήρωση demo δεδομένων", type="secondary"):
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

# ------------------------- Grid / IO helpers ------------------------- #
def _week_dates(start_date: dt.date, days: int = 7) -> List[dt.date]:
    return [start_date + dt.timedelta(days=i) for i in range(days)]

def _column_key(date: dt.date, shift: str) -> str:
    return f"{date.isoformat()}__{shift}"

def _parse_column_key(k: str) -> Tuple[dt.date, str]:
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

def _validate_no_double_bookings(grid_df: pd.DataFrame) -> List[str]:
    errors = []
    for _, row in grid_df.iterrows():
        name = row["Υπάλληλος"]
        per_day: Dict[dt.date, List[str]] = {}
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

def _grid_from_db_week(company_id: int, employees: List[Dict[str, Any]], start_date: dt.date) -> pd.DataFrame:
    dates = _week_dates(start_date)
    active_shifts = st.session_state.company.get("active_shifts", [])
    cols = ["Υπάλληλος"] + [_column_key(d, s) for d in dates for s in active_shifts]
    df = pd.DataFrame(columns=cols)
    df["Υπάλληλος"] = [e["name"] for e in employees]
    for c in cols:
        if c != "Υπάλληλος":
            df[c] = "— (καμία)"

    if callable(get_schedule_range):
        try:
            existing = _cached_schedule(company_id, dates[0].isoformat(), dates[-1].isoformat())
            for row in existing or []:
                key = _column_key(dt.date.fromisoformat(row["date"]), row["shift"])
                value = row.get("role") if row.get("role") else "— (χωρίς ρόλο)"
                if key in df.columns:
                    df.loc[df["Υπάλληλος"] == row.get("employee_name", ""), key] = value
        except Exception:
            st.info("⚠️ Αδυναμία φόρτωσης εβδομάδας από ΒΔ (έλεγχος συμβατότητας).")
    else:
        st.info("Η φόρτωση εβδομάδας από τη ΒΔ δεν είναι διαθέσιμη (λείπει get_schedule_range).")
    return df

def _assignments_from_grid(grid_df: pd.DataFrame, employees: List[Dict[str, Any]], start_date: dt.date) -> List[Dict[str, Any]]:
    name_to_id = {e["name"]: e["id"] for e in employees}
    valid_roles = set(st.session_state.company.get("roles", []))
    assignments: List[Dict[str, Any]] = []
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
            else:
                assignments.append({"employee_id": emp_id, "date": d.isoformat(), "shift": s, "role": None})
    return assignments

# ======================== Generate helpers ========================
def _generate_and_save(company, emps, start_date, days_count):
    df, missing_df = generate_schedule(
        start_date,
        emps,
        company.get("active_shifts", []),
        company.get("roles", []),
        company.get("rules", {}),
        company.get("role_settings", {}),
        days_count,
    )
    if callable(_auto_fix_schedule):
        fixed_df, viols = _auto_fix_schedule(
            df, emps,
            company.get("active_shifts", []),
            company.get("roles", []),
            company.get("rules", {}),
            company.get("role_settings", {}),
            company.get("work_model", "5ήμερο"),
        )
    else:
        _df_for_validation = df.copy()
        if "Ώρες" in _df_for_validation.columns:
            _df_for_validation["Ώρες"] = pd.to_numeric(_df_for_validation["Ώρες"], errors="coerce").fillna(0).astype(int)
        viols = check_violations(_df_for_validation, company.get("rules", {}), company.get("work_model", "5ήμερο"))
        fixed_df = df

    st.session_state.schedule = fixed_df
    st.session_state.missing_staff = missing_df
    st.session_state.violations = viols

    assignments: List[Dict[str, Any]] = []
    period_start = start_date
    period_end = start_date + timedelta(days=days_count - 1)

    def _name_to_id(nm: str):
        if callable(get_employee_id_by_name):
            return get_employee_id_by_name(company["id"], nm)
        return None

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
        if callable(bulk_save_week_schedule):
            bulk_save_week_schedule(company["id"], assignments)  # 2‑arg signature
            st.success("Δημιουργήθηκε και αποθηκεύτηκε η περίοδος.")
        else:
            st.info("Η αποθήκευση δεν είναι διαθέσιμη (λείπει bulk_save_week_schedule).")
    st.rerun()

def _refix_current(company, emps):
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
        _df_for_validation = st.session_state.schedule.copy()
        if "Ώρες" in _df_for_validation.columns:
            _df_for_validation["Ώρες"] = pd.to_numeric(_df_for_validation["Ώρες"], errors="coerce").fillna(0).astype(int)
        fixed_df = st.session_state.schedule
        viols = check_violations(_df_for_validation, company.get("rules", {}), company.get("work_model", "5ήμερο"))
    st.session_state.schedule = fixed_df
    st.session_state.violations = viols
    st.success("Ολοκληρώθηκε ο επανέλεγχος.")
    st.rerun()
