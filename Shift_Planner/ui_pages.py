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
    """Call auto_fix_schedule with flexible signatures and normalize output to (fixed_df, viols)."""
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

    active_shifts = company.get("active_shifts", [])
    roles = company.get("roles", [])
    rules = company.get("rules", {})
    role_settings = company.get("role_settings", {})
    work_model = company.get("work_model", "5ήμερο")

    # Infer start_date if missing from earliest date in df
    if start_date is None:
        try:
            start_date = pd.to_datetime(df["Ημερομηνία"]).dt.date.min()
        except Exception:
            import datetime as _dt
            start_date = _dt.date.today()

    # Infer days_count from number of unique dates if not provided
    if days_count is None:
        try:
            days_count = int(pd.to_datetime(df["Ημερομηνία"]).dt.date.nunique())
            if days_count <= 0:
                days_count = 7
        except Exception:
            days_count = 7

    # Try full signature
    try:
        return _auto_fix_schedule(df, start_date, emps, active_shifts, roles, rules, role_settings, days_count, work_model)
    except TypeError:
        pass
    # Try without days_count
    try:
        return _auto_fix_schedule(df, start_date, emps, active_shifts, roles, rules, role_settings, work_model)
    except TypeError:
        pass
    # Try legacy shapes
    try:
        return _auto_fix_schedule(df, emps, active_shifts, roles, rules, role_settings, days_count, work_model)
    except TypeError:
        pass
    try:
        return _auto_fix_schedule(df, emps, active_shifts, roles, rules, role_settings, work_model)
    except TypeError:
        pass
    try:
        return _auto_fix_schedule(df, active_shifts, rules)
    except TypeError:
        pass
    try:
        return _auto_fix_schedule(df, emps, active_shifts, roles, rules, role_settings)
    except TypeError:
        pass

    _df_for_validation = df.copy()
    if "Ώρες" in _df_for_validation.columns:
        _df_for_validation["Ώρες"] = pd.to_numeric(_df_for_validation["Ώρες"], errors="coerce").fillna(0).astype(float)
    viols = check_violations(_df_for_validation, rules=rules, work_model=work_model)
    return df, viols

    active_shifts = company.get("active_shifts", [])
    roles = company.get("roles", [])
    rules = company.get("rules", {})
    role_settings = company.get("role_settings", {})
    work_model = company.get("work_model", "5ήμερο")

    # Try with days_count if provided
    try:
        if days_count is None:
            # infer from df unique dates
            try:
                days_count = int(pd.to_datetime(df["Ημερομηνία"]).dt.date.nunique())
                if days_count <= 0:
                    days_count = 7
            except Exception:
                days_count = 7
        return _auto_fix_schedule(df, emps, active_shifts, roles, rules, role_settings, days_count, work_model)
    except TypeError:
        pass
    # Try without days_count
    try:
        return _auto_fix_schedule(df, emps, active_shifts, roles, rules, role_settings, work_model)
    except TypeError:
        pass
    # Try legacy minimal signature
    try:
        return _auto_fix_schedule(df, active_shifts, rules)
    except TypeError:
        pass
    # Try without work_model & days_count
    try:
        return _auto_fix_schedule(df, emps, active_shifts, roles, rules, role_settings)
    except TypeError:
        pass

    # Final fallback
    _df_for_validation = df.copy()
    if "Ώρες" in _df_for_validation.columns:
        _df_for_validation["Ώρες"] = pd.to_numeric(_df_for_validation["Ώρες"], errors="coerce").fillna(0).astype(float)
    viols = check_violations(_df_for_validation, rules, work_model)
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
        .block-container { padding-top: 1.2rem; padding-bottom: 2.4rem; }
        section[data-testid="stSidebar"] .block-container { padding-top: 0.8rem; }

        .stMetric { border-radius: 16px; padding: 0.4rem 0.6rem; }
        div[data-testid="stExpander"] > details { border-radius: 14px; }
        div[data-testid="stExpander"] summary { font-weight: 600; }

        div[data-testid="stDataFrame"] .st-emotion-cache-1yycgf0 { white-space: normal !important; }
        div[data-testid="stDataFrame"] .row_heading { font-weight: 600; }
        div[data-testid="stDataFrame"] .blank { color: var(--text-color); }

        .stButton>button, .stDownloadButton>button {
          border-radius: 12px;
          padding: 0.45rem 0.9rem;
          font-weight: 600;
        }

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
    """
    Show a button that clears session_state (company/employees/schedule)
    and επαναφέρει στην επιλογή εταιρείας.
    """
    if st.button("⬅️ Επιστροφή στην Επιλογή Επιχείρησης", key=key):
        for k in ("company", "employees", "schedule", "missing_staff", "violations"):
            st.session_state.pop(k, None)
        st.rerun()





