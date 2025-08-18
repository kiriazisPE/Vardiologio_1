# -*- coding: utf-8 -*-
import pandas as pd
import os, yaml, streamlit as st
from PIL import Image
# main.py (top of file)
from dotenv import load_dotenv; load_dotenv()  # load .env early


# -------------------------
# Page config (must run first)
# -------------------------
st.set_page_config(page_title="Shift Planner Pro", page_icon="🗓️", layout="wide")

# -------------------------
# URL helpers (no experimental APIs)
# -------------------------
def _qp_get(key: str, default: str):
    val = st.query_params.get(key, default)
    if isinstance(val, list):
        return val[0] if val else default
    return val

# Initialize theme from URL once per session
if "theme_mode" not in st.session_state:
    initial = str(_qp_get("theme", "light")).lower()
    st.session_state["theme_mode"] = "dark" if initial in ("dark", "d") else "light"

# -------------------------
# Theme CSS
# -------------------------
def apply_theme(mode: str):
    # Core selectors (kept brace-free for f-strings)
    INPUTS = (
        ".stTextInput input, .stNumberInput input, .stDateInput input, .stTimeInput input, "
        ".stTextArea textarea, .stSelectbox div[role='button'], .stMultiSelect div[role='button']"
    )
    MENUS = "div[data-baseweb='popover'], div[data-baseweb='menu']"  # select/multiselect portals
    LABELS = (
        "[data-testid='stWidgetLabel'] label, label, "
        "[data-testid='stMarkdownContainer'] p, [data-testid='stCaption'], small, "
        ".stCheckbox label, .stRadio label, .stSlider label, "
        ".stSelectbox label, .stMultiSelect label, .stNumberInput label, .stTextInput label, "
        ".stDateInput label, .stTimeInput label"
    )
    GRID = "[data-testid='stDataFrame'] div[role='grid']"

    CSS_LIGHT = f"""
    <style>
    :root {{ --bg:#FFFFFF; --bg2:#F6F8FB; --text:#0F172A; --muted:#475569; --line:#CBD5E1; --primary:#2563EB; --shadow:0 2px 12px rgba(15,23,42,.06); }}

    /* Surfaces */
    html, body, [data-testid="stAppViewContainer"] {{ background:var(--bg); color:var(--text); }}
    [data-testid="stHeader"], [data-testid="stToolbar"] {{ background:var(--bg) !important; border-bottom:1px solid var(--line); }}
    [data-testid="stSidebar"] {{ background:var(--bg2); }}
    .stExpander, div:has(> .st-subheader) {{ border-radius:16px; box-shadow:var(--shadow); }}

    /* Universal text color for common containers */
    {LABELS} {{ color:var(--text) !important; }}
    a {{ color:var(--primary) !important; }}

    /* Inputs & their placeholders */
    {INPUTS} {{
      background:var(--bg2) !important;
      color:var(--text) !important;
      border:1px solid var(--line) !important;
      border-radius:10px !important;
    }}
    .stTextInput input::placeholder,
    .stTextArea textarea::placeholder {{ color:var(--muted) !important; opacity:0.9; }}

    /* Dropdown menus (portals) */
    {MENUS} {{
      background:var(--bg2) !important;
      color:var(--text) !important;
      border:1px solid var(--line) !important;
      box-shadow:var(--shadow) !important;
    }}
    {MENUS} * {{ color:var(--text) !important; }}

    /* Tables, sliders, metrics, progress */
    {GRID} {{ background:var(--bg2) !important; color:var(--text) !important; }}
    [data-testid="stMetricValue"] {{ border-radius:10px; padding:2px 8px; background:var(--bg2); color:var(--text) !important; }}
    [data-baseweb="slider"] div[role="slider"] {{ background:var(--primary) !important; }}
    [data-testid="stProgressBar"] > div > div {{ background: var(--primary) !important; }}

    /* Buttons */
    button[kind="primary"] {{ background:var(--primary) !important; color:#fff !important; border-radius:12px !important; font-weight:600; transition:transform .06s, box-shadow .12s; }}
    button[kind="primary"]:hover {{ transform:translateY(-1px); box-shadow:0 6px 18px rgba(37,99,235,.18); }}
    </style>
    """

    CSS_DARK = f"""
    <style>
    :root {{ --bg:#0B1220; --bg2:#111827; --text:#E5E7EB; --muted:#94A3B8; --line:#1F2937; --primary:#60A5FA; --shadow:0 2px 14px rgba(0,0,0,.45); }}

    html, body, [data-testid="stAppViewContainer"] {{ background:var(--bg); color:var(--text); }}
    [data-testid="stHeader"], [data-testid="stToolbar"] {{ background:var(--bg) !important; border-bottom:1px solid var(--line); }}
    [data-testid="stSidebar"] {{ background:var(--bg2); }}
    .stExpander, div:has(> .st-subheader) {{ border-radius:16px; box-shadow:var(--shadow); }}

    {LABELS} {{ color:var(--text) !important; }}
    a {{ color:var(--primary) !important; }}

    {INPUTS} {{
      background:var(--bg2) !important;
      color:var(--text) !important;
      border:1px solid var(--line) !important;
      border-radius:10px !important;
    }}
    .stTextInput input::placeholder,
    .stTextArea textarea::placeholder {{ color:var(--muted) !important; opacity:0.9; }}

    {MENUS} {{
      background:var(--bg2) !important;
      color:var(--text) !important;
      border:1px solid var(--line) !important;
      box-shadow:var(--shadow) !important;
    }}
    {MENUS} * {{ color:var(--text) !important; }}

    {GRID} {{ background:#0F172A !important; color:var(--text) !important; }}
    [data-testid="stMetricValue"] {{ border-radius:10px; padding:2px 8px; background:#0F172A; color:var(--text) !important; }}
    [data-baseweb="slider"] div[role="slider"] {{ background:var(--primary) !important; }}
    [data-testid="stProgressBar"] > div > div {{ background: var(--primary) !important; }}

    button[kind="primary"] {{ background:var(--primary) !important; color:#0B1220 !important; border-radius:12px !important; font-weight:600; transition:transform .06s, box-shadow .12s; }}
    button[kind="primary"]:hover {{ transform:translateY(-1px); box-shadow:0 6px 18px rgba(96,165,250,.25); }}
    </style>
    """
    st.markdown(CSS_DARK if mode == "dark" else CSS_LIGHT, unsafe_allow_html=True)



