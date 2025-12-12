# -*- coding: utf-8 -*-
"""
Notification and toast system for user feedback.
Provides contextual notifications, progress tracking, and status updates.
"""

import streamlit as st
from datetime import datetime
from typing import Literal, Optional, Dict, Any
from enum import Enum


class NotificationType(Enum):
    """Notification types with corresponding icons and colors."""
    SUCCESS = ("✅", "success")
    ERROR = ("❌", "error")
    WARNING = ("⚠️", "warning")
    INFO = ("ℹ️", "info")
    LOADING = ("⏳", "info")


class NotificationManager:
    """Centralized notification management."""
    
    @staticmethod
    def show_toast(message: str, icon: str = "✅"):
        """Show a quick toast notification."""
        st.toast(message, icon=icon)
    
    @staticmethod
    def show_success(message: str, use_toast: bool = False):
        """Show success message."""
        if use_toast:
            st.toast(message, icon="✅")
        else:
            st.success(message)
    
    @staticmethod
    def show_error(message: str, use_toast: bool = False):
        """Show error message."""
        if use_toast:
            st.toast(message, icon="❌")
        else:
            st.error(message)
    
    @staticmethod
    def show_warning(message: str, use_toast: bool = False):
        """Show warning message."""
        if use_toast:
            st.toast(message, icon="⚠️")
        else:
            st.warning(message)
    
    @staticmethod
    def show_info(message: str, use_toast: bool = False):
        """Show info message."""
        if use_toast:
            st.toast(message, icon="ℹ️")
        else:
            st.info(message)


@st.fragment
def render_notification_center():
    """Render a notification center showing recent activities."""
    
    if "notifications" not in st.session_state:
        st.session_state.notifications = []
    
    with st.popover("🔔 Ειδοποιήσεις", use_container_width=False):
        st.markdown("### 📬 Πρόσφατες Ενέργειες")
        
        if not st.session_state.notifications:
            st.info("Δεν υπάρχουν πρόσφατες ειδοποιήσεις")
        else:
            for notif in reversed(st.session_state.notifications[-10:]):  # Show last 10
                timestamp = notif.get("timestamp", "")
                message = notif.get("message", "")
                type_ = notif.get("type", "info")
                
                icon = {
                    "success": "✅",
                    "error": "❌",
                    "warning": "⚠️",
                    "info": "ℹ️"
                }.get(type_, "ℹ️")
                
                st.markdown(f"{icon} **{message}**")
                st.caption(timestamp)
                st.divider()
        
        if st.button("🗑️ Καθαρισμός", use_container_width=True):
            st.session_state.notifications = []
            st.rerun()


def add_notification(message: str, type_: Literal["success", "error", "warning", "info"] = "info"):
    """Add a notification to the session state."""
    if "notifications" not in st.session_state:
        st.session_state.notifications = []
    
    st.session_state.notifications.append({
        "message": message,
        "type": type_,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })


@st.fragment
def render_progress_tracker(total_steps: int, current_step: int, step_names: Optional[list] = None):
    """Render a visual progress tracker for multi-step operations."""
    
    st.markdown("### 📊 Πρόοδος")
    
    progress = current_step / total_steps
    st.progress(progress, text=f"Βήμα {current_step} από {total_steps}")
    
    if step_names and len(step_names) >= total_steps:
        cols = st.columns(total_steps)
        for i, col in enumerate(cols):
            status = "✅" if i < current_step else "⏳" if i == current_step else "⭕"
            col.markdown(f"{status}")
            col.caption(step_names[i])


def show_operation_status(operation_name: str, steps: list):
    """Show detailed status for long-running operations."""
    
    with st.status(operation_name, expanded=True) as status:
        for i, step in enumerate(steps):
            st.write(f"🔄 {step}")
            yield i + 1  # Progress update
        
        status.update(label=f"{operation_name} - Ολοκληρώθηκε!", state="complete")


