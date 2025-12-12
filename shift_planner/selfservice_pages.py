# -*- coding: utf-8 -*-
"""
Employee Self-Service UI Pages
Shift swaps, pickups, and bidding
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from shift_swaps import (
    create_swap_request, get_swap_requests, get_pending_swap_requests_for_approval,
    approve_swap_request, reject_swap_request, cancel_swap_request,
    create_shift_bid, get_shift_bids, award_shift_bid, SwapStatus
)


def page_self_service():
    """Employee self-service page"""
    st.title("🔄 Self-Service Portal")
    st.markdown("Manage your shifts, swaps, and bids")
    
    # Check if user is employee or manager
    is_manager = st.session_state.get('username', 'admin') == 'admin' or st.session_state.get('username', '').startswith('manager')
    
    if is_manager:
        tabs = st.tabs(["📋 My Requests", "✅ Approve Swaps", "🎯 Shift Bids", "➕ Request Swap"])
    else:
        tabs = st.tabs(["📋 My Requests", "➕ Request Swap", "🎯 Bid on Shifts"])
    
    with tabs[0]:
        _my_swap_requests()
    
    if is_manager:
        with tabs[1]:
            _approve_swaps()
        with tabs[2]:
            _manage_shift_bids()
        with tabs[3]:
            _request_swap()
    else:
        with tabs[1]:
            _request_swap()
        with tabs[2]:
            _bid_on_shifts()


def _my_swap_requests():
    """Display user's swap requests"""
    st.subheader("My Swap Requests")
    
    # Mock employee ID (in real app, would come from authentication)
    employee_id = st.session_state.get('current_employee_id', 1)
    
    try:
        requests = get_swap_requests(employee_id=employee_id)
        
        if not requests:
            st.info("You have no swap requests yet")
            return
        
        # Filter by status
        status_filter = st.selectbox(
            "Filter by status",
            ["All", "Pending", "Approved", "Rejected", "Cancelled"],
            key="my_swaps_filter"
        )
        
        if status_filter != "All":
            requests = [r for r in requests if r.status == status_filter.lower()]
        
        # Display requests
        for req in requests:
            status_icon = {
                'pending': '⏳',
                'approved': '✅',
                'rejected': '❌',
                'cancelled': '🚫',
                'completed': '✔️'
            }.get(req.status, '❓')
            
            with st.expander(f"{status_icon} {req.shift_date} - {req.shift_type.title()} Shift ({req.status.title()})", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Shift:** {req.shift_date} ({req.shift_type.title()})")
                    st.markdown(f"**Role:** {req.role}")
                    st.markdown(f"**Type:** {req.swap_type.title()}")
                    if req.target_employee_name:
                        st.markdown(f"**With:** {req.target_employee_name}")
                    if req.reason:
                        st.markdown(f"**Reason:** {req.reason}")
                    st.markdown(f"**Requested:** {req.requested_at[:10] if req.requested_at else 'N/A'}")
                    
                    if req.status in ['approved', 'rejected']:
                        st.markdown(f"**Decided by:** {req.approved_by or 'N/A'}")
                        if req.response_message:
                            st.info(f"💬 {req.response_message}")
                
                with col2:
                    if req.status == 'pending':
                        if st.button("🚫 Cancel", key=f"cancel_swap_{req.id}"):
                            if cancel_swap_request(req.id):
                                st.success("Request cancelled")
                                st.rerun()
    
    except Exception as e:
        st.error(f"Error loading swap requests: {e}")


def _request_swap():
    """Request a shift swap"""
    st.subheader("Request Shift Swap")
    
    # Get employee info
    employee_id = st.session_state.get('current_employee_id', 1)
    employee_name = st.session_state.get('username', 'Current User')
    
    # Get upcoming shifts for this employee
    # (In real implementation, query from schedules table)
    st.info("💡 Select one of your upcoming shifts to swap or drop")
    
    with st.form("swap_request_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            swap_type = st.selectbox(
                "Request Type",
                ["swap", "drop", "pickup"],
                format_func=lambda x: {"swap": "Swap with someone", "drop": "Drop shift", "pickup": "Pick up open shift"}[x],
                key="swap_type_select"
            )
            
            shift_date = st.date_input(
                "Shift Date",
                value=date.today() + timedelta(days=1),
                min_value=date.today(),
                key="swap_shift_date"
            )
            
            shift_type = st.selectbox(
                "Shift Type",
                ["morning", "afternoon", "evening", "day", "night"],
                key="swap_shift_type"
            )
        
        with col2:
            role = st.selectbox(
                "Role",
                ["Manager", "Server", "Cook", "Cashier", "Host", "Bartender"],
                key="swap_role"
            )
            
            # If swapping, select target employee
            if swap_type == "swap":
                target_employee = st.selectbox(
                    "Swap with (optional)",
                    ["Anyone available", "John Doe", "Jane Smith", "Bob Johnson"],
                    key="swap_target"
                )
            else:
                target_employee = None
            
            reason = st.text_area(
                "Reason (optional)",
                placeholder="e.g., Doctor appointment, family emergency, etc.",
                key="swap_reason"
            )
        
        submitted = st.form_submit_button("📤 Submit Request", use_container_width=True)
        
        if submitted:
            try:
                target_id = None if target_employee == "Anyone available" or not target_employee else 2
                target_name = None if target_employee == "Anyone available" else target_employee
                
                swap_id = create_swap_request(
                    requesting_employee_id=employee_id,
                    requesting_employee_name=employee_name,
                    shift_date=shift_date.isoformat(),
                    shift_type=shift_type,
                    role=role,
                    swap_type=swap_type,
                    target_employee_id=target_id,
                    target_employee_name=target_name,
                    reason=reason
                )
                
                st.success(f"✅ Swap request #{swap_id} submitted successfully!")
                st.info("Your manager will review this request")
                
            except Exception as e:
                st.error(f"Error submitting request: {e}")


def _approve_swaps():
    """Manager: Approve or reject swap requests"""
    st.subheader("Pending Swap Requests")
    
    try:
        pending_requests = get_pending_swap_requests_for_approval()
        
        if not pending_requests:
            st.success("✅ No pending swap requests")
            return
        
        st.info(f"📝 {len(pending_requests)} requests awaiting approval")
        
        for req in pending_requests:
            with st.expander(f"⏳ {req.requesting_employee_name} - {req.shift_date} ({req.shift_type.title()})", expanded=True):
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.markdown(f"**Employee:** {req.requesting_employee_name}")
                    st.markdown(f"**Shift:** {req.shift_date} - {req.shift_type.title()}")
                    st.markdown(f"**Role:** {req.role}")
                    st.markdown(f"**Type:** {req.swap_type.title()}")
                    if req.target_employee_name:
                        st.markdown(f"**Swap with:** {req.target_employee_name}")
                    if req.reason:
                        st.markdown(f"**Reason:** {req.reason}")
                
                with col2:
                    response_msg = st.text_input(
                        "Response message (optional)",
                        key=f"response_{req.id}",
                        placeholder="Add a note..."
                    )
                
                with col3:
                    if st.button("✅ Approve", key=f"approve_{req.id}", use_container_width=True):
                        approved_by = st.session_state.get('username', 'admin')
                        if approve_swap_request(req.id, approved_by, response_msg):
                            st.success("Approved!")
                            st.rerun()
                    
                    if st.button("❌ Reject", key=f"reject_{req.id}", use_container_width=True):
                        approved_by = st.session_state.get('username', 'admin')
                        if reject_swap_request(req.id, approved_by, response_msg or "Request denied"):
                            st.success("Rejected")
                            st.rerun()
    
    except Exception as e:
        st.error(f"Error loading requests: {e}")


def _bid_on_shifts():
    """Employee: Bid on open shifts"""
    st.subheader("Available Open Shifts")
    st.info("🚧 Open shifts bidding coming soon!")
    st.markdown("""
    Features:
    - Browse open shifts
    - Express interest / bid on shifts
    - See your bid status
    - Auto-assignment based on seniority/priority
    """)


def _manage_shift_bids():
    """Manager: Review and award shift bids"""
    st.subheader("Shift Bid Management")
    st.info("🚧 Bid management coming soon!")
    st.markdown("""
    Features:
    - View all pending bids
    - Award shifts to employees
    - Set bidding rules (seniority, performance, etc.)
    """)