# ===== Helpers for Employees page (added) =====
def _empty_state(title: str, bullets: list[str] | None = None, demo_button: bool = False, on_demo=None):
    st.info(f"**{title}**")
    for b in (bullets or []):
        st.markdown(f"- {b}")
    if demo_button and st.button("🪄 Γέμισε με demo υπαλλήλους"):
        if callable(on_demo):
            on_demo()
            st.success("Προστέθηκαν demo υπάλληλοι.")
            st.rerun()

def _employee_roles(emp: dict) -> list[str]:
    roles = emp.get("roles") or []
    if isinstance(roles, str):
        # handle CSV string
        roles = [r.strip() for r in roles.split(",") if r.strip()]
    if emp.get("role"):
        r = emp["role"]
        if r not in roles:
            roles = roles + [r]
    # dedup preserve order
    seen = set()
    out = []
    for r in roles:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out

def _availability_list(emp: dict) -> list[str]:
    av = emp.get("availability") or []
    if isinstance(av, str):
        av = [x.strip() for x in av.split(",") if x.strip()]
    # unique
    return list(dict.fromkeys(av))

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

def _save_employee_handler(emp: dict, new_name: str, new_roles: list[str], new_av: list[str],
                           role_options: list[str], shift_options: list[str]):
    new_name = (new_name or "").strip()
    if not new_name:
        st.warning("Το όνομα δεν μπορεί να είναι κενό.")
        return
    roles, _ = _sanitize_default(role_options or [], new_roles or [])
    av, _ = _sanitize_default(shift_options or [], new_av or [])
    if callable(update_employee) and emp.get("id"):
        try:
            update_employee(int(emp["id"]), new_name, roles, av)
            _refresh_employees(int(st.session_state.company.get("id", -1)))
            st.toast("💾 Αποθηκεύτηκαν οι αλλαγές.", icon="✅")
        except Exception as ex:
            st.error(f"Αποτυχία αποθήκευσης: {ex}")
    else:
        for e in st.session_state.get("employees", []):
            if e is emp or e.get("id") == emp.get("id"):
                e["name"], e["roles"], e["availability"] = new_name, roles, av
                break

def _delete_employee_handler(emp: dict):
    if callable(delete_employee) and emp.get("id"):
        try:
            delete_employee(int(emp["id"]))
            _refresh_employees(int(st.session_state.company.get("id", -1)))
            st.toast("🗑️ Διαγράφηκε.", icon="✅")
        except Exception as ex:
            st.error(f"Αποτυχία διαγραφής: {ex}")
    else:
        st.session_state["employees"] = [e for e in st.session_state.get("employees", []) if e is not emp and e.get("id") != emp.get("id")]

