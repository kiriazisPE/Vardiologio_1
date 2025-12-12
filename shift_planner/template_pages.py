# -*- coding: utf-8 -*-
"""
Schedule Templates UI Pages
Manage reusable schedule templates
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from schedule_templates import (
    ScheduleTemplate, save_template, load_template,
    list_templates, delete_template, apply_template_to_schedule,
    create_template_from_schedule
)


def page_templates():
    """Template management page"""
    st.title("📋 Schedule Templates")
    st.markdown("Create and manage reusable schedule patterns")
    
    # Tab navigation
    tab1, tab2, tab3 = st.tabs(["📚 Template Library", "✏️ Create/Edit Template", "🔄 Apply Template"])
    
    with tab1:
        _template_library()
    
    with tab2:
        _create_edit_template()
    
    with tab3:
        _apply_template()


def _template_library():
    """Display template library"""
    st.subheader("Template Library")
    
    # Filters
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        pattern_filter = st.selectbox(
            "Pattern Type",
            ["All", "weekly", "biweekly", "monthly"],
            key="template_pattern_filter"
        )
    with col2:
        show_inactive = st.checkbox("Show inactive templates", key="show_inactive_templates")
    with col3:
        if st.button("➕ New Template", key="new_template_btn"):
            st.session_state['template_action'] = 'create'
            st.rerun()
    
    # Load templates
    try:
        templates = list_templates(
            active_only=not show_inactive,
            pattern_type=None if pattern_filter == "All" else pattern_filter
        )
        
        if not templates:
            st.info("No templates found. Create your first template to get started!")
            return
        
        # Display templates as cards
        for i, template in enumerate(templates):
            with st.expander(f"📋 {template.name}", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Description:** {template.description or 'No description'}")
                    st.markdown(f"**Business Model:** {template.business_model}")
                    st.markdown(f"**Pattern:** {template.pattern_type}")
                    st.markdown(f"**Shifts:** {', '.join(template.active_shifts)}")
                    st.markdown(f"**Roles:** {', '.join(template.roles)}")
                    
                    # Coverage summary
                    if template.role_coverage:
                        st.markdown("**Coverage Requirements:**")
                        for role, shifts in template.role_coverage.items():
                            coverage_str = ", ".join([f"{shift}: {count}" for shift, count in shifts.items() if count > 0])
                            if coverage_str:
                                st.markdown(f"  - *{role}*: {coverage_str}")
                    
                    if template.created_at:
                        st.caption(f"Created: {template.created_at[:10]}")
                
                with col2:
                    if st.button("✏️ Edit", key=f"edit_template_{template.id}"):
                        st.session_state['template_action'] = 'edit'
                        st.session_state['template_id'] = template.id
                        st.rerun()
                    
                    if st.button("🔄 Apply", key=f"apply_template_{template.id}"):
                        st.session_state['template_action'] = 'apply'
                        st.session_state['template_id'] = template.id
                        st.rerun()
                    
                    if st.button("📋 Clone", key=f"clone_template_{template.id}"):
                        st.session_state['template_action'] = 'clone'
                        st.session_state['template_id'] = template.id
                        st.rerun()
                    
                    if template.is_active:
                        if st.button("🗑️ Archive", key=f"archive_template_{template.id}"):
                            delete_template(template.id, soft_delete=True)
                            st.success(f"Template '{template.name}' archived")
                            st.rerun()
                    else:
                        st.caption("(Archived)")
    
    except Exception as e:
        st.error(f"Error loading templates: {e}")


def _create_edit_template():
    """Create or edit template"""
    action = st.session_state.get('template_action', 'create')
    template_id = st.session_state.get('template_id')
    
    if action == 'edit' and template_id:
        st.subheader("Edit Template")
        template = load_template(template_id)
        if not template:
            st.error("Template not found")
            return
    elif action == 'clone' and template_id:
        st.subheader("Clone Template")
        template = load_template(template_id)
        if template:
            template.id = None
            template.name = f"{template.name} (Copy)"
        else:
            template = ScheduleTemplate()
    else:
        st.subheader("Create New Template")
        template = ScheduleTemplate()
    
    # Template form
    with st.form("template_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Template Name *", value=template.name or "", key="template_name")
            business_model = st.selectbox(
                "Business Model *",
                ["5ήμερο", "6ήμερο"],
                index=0 if template.business_model == "5ήμερο" else 1,
                key="template_business_model"
            )
            pattern_type = st.selectbox(
                "Pattern Type *",
                ["weekly", "biweekly", "monthly"],
                index=["weekly", "biweekly", "monthly"].index(template.pattern_type) if template.pattern_type in ["weekly", "biweekly", "monthly"] else 0,
                key="template_pattern_type"
            )
        
        with col2:
            description = st.text_area(
                "Description",
                value=template.description or "",
                height=100,
                key="template_description"
            )
        
        st.markdown("---")
        st.markdown("### Shifts & Roles")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Active Shifts**")
            shift_options = ["morning", "afternoon", "evening", "day", "night"]
            active_shifts = st.multiselect(
                "Select shifts",
                shift_options,
                default=template.active_shifts or [],
                key="template_shifts"
            )
        
        with col2:
            st.markdown("**Roles**")
            # Get roles from business settings or allow manual entry
            default_roles = ["Manager", "Server", "Cook", "Cashier", "Host"]
            roles = st.multiselect(
                "Select roles",
                default_roles,
                default=template.roles or [],
                key="template_roles"
            )
        
        st.markdown("---")
        st.markdown("### Role Coverage Requirements")
        st.caption("Specify how many employees needed per role per shift")
        
        role_coverage = {}
        if roles and active_shifts:
            for role in roles:
                st.markdown(f"**{role}**")
                role_coverage[role] = {}
                cols = st.columns(len(active_shifts))
                for idx, shift in enumerate(active_shifts):
                    with cols[idx]:
                        default_val = template.role_coverage.get(role, {}).get(shift, 1) if template.role_coverage else 1
                        count = st.number_input(
                            shift,
                            min_value=0,
                            max_value=10,
                            value=default_val,
                            key=f"coverage_{role}_{shift}"
                        )
                        role_coverage[role][shift] = count
        
        # Submit buttons
        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            submit = st.form_submit_button("💾 Save Template", use_container_width=True)
        with col2:
            cancel = st.form_submit_button("❌ Cancel", use_container_width=True)
        
        if submit:
            if not name:
                st.error("Please provide a template name")
            elif not active_shifts:
                st.error("Please select at least one shift")
            elif not roles:
                st.error("Please select at least one role")
            else:
                template.name = name
                template.description = description
                template.business_model = business_model
                template.pattern_type = pattern_type
                template.active_shifts = active_shifts
                template.roles = roles
                template.role_coverage = role_coverage
                template.created_by = st.session_state.get('username', 'admin')
                
                try:
                    template_id = save_template(template)
                    st.success(f"✅ Template '{name}' saved successfully!")
                    st.session_state.pop('template_action', None)
                    st.session_state.pop('template_id', None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving template: {e}")
        
        if cancel:
            st.session_state.pop('template_action', None)
            st.session_state.pop('template_id', None)
            st.rerun()


def _apply_template():
    """Apply template to generate schedule"""
    st.subheader("Apply Template to Schedule")
    
    template_id = st.session_state.get('template_id')
    
    # Template selection
    templates = list_templates(active_only=True)
    
    if not templates:
        st.info("No active templates available. Create a template first!")
        return
    
    template_options = {f"{t.name} ({t.pattern_type})": t.id for t in templates}
    
    selected_template_name = st.selectbox(
        "Select Template",
        list(template_options.keys()),
        index=0 if not template_id else list(template_options.values()).index(template_id) if template_id in template_options.values() else 0,
        key="apply_template_select"
    )
    
    selected_template_id = template_options[selected_template_name]
    template = load_template(selected_template_id)
    
    if not template:
        st.error("Could not load template")
        return
    
    # Show template details
    with st.expander("📋 Template Details", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Business Model", template.business_model)
        with col2:
            st.metric("Pattern Type", template.pattern_type)
        with col3:
            st.metric("Roles", len(template.roles))
        
        st.markdown(f"**Shifts:** {', '.join(template.active_shifts)}")
        st.markdown(f"**Description:** {template.description or 'No description'}")
    
    # Application settings
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=date.today() + timedelta(days=1),
            key="apply_template_start_date"
        )
    
    with col2:
        days_count = st.number_input(
            "Number of Days",
            min_value=1,
            max_value=31,
            value=7 if template.pattern_type == "weekly" else 14 if template.pattern_type == "biweekly" else 30,
            key="apply_template_days"
        )
    
    # Preview
    if st.button("👁️ Preview Schedule Structure", key="preview_template"):
        with st.spinner("Generating preview..."):
            try:
                # Get employees for context
                from shift_plus_core import get_conn
                conn = get_conn()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM employees LIMIT 10")
                employees = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
                conn.close()
                
                # Apply template
                schedule_data = apply_template_to_schedule(template, start_date, employees, days_count)
                
                st.success(f"✅ Preview generated: {len(schedule_data['assignments'])} shift slots")
                
                # Show summary
                st.markdown("### Schedule Preview")
                
                # Group by date
                assignments_by_date = {}
                for assignment in schedule_data['assignments']:
                    date_key = assignment['date']
                    if date_key not in assignments_by_date:
                        assignments_by_date[date_key] = []
                    assignments_by_date[date_key].append(assignment)
                
                # Display in table
                preview_data = []
                for date_key, assignments in sorted(assignments_by_date.items()):
                    shifts_summary = {}
                    for assign in assignments:
                        shift = assign['shift']
                        if shift not in shifts_summary:
                            shifts_summary[shift] = 0
                        shifts_summary[shift] += 1
                    
                    preview_data.append({
                        'Date': date_key,
                        'Day': assignments[0]['day'],
                        **{f"{shift.title()} Shift": count for shift, count in shifts_summary.items()}
                    })
                
                if preview_data:
                    df = pd.DataFrame(preview_data)
                    st.dataframe(df, use_container_width=True)
                
                st.info("💡 This shows the structure. Actual schedule generation will assign specific employees.")
                
            except Exception as e:
                st.error(f"Error generating preview: {e}")
    
    # Apply button
    if st.button("✨ Apply Template & Generate Schedule", type="primary", key="apply_template_generate"):
        st.info("🚧 Integration with schedule generation is coming soon!")
        st.markdown("""
        To use this template:
        1. Go to the **Schedule** page
        2. Use the template's coverage requirements as a guide
        3. Or we'll integrate automatic template application in the next update
        """)


def page_create_template_from_schedule():
    """Create template from existing schedule"""
    st.subheader("Create Template from Existing Schedule")
    st.info("🚧 This feature will analyze your existing schedules and create reusable templates")
    
    # Future implementation:
    # - Select existing schedule
    # - Analyze patterns
    # - Extract role coverage
    # - Save as template