# Apply theme on load
apply_theme(st.session_state["theme_mode"])


# -------------------------
# Optional: brand/logo (theme-aware, safe fallback)
# -------------------------
def _safe_logo():
    try:
        mode = st.session_state.get("theme_mode", "light")
        brand_src = "assets/brand_dark.png" if mode == "dark" and os.path.exists("assets/brand_dark.png") else "assets/brand.png"
        icon_src  = "assets/calendar_icon.png"
        st.logo(Image.open(brand_src), icon_image=Image.open(icon_src))
    except Exception:
        st.markdown("### 🗓️ Shift Planner Pro")

_safe_logo()

# -------------------------
# Extra UI polish (neutral; doesn’t fight theme colors)
# -------------------------
st.markdown("""
<style>
h1,h2,h3 { letter-spacing:-0.01em; }
.block-container { padding-top: 1.25rem; padding-bottom: 2.5rem; }
.stExpander, div:has(> .st-subheader) { border-radius: 16px; box-shadow: 0 2px 12px rgba(15,23,42,.06); }
input, select, textarea { border-radius: 10px !important; }
:focus-visible { outline: 2px solid #2563EB33; outline-offset: 2px; }
button[kind="primary"] { border-radius: 12px !important; font-weight: 600; transition: transform .06s ease, box-shadow .12s ease; }
button[kind="primary"]:hover { transform: translateY(-1px); box-shadow: 0 6px 18px rgba(37,99,235,.18); }
[data-testid="stDataFrame"] table { font-size: 0.92rem; }
[data-testid="stSidebar"] .stRadio > label { font-weight: 600; }
[data-testid="stMetricValue"] { border-radius: 10px; padding: 2px 8px; }
</style>
""", unsafe_allow_html=True)

# -------------------------
# App imports
# -------------------------
from db import init_db, get_all_companies, create_company
from ui_pages import (
    page_select_company,
    page_business,
    page_employees,
    page_schedule,
)

AUTH_ENABLED = True

# -------------------------
# Auth gate (streamlit-authenticator, dev-friendly fallback)
# -------------------------

