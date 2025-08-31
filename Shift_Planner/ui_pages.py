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


# -------------------------
# Auto-fix flexible caller
# -------------------------
def _call_auto_fix_schedule(df, emps, company, start_date=None, days_count=None):
    \"\"\"Call auto_fix_schedule with flexible signatures and normalize output to (fixed_df, viols).\"\"\"
    def _norm(ret):
        import pandas as _pd
        # Normalize return to (df, viols)
        if isinstance(ret, tuple):
            if len(ret) >= 2:
                return ret[0], ret[1]
            if len(ret) == 1:
                return ret[0], _pd.DataFrame()
            return df, _pd.DataFrame()
        # Single object
        if isinstance(ret, _pd.DataFrame):
            return ret, _pd.DataFrame()
        return df, _pd.DataFrame()

    if _auto_fix_schedule is None:
        _df_for_validation = df.copy()
        if "Ώρες" in _df_for_validation.columns:
            _df_for_validation["Ώρες"] = pd.to_numeric(_df_for_validation["Ώρες"], errors="coerce").fillna(0).astype(float)
        viols = check_violations(_df_for_validation, rules=company.get("rules", {}), work_model=company.get("work_model", "5ήμερο"))
        return df, viols

    # Προειδοποίηση για βάρδιες χωρίς ορισμένες ώρες
    try:
        from constants import SHIFT_TIMES
    except Exception:
        SHIFT_TIMES = {}
    unknown = [s for s in company.get("active_shifts", []) if s not in SHIFT_TIMES]
    if unknown:
        st.warning(
            "Οι παρακάτω βάρδιες δεν έχουν ορισμένες ώρες στο `constants.SHIFT_TIMES` "
            f"και θα παραλειφθούν από τον αλγόριθμο: {', '.join(unknown)}"
        )
    active_shifts = company.get("active_shifts", [])
    roles = company.get("roles", [])
    rules = company.get("rules", {})
    role_settings = company.get("role_settings", {})
    work_model = company.get("work_model", "5ήμερο")

    if start_date is None:
        try:
            start_date = pd.to_datetime(df["Ημερομηνία"]).dt.date.min()
        except Exception:
            import datetime as _dt
            start_date = _dt.date.today()

    if days_count is None:
        try:
            days_count = int(pd.to_datetime(df["Ημερομηνία"]).dt.date.nunique())
            if days_count <= 0:
                days_count = 7
        except Exception:
            days_count = 7

    # Try full signature
    try:
        return _norm(_auto_fix_schedule(df, start_date, emps, active_shifts, roles, rules, role_settings, days_count, work_model))
    except TypeError:
        pass
    # Try without days_count
    try:
        return _norm(_auto_fix_schedule(df, start_date, emps, active_shifts, roles, rules, role_settings, work_model))
    except TypeError:
        pass
    # Try legacy shapes
    try:
        return _norm(_auto_fix_schedule(df, emps, active_shifts, roles, rules, role_settings, days_count, work_model))
    except TypeError:
        pass
    try:
        return _norm(_auto_fix_schedule(df, emps, active_shifts, roles, rules, role_settings, work_model))
    except TypeError:
        pass
    try:
        return _norm(_auto_fix_schedule(df, active_shifts, rules))
    except TypeError:
        pass
    try:
        return _norm(_auto_fix_schedule(df, emps, active_shifts, roles, rules, role_settings))
    except TypeError:
        pass

    _df_for_validation = df.copy()
    if "Ώρες" in _df_for_validation.columns:
        _df_for_validation["Ώρες"] = pd.to_numeric(_df_for_validation["Ώρες"], errors="coerce").fillna(0).astype(float)
    viols = check_violations(_df_for_validation, rules=rules, work_model=work_model)
    return df, viols


