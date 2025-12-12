# -*- coding: utf-8 -*-
import os
import yaml
import pandas as pd
import streamlit as st
from PIL import Image
from dotenv import load_dotenv

# Load .env early
load_dotenv()

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

def apply_theme(mode: str, safe: bool = True):
    # Core selectors (kept brace-free for f-strings)
    INPUTS = (
        ".stTextInput input, .stNumberInput input, .stDateInput input, .stTimeInput input, "
        ".stTextArea textarea, .stSelectbox div[role='button'], .stMultiSelect div[role='button']"
    )
    MENUS = "[role='dialog'], [role='listbox']"
    LABELS = (
        "label, .stCheckbox label, .stRadio label, .stSlider label, "
        ".stSelectbox label, .stMultiSelect label, .stNumberInput label, "
        ".stTextInput label, .stDateInput label, .stTimeInput label"
    )
    GRID = "div[role='grid'], table"

    base_surfaces_safe = """
      html, body { background:var(--bg); color:var(--text); }
      header, footer { background:var(--bg); }
      section, aside { background:transparent; }
    """

    # NOTE: We deliberately avoid private [data-testid] selectors in production CSS.
    # Keeping an "enhanced" variant here for local experiments only.
    base_surfaces_enhanced = """
      [data-testid="stAppViewContainer"] { background:var(--bg); color:var(--text); }
      [data-testid="stHeader"], [data-testid="stToolbar"] { background:var(--bg) !important; border-bottom:1px solid var(--line); }
      [data-testid="stSidebar"] { background:var(--bg2); }
    """

    CSS_LIGHT = f"""
    <style>
    :root {{ --bg:#FFFFFF; --bg2:#F6F8FB; --text:#0F172A; --muted:#475569; --line:#CBD5E1; --primary:#2563EB; --shadow:0 2px 12px rgba(15,23,42,.06); }}

    /* Surfaces */
    {base_surfaces_safe if safe else base_surfaces_enhanced}
    .stExpander {{ border-radius:16px; box-shadow:var(--shadow); }}

    /* Text & links */
    {LABELS} {{ color:var(--text) !important; }}
    a {{ color:var(--primary) !important; }}

    /* Inputs */
    {INPUTS} {{
      background:var(--bg2) !important;
      color:var(--text) !important;
      border:1px solid var(--line) !important;
      border-radius:10px !important;
    }}
    .stTextInput input::placeholder, .stTextArea textarea::placeholder {{ color:var(--muted) !important; opacity:0.9; }}

    /* Menus (generic roles instead of test-ids) */
    {MENUS} {{
      background:var(--bg2) !important;
      color:var(--text) !important;
      border:1px solid var(--line) !important;
      box-shadow:var(--shadow) !important;
    }}
    {MENUS} * {{ color:var(--text) !important; }}

    /* Tables, sliders, metrics, progress */
    {GRID} {{ background:var(--bg2) !important; color:var(--text) !important; }}
    [data-baseweb="slider"] div[role="slider"] {{ background:var(--primary) !important; }}
    </style>
    """

    CSS_DARK = f"""
    <style>
    :root {{ --bg:#0B1220; --bg2:#111827; --text:#E5E7EB; --muted:#94A3B8; --line:#1F2937; --primary:#60A5FA; --shadow:0 2px 14px rgba(0,0,0,.45); }}

    {base_surfaces_safe if safe else base_surfaces_enhanced}
    .stExpander {{ border-radius:16px; box-shadow:var(--shadow); }}

    {LABELS} {{ color:var(--text) !important; }}
    a {{ color:var(--primary) !important; }}

    {INPUTS} {{
      background:var(--bg2) !important;
      color:var(--text) !important;
      border:1px solid var(--line) !important;
      border-radius:10px !important;
    }}
    .stTextInput input::placeholder, .stTextArea textarea::placeholder {{ color:var(--muted) !important; opacity:0.9; }}

    {MENUS} {{
      background:var(--bg2) !important;
      color:var(--text) !important;
      border:1px solid var(--line) !important;
      box-shadow:var(--shadow) !important;
    }}
    {MENUS} * {{ color:var(--text) !important; }}

    {GRID} {{ background:#0F172A !important; color:var(--text) !important; }}
    [data-baseweb="slider"] div[role="slider"] {{ background:var(--primary) !important; }}
    </style>
    """
    
    # Load additional modern styles
    css_content = ""
    try:
        with open("assets/modern_style.css", "r", encoding="utf-8") as f:
            css_content = f"<style>{f.read()}</style>"
    except FileNotFoundError:
        pass
    
    st.markdown(CSS_DARK if mode == "dark" else CSS_LIGHT, unsafe_allow_html=True)
    if css_content:
        st.markdown(css_content, unsafe_allow_html=True)


# Apply theme on load (safe selectors)
apply_theme(st.session_state["theme_mode"], safe=True)


# -------------------------
# Optional: brand/logo (theme-aware, safe fallback)
# -------------------------

def _safe_logo():
    try:
        mode = st.session_state.get("theme_mode", "light")
        brand_src = (
            "assets/brand_dark.png"
            if mode == "dark" and os.path.exists("assets/brand_dark.png")
            else "assets/brand.png"
        )
        icon_src = "assets/calendar_icon.png"
        st.logo(Image.open(brand_src), icon_image=Image.open(icon_src))
    except Exception:
        st.markdown("### 🗓️ Shift Planner Pro")


_safe_logo()