def show_confirmation_dialog(title: str, message: str, 
                            on_confirm=None, on_cancel=None) -> bool:
    """Show a confirmation dialog (using session state pattern)."""
    
    dialog_key = f"confirm_{title.replace(' ', '_')}"
    
    if st.session_state.get(dialog_key, False):
        st.warning(message, icon="⚠️")
        
        col1, col2 = st.columns(2)
        
        if col1.button("❌ Ακύρωση", key=f"{dialog_key}_cancel"):
            st.session_state[dialog_key] = False
            if on_cancel:
                on_cancel()
            st.rerun()
        
        if col2.button("✅ Επιβεβαίωση", key=f"{dialog_key}_confirm", type="primary"):
            st.session_state[dialog_key] = False
            if on_confirm:
                on_confirm()
            return True
    
    return False


@st.fragment
def render_activity_feed(activities: list[Dict[str, Any]]):
    """Render an activity feed showing recent changes."""
    
    st.markdown("### 📜 Ιστορικό Ενεργειών")
    
    if not activities:
        st.info("Δεν υπάρχουν πρόσφατες ενέργειες")
        return
    
    for activity in activities:
        timestamp = activity.get("timestamp", "")
        user = activity.get("user", "Σύστημα")
        action = activity.get("action", "")
        details = activity.get("details", "")
        
        with st.expander(f"🕐 {timestamp} - {action}", expanded=False):
            st.markdown(f"**Χρήστης:** {user}")
            if details:
                st.markdown(f"**Λεπτομέρειες:** {details}")


@st.fragment
def render_validation_results(results: Dict[str, Any]):
    """Render validation results with color-coded feedback."""
    
    st.markdown("### 🔍 Αποτελέσματα Ελέγχου")
    
    errors = results.get("errors", [])
    warnings = results.get("warnings", [])
    info = results.get("info", [])
    
    tab1, tab2, tab3 = st.tabs([
        f"❌ Σφάλματα ({len(errors)})",
        f"⚠️ Προειδοποιήσεις ({len(warnings)})",
        f"ℹ️ Πληροφορίες ({len(info)})"
    ])
    
    with tab1:
        if errors:
            for error in errors:
                st.error(error)
        else:
            st.success("Δεν βρέθηκαν σφάλματα!")
    
    with tab2:
        if warnings:
            for warning in warnings:
                st.warning(warning)
        else:
            st.info("Δεν υπάρχουν προειδοποιήσεις")
    
    with tab3:
        if info:
            for info_msg in info:
                st.info(info_msg)
        else:
            st.caption("Δεν υπάρχουν επιπλέον πληροφορίες")


def show_success_animation(message: str = "Επιτυχής ενέργεια!"):
    """Show a success animation with balloons."""
    st.success(message)
    st.balloons()


def show_loading_spinner(message: str = "Φόρτωση..."):
    """Context manager for showing loading spinner."""
    return st.spinner(message)


@st.fragment
def render_quick_actions_panel(actions: list[Dict[str, Any]]):
    """Render a panel with quick action buttons."""
    
    st.markdown("### ⚡ Γρήγορες Ενέργειες")
    
    cols = st.columns(min(len(actions), 4))
    
    for i, action in enumerate(actions):
        col = cols[i % len(cols)]
        
        with col:
            icon = action.get("icon", "▶️")
            label = action.get("label", "Action")
            callback = action.get("callback")
            disabled = action.get("disabled", False)
            help_text = action.get("help", "")
            
            if st.button(
                f"{icon} {label}",
                key=f"quick_action_{i}",
                use_container_width=True,
                disabled=disabled,
                help=help_text
            ):
                if callback:
                    callback()


@st.fragment  
def render_stats_cards(stats: list[Dict[str, Any]]):
    """Render statistics in card format."""
    
    cols = st.columns(len(stats))
    
    for i, stat in enumerate(stats):
        with cols[i]:
            st.metric(
                label=stat.get("label", ""),
                value=stat.get("value", ""),
                delta=stat.get("delta"),
                delta_color=stat.get("delta_color", "normal"),
                help=stat.get("help")
            )