# ===== Local safe fallback to replace removed DEFAULT_RULES =====
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
    if st.session_state.get("_styled_once"):
        return
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.0rem; padding-bottom: 1.6rem; }
        section[data-testid="stSidebar"] .block-container { padding-top: 0.6rem; }
        .stButton>button, .stDownloadButton>button { border-radius: 12px; padding: 0.45rem 0.9rem; font-weight: 600; }
        .stDataFrame th { font-weight: 600; }
        .kpi-card { background: rgba(200,200,200,.06); border: 1px solid rgba(200,200,200,.12); border-radius: 14px; padding: .75rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state["_styled_once"] = True

# ======================== CACHING HELPERS ========================
if hasattr(st, "cache_data"):
    cache_data = st.cache_data
else:
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

def _refresh_employees(company_id: int):
    try:
        _cached_employees.clear()
    except Exception:
        pass
    st.session_state.employees = _cached_employees(company_id)


def back_to_company_selection(key: str):
    \"\"\"Back to the business chooser & clear volatile state.\"\"\"
    if st.button("⬅️ Πίσω στην Επιλογή Επιχείρησης", key=key):
        for k in ("company", "employees", "schedule", "missing_staff", "violations"):
            st.session_state.pop(k, None)
        st.rerun()


# ===== Helpers for Employees page (kept minimal) =====
def _sanitize_default(options: list[str], selected: list[str] | None) -> tuple[list[str], list[str]]:
    opts = set(options or [])
    sel = selected or []
    valid = [x for x in sel if x in opts]
    missing = [x for x in sel if x not in opts]
    return valid, missing

def _add_employee_handler(company: dict, name: str, roles: list[str], availability: list[str]):
    name = (name or "").strip()
    if not name:
        st.warning("Δώσε όνομα υπαλλήλου.")
        return
    role_opts = company.get("roles", []) or []
    shift_opts = company.get("active_shifts", []) or []
    roles, _ = _sanitize_default(role_opts, roles or [])
    availability, _ = _sanitize_default(shift_opts, availability or [])
    if callable(add_employee):
        try:
            add_employee(int(company.get("id", -1)), name, roles, availability)
            _refresh_employees(int(company.get("id", -1)))
            st.toast("➕ Προστέθηκε υπάλληλος.", icon="✅")
        except Exception as ex:
            st.error(f"Αποτυχία προσθήκης: {ex}")
    else:
        st.session_state.setdefault("employees", [])
        st.session_state.employees.append({"id": -1, "name": name, "roles": roles, "availability": availability})


# ======================== PAGES ========================

def page_select_company():
    st.subheader("🏢 Επιλογή Επιχείρησης")

    companies = get_all_companies() if callable(get_all_companies) else []
    if not companies:
        if callable(create_company) and callable(get_all_companies):
            st.info("Δεν υπάρχουν εταιρείες. Δημιούργησα μια default.")
            create_company("Default Business")
            companies = get_all_companies() or []
        else:
            st.info("Λειτουργία επίδειξης: η ΒΔ δεν είναι διαθέσιμη.")
            companies = [{"id": -1, "name": "Demo Business"}]

    options = {f\"{c.get('name','?')} (ID:{c.get('id','?')})\": c.get('id') for c in companies}
    selected_label = st.selectbox("Επιλογή", list(options.keys()))
    if st.button("✅ Άνοιγμα") and selected_label in options:
        company_id = options[selected_label]
        st.session_state.company = get_company(company_id) if callable(get_company) else {"id": -1, "name": "Demo"}
        st.session_state.company.setdefault("active_shifts", ALL_SHIFTS.copy())
        st.session_state.company.setdefault("roles", DEFAULT_ROLES.copy())
        st.session_state.company.setdefault("rules", DEFAULT_RULES_FALLBACK.copy())
        st.session_state.company.setdefault("role_settings", {})
        st.session_state.company.setdefault("work_model", "5ήμερο")
        st.session_state.employees = _cached_employees(company_id)
        st.rerun()

def page_business():
    _apply_global_style()
    back_to_company_selection("back_business")
    st.subheader("⚙️ Ρυθμίσεις Επιχείρησης")

    if "company" not in st.session_state or not st.session_state.get("company", {}):
        st.warning("Δεν έχει επιλεγεί επιχείρηση.")
        page_select_company()
        return

    company = st.session_state.company
    company.setdefault("active_shifts", ALL_SHIFTS.copy())
    company.setdefault("roles", DEFAULT_ROLES.copy())
    company.setdefault("rules", DEFAULT_RULES_FALLBACK.copy())
    company.setdefault("role_settings", {})
    company.setdefault("work_model", "5ήμερο")

    with st.container():
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

    with st.expander("👔 Ρόλοι", expanded=True):
        new_role = st.text_input("Νέος ρόλος")
        cols = st.columns([0.28, 0.28, 0.44])
        if cols[0].button("➕ Προσθήκη Ρόλου", use_container_width=True):
            if new_role and new_role not in company["roles"]:
                company["roles"].append(new_role)
                st.toast("Προστέθηκε ρόλος.")
        if cols[1].button("📦 Προεπιλεγμένοι ρόλοι", help="Συγχώνευση με τους τρέχοντες ρόλους.", use_container_width=True):
            before = set(company.get("roles", []))
            company["roles"] = sorted(before | set(DEFAULT_ROLES))
            st.toast("Ενημερώθηκαν οι ρόλοι", icon="✅")

    with st.expander("⚖️ Κανόνες", expanded=False):
        rules = company.get("rules", {})
        rule_defs = {
            "max_daily_hours_5days": (6.0, 12.0, float(rules.get("max_daily_hours_5days", 8))),
            "max_daily_hours_6days": (6.0, 12.0, float(rules.get("max_daily_hours_6days", 9))),
            "max_daily_hours_7days": (6.0, 12.0, float(rules.get("max_daily_hours_7days", 9))),
            "max_daily_overtime":    (0.0, 6.0,  float(rules.get("max_daily_overtime", 3))),
            "min_daily_rest":        (8.0, 24.0, float(rules.get("min_daily_rest", 11))),
            "weekly_hours_5days":    (30.0, 60.0, float(rules.get("weekly_hours_5days", 40))),
            "weekly_hours_6days":    (30.0, 60.0, float(rules.get("weekly_hours_6days", 48))),
            "weekly_hours_7days":    (35.0, 80.0, float(rules.get("weekly_hours_7days", 56))),
            "monthly_hours":         (100.0, 320.0, float(rules.get("monthly_hours", 160))),
            "max_consecutive_days":  (3, 10, int(rules.get("max_consecutive_days", 6))),
        }
        for k, (mn, mx, dv) in rule_defs.items():
            if k == "max_consecutive_days":
                rules[k] = st.number_input(k, int(mn), int(mx), int(dv), step=1)
            else:
                rules[k] = float(st.number_input(k, float(mn), float(mx), float(dv), step=0.5, format="%.1f"))
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
        page_select_company()
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
        st.info("Δεν υπάρχουν ακόμα υπάλληλοι. Πρόσθεσε για να ξεκινήσεις.")
        return

    for emp in employees:
        with st.expander(f"{emp['name']}"):
            c1, c2 = st.columns([0.65, 0.35])
            with c1:
                new_name = st.text_input("Όνομα", value=emp["name"], key=f"name_{emp['id']}")
                role_options = company.get("roles", [])
                new_roles = st.multiselect("Ρόλοι", role_options, default=list(dict.fromkeys((emp.get("roles") or []))), key=f"roles_{emp['id']}")
                new_av = st.multiselect("Διαθεσιμότητα", company.get("active_shifts", []), default=list(dict.fromkeys((emp.get('availability') or []))), key=f"av_{emp['id']}")
            with c2:
                st.write(" ")
                st.write(" ")
                if st.button("💾 Αποθήκευση", key=f"save_{emp['id']}"):
                    try:
                        update_employee(int(emp["id"]), new_name, new_roles, new_av) if callable(update_employee) else None
                        _refresh_employees(int(st.session_state.company.get("id", -1)))
                        st.toast("💾 Αποθηκεύτηκαν οι αλλαγές.", icon="✅")
                    except Exception as ex:
                        st.error(f"Αποτυχία αποθήκευσης: {ex}")
                if st.button("🗑️ Διαγραφή", key=f"del_{emp['id']}"):
                    try:
                        delete_employee(int(emp["id"])) if callable(delete_employee) else None
                        _refresh_employees(int(st.session_state.company.get("id", -1)))
                        st.toast("🗑️ Διαγράφηκε.", icon="✅")
                    except Exception as ex:
                        st.error(f"Αποτυχία διαγραφής: {ex}")

# ------------------------- Schedule ------------------------- #

def page_schedule():
    \"\"\"Clean schedule page with generator + compliance + 2 extra analytics tables.\"\"\"
    _apply_global_style()
    back_to_company_selection("back_schedule")
    st.subheader("📅 Πρόγραμμα")

    if "company" not in st.session_state or not st.session_state.get("company"):
        st.warning("Δεν έχει επιλεγεί επιχείρηση.")
        page_select_company()
        return
    if not st.session_state.get("employees"):
        st.warning("Δεν υπάρχουν υπάλληλοι. Πρόσθεσε προσωπικό.")
        return

    st.session_state.setdefault("schedule", pd.DataFrame())
    st.session_state.setdefault("missing_staff", pd.DataFrame())
    st.session_state.setdefault("violations", pd.DataFrame())

    company = st.session_state.company
    emps = st.session_state.employees

    _tab_generate(company, emps)

def _tab_generate(company: Dict[str, Any], emps: List[Dict[str, Any]]):
    st.markdown("#### ⚙️ Δημιουργία πίνακα")
    col = st.columns(3)
    start_date = col[0].date_input("Έναρξη", dt_date.today(), key="gen_start")
    horizon = col[1].selectbox("Διάρκεια", ["7 ημέρες", "30 ημέρες"], index=0, key="gen_horizon")
    days_count = 7 if "7" in horizon else 30
    use_opt = st.checkbox("🔬 Χρήση MILP optimizer (αν υπάρχει pulp)", value=False)

    if st.button("🛠 Δημιουργία & Προεπισκόπηση", type="primary"):
        try:
            if use_opt:
                from scheduler import generate_schedule_opt as _gen
            else:
                from scheduler import generate_schedule_v2 as _gen
            from scheduler import check_violations
        except Exception:
            st.error("Λείπει η scheduler.generate_schedule_*()")
            return
        roles = company.get("roles", [])
        active_shifts = company.get("active_shifts", [])
        rules = company.get("rules", {})
        role_settings = company.get("role_settings", {})
        # Convert legacy {\"Role\": {\"min_per_shift\": N}} to supported {\"per_shift\": {...}} if needed
        _rs = role_settings if isinstance(role_settings, dict) else {}
        if _rs and not any(k in _rs for k in (\"per_day\", \"per_shift\", \"min_per\")):
            converted = {\"per_shift\": {s: {} for s in active_shifts}}
            for role, cfg in _rs.items():
                if isinstance(cfg, dict):
                    n = cfg.get(\"min_per_shift\")
                    if isinstance(n, int) and n > 0:
                        for s in active_shifts:
                            converted[\"per_shift\"][s][role] = n
            role_settings = converted
        work_model = company.get(\"work_model\", \"5ήμερο\")
        df, missing = _gen(start_date, emps, active_shifts, roles, rules, role_settings, days_count, work_model)
        if not df.empty and not pd.api.types.is_datetime64_any_dtype(df[\"Ημερομηνία\"]):
            df[\"Ημερομηνία\"] = pd.to_datetime(df[\"Ημερομηνία\"]).dt.date
        st.session_state.schedule = df
        st.session_state.missing_staff = missing
        # quick violations
        try:
            tmp = df.copy()
            if \"Ώρες\" in tmp.columns:
                tmp[\"Ώρες\"] = pd.to_numeric(tmp[\"Ώρες\"], errors=\"coerce\").fillna(0).astype(float)
            st.session_state.violations = check_violations(tmp, rules=rules, work_model=work_model)
        except Exception:
            st.session_state.violations = pd.DataFrame()

    df = st.session_state.schedule.copy()
    if df.empty:
        st.info(\"Καμία προεπισκόπηση ακόμα. Πάτησε **Δημιουργία & Προεπισκόπηση**.\")
        return

    st.markdown(\"#### 🧾 Πίνακας προεπισκόπησης\")
    role_opts = [\"— (χωρίς ρόλο)\"] + company.get(\"roles\", [])
    view_df = df.copy()
    view_df[\"Ημερομηνία\"] = pd.to_datetime(view_df[\"Ημερομηνία\"]).dt.strftime(\"%Y-%m-%d\")
    names = [e.get(\"name\",\"\") for e in emps]

    edited = st.data_editor(
        view_df,
        column_config={
            \"Βάρδια\": st.column_config.TextColumn(\"Βάρδια\", disabled=True),
            \"Ημερομηνία\": st.column_config.TextColumn(\"Ημερομηνία\", disabled=True),
            \"Υπάλληλος\": st.column_config.SelectboxColumn(\"Υπάλληλος\", options=names, required=True),
            \"Ρόλος\": st.column_config.SelectboxColumn(\"Ρόλος\", options=role_opts, required=False),
            \"Ώρες\": st.column_config.NumberColumn(\"Ώρες\", step=0.5, format=\"%.1f\"),
        },
        use_container_width=True, hide_index=True, num_rows=\"dynamic\", key=\"gen_editor\", height=380
    )
    ed = edited.copy()

    if st.button(\"🧩 Auto-fix τρέχοντος πίνακα\"):
        try:
            fixed_df, viols = _call_auto_fix_schedule(ed, emps, company, start_date=start_date, days_count=days_count)
            st.session_state.schedule = fixed_df
            st.session_state.violations = viols if isinstance(viols, pd.DataFrame) else pd.DataFrame()
            st.success(\"Έγινε auto-fix και ενημερώθηκε ο πίνακας.\")
            st.rerun()
        except Exception as ex:
            st.error(f\"Αποτυχία auto-fix: {ex}\")

    ed[\"Ημερομηνία\"] = pd.to_datetime(ed[\"Ημερομηνία\"]).dt.date
    ed[\"Ρόλος\"] = ed[\"Ρόλος\"].replace({\"— (χωρίς ρόλο)\": None})
    st.session_state.schedule = ed

    # --- KPI row
    k1, k2, k3 = st.columns(3)
    total_slots = len(ed)
    missing_total = int(st.session_state.missing_staff[\"Λείπουν\"].sum()) if not st.session_state.missing_staff.empty else 0
    viol_total = len(st.session_state.violations) if isinstance(st.session_state.violations, pd.DataFrame) else 0
    k1.metric(\"Σύνολο Αναθέσεων\", total_slots)
    k2.metric(\"Ανέκλειστες Ανάγκες\", missing_total)
    k3.metric(\"Παραβιάσεις\", viol_total)

    # --- 3 core panels
    colA, colB, colC = st.columns([0.34, 0.33, 0.33])
    with colA:
        if not st.session_state.missing_staff.empty:
            st.warning(\"Ανέκλειστες ανάγκες (αναλυτικά):\")
            st.dataframe(st.session_state.missing_staff, use_container_width=True, height=160)
    with colB:
        if not st.session_state.violations.empty:
            st.error(\"Παραβιάσεις κανόνων (αναλυτικά):\")
            st.dataframe(st.session_state.violations, use_container_width=True, height=160)
    with colC:
        csv = ed.to_csv(index=False).encode(\"utf-8\")
        st.download_button(\"⬇️ Κατέβασμα CSV\", data=csv, file_name=\"schedule_preview.csv\", mime=\"text/csv\")

    # ===== NEW TABLE 1: Shifts that need people (rolled-up) =====
    if not st.session_state.missing_staff.empty:
        st.markdown(\"#### 🧩 Ανάγκες ανά Ημερομηνία / Βάρδια / Ρόλο\")
        need_df = st.session_state.missing_staff.copy()
        # Normalize date type for pretty display
        try:
            need_df[\"Ημερομηνία\"] = pd.to_datetime(need_df[\"Ημερομηνία\"]).dt.strftime(\"%Y-%m-%d\")
        except Exception:
            pass
        rolled = (need_df.groupby([\"Ημερομηνία\",\"Βάρδια\",\"Ρόλος\"], dropna=False)[\"Λείπουν\"].sum()
                        .reset_index()
                        .sort_values([\"Ημερομηνία\",\"Βάρδια\",\"Ρόλος\"]))
        st.dataframe(rolled, use_container_width=True, height=220)

    # ===== NEW TABLE 2: Employees that broke rules =====
    if isinstance(st.session_state.violations, pd.DataFrame) and not st.session_state.violations.empty:
        st.markdown(\"#### 🚨 Υπάλληλοι με παραβιάσεις\")
        v = st.session_state.violations.copy()
        agg = (v.groupby(\"Υπάλληλος\").agg(
                    Παραβιάσεις=(\"Είδος\",\"count\"),
                    Είδη_Παραβιάσεων=(\"Είδος\", lambda s: \", \".join(sorted(set(map(str,s)))))
               ).reset_index().sort_values([\"Παραβιάσεις\",\"Υπάλληλος\"], ascending=[False, True]))
        st.dataframe(agg, use_container_width=True, height=220)

    # --- Save
    if st.button(\"💾 Αποθήκευση εβδομάδας στη ΒΔ\"):
        if not callable(bulk_save_week_schedule):
            st.info(\"Η αποθήκευση δεν είναι διαθέσιμη σε αυτό το build.\")
        else:
            smin = ed[\"Ημερομηνία\"].min().isoformat()
            smax = ed[\"Ημερομηνία\"].max().isoformat()
            entries = []
            for _, r in ed.iterrows():
                emp_id = None
                if callable(get_employee_id_by_name):
                    try:
                        emp_id = get_employee_id_by_name(company[\"id\"], r[\"Υπάλληλος\'])
                    except Exception as ex:
                        st.error(f\"Πρόβλημα εύρεσης '{r['Υπάλληλος']}': {ex}\")
                        continue
                if not emp_id:
                    for e in st.session_state.employees:
                        if e.get(\"name\") == r[\"Υπάλληλος\"]:
                            emp_id = e.get(\"id\"); break
                if not emp_id:
                    st.error(f\"Άγνωστος υπάλληλος: {r['Υπάλληλος']}\"); continue
                entries.append({
                    \"employee_id\": int(emp_id),
                    \"date\": r[\"Ημερομηνία\"].isoformat(),
                    \"shift\": r[\"Βάρδια\"],
                    \"role\": (r[\"Ρόλος\"] if pd.notna(r[\"Ρόλος\"]) else None)
                })
            try:
                bulk_save_week_schedule(company[\"id\"], smin, smax, entries)  # 4-arg modern API
                st.success(\"Αποθηκεύτηκε το πρόγραμμα.\")
            except TypeError:
                # Legacy 3-arg API (without end_date)
                bulk_save_week_schedule(company[\"id\"], smin, entries)
                st.success(\"Αποθηκεύτηκε το πρόγραμμα.\")
            except Exception as ex:
                st.error(f\"Αποτυχία αποθήκευσης: {ex}\")