def _demo_seed():
    company = st.session_state.get("company", {}) or {}
    role_opts = company.get("roles", []) or []
    shift_opts = company.get("active_shifts", []) or []
    demos = [
        ("Μαρία", role_opts[:1], shift_opts[:2]),
        ("Γιάννης", role_opts[:2], shift_opts[:2]),
        ("Ελένη", role_opts[-1:], shift_opts[-2:] if len(shift_opts) >= 2 else shift_opts),
    ]
    if callable(add_employee):
        for n, r, a in demos:
            try:
                add_employee(int(company.get("id", -1)), n, r, a)
            except Exception:
                pass
        _refresh_employees(int(company.get("id", -1)))
    else:
        st.session_state.setdefault("employees", [])
        for n, r, a in demos:
            st.session_state.employees.append({"id": -1, "name": n, "roles": r, "availability": a})

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
        if cols[1].button("📦 Προεπιλεγμένοι ρόλοι", help="Συγχώνευση με τους τρέχοντες ρόλους.", use_container_width=True):
            before = set(company.get("roles", []))
            company["roles"] = sorted(before | set(DEFAULT_ROLES))
            added = set(company["roles"]) - before
            st.toast("Ενημερώθηκαν οι ρόλοι" + (f" (+{len(added)})" if added else ""), icon="✅")
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

    try:
        names = [e.get("name", "") for e in st.session_state.employees]
        dups = {n for n in names if n and names.count(n) > 1}
        if dups:
            st.warning("Υπάρχουν **διπλά ονόματα** υπαλλήλων: " + ", ".join(sorted(dups)) + ".")
    except Exception:
        pass

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
    """
    Rewritten schedule page: dependable generator + weekly visual grid with editing.
    """
    _apply_global_style()
    back_to_company_selection("back_schedule")
    st.subheader("📅 Πρόγραμμα")

    if "company" not in st.session_state or not st.session_state.get("company"):
        st.warning("Δεν έχει επιλεγεί επιχείρηση.")
        page_select_company()
        return
    if not st.session_state.get("employees"):
        st.warning("Δεν υπάρχουν υπάλληλοι. Προσθέστε για να δημιουργηθεί πρόγραμμα.")
        return

    st.session_state.setdefault("schedule", pd.DataFrame())
    st.session_state.setdefault("missing_staff", pd.DataFrame())
    st.session_state.setdefault("violations", pd.DataFrame())

    company = st.session_state.company
    emps = st.session_state.employees

    # Simple schedule page: only generator + table (no Visual builder)
    _tab_generate(company, emps)