def _auth_gate():
    """Gate the app with optional authentication, enforced in production."""
    app_env = os.getenv("APP_ENV", "dev").lower()  # dev|prod  (from your constants) 
    cfg_path = ".streamlit/auth.yaml"

    # Try to construct the authenticator
    authenticator = None
    try:
        import streamlit_authenticator as stauth
        with open(cfg_path, "r", encoding="utf-8") as f:
            auth_cfg = yaml.safe_load(f)
        authenticator = stauth.Authenticate(
            auth_cfg["credentials"],
            auth_cfg["cookie"]["name"],
            auth_cfg["cookie"]["key"],
            auth_cfg["cookie"]["expiry_days"],
        )
    except FileNotFoundError:
        if app_env == "prod":
            st.error(
                f"❌ Authentication config missing.\n"
                f"Expected file: `{os.path.abspath(cfg_path)}`\n"
                f"Create it with **hashed** passwords."
            )
            st.stop()
    except Exception as e:
        if app_env == "prod":
            st.error(f"❌ Failed to initialize authentication: {e}")
            st.stop()

    # Dev fallback when no authenticator was created
    if authenticator is None:
        with st.sidebar:
            st.info("Auth disabled (dev mode). Provide .streamlit/auth.yaml to enable login.")
        return

    # ---- Render login (new API first; fallback to old) ----
    name = username = None
    auth_status = None
    try:
        # New API (>=0.4.x): returns None; results in session_state
        authenticator.login(location="main", key="Login")
        auth_status = st.session_state.get("authentication_status")
        name = st.session_state.get("name")
        username = st.session_state.get("username")
    except TypeError:
        # Old API (<=0.3.x): returns a tuple
        name, auth_status, username = authenticator.login("Login", "main")

    # Common handling
    if auth_status is not True:
        if auth_status is False:
            st.error("Λάθος username / password.")
        else:
            st.warning("Παρακαλώ εισάγετε username και password.")
        st.stop()

    with st.sidebar:
        st.caption(f"👤 {name or username}")
        try:
            authenticator.logout(location="sidebar")  # new API
        except TypeError:
            authenticator.logout("Logout", "sidebar")  # old API


# -------------------------
# Sidebar helpers
# -------------------------
def _progress_value() -> int:
    company_ready = 1 if st.session_state.get("company", {}).get("name") else 0
    employees_ready = 1 if len(st.session_state.get("employees", [])) > 0 else 0
    sched = st.session_state.get("schedule", None)
    try:
        schedule_ready = 1 if (hasattr(sched, "empty") and sched is not None and not sched.empty) else 0
    except Exception:
        schedule_ready = 0
    return int(company_ready * 33 + employees_ready * 33 + schedule_ready * 34)

def _sidebar_status():
    env = os.getenv("APP_ENV", "dev")
    db_file = os.getenv("DB_FILE", "shifts.db")
    session_ttl = os.getenv("SESSION_TTL_MIN", "240")
    st.divider()
    st.markdown("### Session & Environment")
    st.caption(f"🌐 Env: **{env}** · ⏱ Session: **{session_ttl}′** · 🗄 DB: **{db_file}**")
    st.caption("Data integrity: **ON** · Safe actions with **Undo**")

# -------------------------
# Main
# -------------------------
def main():
    _auth_gate()
    init_db()

    # Ensure at least one company exists
    if not get_all_companies():
        create_company("Default Business")

    # Sidebar: appearance + nav + status
    with st.sidebar:
        # Appearance
        st.markdown("### Appearance")
        dark_on = st.toggle(
            "Dark mode",
            value=(st.session_state.get("theme_mode", "light") == "dark"),
            key="theme_toggle_main_v4",
        )
        new_mode = "dark" if dark_on else "light"
        if new_mode != st.session_state["theme_mode"]:
            st.session_state["theme_mode"] = new_mode
            st.query_params["theme"] = new_mode
            st.rerun()

        # Persist in URL (mapping syntax)
        current_theme = st.query_params.get("theme")
        current_theme = current_theme[0] if isinstance(current_theme, list) else current_theme
        if current_theme != st.session_state["theme_mode"]:
            st.query_params["theme"] = st.session_state["theme_mode"]

        # Re-apply after toggle (also happens on rerun)
        apply_theme(st.session_state["theme_mode"])

        # Navigation
        st.markdown("### Navigation")
        default_idx = 3 if not st.session_state.get("company", {}).get("name") else 0
        page = st.radio(
            "Go to",
            options=["🏢 Επιχείρηση", "👥 Υπάλληλοι", "📅 Πρόγραμμα", "🔍 Επιλογή"],
            index=default_idx,
            key="nav_radio",
        )

        # Progress + status
        st.progress(_progress_value(), text="Setup progress")
        _sidebar_status()

    # Routing
    if page == "🔍 Επιλογή" or not st.session_state.get("company", {}).get("name"):
        page_select_company()
        return

    if page == "🏢 Επιχείρηση":
        page_business()
    elif page == "👥 Υπάλληλοι":
        page_employees()
    elif page == "📅 Πρόγραμμα":
        page_schedule()

if __name__ == "__main__":
    main()
