# -*- coding: utf-8 -*-
"""
main.py — Streamlit runner, theming, auth (refactored)
- Centralized settings via Settings dataclass
- Dark-mode toggle flicker guard
- Page config only in Streamlit context
- Safe theme application and logo loading with fallbacks
- Idempotent DB init (if db.py is present) + seed default company if empty
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, Optional

import streamlit as st
from PIL import Image
from dotenv import load_dotenv

# Load .env early (safe outside Streamlit)
load_dotenv()

# -------------------------
# Settings
# -------------------------

@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "dev")
    show_errors: bool = os.getenv("SHOW_ERRORS", "1") in {"1", "true", "True"}
    auth_enabled: bool = os.getenv("AUTH_ENABLED", "0") in {"1", "true", "True"}
    dev_auth_fallback: bool = os.getenv("DEV_AUTH_FALLBACK", "1") in {"1", "true", "True"}
    page_title: str = os.getenv("APP_TITLE", "🧭 Διαχείριση Βαρδιών")
    page_icon: str = os.getenv("APP_ICON", "🧭")
    default_dark: bool = os.getenv("DEFAULT_DARK", "1") in {"1", "true", "True"}
    sidebar_logo_path: str = os.getenv("SIDEBAR_LOGO", "")
    top_logo_path: str = os.getenv("TOP_LOGO", "")

SETTINGS = Settings()


# -------------------------
# Helpers
# -------------------------

def _has_streamlit_ctx() -> bool:
    try:
        _ = st.session_state  # type: ignore[attr-defined]
        return True
    except Exception:
        return False


@lru_cache(maxsize=1)
def _load_image_safe(path: str) -> Optional[Image.Image]:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        return Image.open(p)
    except Exception:
        return None


def _set_page_config_once():
    """Set page config once per process. Streamlit ignores subsequent calls, but we guard anyway."""
    if not _has_streamlit_ctx():
        return
    if st.session_state.get("_page_config_set"):
        return
    st.set_page_config(
        page_title=SETTINGS.page_title,
        page_icon=SETTINGS.page_icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.session_state["_page_config_set"] = True


def _apply_theme(dark: bool):
    """Apply a minimal light/dark theme via CSS variables. Keep it tiny to avoid flicker."""
    # Avoid re-injecting identical CSS repeatedly
    key = f"theme_css_{'dark' if dark else 'light'}"
    if st.session_state.get("_theme_key") == key:
        return
    st.session_state["_theme_key"] = key

    css = """
    <style>
      :root {
        --bg: %s;
        --fg: %s;
        --card: %s;
        --muted: %s;
        --accent: %s;
      }
      .stApp { background: var(--bg); color: var(--fg); }
      .stMarkdown, .stText, .stDataFrame { color: var(--fg); }
      .st-emotion-cache-1r6slb0 { background: var(--card); } /* cards */
      .st-emotion-cache-1jicfl2, .st-emotion-cache-16txtl3 { color: var(--fg); }
      header[data-testid="stHeader"] { background: transparent; }
    </style>
    """ % (
        ("#0f172a", "#e5e7eb", "#111827", "#334155", "#22c55e")
        if dark
        else ("#ffffff", "#111827", "#f8fafc", "#cbd5e1", "#0ea5e9")
    )
    st.markdown(css, unsafe_allow_html=True)


def _toggle_dark_mode_ui():
    """Render a dark mode toggle that avoids double reruns & preserves URL query param."""
    # Query param sync
    qp = st.query_params
    qp_dark = qp.get("dark", str(SETTINGS.default_dark)).lower() in {"1", "true", "yes"}

    if "_dark" not in st.session_state:
        st.session_state["_dark"] = qp_dark
        st.session_state["_dark_applied_once"] = False  # flicker guard

    # Show the toggle
    new_val = st.sidebar.toggle("🌗 Σκούρο θέμα", value=st.session_state["_dark"])

    # If the user changed it, sync URL param and re-run once
    if new_val != st.session_state["_dark"]:
        st.session_state["_dark"] = new_val
        st.query_params["dark"] = "1" if new_val else "0"
        # Flicker guard: only rerun when param wasn't already in desired state
        if not st.session_state.get("_dark_applied_once"):
            st.session_state["_dark_applied_once"] = True
            st.rerun()

    _apply_theme(st.session_state["_dark"])


def _maybe_auth() -> bool:
    """Very simple pluggable auth gate. Return True if signed in/allowed, else False.
    Implement your real auth here. In dev, allow bypass if configured.
    """
    if not SETTINGS.auth_enabled:
        if SETTINGS.app_env != "prod":
            return True  # no auth in dev unless explicitly enabled
        # In prod with auth disabled, still allow (or you can choose to block)
        return True

    # Example stub: look for a cookie/param or fallback to dev bypass
    user = st.experimental_user or None  # type: ignore[attr-defined]
    if user:
        return True

    if SETTINGS.dev_auth_fallback and SETTINGS.app_env != "prod":
        st.info("🔓 Dev auth bypass active. Set AUTH_ENABLED=0 to skip this gate entirely.")
        return True

    st.error("🔒 Απαιτείται σύνδεση για πρόσβαση.")
    return False


def _seed_defaults_if_needed():
    """Idempotent DB init + seed default company if empty, if db.py exists with expected funcs."""
    try:
        import db  # type: ignore
    except Exception:
        return
    try:
        if hasattr(db, "init_db"):
            db.init_db()
        # Seed a default company if table exists and is empty
        if hasattr(db, "get_companies") and hasattr(db, "create_company"):
            companies = db.get_companies()
            if not companies:
                db.create_company({"name": "Default Company"})
    except Exception as e:
        if SETTINGS.show_errors:
            st.warning(f"DB init/seed skipped due to error: {e}")


def _lazy_import_pages():
    """Try import page modules; return callables or no-op placeholders."""
    def null_page():
        st.write("⚠️ Η σελίδα δεν είναι διαθέσιμη σε αυτό το build.")

    def imp(fn_name: str) -> Callable[[], None]:
        parts = fn_name.split(":")
        if len(parts) == 2:
            mod, func = parts
        else:
            mod, func = fn_name, "main"
        try:
            module = __import__(mod, fromlist=[func])
            return getattr(module, func)
        except Exception:
            return null_page

    return {
        "🏢 Επιχείρηση": imp("page_business:page_business"),
        "👥 Υπάλληλοι": imp("ui_pages:page_employees"),
        "📅 Πρόγραμμα": imp("ui_pages:page_schedule"),
        "🤖 Chatbot": imp("ui_pages:page_chatbot"),
    }


def _sidebar_branding():
    st.sidebar.markdown("### " + SETTINGS.page_title)
    logo = _load_image_safe(SETTINGS.sidebar_logo_path)
    if logo:
        st.sidebar.image(logo, use_column_width=True)


def main():
    _set_page_config_once()

    if not _maybe_auth():
        return

    _sidebar_branding()
    _toggle_dark_mode_ui()

    _seed_defaults_if_needed()

    pages = _lazy_import_pages()

    # Sidebar navigation
    page_key = "nav_page"
    choice = st.sidebar.radio("Μενού", list(pages.keys()), index=0, key=page_key)

    # Optional top logo
    top_logo = _load_image_safe(SETTINGS.top_logo_path)
    if top_logo:
        st.image(top_logo, width=180)

    # Render the selected page
    page_fn = pages.get(choice)
    if page_fn:
        page_fn()
    else:
        st.write("Δεν βρέθηκε η σελίδα.")

if __name__ == "__main__":
    if not _has_streamlit_ctx():
        print("This app is intended to be run with:  streamlit run main.py")
    else:
        main()