def _tab_generate(company: Dict[str, Any], emps: List[Dict[str, Any]]):
    st.markdown("#### ⚙️ Δημιουργία πίνακα")
    col = st.columns(3)
    start_date = col[0].date_input("Έναρξη", dt_date.today(), key="gen_start")
    horizon = col[1].selectbox("Διάρκεια", ["7 ημέρες", "30 ημέρες"], index=0, key="gen_horizon")
    days_count = 7 if "7" in horizon else 30
    if st.button("🛠 Δημιουργία & Προεπισκόπηση", type="primary"):
        try:
            from scheduler import generate_schedule_v2, check_violations
        except Exception:
            st.error("Λείπει η scheduler.generate_schedule_v2()")
            return
        roles = company.get("roles", [])
        active_shifts = company.get("active_shifts", [])
        rules = company.get("rules", {})
        role_settings = company.get("role_settings", {})
        # Convert legacy {"Role": {"min_per_shift": N}} to supported {"per_shift": {...}} if needed
        _rs = role_settings if isinstance(role_settings, dict) else {}
        if _rs and not any(k in _rs for k in ("per_day", "per_shift", "min_per")):
            converted = {"per_shift": {s: {} for s in active_shifts}}
            for role, cfg in _rs.items():
                if isinstance(cfg, dict):
                    n = cfg.get("min_per_shift")
                    if isinstance(n, int) and n > 0:
                        for s in active_shifts:
                            converted["per_shift"][s][role] = n
            role_settings = converted
        work_model = company.get("work_model", "5ήμερο")
        df, missing = generate_schedule_v2(
            start_date, emps, active_shifts, roles, rules, role_settings, days_count, work_model
        )
        if not df.empty and not pd.api.types.is_datetime64_any_dtype(df["Ημερομηνία"]):
            df["Ημερομηνία"] = pd.to_datetime(df["Ημερομηνία"]).dt.date
        st.session_state.schedule = df
        st.session_state.missing_staff = missing
        # quick violations
        try:
            tmp = df.copy()
            if "Ώρες" in tmp.columns:
                tmp["Ώρες"] = pd.to_numeric(tmp["Ώρες"], errors="coerce").fillna(0).astype(float)
            st.session_state.violations = check_violations(tmp, rules=rules, work_model=work_model)
        except Exception:
            st.session_state.violations = pd.DataFrame()

    df = st.session_state.schedule.copy()
    if df.empty:
        st.info("Καμία προεπισκόπηση ακόμα. Πάτησε **Δημιουργία & Προεπισκόπηση**.")
        return

    st.markdown("#### 🧾 Πίνακας προεπισκόπησης")
    role_opts = ["— (χωρίς ρόλο)"] + company.get("roles", [])
    view_df = df.copy()
    view_df["Ημερομηνία"] = pd.to_datetime(view_df["Ημερομηνία"]).dt.strftime("%Y-%m-%d")
    edited = st.data_editor(
        view_df,
        column_config={
            "Βάρδια": st.column_config.TextColumn("Βάρδια", disabled=True),
            "Ημερομηνία": st.column_config.TextColumn("Ημερομηνία", disabled=True),
            "Υπάλληλος": st.column_config.TextColumn("Υπάλληλος", disabled=True),
            "Ρόλος": st.column_config.SelectboxColumn("Ρόλος", options=role_opts, required=False),
            "Ώρες": st.column_config.NumberColumn("Ώρες", step=0.5, format="%.1f"),
        },
        use_container_width=True, hide_index=True, num_rows="dynamic", key="gen_editor", height=380
    )
    ed = edited.copy()
    ed["Ημερομηνία"] = pd.to_datetime(ed["Ημερομηνία"]).dt.date
    ed["Ρόλος"] = ed["Ρόλος"].replace({"— (χωρίς ρόλο)": None})
    st.session_state.schedule = ed

    colA, colB, colC = st.columns([0.34, 0.33, 0.33])
    with colA:
        if not st.session_state.missing_staff.empty:
            st.warning("Ανέκλειστες ανάγκες:")
            st.dataframe(st.session_state.missing_staff, use_container_width=True, height=140)
    with colB:
        if not st.session_state.violations.empty:
            st.error("Παραβιάσεις κανόνων:")
            st.dataframe(st.session_state.violations, use_container_width=True, height=140)
    with colC:
        csv = ed.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Κατέβασμα CSV", data=csv, file_name="schedule_preview.csv", mime="text/csv")

    if st.button("💾 Αποθήκευση εβδομάδας στη ΒΔ"):
        if not callable(bulk_save_week_schedule):
            st.info("Η αποθήκευση δεν είναι διαθέσιμη σε αυτό το build.")
        else:
            smin = ed["Ημερομηνία"].min().isoformat()
            smax = ed["Ημερομηνία"].max().isoformat()
            entries = []
            for _, r in ed.iterrows():
                emp_id = None
                if callable(get_employee_id_by_name):
                    try:
                        emp_id = get_employee_id_by_name(company["id"], r["Υπάλληλος"])
                    except Exception as ex:
                        st.error(f"Πρόβλημα εύρεσης '{r['Υπάλληλος']}': {ex}")
                        continue
                if not emp_id:
                    for e in st.session_state.employees:
                        if e.get("name") == r["Υπάλληλος"]:
                            emp_id = e.get("id"); break
                if not emp_id:
                    st.error(f"Άγνωστος υπάλληλος: {r['Υπάλληλος']}"); continue
                entries.append({
                    "employee_id": int(emp_id),
                    "date": r["Ημερομηνία"].isoformat(),
                    "shift": r["Βάρδια"],
                    "role": (r["Ρόλος"] if pd.notna(r["Ρόλος"]) else None)
                })
            try:
                bulk_save_week_schedule(company["id"], smin, smax, entries)  # 4-arg modern API
                st.success("Αποθηκεύτηκε το πρόγραμμα.")
            except TypeError:
                # Legacy 3-arg API (without end_date)
                bulk_save_week_schedule(company["id"], smin, entries)
                st.success("Αποθηκεύτηκε το πρόγραμμα.")
            except Exception as ex:
                st.error(f"Αποτυχία αποθήκευσης: {ex}")

# (Visual builder removed by request)

def _column_key(d, shift):  # helper for grid column key
    return f"{d.isoformat()}__{shift}"