# -------------------------
# Extra UI polish (neutral; doesn’t fight theme colors)
# -------------------------
# Avoid private test-id selectors entirely here.
st.markdown(
    """
<style>
h1,h2,h3 { letter-spacing:-0.01em; }
.block-container { padding-top: 1.25rem; padding-bottom: 2.5rem; }
.stExpander { border-radius: 16px; box-shadow: 0 2px 12px rgba(15,23,42,.06); }
input, select, textarea { border-radius: 10px !important; }
:focus-visible { outline: 2px solid #2563EB33; outline-offset: 2px; }
button[kind="primary"] { border-radius: 12px !important; font-weight: 600; transition: transform .06s ease, box-shadow .12s ease; }
button[kind="primary"]:hover { transform: translateY(-1px); box-shadow: 0 6px 18px rgba(37,99,235,.18); }
/* keep the table sizing but avoid test-id where feasible */
table { font-size: 0.92rem; }
</style>
""",
    unsafe_allow_html=True,
)

# -------------------------
# App imports
# -------------------------
from db import init_db, get_all_companies, create_company
from ui_pages import page_select_company, page_business, page_employees, page_schedule

# Import onboarding and notifications
try:
    from onboarding import initialize_onboarding, show_welcome_tour
    from notifications import render_notification_center
    ONBOARDING_AVAILABLE = True
except ImportError:
    ONBOARDING_AVAILABLE = False


AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").strip().lower() in ("1", "true", "yes")
st.set_option("client.showErrorDetails", True)

import traceback

DEV_AUTH_FALLBACK = os.getenv("DEV_AUTH_FALLBACK", "false").strip().lower() in ("1", "true", "yes")

# -------------------------
# Auth gate (streamlit-authenticator, dev-friendly but not silent)
# -------------------------

def _auth_gate():
    """Gate the app with optional authentication, enforced in production.

    In development, we *do not* silently swallow configuration errors. To allow
    the legacy "continue without auth" behavior, set DEV_AUTH_FALLBACK=true.
    """
    if not AUTH_ENABLED:
        with st.sidebar:
            st.info("🔓 Authentication disabled.")
        return

    app_env = os.getenv("APP_ENV", "dev").lower()  # dev|prod
    cfg_path = ".streamlit/auth.yaml"

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
        msg = (
            f"❌ Authentication config missing. Expected: {os.path.abspath(cfg_path)}\n"
            f"Create it with **hashed** passwords."
        )
        if app_env == "prod":
            st.error(msg)
            st.stop()
        if not DEV_AUTH_FALLBACK:
            st.error(msg + "\nTo bypass in dev, set DEV_AUTH_FALLBACK=true.")
            st.stop()
        # else: allowed to proceed without auth in dev
    except Exception as e:
        if app_env == "prod":
            st.error(f"❌ Failed to initialize authentication: {e}")
            st.stop()
        if not DEV_AUTH_FALLBACK:
            st.exception(e)
            st.stop()
        else:
            st.warning(f"Auth init failed in dev, continuing without auth: {e}")

    # Dev/override fallback when no authenticator was created
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
    st.caption(f"⚙️ {env.upper()} environment")

# -------------------------
# Main
# -------------------------

def _run_page(fn):
    try:
        fn()
    except Exception:
        st.error(f"❌ Error in {getattr(fn, '__name__', 'page')}")
        st.code(traceback.format_exc())

def main():
    if AUTH_ENABLED:
        _auth_gate()

    # Init DB exactly once per run
    init_db()

    # Ensure at least one company exists
    if not get_all_companies():
        create_company("Default Business")

    # Sidebar: Modern navigation and settings
    with st.sidebar:
        # Company selector at top
        company_name = st.session_state.get("company", {}).get("name", "No Company Selected")
        st.markdown(f"### 🏢 {company_name}")
        
        if st.button("↻ Change Company", use_container_width=True, type="secondary"):
            st.session_state.pop("company", None)
            st.rerun()
        
        st.divider()
        
        # Clean navigation tabs
        default_idx = 5 if not st.session_state.get("company", {}).get("name") else 0
        page = st.radio(
            "Navigate",
            options=["🏢 Business Setup", "👥 Team", "📅 Schedule", "📋 Templates", "🔄 Self-Service", "🔍 Select Company"],
            index=default_idx,
            key="nav_radio",
            label_visibility="collapsed"
        )
        
        st.divider()
        
        # Compact progress indicator
        progress = _progress_value()
        st.caption(f"Setup: {progress}% complete")
        st.progress(progress / 100)
        
        st.divider()
        
        # Theme toggle at bottom
        dark_on = st.toggle(
            "🌙 Dark Mode",
            value=(st.session_state.get("theme_mode", "light") == "dark"),
            key="theme_toggle_main_v4",
        )
        new_mode = "dark" if dark_on else "light"
        if new_mode != st.session_state["theme_mode"]:
            st.session_state["theme_mode"] = new_mode
            st.query_params["theme"] = new_mode
            st.rerun()

        # Persist in URL
        current_theme = st.query_params.get("theme")
        current_theme = current_theme[0] if isinstance(current_theme, list) else current_theme
        if current_theme != st.session_state["theme_mode"]:
            st.query_params["theme"] = st.session_state["theme_mode"]

        # Apply theme
        apply_theme(st.session_state["theme_mode"])

    # Routing
    if page == "🔍 Select Company" or not st.session_state.get("company", {}).get("name"):
        page_select_company()
        return

    if page == "🏢 Business Setup":
        _run_page(page_business)
    elif page == "👥 Team":
        _run_page(page_employees)
    elif page == "📅 Schedule":
        _run_page(page_schedule)
    elif page == "📋 Templates":
        from template_pages import page_templates
        _run_page(page_templates)
    elif page == "🔄 Self-Service":
        from selfservice_pages import page_self_service
        _run_page(page_self_service)


if __name__ == "__main__":
    main()
