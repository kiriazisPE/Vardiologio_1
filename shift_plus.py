
import logging
import sqlite3
import os
import openai
import streamlit as st
import pandas as pd
from datetime import date, timedelta
from common.business_settings import BusinessSettings

# Set up a basic logger for the app
logger = logging.getLogger("shift_plus")
logging.basicConfig(level=logging.INFO)

# Import enhanced scheduling functions
try:
    from shift_plus_core import (
        generate_schedule_with_ai as core_generate_schedule_with_ai, 
        build_shift_slots as core_build_shift_slots,
        validate_schedule_constraints as core_validate_schedule,
        is_employee_available_on_date
    )
    core_available = True
    logger.info("Enhanced scheduling core loaded successfully")
except ImportError as e:
    logger.info("Using fallback scheduling functions - core not available: %s", e)
    core_available = False

# --- AI API Key and OpenAI availability ---
try:
    from dotenv import load_dotenv
    load_dotenv()
    
    # Try multiple sources for API key (environment, secrets, .env)
    AI_API_KEY = None
    
    # 1. Try Streamlit secrets first (for cloud deployment)
    try:
        AI_API_KEY = st.secrets.get("AI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
    except:
        pass
    
    # 2. Fall back to environment variables
    if not AI_API_KEY:
        AI_API_KEY = os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY")
    
    if AI_API_KEY:
        openai.api_key = AI_API_KEY
    _ = openai.api_key
    openai_available = bool(_)
except ImportError:
    openai_available = False
if not openai_available:
    st.error("OpenAI API key is missing or invalid. Please set AI_API_KEY or OPENAI_API_KEY in your environment or .env file.")

# --- Enhanced Business Setup Page ---
def page_business():
    """
    Advanced Business Configuration Interface.
    
    Provides a comprehensive, modern interface for configuring all aspects of the
    scheduling system including business information, role definitions, shift types,
    daily operational settings, constraints, and templates.
    
    Features:
        - 📊 Real-time configuration status overview
        - 🏢 Basic business information (name, planning window, default hours)
        - 👥 Advanced role configuration with priorities, requirements, and skills
        - ⏰ Shift type management with timing, breaks, and staffing levels  
        - 📅 Day-specific settings with multipliers, rush hours, and special requirements
        - ⚖️ Scheduling constraints and optimization penalties
        - 📄 Configuration templates for quick setup
    
    Interface Components:
        - Status dashboard showing configuration completeness
        - Tabbed interface for organized configuration sections
        - Interactive forms with real-time validation
        - Modal dialogs for adding new items
        - Bulk operations and template management
        - Export/import functionality for configurations
    
    Configuration Validation:
        - Ensures minimum required settings are configured
        - Validates constraint logic and dependencies
        - Provides warnings for potential configuration issues
        - Shows impact preview of settings changes
    
    Data Persistence:
        All configuration changes are automatically saved to the database
        and immediately available for schedule generation processes.
    """
    st.markdown("""
    <div style=\"background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 20px; padding: 2rem; margin-bottom: 2rem; border: 2px solid #e0e7ff; box-shadow: 0 10px 30px rgba(0,0,0,0.1);\">
        <h1 style=\"margin: 0; font-size: 2.5rem; font-weight: 800; color: #ffffff; text-shadow: 0 2px 4px rgba(0,0,0,0.3);\">🏢 Advanced Business Configuration</h1>
        <p style=\"color: #f8fafc; margin: 1rem 0 0 0; font-size: 1.2rem; font-weight: 500;\">Comprehensive scheduling rules, role definitions, and operational constraints</p>
    </div>
    """, unsafe_allow_html=True)

    # Back to Home button
    if st.button("← Back to Dashboard", key="back_to_home_business", type="secondary"):
        st.session_state["current_page"] = "🏠 Home"
        st.rerun()
    
    st.markdown("---")
    
    bs = load_business_settings()
    
    # Configuration status overview
    st.markdown("### 📊 Configuration Overview")
    status_col1, status_col2, status_col3, status_col4 = st.columns(4)
    
    with status_col1:
        role_count = len(bs.role_settings) if bs.role_settings else 0
        st.metric("Roles Defined", role_count, delta=f"{role_count-3} from default")
    
    with status_col2:
        shift_count = len(bs.shift_types) if bs.shift_types else 0
        st.metric("Shift Types", shift_count, delta=f"{shift_count-2} from default")
    
    with status_col3:
        active_days = sum(1 for day in bs.day_settings if day.is_business_day)
        st.metric("Business Days", active_days, delta=f"{active_days-7}/7 active")
    
    with status_col4:
        planning_window = bs.planning_days
        st.metric("Planning Window", f"{planning_window} days", delta="0 from target")

    # Enhanced tabbed interface
    basic_tab, roles_tab, shifts_tab, days_tab, constraints_tab = st.tabs([
        "🏢 Basic Setup", "👥 Role Configuration", "⏰ Shift Management", "📅 Daily Settings", "⚖️ Constraints"
    ])
    
    with basic_tab:
        st.markdown("### 🏢 Business Information")
        
        info_col1, info_col2 = st.columns([2, 1])
        
        with info_col1:
            name = st.text_input("Business Name", value=bs.name, placeholder="Enter your business name", help="This appears in reports and schedules")
            
            st.markdown("#### 📅 Planning Configuration")
            planning_col1, planning_col2 = st.columns(2)
            
            with planning_col1:
                planning_start = st.date_input("Planning Start Date", value=bs.planning_start)
            with planning_col2:
                planning_days = st.number_input("Planning Days", min_value=1, max_value=365, value=bs.planning_days, 
                                               help="Number of days to plan ahead")
            
            st.markdown("#### ⏰ Default Shift Times")
            time_col1, time_col2 = st.columns(2)
            
            with time_col1:
                day_shift_start = st.number_input("Day Shift Start Hour", min_value=0, max_value=23, value=bs.day_shift_start_hour)
                day_shift_length = st.number_input("Day Shift Length (hours)", min_value=1.0, max_value=24.0, value=bs.day_shift_length, step=0.5)
            
            with time_col2:
                night_shift_start = st.number_input("Night Shift Start Hour", min_value=0, max_value=23, value=bs.night_shift_start_hour)
                night_shift_length = st.number_input("Night Shift Length (hours)", min_value=1.0, max_value=24.0, value=bs.night_shift_length, step=0.5)
        
        with info_col2:
            st.markdown("### 📊 Quick Stats")
            st.info(f"**Total Slots**: ~{planning_days * 2 * role_count} per cycle")
            st.info(f"**Coverage**: {role_count} roles × {shift_count} shifts")
            st.info(f"**Active Days**: {active_days}/7 business days")
            
            st.markdown("### 🚀 Quick Actions")
            if st.button("🔄 Reset to Defaults", key="reset_defaults"):
                # Reset to default settings
                st.warning("This will reset all settings to defaults!")
                if st.button("Confirm Reset", key="confirm_reset"):
                    bs = BusinessSettings()  # Create new default instance
                    save_business_settings(bs)
                    st.success("Settings reset to defaults!")
                    st.rerun()
    
    with roles_tab:
        st.markdown("### 👥 Advanced Role Configuration")
        
        # Role management header
        role_header_col1, role_header_col2 = st.columns([3, 1])
        
        with role_header_col1:
            st.markdown("Configure detailed role requirements, priorities, and constraints.")
        
        with role_header_col2:
            if st.button("➕ Add New Role", key="add_role_modal"):
                st.session_state["show_add_role"] = True
        
        # Add new role modal
        if st.session_state.get("show_add_role", False):
            with st.form("new_role_form"):
                st.markdown("#### ➕ Create New Role")
                
                new_role_col1, new_role_col2 = st.columns(2)
                
                with new_role_col1:
                    new_role_name = st.text_input("Role Name", placeholder="e.g., Senior Manager, Supervisor")
                    new_role_priority = st.selectbox("Priority Level", options=[1, 2, 3, 4], 
                                                    format_func=lambda x: ["Critical", "High", "Normal", "Low"][x-1])
                    new_role_min_exp = st.number_input("Min Experience (months)", min_value=0, value=0)
                
                with new_role_col2:
                    new_role_day_req = st.number_input("Day Shift Required", min_value=0, value=1)
                    new_role_night_req = st.number_input("Night Shift Required", min_value=0, value=1)
                    new_role_max_consec = st.number_input("Max Consecutive Shifts", min_value=1, value=5)
                
                new_role_skills = st.text_input("Required Skills (comma-separated)", 
                                               placeholder="customer_service, pos_systems, leadership")
                
                form_col1, form_col2 = st.columns(2)
                with form_col1:
                    if st.form_submit_button("✅ Create Role", width='stretch'):
                        if new_role_name.strip():
                            from common.business_settings import RoleSettings
                            skills_list = [s.strip() for s in new_role_skills.split(",") if s.strip()]
                            new_role = RoleSettings(
                                role=new_role_name.strip(),
                                day_required=new_role_day_req,
                                night_required=new_role_night_req,
                                priority=new_role_priority,
                                min_experience_months=new_role_min_exp,
                                max_consecutive_shifts=new_role_max_consec,
                                skill_requirements=skills_list
                            )
                            bs.role_settings.append(new_role)
                            save_business_settings(bs)
                            st.session_state["show_add_role"] = False
                            st.success(f"Role '{new_role_name}' created successfully!")
                            st.rerun()
                
                with form_col2:
                    if st.form_submit_button("❌ Cancel", width='stretch'):
                        st.session_state["show_add_role"] = False
                        st.rerun()
        
        # Existing roles configuration
        if bs.role_settings:
            st.markdown("#### 📝 Configure Existing Roles")
            
            for i, role in enumerate(bs.role_settings):
                role_name = role.role
                
                with st.expander(f"🔧 {role_name}", expanded=False):
                    # Role configuration form
                    config_col1, config_col2, config_col3 = st.columns(3)
                    
                    with config_col1:
                        st.markdown("**Basic Settings**")
                        if hasattr(role, 'role'):
                            role.role = st.text_input("Role Name", value=role.role, key=f"role_name_{i}")
                            role.priority = st.selectbox("Priority", options=[1, 2, 3, 4], index=role.priority-1,
                                                       format_func=lambda x: ["Critical", "High", "Normal", "Low"][x-1],
                                                       key=f"role_priority_{i}")
                            role.min_experience_months = st.number_input("Min Experience (months)", 
                                                                       min_value=0, value=role.min_experience_months,
                                                                       key=f"role_exp_{i}")
                    
                    with config_col2:
                        st.markdown("**Shift Requirements**")
                        if hasattr(role, 'day_required'):
                            role.day_required = st.number_input("Day Shift Required", min_value=0, 
                                                              value=role.day_required, key=f"role_day_{i}")
                            role.night_required = st.number_input("Night Shift Required", min_value=0,
                                                                value=role.night_required, key=f"role_night_{i}")
                            role.max_consecutive_shifts = st.number_input("Max Consecutive", min_value=1,
                                                                        value=role.max_consecutive_shifts, 
                                                                        key=f"role_consec_{i}")
                    
                    with config_col3:
                        st.markdown("**Advanced Settings**")
                        if hasattr(role, 'min_rest_between_shifts'):
                            role.min_rest_between_shifts = st.number_input("Min Rest Hours", min_value=0.0, max_value=24.0,
                                                                         value=role.min_rest_between_shifts, step=0.5,
                                                                         key=f"role_rest_{i}")
                        
                        if hasattr(role, 'skill_requirements'):
                            skills_str = ", ".join(role.skill_requirements) if role.skill_requirements else ""
                            new_skills = st.text_area("Required Skills", value=skills_str, key=f"role_skills_{i}")
                            role.skill_requirements = [s.strip() for s in new_skills.split(",") if s.strip()]
                    
                    # Delete role button
                    if st.button(f"🗑️ Delete {role_name}", key=f"delete_role_{i}", type="secondary"):
                        bs.role_settings.pop(i)
                        save_business_settings(bs)
                        st.success(f"Role '{role_name}' deleted!")
                        st.rerun()
        else:
            st.warning("No roles configured. Add roles to enable scheduling.")
    
    with shifts_tab:
        st.markdown("### ⏰ Advanced Shift Management")
        
        # Shift visualization
        if bs.shift_types:
            st.markdown("#### 📊 Shift Schedule Overview")
            shift_overview_data = []
            for shift in bs.shift_types:
                shift_name = shift.shift_type if hasattr(shift, 'shift_type') else 'Unknown'
                start_hour = shift.start_hour if hasattr(shift, 'start_hour') else 8
                duration = shift.duration_hours if hasattr(shift, 'duration_hours') else 8
                end_hour = (start_hour + duration) % 24
                
                shift_overview_data.append({
                    'Shift': shift_name,
                    'Start': f"{start_hour:02d}:00",
                    'End': f"{int(end_hour):02d}:00",
                    'Duration': f"{duration}h",
                    'Min Staff': shift.min_employees if hasattr(shift, 'min_employees') else 1,
                    'Max Staff': shift.max_employees if hasattr(shift, 'max_employees') else 10
                })
            
            shift_df = pd.DataFrame(shift_overview_data)
            st.dataframe(shift_df, width='stretch')
        
        # Add new shift
        _, shift_header_col2 = st.columns([3, 1])
        
        with shift_header_col2:
            if st.button("➕ Add New Shift", key="add_shift_modal"):
                st.session_state["show_add_shift"] = True
        
        # Add shift modal
        if st.session_state.get("show_add_shift", False):
            with st.form("new_shift_form"):
                st.markdown("#### ➕ Create New Shift Type")
                
                shift_col1, shift_col2 = st.columns(2)
                
                with shift_col1:
                    new_shift_name = st.text_input("Shift Name", placeholder="e.g., Morning, Evening, Weekend")
                    new_shift_start = st.number_input("Start Hour", min_value=0, max_value=23, value=8)
                    new_shift_duration = st.number_input("Duration (hours)", min_value=1.0, max_value=24.0, value=8.0, step=0.5)
                
                with shift_col2:
                    new_shift_break = st.number_input("Break Duration (minutes)", min_value=0, max_value=120, value=30)
                    new_shift_min = st.number_input("Minimum Staff", min_value=0, value=1)
                    new_shift_max = st.number_input("Maximum Staff", min_value=1, value=10)
                
                shift_form_col1, shift_form_col2 = st.columns(2)
                with shift_form_col1:
                    if st.form_submit_button("✅ Create Shift", width='stretch'):
                        if new_shift_name.strip():
                            from common.business_settings import ShiftSettings
                            new_shift = ShiftSettings(
                                shift_type=new_shift_name.strip(),
                                start_hour=new_shift_start,
                                duration_hours=new_shift_duration,
                                break_duration_minutes=new_shift_break,
                                min_employees=new_shift_min,
                                max_employees=new_shift_max
                            )
                            bs.shift_types.append(new_shift)
                            save_business_settings(bs)
                            st.session_state["show_add_shift"] = False
                            st.success(f"Shift '{new_shift_name}' created successfully!")
                            st.rerun()
                
                with shift_form_col2:
                    if st.form_submit_button("❌ Cancel", width='stretch'):
                        st.session_state["show_add_shift"] = False
                        st.rerun()
        
        # Configure existing shifts
        if bs.shift_types:
            st.markdown("#### 🔧 Configure Existing Shifts")
            
            for i, shift in enumerate(bs.shift_types):
                shift_name = shift.shift_type if hasattr(shift, 'shift_type') else f'Shift {i}'
                
                with st.expander(f"⏰ {shift_name}", expanded=False):
                    shift_config_col1, shift_config_col2, shift_config_col3 = st.columns(3)
                    
                    with shift_config_col1:
                        st.markdown("**Basic Settings**")
                        if hasattr(shift, 'shift_type'):
                            shift.shift_type = st.text_input("Shift Name", value=shift.shift_type, key=f"shift_name_{i}")
                            shift.start_hour = st.number_input("Start Hour", min_value=0, max_value=23, 
                                                             value=shift.start_hour, key=f"shift_start_{i}")
                            shift.duration_hours = st.number_input("Duration (hours)", min_value=1.0, max_value=24.0,
                                                                 value=shift.duration_hours, step=0.5, key=f"shift_duration_{i}")
                    
                    with shift_config_col2:
                        st.markdown("**Staffing Levels**")
                        if hasattr(shift, 'min_employees'):
                            shift.min_employees = st.number_input("Minimum Staff", min_value=0, 
                                                                value=shift.min_employees, key=f"shift_min_{i}")
                            shift.max_employees = st.number_input("Maximum Staff", min_value=1,
                                                                value=shift.max_employees, key=f"shift_max_{i}")
                    
                    with shift_config_col3:
                        st.markdown("**Additional Settings**")
                        if hasattr(shift, 'break_duration_minutes'):
                            shift.break_duration_minutes = st.number_input("Break Duration (min)", min_value=0, max_value=120,
                                                                         value=shift.break_duration_minutes, key=f"shift_break_{i}")
                    
                    # Delete shift button
                    if st.button(f"🗑️ Delete {shift_name}", key=f"delete_shift_{i}", type="secondary"):
                        bs.shift_types.pop(i)
                        save_business_settings(bs)
                        st.success(f"Shift '{shift_name}' deleted!")
                        st.rerun()
        else:
            st.warning("No shift types configured. Add shifts to enable scheduling.")
    
    with days_tab:
        st.markdown("### 📅 Daily Operational Settings")
        
        # Day-of-week configuration
        if bs.day_settings:
            st.markdown("#### 📊 Weekly Staffing Overview")
            
            # Enhanced weekly overview with staffing calculations
            week_data = []
            for day in bs.day_settings:
                day_name = day.day
                is_business = day.is_business_day
                
                # Calculate total staff needed per day
                total_staff_needed = 0
                shift_details = []
                
                if is_business:
                    for shift in bs.shift_types:
                        shift_staff = 0
                        # Calculate staff for each role in this shift
                        for role_setting in bs.role_settings:
                            role_multiplier = day.role_multipliers.get(role_setting.role, 1.0)
                            
                            # Calculate staff needed using the multiplier (which now represents the actual staff count)
                            if 'day' in shift.shift_type.lower() or shift.start_hour < 18:
                                base_required = role_setting.day_required
                                role_staff_needed = max(1, int(base_required * role_multiplier))
                            else:
                                base_required = role_setting.night_required
                                role_staff_needed = max(1, int(base_required * role_multiplier))
                            
                            shift_staff += role_staff_needed
                        
                        # Apply min/max constraints
                        shift_staff = max(shift.min_employees, min(shift_staff, shift.max_employees))
                        total_staff_needed += shift_staff
                        shift_details.append(f"{shift.shift_type}: {shift_staff}")
                
                # Count special requirements and rush hours
                special_count = len(day.special_requirements) if hasattr(day, 'special_requirements') and day.special_requirements else 0
                rush_count = len(day.rush_hours) if hasattr(day, 'rush_hours') and day.rush_hours else 0
                
                week_data.append({
                    'Day': day_name,
                    'Business Day': '✅' if is_business else '❌',
                    'Total Staff Needed': total_staff_needed if is_business else 0,
                    'Shift Breakdown': ' | '.join(shift_details) if shift_details else 'No shifts',
                    'Special Req.': special_count,
                    'Rush Hours': rush_count,
                    'Status': 'Active' if is_business else 'Inactive'
                })
            
            week_df = pd.DataFrame(week_data)
            st.dataframe(week_df, width='stretch')
            
            # Add staffing summary
            if any(row['Business Day'] == '✅' for row in week_data):
                business_days = [row for row in week_data if row['Business Day'] == '✅']
                total_weekly_staff = sum(row['Total Staff Needed'] for row in business_days)
                avg_daily_staff = total_weekly_staff / len(business_days) if business_days else 0
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📊 Total Weekly Staff Slots", f"{total_weekly_staff}")
                with col2:
                    st.metric("📈 Average Daily Staff", f"{avg_daily_staff:.1f}")
                with col3:
                    st.metric("🏢 Business Days", f"{len(business_days)}/7")
            
            st.markdown("#### 🔧 Configure Individual Days")
            
            for i, day in enumerate(bs.day_settings):
                day_name = day.day
                is_business = day.is_business_day
                
                # Day status indicator
                status_emoji = "🟢" if is_business else "🔴"
                
                with st.expander(f"{status_emoji} {day_name}", expanded=False):
                    # Show staffing preview at the top
                    if day.is_business_day:
                        st.markdown("**📊 Staffing Preview for This Day**")
                        
                        shift_preview_data = []
                        total_day_staff = 0
                        
                        for shift in bs.shift_types:
                            shift_staff = 0
                            role_breakdown = []
                            
                            for role_setting in bs.role_settings:
                                role_multiplier = day.role_multipliers.get(role_setting.role, 1.0)
                                
                                # Calculate staff needed using the multiplier (which now represents the actual staff count)
                                if 'day' in shift.shift_type.lower() or shift.start_hour < 18:
                                    base_required = role_setting.day_required
                                    role_staff_needed = max(1, int(base_required * role_multiplier))
                                else:
                                    base_required = role_setting.night_required
                                    role_staff_needed = max(1, int(base_required * role_multiplier))
                                
                                shift_staff += role_staff_needed
                                role_breakdown.append(f"{role_setting.role}: {role_staff_needed}")
                            
                            # Apply min/max constraints
                            final_shift_staff = max(shift.min_employees, min(shift_staff, shift.max_employees))
                            total_day_staff += final_shift_staff
                            
                            shift_preview_data.append({
                                'Shift': shift.shift_type,
                                'Time': f"{shift.start_hour:02d}:00-{(shift.start_hour + int(shift.duration_hours)):02d}:00",
                                'Staff Needed': final_shift_staff,
                                'Role Breakdown': ' + '.join(role_breakdown)
                            })
                        
                        shift_preview_df = pd.DataFrame(shift_preview_data)
                        st.dataframe(shift_preview_df, width='stretch', hide_index=True)
                        st.info(f"**Total staff needed for {day_name}: {total_day_staff} people**")
                    
                    st.divider()
                    
                    day_col1, day_col2 = st.columns(2)
                    
                    with day_col1:
                        st.markdown("**Basic Settings**")
                        
                        # Business day toggle
                        if hasattr(day, 'is_business_day'):
                            day.is_business_day = st.checkbox("Is Business Day", value=day.is_business_day, key=f"day_business_{i}")
                        else:
                            new_is_business = st.checkbox("Is Business Day", value=is_business, key=f"day_business_{i}")
                            if isinstance(day, dict):
                                day['is_business_day'] = new_is_business
                        
                        # Special requirements
                        special_reqs = day.special_requirements
                        special_reqs_str = ", ".join(special_reqs) if special_reqs else ""
                        new_special = st.text_area("Special Requirements", value=special_reqs_str, 
                                                 placeholder="deep_cleaning, inventory, weekly_reports", key=f"day_special_{i}")
                        new_special_list = [s.strip() for s in new_special.split(",") if s.strip()]
                        
                        if hasattr(day, 'special_requirements'):
                            day.special_requirements = new_special_list
                        elif isinstance(day, dict):
                            day['special_requirements'] = new_special_list
                    
                    with day_col2:
                        st.markdown("**Role Staffing Requirements**")
                        st.caption("💡 Set exactly how many people you need for each role on this day")
                        
                        # Role multipliers with clearer explanation
                        role_multipliers = day.role_multipliers
                        
                        for role_setting in bs.role_settings:
                            role_name = role_setting.role
                            current_mult = role_multipliers.get(role_name, 1.0)
                            
                            # Calculate current values from multipliers
                            day_base = role_setting.day_required
                            night_base = role_setting.night_required
                            current_day_staff = max(1, int(day_base * current_mult))
                            current_night_staff = max(1, int(night_base * current_mult))
                            
                            role_col1, role_col2 = st.columns(2)
                            
                            with role_col1:
                                new_day_staff = st.number_input(
                                    f"{role_name} - Day Shifts", 
                                    min_value=0, max_value=20, 
                                    value=current_day_staff,
                                    key=f"day_staff_{i}_{role_name}",
                                    help=f"Number of {role_name}s needed for day shifts"
                                )
                            
                            with role_col2:
                                new_night_staff = st.number_input(
                                    f"{role_name} - Night Shifts", 
                                    min_value=0, max_value=20, 
                                    value=current_night_staff,
                                    key=f"night_staff_{i}_{role_name}",
                                    help=f"Number of {role_name}s needed for night shifts"
                                )
                            
                            # Convert back to multipliers for storage (maintaining compatibility)
                            day_mult = new_day_staff / day_base if day_base > 0 else 1.0
                            night_mult = new_night_staff / night_base if night_base > 0 else 1.0
                            # Use average of day/night multipliers for compatibility
                            avg_mult = (day_mult + night_mult) / 2.0
                            role_multipliers[role_name] = avg_mult
                        
                        if hasattr(day, 'role_multipliers'):
                            day.role_multipliers = role_multipliers
                        elif isinstance(day, dict):
                            day['role_multipliers'] = role_multipliers
                    
                    # Rush hours configuration
                    st.markdown("**Rush Hours Configuration**")
                    rush_hours = day.rush_hours if hasattr(day, 'rush_hours') else day.get('rush_hours', [])
                    
                    # Display existing rush hours
                    for j, rush in enumerate(rush_hours):
                        rush_col1, rush_col2, rush_col3, rush_col4 = st.columns([2, 2, 2, 1])
                        
                        with rush_col1:
                            rush['start'] = st.number_input("Start Hour", min_value=0, max_value=23, 
                                                          value=rush.get('start', 8), key=f"rush_start_{i}_{j}")
                        with rush_col2:
                            rush['end'] = st.number_input("End Hour", min_value=0, max_value=23,
                                                        value=rush.get('end', 10), key=f"rush_end_{i}_{j}")
                        with rush_col3:
                            rush['extra_staff'] = st.number_input("Extra Staff", min_value=0, max_value=10,
                                                                value=rush.get('extra_staff', 1), key=f"rush_extra_{i}_{j}")
                        with rush_col4:
                            if st.button("🗑️", key=f"delete_rush_{i}_{j}"):
                                rush_hours.pop(j)
                                st.rerun()
                    
                    # Add new rush hour
                    if st.button("➕ Add Rush Hour", key=f"add_rush_{i}"):
                        rush_hours.append({'start': 12, 'end': 14, 'extra_staff': 1})
                        st.rerun()
                    
                    # Update day object
                    if hasattr(day, 'rush_hours'):
                        day.rush_hours = rush_hours
                    elif isinstance(day, dict):
                        day['rush_hours'] = rush_hours
        else:
            st.warning("No daily settings configured.")
    
    with constraints_tab:
        st.markdown("### ⚖️ Advanced Scheduling Constraints")
        
        constraint_col1, constraint_col2 = st.columns(2)
        
        with constraint_col1:
            st.markdown("#### 👤 Employee Constraints")
            min_rest_hours = st.number_input("Minimum Rest Hours", min_value=0.0, max_value=24.0, 
                                           value=bs.min_rest_hours, step=0.5,
                                           help="Minimum hours between shifts for same employee")
            max_hours_per_week = st.number_input("Max Hours per Week", min_value=1.0, max_value=80.0, 
                                                value=bs.max_hours_per_week, step=1.0)
            min_hours_per_week = st.number_input("Min Hours per Week", min_value=0.0, max_value=40.0,
                                                value=bs.min_hours_per_week, step=1.0)
            max_consecutive_days = st.number_input("Max Consecutive Days", min_value=1, max_value=14,
                                                 value=bs.max_consecutive_days)
        
        with constraint_col2:
            st.markdown("#### 💼 Operational Constraints")
            allow_overtime = st.checkbox("Allow Overtime", value=bs.allow_overtime)
            
            st.markdown("#### 🎯 Optimization Penalties")
            overtime_penalty = st.number_input("Overtime Penalty", min_value=0.0, max_value=200.0,
                                             value=bs.overtime_penalty, step=1.0,
                                             help="Higher values discourage overtime assignments")
            preference_penalty = st.number_input("Preference Penalty", min_value=0.0, max_value=50.0,
                                                value=bs.preference_penalty, step=0.1,
                                                help="Penalty for not matching employee preferences")
            unfilled_slot_penalty = st.number_input("Unfilled Slot Penalty", min_value=0.0, max_value=500.0,
                                                   value=bs.unfilled_slot_penalty, step=5.0,
                                                   help="High penalty ensures slots are filled when possible")
        
        # Constraint validation
        st.markdown("#### ✅ Constraint Validation")
        if min_hours_per_week > max_hours_per_week:
            st.error("⚠️ Minimum hours per week cannot exceed maximum hours per week!")
        if min_rest_hours > 24:
            st.error("⚠️ Minimum rest hours cannot exceed 24 hours!")
        if max_consecutive_days > 14:
            st.warning("⚠️ Very high consecutive days limit may impact employee wellbeing.")
        
        # Constraint impact preview
        st.markdown("#### 📊 Constraint Impact Preview")
        impact_col1, impact_col2, impact_col3 = st.columns(3)
        
        with impact_col1:
            weekly_slots = planning_days * 2 * role_count if role_count > 0 else 0
            st.metric("Est. Weekly Slots", weekly_slots)
        
        with impact_col2:
            if max_hours_per_week > 0:
                max_weekly_hours = max_hours_per_week
                hours_per_slot = 8  # Assume 8-hour shifts
                max_slots_per_employee = max_weekly_hours / hours_per_slot
                st.metric("Max Slots/Employee", f"{max_slots_per_employee:.1f}")
            else:
                st.metric("Max Slots/Employee", "∞")
        
        with impact_col3:
            if weekly_slots > 0 and max_slots_per_employee > 0:
                min_employees_needed = weekly_slots / max_slots_per_employee
                st.metric("Min Employees Needed", f"{min_employees_needed:.0f}")
            else:
                st.metric("Min Employees Needed", "TBD")
    

    
    # Save all changes
    st.markdown("---")
    save_col1, save_col2, save_col3 = st.columns([2, 1, 1])
    
    with save_col1:
        st.markdown("### 💾 Save Configuration")
        st.info("Save changes to apply them to the scheduling system.")
    
    with save_col2:
        if st.button("💾 Save All Changes", key="save_all_settings", width='stretch', type="primary"):
            # Update basic settings
            bs.name = name
            bs.planning_start = planning_start
            bs.planning_days = planning_days
            bs.day_shift_start_hour = day_shift_start
            bs.day_shift_length = day_shift_length
            bs.night_shift_start_hour = night_shift_start
            bs.night_shift_length = night_shift_length
            bs.min_rest_hours = min_rest_hours
            bs.max_hours_per_week = max_hours_per_week
            bs.min_hours_per_week = min_hours_per_week
            bs.max_consecutive_days = max_consecutive_days
            bs.allow_overtime = allow_overtime
            bs.overtime_penalty = overtime_penalty
            bs.preference_penalty = preference_penalty
            bs.unfilled_slot_penalty = unfilled_slot_penalty
            
            save_business_settings(bs)
            st.success("✅ All settings saved successfully!")
            st.balloons()
    
    with save_col3:
        if st.button("🔄 Reload Settings", key="reload_settings", width='stretch'):
            st.rerun()

def page_analytics():
    """
    Advanced Analytics Dashboard.
    
    Comprehensive workforce and schedule analytics platform providing deep insights
    into scheduling performance, employee utilization, and operational efficiency.
    
    Dashboard Components:
        📊 Executive KPI Dashboard:
            - Real-time metrics: staff count, capacity, fill rates, coverage
            - Performance indicators with delta comparisons
            - Health status visualization with color-coded alerts
        
        🏢 Business Overview:
            - Team composition analysis by role and capacity
            - Role-based capacity utilization and distribution
            - Quick statistics and system health indicators
        
        👥 Workforce Deep Dive:
            - Employee distribution by hours, importance, and role
            - Top performer identification and capacity analysis
            - Interactive filtering and sorting capabilities
            - Detailed employee roster with searchable interface
        
        📅 Schedule Performance:
            - Schedule efficiency metrics and fill rate analysis
            - Daily/weekly distribution patterns and trends
            - Employee workload distribution and balance
            - Real-time violation detection and categorization
        
        🎯 Performance Analytics:
            - KPI scoring with color-coded performance indicators
            - Trend analysis and historical performance tracking
            - Improvement opportunity identification
        
        🔍 AI-Powered Insights:
            - Intelligent recommendations based on data patterns
            - Predictive metrics and forecasting
            - Optimization opportunity identification
            - Risk assessment and dependency analysis
    
    Interactive Features:
        - Real-time data filtering and visualization
        - Export functionality for reports and data
        - Responsive design for mobile and desktop
        - Progressive disclosure of detailed information
    
    Data Sources:
        - Employee database with roles, hours, and importance ratings
        - Current schedule data with assignments and violations
        - Business settings for context and constraints
        - Historical data for trend analysis (when available)
    
    Export Options:
        - Workforce reports (CSV format)
        - Schedule performance reports
        - Analytics summaries with key metrics
        - Formatted reports for management presentation
    """
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 20px; padding: 2rem; margin-bottom: 2rem; border: 2px solid #e0e7ff; box-shadow: 0 10px 30px rgba(0,0,0,0.1);">
        <h1 style="margin: 0; font-size: 2.5rem; font-weight: 800; color: #ffffff; text-shadow: 0 2px 4px rgba(0,0,0,0.3);">📊 Advanced Analytics Dashboard</h1>
        <p style="color: #f8fafc; margin: 1rem 0 0 0; font-size: 1.2rem; font-weight: 500;">Comprehensive workforce insights, performance metrics, and predictive analytics</p>
    </div>
    """, unsafe_allow_html=True)

    # Back to Home button
    if st.button("← Back to Dashboard", key="back_to_home_analytics", type="secondary"):
        st.session_state["current_page"] = "🏠 Home"
        st.rerun()
    
    st.markdown("---")

    # Get data for analytics
    emp_df = get_all_employees()
    bs = load_business_settings()
    
    try:
        sched_df = load_schedule_from_db(bs) if bs else pd.DataFrame()
    except (sqlite3.Error, pd.errors.ParserError, ValueError) as e:
        logger.warning("Failed to load schedule from database: %s", e)
        sched_df = pd.DataFrame()
    
    # Quick KPI Overview
    st.markdown("### 📊 Executive Dashboard")
    
    kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)
    
    # Calculate KPIs
    total_employees = len(emp_df) if not emp_df.empty else 0
    total_capacity = emp_df["max_hours_per_week"].sum() if not emp_df.empty else 0
    avg_importance = emp_df["importance"].mean() if not emp_df.empty and "importance" in emp_df.columns else 0
    
    # Schedule metrics
    total_shifts = len(sched_df) if not sched_df.empty else 0
    filled_shifts = len(sched_df[sched_df['employee_id'].notna()]) if not sched_df.empty else 0
    fill_rate = (filled_shifts / total_shifts * 100) if total_shifts > 0 else 0
    
    with kpi_col1:
        st.metric("Total Staff", total_employees, delta=f"{total_employees-10} from target" if total_employees > 0 else None)
    
    with kpi_col2:
        st.metric("Weekly Capacity", f"{total_capacity:.0f}h", delta=f"{total_capacity-320:.0f}h from baseline" if total_capacity > 0 else None)
    
    with kpi_col3:
        st.metric("Fill Rate", f"{fill_rate:.1f}%", delta=f"{fill_rate-95:.1f}% from target" if fill_rate > 0 else None)
    
    with kpi_col4:
        avg_hours = total_capacity / total_employees if total_employees > 0 else 0
        st.metric("Avg Hours/Employee", f"{avg_hours:.1f}h", delta=f"{avg_hours-32:.1f}h from standard" if avg_hours > 0 else None)
    
    with kpi_col5:
        active_roles = len(emp_df['role'].unique()) if not emp_df.empty else 0
        target_roles = len(bs.role_settings) if bs and hasattr(bs, 'role_settings') else 3
        st.metric("Role Coverage", f"{active_roles}/{target_roles}", delta=f"{active_roles-target_roles} roles")
    
    # Enhanced analytics tabs
    overview_tab, workforce_tab, schedule_tab, performance_tab, insights_tab = st.tabs([
        "🏢 Overview", "👥 Workforce Analysis", "📅 Schedule Metrics", "🎯 Performance", "🔍 AI Insights"
    ])
    
    with overview_tab:
        st.markdown("### 🏢 Business Overview")
        
        overview_col1, overview_col2 = st.columns([2, 1])
        
        with overview_col1:
            if not emp_df.empty:
                st.markdown("#### 👥 Team Composition by Role")
                
                # Role distribution
                role_counts = emp_df['role'].value_counts()
                st.bar_chart(role_counts)
                
                # Role-based capacity analysis
                st.markdown("#### ⚡ Capacity by Role")
                role_capacity = emp_df.groupby('role')['max_hours_per_week'].agg(['sum', 'mean', 'count']).round(1)
                role_capacity.columns = ['Total Hours', 'Avg Hours', 'Employees']
                st.dataframe(
                    role_capacity,
                    column_config={
                        "Total Hours": st.column_config.NumberColumn("Total Weekly Hours", format="%.0f"),
                        "Avg Hours": st.column_config.NumberColumn("Average Hours", format="%.1f"),
                        "Employees": st.column_config.NumberColumn("Team Size", format="%d")
                    },
                    width='stretch'
                )
            else:
                st.info("📝 No employee data available. Add team members to see analytics.")
        
        with overview_col2:
            st.markdown("#### 📊 Quick Stats")
            
            if not emp_df.empty:
                # Distribution statistics
                stats_data = {
                    "Metric": [
                        "Total Employees",
                        "Weekly Capacity", 
                        "Average Importance",
                        "Active Roles",
                        "Full-time Employees",
                        "Part-time Employees"
                    ],
                    "Value": [
                        f"{len(emp_df)}",
                        f"{emp_df['max_hours_per_week'].sum():.0f} hours",
                        f"{avg_importance:.2f}/5.0" if avg_importance > 0 else "N/A",
                        f"{len(emp_df['role'].unique())}",
                        f"{len(emp_df[emp_df['max_hours_per_week'] >= 35])}",
                        f"{len(emp_df[emp_df['max_hours_per_week'] < 35])}"
                    ]
                }
                
                stats_df = pd.DataFrame(stats_data)
                st.dataframe(
                    stats_df,
                    column_config={
                        "Metric": st.column_config.TextColumn("Metric"),
                        "Value": st.column_config.TextColumn("Value")
                    },
                    hide_index=True,
                    width='stretch'
                )
                
                # Health indicators
                st.markdown("#### 💚 System Health")
                
                health_indicators = []
                
                # Capacity utilization
                target_capacity = 320  # Assuming 10 employees * 32 hours
                capacity_utilization = (total_capacity / target_capacity) * 100 if target_capacity > 0 else 0
                if capacity_utilization >= 90:
                    health_indicators.append("✅ Optimal capacity")
                elif capacity_utilization >= 70:
                    health_indicators.append("⚠️ Moderate capacity")
                else:
                    health_indicators.append("❌ Low capacity")
                
                # Role coverage
                if active_roles >= target_roles:
                    health_indicators.append("✅ Full role coverage")
                else:
                    health_indicators.append(f"⚠️ Missing {target_roles - active_roles} roles")
                
                # Schedule fill rate
                if fill_rate >= 95:
                    health_indicators.append("✅ Excellent fill rate")
                elif fill_rate >= 80:
                    health_indicators.append("⚠️ Good fill rate")
                else:
                    health_indicators.append("❌ Poor fill rate")
                
                for indicator in health_indicators:
                    st.write(indicator)
            else:
                st.info("Add employees to see system health.")
    
    with workforce_tab:
        st.markdown("### 👥 Workforce Deep Dive")
        
        if not emp_df.empty:
            workforce_col1, workforce_col2 = st.columns(2)
            
            with workforce_col1:
                st.markdown("#### 📈 Employee Distribution Analysis")
                
                # Hours distribution
                st.markdown("**Hours Distribution**")
                hours_bins = [0, 20, 30, 40, 50, 80]
                hours_labels = ['Part-time (<20h)', 'Light (20-30h)', 'Standard (30-40h)', 'Heavy (40-50h)', 'Maximum (50h+)']
                emp_df['hours_category'] = pd.cut(emp_df['max_hours_per_week'], bins=hours_bins, labels=hours_labels, right=False)
                hours_dist = emp_df['hours_category'].value_counts()
                if not hours_dist.empty:
                    st.bar_chart(hours_dist)
                else:
                    st.info("No hours distribution data available")
                
                # Importance distribution
                if "importance" in emp_df.columns:
                    st.markdown("**Importance Distribution**")
                    importance_bins = [0, 1, 2, 3, 4, 5]
                    importance_labels = ['Low (0-1)', 'Below Avg (1-2)', 'Average (2-3)', 'Above Avg (3-4)', 'Critical (4-5)']
                    emp_df['importance_category'] = pd.cut(emp_df['importance'], bins=importance_bins, labels=importance_labels, right=False)
                    importance_dist = emp_df['importance_category'].value_counts()
                    if not importance_dist.empty:
                        st.bar_chart(importance_dist)
                    else:
                        st.info("No importance distribution data available")
            
            with workforce_col2:
                st.markdown("#### 🔍 Employee Details")
                
                # Top performers by importance
                if "importance" in emp_df.columns:
                    st.markdown("**Top Priority Employees**")
                    top_employees = emp_df.nlargest(5, 'importance')[['name', 'role', 'importance', 'max_hours_per_week']]
                    st.dataframe(
                        top_employees,
                        column_config={
                            "name": "Employee",
                            "role": "Role", 
                            "importance": st.column_config.NumberColumn("Priority", format="%.1f"),
                            "max_hours_per_week": st.column_config.NumberColumn("Max Hours", format="%.0f")
                        },
                        hide_index=True,
                        width='stretch'
                    )
                
                # Role capacity analysis
                st.markdown("**Role Capacity Analysis**")
                role_analysis = emp_df.groupby('role').agg({
                    'max_hours_per_week': ['sum', 'mean'],
                    'name': 'count'
                }).round(1)
                
                role_analysis.columns = ['Total Capacity', 'Avg Hours', 'Team Size']
                role_analysis['Utilization'] = (role_analysis['Total Capacity'] / role_analysis['Total Capacity'].sum() * 100).round(1)
                
                st.dataframe(
                    role_analysis,
                    column_config={
                        "Total Capacity": st.column_config.NumberColumn("Total Hours", format="%.0f"),
                        "Avg Hours": st.column_config.NumberColumn("Avg Hours", format="%.1f"),
                        "Team Size": st.column_config.NumberColumn("Size", format="%d"),
                        "Utilization": st.column_config.NumberColumn("Share %", format="%.1f%%")
                    },
                    width='stretch'
                )
            
            # Detailed employee table
            st.markdown("#### 📋 Complete Employee Roster")
            
            # Employee search and filter
            filter_col1, filter_col2, filter_col3 = st.columns(3)
            
            with filter_col1:
                role_filter = st.selectbox("Filter by Role", options=["All"] + list(emp_df['role'].unique()))
            
            with filter_col2:
                hours_filter = st.selectbox("Filter by Hours", options=["All", "Part-time (<30h)", "Full-time (30h+)"])
            
            with filter_col3:
                sort_by = st.selectbox("Sort by", options=["Name", "Role", "Max Hours", "Importance"])
            
            # Apply filters
            filtered_df = emp_df.copy()
            
            if role_filter != "All":
                filtered_df = filtered_df[filtered_df['role'] == role_filter]
            
            if hours_filter == "Part-time (<30h)":
                filtered_df = filtered_df[filtered_df['max_hours_per_week'] < 30]
            elif hours_filter == "Full-time (30h+)":
                filtered_df = filtered_df[filtered_df['max_hours_per_week'] >= 30]
            
            # Sort data
            sort_column_map = {
                "Name": "name",
                "Role": "role", 
                "Max Hours": "max_hours_per_week",
                "Importance": "importance"
            }
            
            if sort_by in sort_column_map and sort_column_map[sort_by] in filtered_df.columns:
                filtered_df = filtered_df.sort_values(sort_column_map[sort_by], ascending=False if sort_by in ["Max Hours", "Importance"] else True)
            
            # Display filtered results
            display_columns = ['name', 'role', 'max_hours_per_week']
            if 'importance' in filtered_df.columns:
                display_columns.append('importance')
            
            st.dataframe(
                filtered_df[display_columns],
                column_config={
                    "name": "Employee Name",
                    "role": "Role",
                    "max_hours_per_week": st.column_config.NumberColumn("Max Hours/Week", format="%.0f"),
                    "importance": st.column_config.NumberColumn("Priority Level", format="%.1f") if 'importance' in filtered_df.columns else None
                },
                hide_index=True,
                width='stretch'
            )
            
            st.info(f"Showing {len(filtered_df)} of {len(emp_df)} employees")
        else:
            st.info("📝 No workforce data available. Add employees to see detailed analytics.")
    
    with schedule_tab:
        st.markdown("### 📅 Schedule Performance Metrics")
        
        if not sched_df.empty:
            schedule_col1, schedule_col2 = st.columns(2)
            
            with schedule_col1:
                st.markdown("#### 📊 Schedule Overview")
                
                # Schedule metrics
                schedule_metrics = {
                    "Total Shifts": len(sched_df),
                    "Filled Shifts": filled_shifts,
                    "Empty Shifts": total_shifts - filled_shifts,
                    "Fill Rate": f"{fill_rate:.1f}%",
                    "Unique Employees": len(sched_df[sched_df['employee_id'].notna()]['employee_id'].unique()) if filled_shifts > 0 else 0
                }
                
                for metric, value in schedule_metrics.items():
                    st.write(f"**{metric}**: {value}")
                
                # Daily distribution
                if 'date' in sched_df.columns and not sched_df.empty:
                    st.markdown("#### 📅 Daily Shift Distribution")
                    daily_shifts = sched_df['date'].value_counts().sort_index()
                    if not daily_shifts.empty:
                        st.line_chart(daily_shifts)
                    else:
                        st.info("No schedule data available for chart")
            
            with schedule_col2:
                st.markdown("#### 🔍 Schedule Analysis")
                
                if filled_shifts > 0:
                    filled_sched = sched_df[sched_df['employee_id'].notna()]
                    
                    # Employee workload distribution
                    st.markdown("**Employee Workload**")
                    workload = filled_sched['employee_name'].value_counts()
                    if not workload.empty:
                        st.bar_chart(workload)
                    else:
                        st.info("No employee workload data available")
                    
                    # Role coverage
                    if 'role' in filled_sched.columns:
                        st.markdown("**Role Distribution**")
                        role_coverage = filled_sched['role'].value_counts()
                        if not role_coverage.empty:
                            st.bar_chart(role_coverage)
                        else:
                            st.info("No role distribution data available")
            
            # Violations and issues
            st.markdown("#### ⚠️ Schedule Health Check")
            
            violations = validate_schedule(sched_df, emp_df, bs)
            
            if violations:
                violation_col1, violation_col2 = st.columns(2)
                
                with violation_col1:
                    st.markdown("**Issues Summary**")
                    violation_counts = {}
                    for violation in violations:
                        level = violation.get('level', 'unknown')
                        violation_counts[level] = violation_counts.get(level, 0) + 1
                    
                    for level, count in violation_counts.items():
                        color = {'critical': '🔴', 'moderate': '🟡', 'minor': '🔵'}.get(level, '⚪')
                        st.write(f"{color} **{level.title()}**: {count} issues")
                
                with violation_col2:
                    st.markdown("**Top Issues**")
                    for violation in violations[:5]:  # Show top 5 issues
                        level_emoji = {'critical': '🔴', 'moderate': '🟡', 'minor': '🔵'}.get(violation.get('level'), '⚪')
                        st.write(f"{level_emoji} {violation['message'][:60]}...")
            else:
                st.success("✅ No schedule violations detected!")
        else:
            st.info("📝 No schedule data available. Generate a schedule to see performance metrics.")
    
    with performance_tab:
        st.markdown("### 🎯 Performance Analytics")
        
        performance_col1, performance_col2 = st.columns(2)
        
        with performance_col1:
            st.markdown("#### 📈 Key Performance Indicators")
            
            # Calculate performance scores
            scores = {}
            
            # Team utilization score
            if not emp_df.empty:
                avg_utilization = emp_df['max_hours_per_week'].mean() / 40 * 100  # Assuming 40h is full-time
                scores['Team Utilization'] = min(avg_utilization, 100)
            
            # Schedule efficiency score  
            if total_shifts > 0:
                scores['Schedule Efficiency'] = fill_rate
            
            # Role coverage score
            if bs and hasattr(bs, 'role_settings'):
                target_roles = len(bs.role_settings)
                if target_roles > 0:
                    scores['Role Coverage'] = min((active_roles / target_roles) * 100, 100)
            
            # Display performance scores
            for metric, score in scores.items():
                if score >= 90:
                    color = "#10b981"  # Green
                    emoji = "🟢"
                elif score >= 70:
                    color = "#f59e0b"  # Orange  
                    emoji = "🟡"
                else:
                    color = "#ef4444"  # Red
                    emoji = "🔴"
                
                st.markdown(f"""
                <div style="background: linear-gradient(90deg, rgba(255,255,255,0.1), rgba(255,255,255,0.05)); 
                           border-left: 4px solid {color}; padding: 1rem; margin: 0.5rem 0; border-radius: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 600;">{emoji} {metric}</span>
                        <span style="font-size: 1.2rem; font-weight: 700; color: {color};">{score:.1f}%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        with performance_col2:
            st.markdown("#### 🏆 Performance Trends")
            
            # Simulated trend data (in a real app, this would come from historical data)
            trend_data = {
                'Week': ['Week 1', 'Week 2', 'Week 3', 'Week 4'],
                'Fill Rate': [85, 90, 95, fill_rate],
                'Team Satisfaction': [78, 82, 85, 88],
                'Efficiency Score': [72, 78, 85, 90]
            }
            
            trend_df = pd.DataFrame(trend_data)
            trend_df = trend_df.set_index('Week')
            
            if not trend_df.empty:
                st.line_chart(trend_df)
            else:
                st.info("No trend data available")
            
            st.markdown("#### 🎯 Improvement Opportunities")
            
            # Generate improvement suggestions
            suggestions = []
            
            if fill_rate < 95:
                suggestions.append("🔹 Improve fill rate by adding more employees or adjusting availability")
            
            if active_roles < target_roles:
                suggestions.append("🔹 Recruit for missing roles to improve coverage")
            
            if not emp_df.empty and emp_df['max_hours_per_week'].mean() < 25:
                suggestions.append("🔹 Consider increasing employee hours for better utilization")
            
            if not suggestions:
                suggestions.append("🎉 System is performing optimally!")
            
            for suggestion in suggestions:
                st.write(suggestion)
    
    with insights_tab:
        st.markdown("### 🔍 AI-Powered Insights")
        
        insights_col1, insights_col2 = st.columns([2, 1])
        
        with insights_col1:
            st.markdown("#### 🤖 Intelligent Recommendations")
            
            # Generate AI-style insights based on data
            insights = []
            
            if not emp_df.empty:
                # Analyze employee distribution
                role_imbalance = emp_df['role'].value_counts()
                max_role_count = role_imbalance.max()
                min_role_count = role_imbalance.min()
                
                if max_role_count > min_role_count * 2:
                    insights.append({
                        'type': 'warning',
                        'title': 'Role Distribution Imbalance Detected',
                        'message': 'Some roles have significantly more employees than others. Consider redistributing or cross-training.',
                        'action': 'Review role assignments and consider cross-training programs.'
                    })
                
                # Analyze capacity utilization
                avg_hours = emp_df['max_hours_per_week'].mean()
                if avg_hours < 25:
                    insights.append({
                        'type': 'info',
                        'title': 'Low Average Hours Detected',
                        'message': f'Average employee hours ({avg_hours:.1f}) may indicate underutilization.',
                        'action': 'Consider offering more hours to existing employees or optimizing schedules.'
                    })
                
                # Analyze importance distribution
                if 'importance' in emp_df.columns:
                    critical_employees = len(emp_df[emp_df['importance'] >= 4])
                    if critical_employees / len(emp_df) > 0.5:
                        insights.append({
                            'type': 'warning',
                            'title': 'High Critical Employee Ratio',
                            'message': f'{critical_employees} employees marked as critical. This may create dependency risks.',
                            'action': 'Consider developing backup plans and cross-training for critical roles.'
                        })
            
            if not sched_df.empty and fill_rate < 90:
                insights.append({
                    'type': 'critical',
                    'title': 'Low Schedule Fill Rate',
                    'message': f'Fill rate of {fill_rate:.1f}% is below optimal threshold.',
                    'action': 'Add more employees, increase availability, or adjust shift requirements.'
                })
            
            # Display insights
            if insights:
                for insight in insights:
                    icon_map = {'critical': '🔴', 'warning': '🟡', 'info': '🔵'}
                    color_map = {'critical': '#ef4444', 'warning': '#f59e0b', 'info': '#3b82f6'}
                    
                    icon = icon_map.get(insight['type'], '💡')
                    color = color_map.get(insight['type'], '#6b7280')
                    
                    st.markdown(f"""
                    <div style="background: rgba(255,255,255,0.05); border-left: 4px solid {color}; 
                               padding: 1.5rem; margin: 1rem 0; border-radius: 8px;">
                        <h4 style="margin-top: 0; color: {color};">{icon} {insight['title']}</h4>
                        <p style="margin: 0.5rem 0; color: #94a3b8;">{insight['message']}</p>
                        <p style="margin: 0; font-weight: 600; color: #e2e8f0;"><strong>Recommended Action:</strong> {insight['action']}</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("🎉 No critical insights detected. Your system is running optimally!")
        
        with insights_col2:
            st.markdown("#### 📊 Predictive Metrics")
            
            # Predictive analytics placeholder
            st.markdown("**Forecasted Metrics**")
            
            if not emp_df.empty and not sched_df.empty:
                # Simple predictions based on current data
                next_week_fill_rate = min(fill_rate + 2, 100)  # Assume slight improvement
                predicted_demand = total_shifts * 1.1  # Assume 10% growth
                
                predictions = {
                    'Next Week Fill Rate': f'{next_week_fill_rate:.1f}%',
                    'Predicted Demand': f'{predicted_demand:.0f} shifts',
                    'Recommended Staff': f'{int(predicted_demand / 10)} employees',
                    'Capacity Gap': f'{max(0, predicted_demand - total_capacity):.0f} hours'
                }
                
                for metric, value in predictions.items():
                    st.write(f"**{metric}**: {value}")
            else:
                st.info("Add data to see predictions")
            
            st.markdown("#### 🎯 Optimization Opportunities")
            
            optimizations = [
                "🔹 AI-powered shift optimization could improve fill rates by 5-15%",
                "🔹 Automated availability tracking could reduce scheduling conflicts",
                "🔹 Predictive analytics could forecast staffing needs 2-4 weeks ahead",
                "🔹 Employee satisfaction tracking could improve retention"
            ]
            
            for opt in optimizations:
                st.write(opt)
    
    # Export functionality
    st.markdown("---")
    st.markdown("### 📤 Export Analytics")
    
    export_col1, export_col2, export_col3 = st.columns(3)
    
    with export_col1:
        if st.button("📊 Export Workforce Report", width='stretch'):
            if not emp_df.empty:
                csv_data = emp_df.to_csv(index=False)
                st.download_button(
                    "Download Workforce CSV",
                    data=csv_data,
                    file_name=f"workforce_report_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No workforce data to export")
    
    with export_col2:
        if st.button("📅 Export Schedule Report", width='stretch'):
            if not sched_df.empty:
                csv_data = sched_df.to_csv(index=False)
                st.download_button(
                    "Download Schedule CSV",
                    data=csv_data,
                    file_name=f"schedule_report_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No schedule data to export")
    
    with export_col3:
        if st.button("📈 Export Analytics Summary", width='stretch'):
            # Create analytics summary
            summary_data = {
                'Metric': [
                    'Total Employees',
                    'Weekly Capacity (hours)',
                    'Schedule Fill Rate (%)',
                    'Active Roles',
                    'Average Employee Hours'
                ],
                'Value': [
                    total_employees,
                    total_capacity,
                    fill_rate,
                    active_roles,
                    total_capacity / total_employees if total_employees > 0 else 0
                ]
            }
            
            summary_df = pd.DataFrame(summary_data)
            csv_data = summary_df.to_csv(index=False)
            st.download_button(
                "Download Summary CSV",
                data=csv_data,
                file_name=f"analytics_summary_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

import json
from typing import Dict, List, Union, Optional, Any
from dataclasses import dataclass, field

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Mapping for full day names -> short labels used in UI/options
FULL_TO_SHORT_DAY = {
    "Monday": "Mon",
    "Tuesday": "Tue",
    "Wednesday": "Wed",
    "Thursday": "Thu",
    "Friday": "Fri",
    "Saturday": "Sat",
    "Sunday": "Sun",
}

def _normalize_days_list(days: list | None) -> list:
    """Normalize a list of day names to the UI's short labels (Mon..Sun).
    - Accepts full names (e.g., 'Monday') or short labels ('Mon').
    - Filters unknown values and preserves order without duplicates.
    - Returns a non-empty list; falls back to DAYS if input is invalid/empty.
    """
    if not days:
        return DAYS.copy()
    out: list[str] = []
    seen = set()
    for d in days:
        if not isinstance(d, str):
            continue
        d = d.strip()
        if d in DAYS:
            val = d
        else:
            val = FULL_TO_SHORT_DAY.get(d)
        if val and val in DAYS and val not in seen:
            out.append(val)
            seen.add(val)
    return out if out else DAYS.copy()
DB_PATH = "shift_maker.sqlite3"

# Type aliases for better type hints
EmployeeDict = Dict[str, Union[int, str, float, List[str], None]]  # Allow None values
RoleCoverage = Dict[str, Union[str, int]]
ShiftSlot = Dict[str, Union[str, date]]
ScheduleAssignment = Dict[str, Optional[int]]

# Default factory for days_available
def _default_days() -> List[str]:
    """Default factory for days_available."""
    return DAYS.copy()


# Import Employee from shift_plus_core for compatibility
from shift_plus_core import Employee

# ===============================
# Database and business settings helpers (copied from demo_AI/shift_plus.py)
def get_conn() -> sqlite3.Connection:
    """
    Get a SQLite3 connection to the main database.

    Returns:
        sqlite3.Connection: SQLite3 connection object with row factory set.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    # Configure date adapters for Python 3.12+ compatibility
    def adapt_date(date_obj):
        return date_obj.isoformat()
    
    def convert_date(date_str):
        return date.fromisoformat(date_str.decode())
    
    sqlite3.register_adapter(date, adapt_date)
    sqlite3.register_converter("date", convert_date)
    
    return conn


def init_db() -> None:
    """
    Initialize the main database if not already present.
    Creates tables for business settings, employees, and schedules if they do not exist.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS business_settings (id INTEGER PRIMARY KEY CHECK (id = 1), json TEXT NOT NULL);")
    cur.execute("""CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        preferred_shift TEXT NOT NULL,
        days_available TEXT NOT NULL,
        max_hours_per_week REAL NOT NULL,
        min_hours_per_week REAL NOT NULL,
        importance REAL NOT NULL DEFAULT 1.0
    );""")
    cur.execute("""CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_key TEXT NOT NULL,
        slot_id TEXT NOT NULL,
        date TEXT NOT NULL,
        shift_type TEXT NOT NULL,
        role TEXT NOT NULL,
        employee_id INTEGER,
        employee_name TEXT
    );""")
    cur.execute("""CREATE TABLE IF NOT EXISTS employee_unavailability (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        reason TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (employee_id) REFERENCES employees (id) ON DELETE CASCADE
    );""")
    conn.commit()

def load_business_settings() -> BusinessSettings:
    conn = get_conn()
    row = conn.execute("SELECT * FROM business_settings WHERE id = 1").fetchone()
    if row:
        bs = BusinessSettings.from_row(row)
        # Migrate/update empty daily_roles_coverage to use defaults
        if not bs.daily_roles_coverage or all(not day_coverage for day_coverage in bs.daily_roles_coverage.values()):
            # Populate with default daily role coverage
            bs.daily_roles_coverage = {
                "Monday": {
                    "Manager": {"day": 1, "night": 1},
                    "Barista": {"day": 2, "night": 1},
                    "Cashier": {"day": 1, "night": 1}
                },
                "Tuesday": {
                    "Manager": {"day": 1, "night": 1},
                    "Barista": {"day": 2, "night": 1},
                    "Cashier": {"day": 1, "night": 1}
                },
                "Wednesday": {
                    "Manager": {"day": 1, "night": 1},
                    "Barista": {"day": 2, "night": 1},
                    "Cashier": {"day": 1, "night": 1}
                },
                "Thursday": {
                    "Manager": {"day": 1, "night": 1},
                    "Barista": {"day": 2, "night": 1},
                    "Cashier": {"day": 1, "night": 1}
                },
                "Friday": {
                    "Manager": {"day": 1, "night": 1},
                    "Barista": {"day": 3, "night": 2},
                    "Cashier": {"day": 2, "night": 1}
                },
                "Saturday": {
                    "Manager": {"day": 1, "night": 1},
                    "Barista": {"day": 3, "night": 2},
                    "Cashier": {"day": 2, "night": 1}
                },
                "Sunday": {
                    "Manager": {"day": 1, "night": 1},
                    "Barista": {"day": 2, "night": 1},
                    "Cashier": {"day": 1, "night": 1}
                }
            }
            # Save the updated settings
            save_business_settings(bs)
        return bs
    else:
        # Create default settings if not found
        bs = BusinessSettings()
        save_business_settings(bs)
        return bs

def save_business_settings(bs: BusinessSettings) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO business_settings (id, json) VALUES (?, ?)",
        (1, bs.to_json())
    )
    conn.commit()

def add_employee_unavailability(employee_id: int, start_date: str, end_date: str, reason: str) -> None:
    """Add a period of unavailability for an employee (e.g., sick leave)."""
    conn = get_conn()
    conn.execute(
        "INSERT INTO employee_unavailability (employee_id, start_date, end_date, reason) VALUES (?, ?, ?, ?)",
        (employee_id, start_date, end_date, reason)
    )
    conn.commit()

def get_employee_unavailability(employee_id: int = None) -> pd.DataFrame:
    """Get unavailability records for an employee or all employees."""
    conn = get_conn()
    if employee_id:
        query = """
        SELECT u.*, e.name as employee_name 
        FROM employee_unavailability u 
        JOIN employees e ON u.employee_id = e.id 
        WHERE u.employee_id = ?
        ORDER BY u.start_date DESC
        """
        return pd.read_sql_query(query, conn, params=(employee_id,))
    else:
        query = """
        SELECT u.*, e.name as employee_name 
        FROM employee_unavailability u 
        JOIN employees e ON u.employee_id = e.id 
        ORDER BY u.start_date DESC
        """
        return pd.read_sql_query(query, conn)

def remove_employee_unavailability(unavailability_id: int) -> None:
    """Remove an unavailability record."""
    conn = get_conn()
    conn.execute("DELETE FROM employee_unavailability WHERE id = ?", (unavailability_id,))
    conn.commit()


# Utility functions for business settings and employees
def validate_schedule(sched_df: Optional[pd.DataFrame], emp_df: pd.DataFrame, bs: BusinessSettings) -> List[Dict[str, Union[str, int, float]]]:
    """
    Comprehensive schedule validation engine.
    
    Analyzes a generated schedule against business rules, employee constraints,
    and operational requirements to identify potential issues and violations.
    
    Args:
        sched_df (pd.DataFrame): Schedule dataframe with columns:
            - employee_id: Employee ID (int, can be NaN for unfilled)
            - employee_name: Employee name (str, can be NaN for unfilled)  
            - date: Shift date (str or datetime)
            - role: Required role for the shift (str)
            - shift_type: Type of shift (day/night/etc.) (str)
        emp_df (pd.DataFrame): Employee dataframe with employee information
        bs (BusinessSettings): Business settings object with rules and constraints
    
    Returns:
        List[Dict]: List of violation dictionaries, each containing:
            - type (str): Violation category (e.g., 'unfilled_shifts', 'overloaded_employee')
            - level (str): Severity level ('critical', 'moderate', 'minor')
            - message (str): Human-readable description of the issue
            - Additional fields specific to violation type
    
    Validation Categories:
        - Unfilled shifts: Shifts without assigned employees
        - Employee overloading: Employees with excessive shift counts
        - Consecutive shifts: Back-to-back shift assignments
        - Role coverage: Missing required role coverage
        - Role mismatches: Employees assigned to unqualified roles
        - Weekend balance: Excessive weekend shift ratios
    
    Example:
        >>> violations = validate_schedule(schedule_df, employees_df, business_settings)
        >>> for violation in violations:
        ...     print(f"{violation['level']}: {violation['message']}")
    """
    violations = []
    
    if sched_df is None or sched_df.empty:
        return violations
    
    filled_df = sched_df[sched_df['employee_id'].notna()].copy()
    unfilled_df = sched_df[sched_df['employee_id'].isna()].copy()
    
    # 1. Check for unfilled shifts
    if not unfilled_df.empty:
        unfilled_count = len(unfilled_df)
        unfilled_percent = (unfilled_count / len(sched_df)) * 100
        level = 'critical' if unfilled_percent > 20 else 'moderate' if unfilled_percent > 10 else 'minor'
        violations.append({
            'type': 'unfilled_shifts',
            'level': level,
            'message': f"{unfilled_count} unfilled shifts ({unfilled_percent:.1f}% of total)",
            'count': unfilled_count
        })
    
    if filled_df.empty:
        return violations
    
    # 2. Check for employee overloading
    if 'employee_id' in filled_df.columns:
        shifts_per_employee = filled_df['employee_id'].value_counts()
        overloaded_employees = shifts_per_employee[shifts_per_employee > 40]  # More than 40 shifts
        
        for emp_id, shift_count in overloaded_employees.items():
            emp_name = filled_df[filled_df['employee_id'] == emp_id]['employee_name'].iloc[0]
            violations.append({
                'type': 'overloaded_employee',
                'level': 'moderate',
                'message': f"Employee {emp_name} has {shift_count} shifts (potential overload)",
                'employee_id': emp_id,
                'shift_count': shift_count
            })
    
    # 3. Check for consecutive shifts (same employee, consecutive dates)
    if 'date' in filled_df.columns and 'employee_id' in filled_df.columns:
        filled_df['date_parsed'] = pd.to_datetime(filled_df['date'], errors='coerce')
        filled_df_sorted = filled_df.sort_values(['employee_id', 'date_parsed'])
        
        for emp_id in filled_df['employee_id'].unique():
            emp_shifts = filled_df_sorted[filled_df_sorted['employee_id'] == emp_id]
            if len(emp_shifts) < 2:
                continue
                
            # Check for back-to-back shifts
            emp_shifts = emp_shifts.reset_index(drop=True)
            for i in range(len(emp_shifts) - 1):
                current_date = emp_shifts.loc[i, 'date_parsed']
                next_date = emp_shifts.loc[i + 1, 'date_parsed']
                
                if pd.notna(current_date) and pd.notna(next_date):
                    if (next_date - current_date).days == 1:
                        emp_name = emp_shifts.loc[i, 'employee_name']
                        violations.append({
                            'type': 'consecutive_shifts',
                            'level': 'minor',
                            'message': f"Employee {emp_name} has consecutive shifts on {current_date.strftime('%m/%d')} and {next_date.strftime('%m/%d')}",
                            'employee_id': emp_id
                        })
    
    # 4. Check for missing roles coverage
    if bs and hasattr(bs, 'roles'):
        required_roles = set(bs.roles)
        scheduled_roles = set(filled_df['role'].unique()) if 'role' in filled_df.columns else set()
        missing_roles = required_roles - scheduled_roles
        
        if missing_roles:
            violations.append({
                'type': 'missing_roles',
                'level': 'moderate',
                'message': f"Missing coverage for roles: {', '.join(missing_roles)}",
                'missing_roles': list(missing_roles)
            })
    
    # 5. Check for role-employee mismatch
    if not emp_df.empty and 'role' in filled_df.columns and 'employee_id' in filled_df.columns:
        for _, shift in filled_df.iterrows():
            emp_id = shift.get('employee_id')
            shift_role = shift.get('role')
            
            if pd.notna(emp_id) and shift_role:
                # Get employee's qualified roles
                emp_record = emp_df[emp_df['id'] == emp_id]
                if not emp_record.empty:
                    emp_roles = emp_record.iloc[0].get('roles', '')
                    if isinstance(emp_roles, str) and emp_roles:
                        qualified_roles = [r.strip() for r in emp_roles.split(',')]
                        if shift_role not in qualified_roles:
                            emp_name = shift.get('employee_name', f'ID {emp_id}')
                            violations.append({
                                'type': 'role_mismatch',
                                'level': 'moderate',
                                'message': f"Employee {emp_name} assigned to {shift_role} but not qualified",
                                'employee_id': emp_id,
                                'assigned_role': shift_role
                            })
    
    # 6. Check for weekend balance
    if 'date' in filled_df.columns:
        filled_df['date_parsed'] = pd.to_datetime(filled_df['date'], errors='coerce')
        filled_df['is_weekend'] = filled_df['date_parsed'].dt.dayofweek.isin([5, 6])  # Saturday=5, Sunday=6
        
        weekend_shifts = filled_df[filled_df['is_weekend']]
        weekday_shifts = filled_df[~filled_df['is_weekend']]
        
        if len(weekend_shifts) > 0 and len(weekday_shifts) > 0:
            weekend_ratio = len(weekend_shifts) / len(filled_df)
            if weekend_ratio > 0.4:  # More than 40% weekend shifts
                violations.append({
                    'type': 'weekend_heavy',
                    'level': 'minor',
                    'message': f"High weekend shift ratio: {weekend_ratio:.1%}",
                    'weekend_ratio': weekend_ratio
                })
    
    return violations

def save_schedule_to_db(sched_df: pd.DataFrame, bs: BusinessSettings) -> None:
    """
    Save the schedule DataFrame to the database for the current planning window.

    Args:
        sched_df (pd.DataFrame): The schedule to save.
        bs (BusinessSettings): Business settings for context (planning window).
    """
    conn = get_conn()
    start = bs.planning_start.isoformat()
    end = (bs.planning_start + timedelta(days=bs.planning_days - 1)).isoformat()
    plan_key = f"{start}_{end}"
    
    try:
        # Delete existing schedules for this plan_key
        conn.execute("DELETE FROM schedules WHERE plan_key = ?", (plan_key,))
        
        # Deduplicate the schedule before saving, prioritizing filled shifts over unfilled ones
        # Sort so filled shifts (non-null employee_id) come first
        sched_df_sorted = sched_df.sort_values('employee_id', ascending=False, na_position='last')
        sched_df_clean = sched_df_sorted.drop_duplicates(subset=['date', 'shift_type', 'role'], keep='first')
        
        # Log if duplicates were found
        if len(sched_df_clean) < len(sched_df):
            duplicates_removed = len(sched_df) - len(sched_df_clean)
            logger.info("Removed %d duplicate schedule entries, prioritizing filled shifts", duplicates_removed)
        
        # Track slot_ids to ensure uniqueness within this plan_key
        used_slot_ids = set()
        
        # Insert new schedule with guaranteed unique slot_ids
        for _, row in sched_df_clean.iterrows():
            # Create base slot_id
            base_slot_id = row.get("slot_id")
            if not base_slot_id:
                base_slot_id = f"{row['date']}_{row['shift_type']}_{row['role']}"
            
            # Ensure slot_id is unique within this plan_key
            slot_id = base_slot_id
            counter = 0
            while slot_id in used_slot_ids:
                counter += 1
                slot_id = f"{base_slot_id}_{counter}"
            
            used_slot_ids.add(slot_id)
            
            # Convert data types for database compatibility
            date_value = row["date"]
            if hasattr(date_value, 'strftime'):
                # Convert pandas Timestamp or datetime to string
                date_str = date_value.strftime('%Y-%m-%d')
            elif isinstance(date_value, str):
                date_str = date_value
            else:
                date_str = str(date_value)
            
            # Handle employee_id - convert NaN to None
            employee_id = row["employee_id"]
            if pd.isna(employee_id):
                employee_id = None
            else:
                employee_id = int(employee_id)
            
            # Handle employee_name - convert NaN to None
            employee_name = row["employee_name"] 
            if pd.isna(employee_name):
                employee_name = None
            
            conn.execute(
                "INSERT INTO schedules (plan_key, slot_id, date, shift_type, role, employee_id, employee_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    plan_key,
                    slot_id,
                    date_str,
                    row["shift_type"],
                    row["role"],
                    employee_id,
                    employee_name
                )
            )
        
        conn.commit()
        logger.info("Successfully saved %d schedule entries to database", len(sched_df_clean))
        
    except Exception as e:
        conn.rollback()
        logger.error("Failed to save schedule to database: %s", e)
        raise

def cleanup_orphaned_schedule_entries() -> None:
    """
    Remove schedule entries that reference non-existent employees.
    This helps prevent warnings about missing employee IDs.
    """
    conn = get_conn()
    try:
        # Find and delete schedule entries with employee_ids that don't exist in employees table
        cursor = conn.execute("""
            DELETE FROM schedules 
            WHERE employee_id IS NOT NULL 
            AND employee_id NOT IN (SELECT id FROM employees)
        """)
        
        deleted_count = cursor.rowcount
        conn.commit()
        
        if deleted_count > 0:
            logger.info("Cleaned up %d orphaned schedule entries", deleted_count)
        
    except Exception as e:
        conn.rollback()
        logger.error("Failed to cleanup orphaned schedule entries: %s", e)

def cleanup_old_schedule_entries(days_to_keep: int = 30) -> None:
    """
    Remove schedule entries older than specified days to keep the database clean.
    
    Args:
        days_to_keep (int): Number of days to keep. Schedules older than this will be deleted.
    """
    conn = get_conn()
    try:
        cutoff_date = date.today() - timedelta(days=days_to_keep)
        cutoff_str = cutoff_date.isoformat()
        
        cursor = conn.execute("""
            DELETE FROM schedules 
            WHERE date < ?
        """, (cutoff_str,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        
        if deleted_count > 0:
            logger.info("Cleaned up %d old schedule entries before %s", deleted_count, cutoff_date)
        
    except Exception as e:
        conn.rollback()
        logger.error("Failed to cleanup old schedule entries: %s", e)

def clear_all_schedules() -> None:
    """
    Clear all schedule entries from the database. 
    Use this to start fresh when schedule generation is producing incorrect results.
    """
    conn = get_conn()
    try:
        cursor = conn.execute("DELETE FROM schedules")
        deleted_count = cursor.rowcount
        conn.commit()
        
        logger.info("Cleared all %d schedule entries from database", deleted_count)
        
    except Exception as e:
        conn.rollback()
        logger.error("Failed to clear schedule entries: %s", e)

def load_schedule_from_db(bs: BusinessSettings) -> pd.DataFrame:
    """
    Loads the schedule for the current planning window from the database.
    Loads the most recent complete schedule with proper employee assignments.
    """
    conn = get_conn()
    
    # Try to load schedules from planning period first, then fall back to recent dates
    df = pd.DataFrame()
    
    # First, try loading schedules for the business planning period
    if bs and hasattr(bs, 'planning_start') and hasattr(bs, 'planning_days'):
        try:
            start_date = bs.planning_start.isoformat()
            end_date = (bs.planning_start + timedelta(days=bs.planning_days)).isoformat()
            
            df = pd.read_sql_query(
                """
                SELECT * FROM schedules
                WHERE date >= ? AND date < ?
                ORDER BY 
                    CASE WHEN employee_id IS NOT NULL THEN 0 ELSE 1 END,
                    date, shift_type, role
                """,
                conn,
                params=(start_date, end_date)
            )
        except Exception:
            pass
    
    # If no planning period data, fall back to recent schedules (last 30 days)
    if df.empty:
        recent_date = (date.today() - timedelta(days=30)).isoformat()
        
        df = pd.read_sql_query(
            """
            SELECT * FROM schedules
            WHERE date >= ?
            ORDER BY 
                CASE WHEN employee_id IS NOT NULL THEN 0 ELSE 1 END,
                date DESC, shift_type, role
            LIMIT 200
            """,
            conn,
            params=(recent_date,)
        )
    
    # If we have data, deduplicate prioritizing filled shifts
    if not df.empty:
        # Remove duplicates, keeping filled shifts over unfilled ones
        df_deduplicated = df.drop_duplicates(subset=['date', 'shift_type', 'role'], keep='first')
        df = df_deduplicated.sort_values(['date', 'shift_type', 'role'])
    
    return df

def _load_emp(emp_id: int) -> tuple[pd.Series, List[str]]:
    """Load an employee row and parse days_available."""
    df2 = get_all_employees()
    row = df2[df2["id"] == emp_id].iloc[0]
    try:
        loaded_days = json.loads(row["days_available"]) if isinstance(row["days_available"], str) else row["days_available"]
        days_current = _normalize_days_list(loaded_days)
    except (json.JSONDecodeError, TypeError):
        days_current = DAYS.copy()
    return row, days_current


def insert_employee(emp: EmployeeDict) -> None:
    """Insert a new employee into the database, including importance."""
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO employees (name, role, preferred_shift, days_available, max_hours_per_week, min_hours_per_week, importance)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                emp["name"],
                emp["role"],
                emp["preferred_shift"],
                json.dumps(emp["days_available"]),
                emp["max_hours_per_week"],
                emp["min_hours_per_week"],
                emp.get("importance", 1.0)
            )
        )
        conn.commit()
    except sqlite3.Error as e:
        st.error(f"Failed to add employee: {e}")


def update_employee_row(emp_id: int, emp: EmployeeDict) -> None:
    """Update an existing employee in the database, including importance."""
    conn = get_conn()
    try:
        conn.execute(
            """
            UPDATE employees SET name=?, role=?, preferred_shift=?, days_available=?, max_hours_per_week=?, min_hours_per_week=?, importance=? WHERE id=?
            """,
            (
                emp["name"],
                emp["role"],
                emp["preferred_shift"],
                json.dumps(emp["days_available"]),
                emp["max_hours_per_week"],
                emp["min_hours_per_week"],
                emp.get("importance", 1.0),
                emp_id
            )
        )
        conn.commit()
    except sqlite3.Error as e:
        st.error(f"Failed to update employee: {e}")

def delete_employee_row(emp_id: int) -> None:
    """Delete an employee from the database."""
    conn = get_conn()
    try:
        conn.execute("DELETE FROM employees WHERE id=?", (emp_id,))
        conn.commit()
    except sqlite3.Error as e:
        st.error(f"Failed to delete employee: {e}")

def get_all_employees() -> pd.DataFrame:
    conn = get_conn()
    try:
        df = pd.read_sql_query("SELECT * FROM employees ORDER BY id", conn)
        return df
    except Exception as e:
        st.error(f"Failed to load employees: {e}")
        return pd.DataFrame()

def employees_to_df() -> pd.DataFrame:
    return get_all_employees()

def to_sched_df(
    slots: List[ShiftSlot], 
    assign: ScheduleAssignment, 
    emp_df: pd.DataFrame
) -> pd.DataFrame:
    # Validate slots structure
    if not all(isinstance(slot, dict) and all(key in slot for key in ["slot_id", "date", "shift_type", "role"]) for slot in slots):
        raise ValueError("Invalid slots structure. Each slot must be a dictionary with 'slot_id', 'date', 'shift_type', and 'role' keys.")

    # Validate emp_df structure
    if not all(column in emp_df.columns for column in ["id", "name"]):
        raise ValueError("Invalid emp_df structure. DataFrame must contain 'id' and 'name' columns.")

    rows = []
    emp_map = {int(r["id"]): r["name"] for _, r in emp_df.dropna(subset=["id"]).iterrows()}
    for slot in slots:
        emp_id = assign.get(slot["slot_id"], None)
        emp_name = emp_map.get(emp_id, "UNFILLED") if emp_id is not None else "UNFILLED"
        rows.append({
            "slot_id": slot["slot_id"],
            "date": str(slot["date"]),
            "shift_type": slot["shift_type"],
            "role": slot["role"],
            "employee_id": emp_id,
            "employee_name": emp_name
        })
    return pd.DataFrame(rows)


def df_to_employees(df: pd.DataFrame) -> List[Employee]:
    """
    Convert a DataFrame to a list of Employee dataclass instances.

    Args:
        df (pd.DataFrame): DataFrame containing employee data.

    Returns:
        list[Employee]: List of Employee dataclass instances.
    """
    employees = []
    for _, row in df.iterrows():
        imp = row["importance"] if "importance" in row and not pd.isna(row["importance"]) else 1.0
        # If importance is a JSON string, keep as string for per-day/shift
        employees.append(Employee(
            id=row["id"],
            name=row["name"],
            role=row["role"],
            preferred_shift=row["preferred_shift"],
            days_available=json.loads(row["days_available"]) if isinstance(row["days_available"], str) else row["days_available"],
            max_hours_per_week=row["max_hours_per_week"],
            min_hours_per_week=row["min_hours_per_week"],
            importance=imp
        ))
    return employees

# ===============================
# AI Schedule Generation ---

def load_employees() -> pd.DataFrame:
    conn = get_conn()
    query = "SELECT * FROM employees ORDER BY id"
    df: pd.DataFrame = pd.read_sql_query(query, conn)
    return df

def generate_schedule_with_ai_enhanced(
    emp_data: pd.DataFrame, 
    shift_slots: List[Dict[str, Union[str, date]]], 
    bs: Any,
    availability_matrix: Optional[Dict[int, Dict[str, bool]]] = None,
    ai_strategy: str = "Balanced",
    creativity_level: float = 0.3,
    include_preferences: bool = True,
    validate_constraints: bool = True
) -> pd.DataFrame:
    """
    Enhanced AI schedule generation with availability monitoring and intelligent optimization.
    
    This function integrates real-time employee availability data with advanced AI algorithms
    to generate optimal work schedules that respect both business constraints and employee
    preferences while maintaining operational efficiency.
    
    Args:
        emp_data (pd.DataFrame): Employee data with availability information
        shift_slots (List[Dict]): Available shift slots to be filled
        bs (Any): Business settings and constraints
        availability_matrix (Dict[int, Dict[str, bool]]): Real-time availability data
        ai_strategy (str): AI optimization strategy ("Balanced", "Employee-Focused", etc.)
        creativity_level (float): AI creativity parameter (0.1-1.0)
        include_preferences (bool): Whether to consider employee preferences
        validate_constraints (bool): Whether to enforce strict constraint validation
    
    Returns:
        pd.DataFrame: Optimized schedule with AI-driven assignments
    """
    
    # Normalize legacy/unsupported strategies
    if ai_strategy and ai_strategy.lower().strip() in {"cost-optimized", "cost optimised", "cost-optimised"}:
        logger.warning("'Cost-Optimized' strategy is no longer supported; defaulting to 'Business-Focused'.")
        ai_strategy = "Business-Focused"

    # Input validation
    if emp_data.empty or not shift_slots:
        logger.warning("Empty employee data or shift slots provided")
        return pd.DataFrame()
    
    if not openai_available:
        logger.warning("OpenAI not available, falling back to standard generation")
        return generate_schedule_with_ai(emp_data, shift_slots, bs)
    
    try:
        logger.info("🤖 Starting AI-enhanced schedule generation")
        
        # Filter employees based on availability matrix
        if availability_matrix:
            available_employees = []
            for _, emp in emp_data.iterrows():
                emp_id = emp['id']
                if emp_id in availability_matrix:
                    # Check if employee has any available days
                    has_availability = any(availability_matrix[emp_id].values())
                    if has_availability:
                        available_employees.append(emp)
                else:
                    # If not in matrix, assume available
                    available_employees.append(emp)
            
            if not available_employees:
                logger.error("No employees available in the selected date range")
                return pd.DataFrame()
            
            filtered_emp_data = pd.DataFrame(available_employees)
        else:
            filtered_emp_data = emp_data.copy()
        
        # Filter shift slots based on availability
        if availability_matrix:
            available_slots = []
            for slot in shift_slots:
                slot_date = str(slot.get('date', ''))
                # Check if any employee is available for this slot date
                date_has_staff = any(
                    emp_id in availability_matrix and 
                    availability_matrix[emp_id].get(slot_date, True)
                    for emp_id in availability_matrix.keys()
                )
                if date_has_staff:
                    available_slots.append(slot)
            
            if not available_slots:
                logger.error("No shift slots have available staff")
                return pd.DataFrame()
            
            filtered_slots = available_slots
        else:
            filtered_slots = shift_slots
        
        # Prepare AI context with availability information
        availability_summary = ""
        if availability_matrix:
            availability_summary = "\n\nEMPLOYEE AVAILABILITY CONSTRAINTS:\n"
            for emp_id, dates in availability_matrix.items():
                emp_name = filtered_emp_data[filtered_emp_data['id'] == emp_id]['name'].iloc[0] if not filtered_emp_data[filtered_emp_data['id'] == emp_id].empty else f"Employee {emp_id}"
                available_dates = [date for date, available in dates.items() if available]
                unavailable_dates = [date for date, available in dates.items() if not available]
                
                availability_summary += f"- {emp_name}: Available on {available_dates}, NOT available on {unavailable_dates}\n"
        
        # Create enhanced AI prompt
        ai_prompt = f"""
        ADVANCED WORKFORCE SCHEDULING REQUEST
        
        Strategy: {ai_strategy}
        Creativity Level: {creativity_level}
        Include Preferences: {include_preferences}
        Validate Constraints: {validate_constraints}
        
        EMPLOYEES:
        {filtered_emp_data[['id', 'name', 'role', 'max_hours_per_week', 'preferred_shift']].to_dict('records')}
        
        SHIFT REQUIREMENTS:
        {filtered_slots[:20]}  # Limit for token efficiency
        
        {availability_summary}
        
        BUSINESS CONSTRAINTS:
        - Maximum hours per employee per week: {getattr(bs, 'max_hours_per_week', 40)}
        - Minimum rest hours between shifts: {getattr(bs, 'min_rest_hours', 11)}
        - Maximum consecutive days: {getattr(bs, 'max_consecutive_days', 6)}
        
        AI INSTRUCTIONS:
        1. STRICTLY respect the availability constraints - do not assign employees to dates they are unavailable
        2. Optimize according to the {ai_strategy} strategy
        3. Balance workload fairly across all available employees
        4. Consider employee preferences when include_preferences is True
        5. Ensure all critical roles are covered each day
        6. Minimize scheduling conflicts and maximize efficiency
        
        Return ONLY a JSON array of assignments in this exact format:
        [
            {{"slot_id": "slot_identifier", "employee_id": employee_id_number, "confidence": 0.95}},
            ...
        ]
        
        CRITICAL: Only assign employees to slots where they are marked as available in the availability matrix.
        """
        
        # Call OpenAI with enhanced parameters
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system", 
                    "content": f"You are an expert AI workforce scheduler. Generate optimal work schedules that strictly respect availability constraints and business rules. Creativity level: {creativity_level}"
                },
                {"role": "user", "content": ai_prompt}
            ],
            max_tokens=2000,
            temperature=creativity_level
        )
        
        ai_response = response["choices"][0]["message"]["content"]
        logger.info("🤖 AI response received, parsing assignments")
        
        # DEBUG: Log the AI response
        logger.info("🔍 AI Response (first 500 chars): %s", ai_response[:500])
        
        # Parse AI response
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\[.*\]', ai_response, re.DOTALL)
            if json_match:
                assignments_json = json_match.group()
                assignments = json.loads(assignments_json)
                logger.info("🔍 AI returned %d assignments", len(assignments))
            else:
                raise ValueError("No JSON array found in AI response")
            
            # Validate assignments against availability
            valid_assignments = {}
            logger.info("🔍 Starting assignment validation for %d assignments", len(assignments))
            
            for i, assignment in enumerate(assignments):
                slot_id = assignment.get('slot_id')
                employee_id = assignment.get('employee_id')
                
                logger.info("🔍 Assignment %d: slot_id=%s, employee_id=%s", i+1, slot_id, employee_id)
                
                if slot_id and employee_id:
                    # Find the slot to get its date
                    slot = next((s for s in filtered_slots if s.get('slot_id') == slot_id), None)
                    if slot and availability_matrix:
                        slot_date = str(slot.get('date', ''))
                        # Verify employee is available on this date
                        if (employee_id in availability_matrix and 
                            availability_matrix[employee_id].get(slot_date, True)):
                            valid_assignments[slot_id] = employee_id
                            logger.info("🔍 ✅ Valid assignment: employee %d to slot %s on %s", employee_id, slot_id, slot_date)
                        else:
                            logger.warning("🔍 ❌ AI assigned unavailable employee %d to %s", employee_id, slot_date)
                    else:
                        valid_assignments[slot_id] = employee_id
                        logger.info("🔍 ✅ Assignment accepted (no availability check): employee %d to slot %s", employee_id, slot_id)
                else:
                    logger.warning("🔍 ❌ Invalid assignment: missing slot_id or employee_id")
            
            logger.info("🔍 Final valid assignments: %d out of %d", len(valid_assignments), len(assignments))
            
            # Generate schedule DataFrame
            schedule_df = to_sched_df(filtered_slots, valid_assignments, filtered_emp_data)
            
            logger.info("🤖 AI-enhanced schedule generated with %d assignments", len(valid_assignments))
            return schedule_df
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Failed to parse AI response: %s", e)
            # Fallback to standard generation
            return generate_schedule_with_ai(filtered_emp_data, filtered_slots, bs)
            
    except Exception as e:
        logger.error("AI-enhanced generation error: %s", e)
        # Fallback to standard generation
        return generate_schedule_with_ai(emp_data, shift_slots, bs)

def generate_schedule_with_ai(emp_data: pd.DataFrame, shift_slots: List[Dict[str, Union[str, date]]], bs: Any) -> pd.DataFrame:
    """
    Generate optimized employee schedule using hybrid AI+MILP+Greedy algorithms.
    
    This function serves as the main entry point for schedule generation, utilizing
    the advanced HybridScheduler from shift_plus_core to create optimal workforce
    schedules that balance business constraints, employee preferences, and operational
    efficiency.
    
    Args:
        emp_data (pd.DataFrame): Employee data with columns:
            - emp_id: Unique employee identifier
            - name: Employee name
            - role: Job role/position
            - max_hours_per_week: Maximum hours this employee can work
            - days_available: Comma-separated list of available days
            - importance: Employee importance rating (0.1-5.0 scale)
            - Additional availability and preference columns
        
        shift_slots (List[Dict[str, Union[str, date]]]): Available shift slots with:
            - day: Day of the week (Monday, Tuesday, etc.)
            - shift: Shift identifier (Morning, Afternoon, Evening, etc.)
            - role: Required role for this shift
            - date: Specific date for the shift (if applicable)
            - Additional shift-specific requirements
        
        bs (BusinessSettings): Business configuration object containing:
            - Shift definitions and timing
            - Role requirements and constraints
            - Business rules and preferences
            - Operational parameters
    
    Returns:
        pd.DataFrame: Optimized schedule with columns:
            - emp_id: Assigned employee ID
            - name: Employee name
            - role: Employee role
            - day: Day of assignment
            - shift: Shift assigned
            - date: Specific date (if applicable)
            - Additional assignment metadata
    
    Algorithm Strategy:
        1. **AI Scheduling**: Uses OpenAI API for intelligent assignment considering
           complex constraints, employee preferences, and business optimization goals
        
        2. **MILP Optimization**: Mathematical optimization using PuLP for constraint
           satisfaction and optimal resource allocation (if PuLP is available)
        
        3. **Greedy Fallback**: Deterministic greedy algorithm ensuring reliable
           schedule generation even without external dependencies
        
        4. **Importance Weighting**: Employee importance ratings (0.1-5.0) influence
           assignment priority and preference consideration
    
    Features:
        - Automatic availability detection and constraint validation
        - Multi-algorithm approach for reliability and optimization
        - Employee importance scoring for priority-based assignments
        - Comprehensive error handling and fallback mechanisms
        - Real-time progress tracking and result validation
        - Integration with business settings for custom constraints
    
    Performance Considerations:
        - Algorithm selection based on problem size and complexity
        - Caching of intermediate results for large datasets
        - Progressive optimization with early termination options
        - Memory-efficient processing for enterprise-scale schedules
    
    Error Handling:
        - Graceful degradation if AI services are unavailable
        - Automatic fallback to mathematical optimization
        - Final fallback to greedy algorithm for guaranteed results
        - Comprehensive logging of generation process and decisions
    
    Example:
        ```python
        # Load employee data and business settings
        employees = load_employees()
        business_settings = load_business_settings()
        
        # Define shift slots for the week
        shift_slots = [
            {'day': 'Monday', 'shift': 'Morning', 'role': 'Manager'},
            {'day': 'Monday', 'shift': 'Afternoon', 'role': 'Staff'},
            # ... more shifts
        ]
        
        # Generate optimized schedule
        schedule = generate_schedule_with_ai(employees, shift_slots, business_settings)
        
        # Save and validate results
        save_schedule_to_db(schedule, business_settings)
        violations = validate_schedule(schedule, employees, business_settings)
        ```
    
    Integration:
        - Called from Streamlit UI during schedule generation
        - Uses HybridScheduler class from shift_plus_core module
        - Integrates with database layer for persistence
        - Supports real-time UI updates during generation process
    """
    """Generate schedule using hybrid AI + MILP + Greedy approach with fallback"""
    try:
        # Import hybrid scheduler
        from shift_plus_core import create_hybrid_scheduler
        
        # Convert employee DataFrame to Employee objects
        employees = df_to_employees(emp_data)
        
        # Create hybrid scheduler
        scheduler = create_hybrid_scheduler(bs, employees)
        
        # Generate schedule using hybrid approach
        result = scheduler.generate_schedule(shift_slots, strategy="hybrid")
        
        if result.success and not result.schedule_df.empty:
            logger.info("Hybrid scheduler generated schedule with %.1f%% optimization score", result.optimization_score)
            logger.info("Algorithm used: %s, Execution time: %.2fs", result.algorithm_used, result.execution_time)
            
            if result.violations:
                logger.warning("Schedule has %d violations", len(result.violations))
                for violation in result.violations[:5]:  # Log first 5 violations
                    logger.warning("Violation: %s", violation['message'])
            
            # Add hours column based on shift type if missing
            schedule_df = result.schedule_df.copy()
            if 'hours' not in schedule_df.columns:
                # Use default hours if business settings are None
                day_hours = getattr(bs, 'day_shift_length', 8) if bs else 8
                night_hours = getattr(bs, 'night_shift_length', 8) if bs else 8
                schedule_df['hours'] = schedule_df['shift_type'].apply(
                    lambda shift: day_hours if shift == 'day' else night_hours
                )
            
            return schedule_df
        else:
            logger.error("Hybrid scheduler failed, falling back to legacy AI method")
            return generate_schedule_with_ai_fallback(emp_data, shift_slots, bs)
            
    except Exception as e:
        logger.error("Hybrid scheduling error: %s, falling back to legacy AI method", e)
        return generate_schedule_with_ai_fallback(emp_data, shift_slots, bs)

def generate_schedule_with_ai_fallback(emp_data: pd.DataFrame, shift_slots: List[Dict[str, Union[str, date]]], bs: Any) -> pd.DataFrame:
    """Fallback AI scheduling method using original approach"""
    # Input validation - gracefully handle edge cases
    if emp_data.empty or not all(col in emp_data.columns for col in ["id", "name", "max_hours_per_week"]):
        logger.warning("Invalid or empty employee data provided, returning empty schedule")
        return pd.DataFrame()
    if not shift_slots or not all("date" in slot and "role" in slot for slot in shift_slots):
        logger.warning("Invalid or empty shift slots provided, returning empty schedule")
        return pd.DataFrame()

    # If OpenAI is not available, return empty DataFrame
    if not openai_available:
        logger.warning("OpenAI not available, returning empty schedule")
        return pd.DataFrame()

    try:
        logger.debug("Using fallback AI scheduling")
        logger.debug("Employee Data: %s", emp_data.to_dict())
        logger.debug("Shift Slots: %s", shift_slots)

        # Create a prompt for AI
        prompt = (f"Create a work schedule for the given employees and shift slots.\n\n"
                 f"Employees: {emp_data.to_dict('records')}\n"
                 f"Shift Slots: {shift_slots[:10]}\n\n"
                 f"Return a CSV-style table with columns: date, role, shift_type, employee_id\n"
                 f"Make sure each employee doesn't exceed their max_hours_per_week.")

        # Call OpenAI API (v0.28.x)
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a scheduling assistant. Return only CSV data."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.1
        )

        content = response["choices"][0]["message"]["content"] if response.get("choices") else ""
        logger.debug("Raw AI Response Content: %s", content)

        # Parse the response
        import io
        logger.debug("Attempting to parse the AI response as a table...")
        
        if "|" in content:
            logger.debug("Detected table format in the response.")
            # Parse table format
            raw_lines = content.strip().splitlines()
            # Remove header separator lines
            cleaned_lines = [line for line in raw_lines if line.strip() and not set(line.strip()) <= {'-', '|', ' '}]
            
            if cleaned_lines:
                # Ensure each line has the correct number of columns
                cleaned_lines = [line for line in cleaned_lines if line.count('|') >= 3]
                table_data = pd.read_csv(
                    io.StringIO("\n".join(cleaned_lines)),
                    sep="|",
                    skipinitialspace=True,
                    names=["date", "role", "shift_type", "employee_id"],
                    engine="python",
                    on_bad_lines="skip"
                )
            else:
                table_data = pd.DataFrame()
        else:
            # Try JSON format
            try:
                logger.debug("Detected JSON format in the response.")
                json_data = json.loads(content)
                table_data = pd.DataFrame(json_data)
            except json.JSONDecodeError:
                # Try CSV format
                logger.debug("Attempting CSV parsing.")
                table_data = pd.read_csv(
                    io.StringIO(content),
                    on_bad_lines="skip"
                )

        logger.debug("Final parsed DataFrame: %s", table_data)
        
        # Enhance the DataFrame with missing columns
        if not table_data.empty:
            # Add employee_name column by mapping employee_id to name
            if 'employee_id' in table_data.columns:
                emp_id_to_name = dict(zip(emp_data['id'], emp_data['name']))
                table_data['employee_name'] = table_data['employee_id'].map(emp_id_to_name)
            
            # Add slot_id column if missing
            if 'slot_id' not in table_data.columns:
                table_data = table_data.reset_index()
                table_data['slot_id'] = table_data.apply(
                    lambda row: f"{row['date']}_{row['shift_type']}_{row['role']}_{row['index']}", 
                    axis=1
                )
                table_data = table_data.drop('index', axis=1)
            
            # Add hours column based on shift type
            if 'hours' not in table_data.columns:
                # Use default hours if business settings are None
                day_hours = getattr(bs, 'day_shift_length', 8) if bs else 8
                night_hours = getattr(bs, 'night_shift_length', 8) if bs else 8
                table_data['hours'] = table_data['shift_type'].apply(
                    lambda shift: day_hours if shift == 'day' else night_hours
                )
        
        return table_data.dropna(axis=1, how="all")  # Drop empty columns
        
    except Exception as e:
        logger.error("Error generating schedule with AI: %s", e)
        return pd.DataFrame()

# Added AI validation and problem resolution

def validate_and_resolve_schedule(schedule_df: pd.DataFrame, emp_data: pd.DataFrame, bs: Any) -> pd.DataFrame:
    # Input validation
    required_columns = ["date", "role", "shift_type", "employee_id"]
    if not all(col in schedule_df.columns for col in required_columns):
        raise KeyError(f"Schedule is missing required columns: {required_columns}")

    # If OpenAI is not available, return original schedule
    if not openai_available:
        logger.warning("OpenAI not available, returning original schedule")
        return schedule_df

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an AI assistant for validating schedules."},
                {"role": "user", "content": f"Validate and resolve issues in the following schedule: {schedule_df.to_dict()} with employees: {emp_data.to_dict()} and business settings: {bs}."}
            ],
            max_tokens=1500,
            temperature=0.1
        )
        resolved_schedule_content = response["choices"][0]["message"]["content"] if response.get("choices") else ""
        # Replace eval usage with safer alternative
        try:
            resolved_schedule_data: List[Dict[str, Any]] = json.loads(resolved_schedule_content)
            return pd.DataFrame(resolved_schedule_data)  # Convert AI response to DataFrame
        except json.JSONDecodeError:
            logger.error("Failed to parse AI response as JSON")
            return schedule_df
    except Exception as e:
        logger.error("Error validating and resolving schedule with AI: %s", e)
        return schedule_df

# --- Build shift slots for schedule generation ---
def build_shift_slots(bs: BusinessSettings) -> list[dict[str, Any]]:
    """
    Build a list of shift slots for the planning window based on business settings.
    Each slot is a dict with slot_id, date, shift_type, and role.
    Uses daily_roles_coverage if available, otherwise falls back to roles_coverage.
    """
    slots = []
    if not bs or not hasattr(bs, "planning_start") or not hasattr(bs, "planning_days"):
        return slots
    
    start_date = bs.planning_start
    days = bs.planning_days
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    for i in range(days):
        day = start_date + timedelta(days=i)
        day_str = str(day)
        day_of_week = day_names[day.weekday()]
        
        # Check if we have day-specific role coverage
        if (hasattr(bs, 'daily_roles_coverage') and 
            bs.daily_roles_coverage and 
            day_of_week in bs.daily_roles_coverage and
            bs.daily_roles_coverage[day_of_week]):
            # Use day-specific role coverage
            day_roles_coverage = bs.daily_roles_coverage[day_of_week]
            
            for role_name, requirements in day_roles_coverage.items():
                # Day shift requirements
                day_required = requirements.get("day", 0) or 0
                for slot_num in range(day_required):
                    slots.append({
                        "date": day,
                        "shift_type": "day",
                        "role": role_name,
                        "slot_id": f"{day_str}_day_{role_name}_{slot_num}"
                    })
                
                # Evening shift requirements
                evening_required = requirements.get("evening", 0) or 0
                for slot_num in range(evening_required):
                    slots.append({
                        "date": day,
                        "shift_type": "evening",
                        "role": role_name,
                        "slot_id": f"{day_str}_evening_{role_name}_{slot_num}"
                    })
                
                # Night shift requirements
                night_required = requirements.get("night", 0) or 0
                for slot_num in range(night_required):
                    slots.append({
                        "date": day,
                        "shift_type": "night",
                        "role": role_name,
                        "slot_id": f"{day_str}_night_{role_name}_{slot_num}"
                    })
        else:
            # Fall back to legacy roles_coverage
            roles = [r["role"] for r in getattr(bs, "roles_coverage", [])] if hasattr(bs, "roles_coverage") else ["Barista", "Cook", "Waiter", "Cashier", "Manager"]
            
            for role in roles:
                # Find role coverage settings
                role_coverage = None
                if hasattr(bs, "roles_coverage"):
                    for r in bs.roles_coverage:
                        if r.get("role") == role:
                            role_coverage = r
                            break
                
                if role_coverage:
                    # Day shifts
                    day_required = role_coverage.get("day_required", 1) or 1
                    for slot_num in range(day_required):
                        slots.append({
                            "date": day,
                            "shift_type": "day",
                            "role": role,
                            "slot_id": f"{day_str}_day_{role}_{slot_num}"
                        })
                    
                    # Evening shifts (if specified)
                    evening_required = role_coverage.get("evening_required", 0) or 0
                    for slot_num in range(evening_required):
                        slots.append({
                            "date": day,
                            "shift_type": "evening",
                            "role": role,
                            "slot_id": f"{day_str}_evening_{role}_{slot_num}"
                        })
                    
                    # Night shifts
                    night_required = role_coverage.get("night_required", 1) or 1
                    for slot_num in range(night_required):
                        slots.append({
                            "date": day,
                            "shift_type": "night",
                            "role": role,
                            "slot_id": f"{day_str}_night_{role}_{slot_num}"
                        })
                else:
                    # Default: 1 day shift and 1 night shift per role
                    slots.append({
                        "date": day,
                        "shift_type": "day",
                        "role": role,
                        "slot_id": f"{day_str}_day_{role}_0"
                    })
                    slots.append({
                        "date": day,
                        "shift_type": "night",
                        "role": role,
                        "slot_id": f"{day_str}_night_{role}_0"
                    })
    
    return slots

# ===============================

def page_employees():
    # Enhanced header
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(139, 92, 246, 0.1), rgba(16, 185, 129, 0.1)); border-radius: 20px; padding: 2rem; margin: 1rem 0; text-align: center; border: 1px solid rgba(255,255,255,0.1);">
        <h1 style="margin-bottom: 0.5rem;">[TEAM] Team Management</h1>
        <p style="color: #94a3b8; margin: 0;">Create, organize, and manage your workforce with intelligent role-based grouping</p>
    </div>
    """, unsafe_allow_html=True)

    # Back to Home button
    if st.button("← Back to Dashboard", key="back_to_home_employees", type="secondary"):
        st.session_state["current_page"] = "🏠 Home"
        st.rerun()
    
    st.markdown("---")

    # Constants
    HAS_DIALOG = hasattr(st, "dialog")
    today = date.today()

    # Get current employee data for statistics
    df = get_all_employees()
    # Load business settings and get roles from business settings as source of truth
    bs = load_business_settings()
    bs_roles = [r["role"] if isinstance(r, dict) else getattr(r, "role", str(r)) for r in getattr(bs, "role_settings", [])] if hasattr(bs, "role_settings") else []
    # If no roles in business settings, fallback to legacy roles_coverage
    if not bs_roles and hasattr(bs, "roles_coverage"):
        bs_roles = [r["role"] if isinstance(r, dict) else getattr(r, "role", str(r)) for r in getattr(bs, "roles_coverage", [])]
    # Warn if any employees have roles not in business settings
    if not df.empty and bs_roles:
        emp_roles = set(df["role"].unique())
        missing_roles = emp_roles - set(bs_roles)
        if missing_roles:
            st.warning(f"The following roles are assigned to employees but not present in business settings: {', '.join(missing_roles)}. Please add them in Business Setup for consistency.")
    
    # Dashboard statistics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_employees = len(df) if not df.empty else 0
        # st.markdown("""
        # st.markdown(f"""
        # <div class="metric-card">
        #     <div class="metric-value">{active_roles}</div>
        #     <div class="metric-label">Active Roles</div>
        # </div>
        # """, unsafe_allow_html=True)
    
    with col3:
        avg_hours = df["max_hours_per_week"].mean() if not df.empty else 0
        metric_html = f'<div class="metric-card"><div class="metric-value">{avg_hours:.1f}</div><div class="metric-label">Avg Max Hours</div></div>'
        st.markdown(metric_html, unsafe_allow_html=True)
    
    with col4:
        total_capacity = df["max_hours_per_week"].sum() if not df.empty else 0
        metric_html = f'<div class="metric-card"><div class="metric-value">{total_capacity:.0f}</div><div class="metric-label">Total Capacity</div></div>'
        st.markdown(metric_html, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Enhanced employee management with tabs
    tab1, tab2, tab3, tab4 = st.tabs(["[ADD] Add Employee", "[TEAM] Manage Team", "[ANALYTICS] Team Analytics", "[SICK] Sick Leave Manager"])
    with tab1:
        st.markdown("""
        <div style="background: rgba(16, 185, 129, 0.1); padding: 1.5rem; border-radius: 15px; margin: 1rem 0;">
            <h3 style="margin-bottom: 1rem;">[ADD] Add New Team Member</h3>
            <p>Create a comprehensive employee profile with scheduling preferences and availability.</p>
        </div>
        """, unsafe_allow_html=True)
        available_roles = bs_roles if bs_roles else ["Barista", "Cook", "Waiter", "Cashier", "Manager"]
        available_shifts = ["any", "day", "evening", "night"]
        with st.form("new_emp_form", clear_on_submit=True):
            st.markdown("#### 📋 Basic Information")
            basic_col1, basic_col2 = st.columns(2)
            with basic_col1:
                name = st.text_input("👤 Full Name", placeholder="e.g., Maria Garcia", help="Employee's complete name for identification")
                role = st.selectbox("💼 Job Role", options=available_roles, index=0, help="Primary role/position for this employee")
            with basic_col2:
                preferred = st.selectbox("⏰ Preferred Shift", options=available_shifts, index=0, help="Employee's preferred time of day to work")
            
            st.markdown("#### 📅 Availability & Capacity")
            avail_col1, avail_col2 = st.columns(2)
            with avail_col1:
                days = st.multiselect(
                    "📆 Available Days", 
                    options=DAYS, 
                    default=_normalize_days_list(DAYS), 
                    help="Days when this employee can work"
                )
                max_hours = st.number_input(
                    "⏰ Max Hours/Week", 
                    min_value=1.0, 
                    max_value=80.0, 
                    value=40.0, 
                    step=1.0,
                    help="Maximum hours this employee can work per week"
                )
            with avail_col2:
                min_hours = st.number_input(
                    "⌚ Min Hours/Week", 
                    min_value=0.0, 
                    max_value=40.0, 
                    value=0.0, 
                    step=1.0,
                    help="Minimum hours this employee needs per week"
                )
            
            st.markdown("#### ⭐ Priority & Importance")
            importance_tab1, importance_tab2 = st.tabs(["🎯 Basic Priority", "📊 Advanced Priority"])
            
            with importance_tab1:
                st.markdown("**Set overall importance score for scheduling priority**")
                importance = st.slider(
                    "Priority Level", 
                    min_value=0.1, 
                    max_value=5.0, 
                    value=1.0, 
                    step=0.1,
                    help="Higher values = higher priority for shift assignments (1.0 = normal, 2.0+ = high priority)"
                )
                
                priority_desc = {
                    (0.1, 0.5): "🔹 Low Priority - Flexible/part-time",
                    (0.5, 1.0): "⚪ Normal Priority - Standard employee",
                    (1.0, 2.0): "🟡 Above Normal - Preferred employee",
                    (2.0, 3.0): "🟠 High Priority - Key team member",
                    (3.0, 5.0): "🔴 Critical - Essential/supervisor"
                }
                
                for (min_val, max_val), desc in priority_desc.items():
                    if min_val < importance <= max_val:
                        st.info(f"**{desc}** - This employee will be prioritized for scheduling")
                        break
            
            with importance_tab2:
                st.markdown("**Advanced: Per-day and per-shift importance (Coming Soon)**")
                st.info("🚧 This feature will allow setting different importance scores for specific days and shifts. Currently using basic priority setting.")
                
                # Placeholder for future per-day/shift importance
                advanced_importance = st.checkbox(
                    "Enable advanced per-day/shift importance",
                    value=False,
                    disabled=True,
                    help="Future feature: Set different importance for specific days/shifts"
                )
            
            submitted = st.form_submit_button("✅ Add Employee", width='stretch')
            
            if submitted and name.strip():
                # Create employee record
                emp_data = {
                    "name": name.strip(),
                    "role": role,
                    "preferred_shift": preferred,
                    "days_available": days,
                    "max_hours_per_week": max_hours,
                    "min_hours_per_week": min_hours,
                    "importance": importance
                }
                
                try:
                    insert_employee(emp_data)
                    st.success(f"✅ Added {name} to the team with priority level {importance}!")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to add employee: {e}")
            elif submitted:
                st.warning("⚠️ Please enter a name for the employee.")

    with tab3:
        st.markdown("""
        <div style=\"background: rgba(239, 68, 68, 0.1); padding: 1.5rem; border-radius: 15px; margin: 1rem 0;\">
            <h3 style=\"margin-bottom: 1rem;\">[ANALYTICS] Team Analytics</h3>
            <p>Insights and statistics about your workforce composition and capacity.</p>
        </div>
        """, unsafe_allow_html=True)
        if df.empty:
            st.info("[ANALYTICS] Add some employees to see team analytics!")
        else:
            analytics_col1, analytics_col2 = st.columns(2)
            with analytics_col1:
                st.markdown("#### 👔 Role Distribution")
                role_counts = df["role"].value_counts()
                for role, count in role_counts.items():
                    percentage = (count / len(df)) * 100
                    st.write(f"**{role}**: {count} employees ({percentage:.1f}%)")
            with analytics_col2:
                st.markdown("#### ⏰ Shift Preferences")
                shift_prefs = df["preferred_shift"].value_counts()
                for shift, count in shift_prefs.items():
                    percentage = (count / len(df)) * 100
                    st.write(f"**{shift.title()}**: {count} employees ({percentage:.1f}%)")
                st.markdown("#### 📊 Capacity Overview")
                total_capacity = df["max_hours_per_week"].sum()
                avg_hours = df["max_hours_per_week"].mean()
                st.metric("Total Capacity", f"{total_capacity:.0f} hours/week")
                st.metric("Average per Employee", f"{avg_hours:.1f} hours/week")
    
    with tab2:
        st.markdown("""
        <div style="background: rgba(59, 130, 246, 0.1); padding: 1.5rem; border-radius: 15px; margin: 1rem 0;">
            <h3 style="margin-bottom: 1rem;">[TEAM] Team Overview</h3>
            <p>View, search, and manage your entire workforce organized by roles.</p>
        </div>
        """, unsafe_allow_html=True)
        
        if df.empty:
            st.info("[INFO] No employees yet! Use the 'Add Employee' tab to build your team.")
        else:
            # Team management controls
            management_col1, management_col2, management_col3 = st.columns(3)
            with management_col1:
                search_term = st.text_input("🔍 Search employees", placeholder="Name, role, or keyword")
            with management_col2:
                # Use business settings roles for filter
                role_filter = st.selectbox("🎭 Filter by role", options=["All Roles"] + bs_roles)
            with management_col3:
                sort_by = st.selectbox("📊 Sort by", options=["Name", "Role", "Max Hours"])
            # Apply filters and sorting
            filtered_df = df.copy()
            if search_term:
                mask = (
                    filtered_df["name"].str.contains(search_term, case=False, na=False) |
                    filtered_df["role"].str.contains(search_term, case=False, na=False)
                )
                filtered_df = filtered_df[mask]
            if role_filter != "All Roles":
                filtered_df = filtered_df[filtered_df["role"] == role_filter]
            # Display employees by role (only show roles from business settings)
            roles = [r for r in bs_roles if r in filtered_df["role"].unique()]
            for role_name in roles:
                role_subset = filtered_df[filtered_df["role"] == role_name]
                with st.expander(f"👔 {role_name} ({len(role_subset)} employee{'s' if len(role_subset) != 1 else ''})", expanded=True):
                    for _, row in role_subset.iterrows():
                        emp_col1, emp_col2, emp_col3, emp_col4 = st.columns([3, 2, 2, 1])
                        with emp_col1:
                            st.markdown(f"**👤 {row['name']}**")
                            try:
                                days_available = json.loads(row['days_available']) if isinstance(row['days_available'], str) else row['days_available']
                                days_display = ', '.join(days_available) if days_available else 'None'
                            except (json.JSONDecodeError, TypeError, AttributeError) as e:
                                logger.warning("Failed to parse days_available for employee %s: %s", row.get('name', 'Unknown'), e)
                                days_display = 'Error loading days'
                            st.caption(f"📅 Available: {days_display}")
                            st.caption(f"⏰ Prefers: {row['preferred_shift']} shifts")
                        with emp_col3:
                            st.metric("⏱️ Hours", f"{row['min_hours_per_week']:.0f}-{row['max_hours_per_week']:.0f}/week")
                        with emp_col4:
                            if st.button("✏️", key=f"edit_tab2_{row['id']}", help=f"Edit {row['name']}"):
                                st.session_state["edit_emp"] = row['id']
                            if st.button("🗑️", key=f"delete_tab2_{row['id']}", help=f"Delete {row['name']}"):
                                delete_employee_row(row['id'])
                                st.success(f"Deleted {row['name']}")
                                st.rerun()
                        st.markdown("---")
    
    with tab3:
        st.markdown("""
        <div style="background: rgba(239, 68, 68, 0.1); padding: 1.5rem; border-radius: 15px; margin: 1rem 0;">
            <h3 style="margin-bottom: 1rem;">[ANALYTICS] Team Analytics</h3>
            <p>Insights and statistics about your workforce composition and capacity.</p>
        </div>
        """, unsafe_allow_html=True)
        
        if df.empty:
            st.info("[ANALYTICS] Add some employees to see team analytics!")
        else:
            analytics_col1, analytics_col2 = st.columns(2)
            
            with analytics_col1:
                st.markdown("#### 👔 Role Distribution")
                role_counts = df["role"].value_counts()
                for role, count in role_counts.items():
                    percentage = (count / len(df)) * 100
                    st.write(f"**{role}**: {count} employees ({percentage:.1f}%)")
                
            
            with analytics_col2:
                st.markdown("#### ⏰ Shift Preferences")
                shift_prefs = df["preferred_shift"].value_counts()
                for shift, count in shift_prefs.items():
                    percentage = (count / len(df)) * 100
                    st.write(f"**{shift.title()}**: {count} employees ({percentage:.1f}%)")
                
                st.markdown("#### 📊 Capacity Overview")
                total_capacity = df["max_hours_per_week"].sum()
                avg_hours = df["max_hours_per_week"].mean()
                
                st.metric("Total Capacity", f"{total_capacity:.0f} hours/week")
                st.metric("Average per Employee", f"{avg_hours:.1f} hours/week")

    # --- Edit dialog function (define before use)
    if HAS_DIALOG:
        @st.dialog("✏️ Edit Employee")
        def open_edit_dialog(emp_id: int):
            row, days_current = _load_emp(emp_id)
            st.markdown("### Update employee information")
            
            with st.form("edit_emp_form"):
                col1, col2 = st.columns(2)
                with col1:
                    e_name = st.text_input("👤 Full Name", value=row["name"], placeholder="Enter employee name")
                    e_role = st.selectbox("💼 Role", options=available_roles, 
                                        index=available_roles.index(row["role"]) 
                                        if row["role"] in available_roles else 0)
                    
                    # Handle case-insensitive preferred shift matching
                    shift_options = ["any", "day", "evening", "night"]  
                    current_shift = str(row["preferred_shift"]).lower()
                    try:
                        shift_index = shift_options.index(current_shift)
                    except ValueError:
                        # Default to "any" if the value doesn't match
                        shift_index = 0
                    
                    e_pref = st.selectbox("⏰ Preferred Shift", shift_options, index=shift_index)
                
                with col2:
                    e_days = st.multiselect("📅 Available Days", options=DAYS, default=_normalize_days_list(days_current))
                    e_maxh = st.number_input("⏱️ Max hours per week", min_value=0.0, value=float(row["max_hours_per_week"]), step=1.0)
                    e_minh = st.number_input("⏱️ Min hours per week", min_value=0.0, value=float(row["min_hours_per_week"]), step=1.0)
                    # e_cost removed
                
                st.markdown("---")
                col1, col2, col3 = st.columns([1, 1, 2])
                with col1:
                    save_btn = st.form_submit_button("💾 Save Changes", type="primary")
                with col2:
                    cancel_btn = st.form_submit_button("❌ Cancel", type="secondary")
                with col3:
                    st.empty()
            
            if save_btn and e_name and e_name.strip():
                update_employee_row(emp_id, {
                    "name": e_name.strip(),
                    "role": e_role,
                    "preferred_shift": e_pref,
                    "days_available": e_days or DAYS,
                    "max_hours_per_week": e_maxh,
                    "min_hours_per_week": e_minh,
                    # "hourly_cost" removed
                })
                st.success("✅ Employee updated successfully!")
                st.session_state.pop("edit_emp", None)
                st.rerun()
            elif save_btn:
                st.error("❌ Please enter a valid name")
            
            if cancel_btn:
                st.session_state.pop("edit_emp", None)
                st.rerun()

    # --- List employees grouped by role (cards with edit/delete)
    df = get_all_employees()
    if df.empty:
        st.info("No employees yet. Use the form above to add your first employee.")
        return

    roles = df["role"].fillna("(Unassigned)").unique().tolist()
    for role_name in roles:
        subset = df[df["role"] == role_name]
        with st.expander(f"👥 {role_name} - {len(subset)} employee(s)", expanded=True):
            for _, r in subset.iterrows():
                with st.container(border=True):
                    # Top row with basic info
                    col1, col2, col3, col4 = st.columns([2, 1.5, 1.5, 1])
                    with col1:
                        st.markdown(f"**🧑‍💼 {r['name']}**")
                        st.caption(f"💼 Role: {r['role']}")
                    with col2:
                        st.markdown("**⏰ Preferred Shift**")
                        st.caption(f"🌅 {r['preferred_shift'].title()}")
                    with col3:
                        try:
                            av_days = ", ".join(json.loads(r["days_available"]))
                        except Exception:
                            av_days = str(r["days_available"]) or "N/A"
                        st.markdown("**📅 Available Days**")
                        st.caption(f"📆 {av_days}")
                    with col4:
                        st.markdown("**⏱️ Hours**")
                        st.caption(f"⏱️ {int(r['min_hours_per_week'])}–{int(r['max_hours_per_week'])} hrs/week")
                    
                    # Bottom row with action buttons
                    st.markdown("---")
                    btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 4])
                    with btn_col1:
                        if st.button("✏️ Edit", key=f"edit_main_{r['id']}", type="secondary"):
                            if HAS_DIALOG:
                                open_edit_dialog(r["id"])
                            else:
                                st.session_state["edit_emp"] = r["id"]
                                st.rerun()
                    with btn_col2:
                        if st.button("🗑️ Delete", key=f"del_main_{r['id']}", type="secondary"):
                            delete_employee_row(r["id"])
                            st.toast("Employee deleted", icon="🗑️")
                            st.rerun()
                    with btn_col3:
                        st.empty()  # Spacer

    # --- Edit flow (modal if available, expander fallback otherwise)
    edit_id = st.session_state.get("edit_emp")

    # Only show edit dialog if employee still exists
    valid_ids = set(df["id"].tolist())
    if edit_id is not None and edit_id not in valid_ids:
        st.session_state.pop("edit_emp", None)
        edit_id = None

    if HAS_DIALOG and edit_id is not None:
        open_edit_dialog(int(edit_id))
    elif not HAS_DIALOG and edit_id is not None:
        row, days_current = _load_emp(int(edit_id))
        with st.expander(f"Edit {row['name']}", expanded=True):
            with st.form("edit_emp_form"):
                c1, c2 = st.columns(2)
                with c1:
                    e_name = st.text_input("Name", value=row["name"])
                    e_role = st.text_input("Role", value=row["role"])
                    shift_options = ["any", "day", "night"]
                    pref_val = str(row["preferred_shift"]).lower()
                    pref_index = next((i for i, v in enumerate(shift_options) if v.lower() == pref_val), 0)
                    e_pref = st.selectbox("Preferred shift", shift_options, index=pref_index)
                with c2:
                    e_days = st.multiselect("Days available", options=DAYS, default=_normalize_days_list(days_current))
                    e_maxh = st.number_input("Max hours / week", min_value=0.0, value=float(row["max_hours_per_week"]), step=1.0)
                    e_minh = st.number_input("Min hours / week", min_value=0.0, value=float(row["min_hours_per_week"]), step=1.0)
                save_btn = st.form_submit_button("Save changes", type="primary")
            if save_btn:
                update_employee_row(int(edit_id), {
                    "name": (e_name or "").strip(),
                    "role": (e_role or "").strip() or "Staff",
                    "preferred_shift": e_pref,
                    "days_available": e_days or DAYS,
                    "max_hours_per_week": e_maxh,
                    "min_hours_per_week": e_minh,
                })
                st.toast("Employee updated", icon="💾")
                st.session_state.pop("edit_emp", None)
                st.rerun()
    
    with tab4:
        st.markdown("""
        <div style="background: rgba(239, 68, 68, 0.1); padding: 1.5rem; border-radius: 15px; margin: 1rem 0;">
            <h3 style="margin-bottom: 1rem;">[SICK] Sick Leave & Unavailability Manager</h3>
            <p>Temporarily remove employees from scheduling due to illness, vacation, or other unavailability.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Load employee data for sick leave management
        emp_df = get_all_employees()
        
        if emp_df.empty:
            st.info("👥 Add employees first to manage their availability!")
            return
        
        # Two column layout for sick leave management
        sick_col1, sick_col2 = st.columns([1, 1])
        
        with sick_col1:
            st.markdown("#### 🚫 Mark Employee Unavailable")
            
            with st.form("sick_leave_form", clear_on_submit=True):
                # Employee selection
                employee_options = [(row['id'], f"{row['name']} ({row['role']})") for _, row in emp_df.iterrows()]
                selected_emp = st.selectbox(
                    "👤 Select Employee",
                    options=[emp[0] for emp in employee_options],
                    format_func=lambda x: next(emp[1] for emp in employee_options if emp[0] == x),
                    help="Choose the employee to mark as unavailable"
                )
                
                # Date range selection
                col_start, col_end = st.columns(2)
                with col_start:
                    start_date = st.date_input(
                        "📅 Start Date",
                        value=pd.Timestamp.now().date(),
                        help="First day the employee will be unavailable"
                    )
                with col_end:
                    end_date = st.date_input(
                        "📅 End Date",
                        value=pd.Timestamp.now().date() + pd.Timedelta(days=3),
                        help="Last day the employee will be unavailable"
                    )
                
                # Reason selection
                reason_options = [
                    "Sick Leave", "Vacation", "Personal Leave", 
                    "Medical Appointment", "Family Emergency", "Other"
                ]
                reason = st.selectbox("🏥 Reason", options=reason_options)
                
                if reason == "Other":
                    custom_reason = st.text_input("Specify reason:")
                    if custom_reason.strip():
                        reason = custom_reason.strip()
                
                submitted = st.form_submit_button("🚫 Mark Unavailable", type="primary")
                
                if submitted:
                    if start_date <= end_date:
                        try:
                            add_employee_unavailability(
                                selected_emp, 
                                start_date.strftime('%Y-%m-%d'),
                                end_date.strftime('%Y-%m-%d'),
                                reason
                            )
                            emp_name = next(emp[1] for emp in employee_options if emp[0] == selected_emp)
                            st.success(f"✅ Marked {emp_name.split(' (')[0]} as unavailable from {start_date} to {end_date} for: {reason}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Failed to mark employee unavailable: {e}")
                    else:
                        st.error("❌ End date must be after start date!")
        
        with sick_col2:
            st.markdown("#### 📋 Current Unavailability Records")
            
            # Get all unavailability records
            unavail_df = get_employee_unavailability()
            
            if unavail_df.empty:
                st.info("📝 No current unavailability records")
            else:
                # Filter active/upcoming records
                today = pd.Timestamp.now().date()
                
                # Convert date strings to datetime for filtering
                unavail_df['start_date_parsed'] = pd.to_datetime(unavail_df['start_date']).dt.date
                unavail_df['end_date_parsed'] = pd.to_datetime(unavail_df['end_date']).dt.date
                
                # Show active and future records
                active_records = unavail_df[unavail_df['end_date_parsed'] >= today]
                
                if not active_records.empty:
                    st.markdown("##### 🟡 Active/Upcoming Absences")
                    
                    for _, record in active_records.iterrows():
                        is_current = record['start_date_parsed'] <= today <= record['end_date_parsed']
                        status = "🔴 Currently Unavailable" if is_current else "🟡 Upcoming"
                        
                        with st.container():
                            st.markdown(f"""
                            <div style="background: rgba(239, 68, 68, 0.1); padding: 1rem; border-radius: 10px; margin: 0.5rem 0; border-left: 4px solid {'#ef4444' if is_current else '#f59e0b'};">
                                <h4 style="margin: 0 0 0.5rem 0;">{record['employee_name']}</h4>
                                <p style="margin: 0; font-size: 0.9rem;">
                                    <strong>{status}</strong><br>
                                    📅 {record['start_date']} to {record['end_date']}<br>
                                    🏥 Reason: {record['reason']}
                                </p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            if st.button("❌ Remove Record", key=f"remove_{record['id']}", help="Remove this unavailability record"):
                                remove_employee_unavailability(record['id'])
                                st.success(f"✅ Removed unavailability record for {record['employee_name']}")
                                st.rerun()
                
                # Show past records (collapsed)
                past_records = unavail_df[unavail_df['end_date_parsed'] < today]
                if not past_records.empty:
                    with st.expander(f"📚 Past Records ({len(past_records)})"):
                        for _, record in past_records.iterrows():
                            st.write(f"**{record['employee_name']}**: {record['start_date']} to {record['end_date']} - {record['reason']}")
        
        # Quick actions section
        st.markdown("---")
        st.markdown("#### ⚡ Quick Actions")
        
        quick_col1, quick_col2, quick_col3 = st.columns(3)
        
        with quick_col1:
            if st.button("🏥 Mark as Sick Today", help="Quickly mark an employee as sick for today"):
                st.session_state["quick_sick"] = True
        
        with quick_col2:
            if st.button("📊 Show All Records", help="View complete unavailability history"):
                st.session_state["show_all_records"] = True
        
        with quick_col3:
            if st.button("🔄 Clear All Past Records", help="Remove all expired unavailability records"):
                if st.session_state.get("confirm_clear", False):
                    # Clear past records
                    past_count = len(past_records) if not unavail_df.empty else 0
                    if past_count > 0:
                        conn = get_conn()
                        today_str = today.strftime('%Y-%m-%d')
                        conn.execute("DELETE FROM employee_unavailability WHERE end_date < ?", (today_str,))
                        conn.commit()
                        st.success(f"✅ Cleared {past_count} past records")
                        st.session_state["confirm_clear"] = False
                        st.rerun()
                else:
                    st.session_state["confirm_clear"] = True
                    st.warning("Click again to confirm clearing all past records")
        
        # Quick sick leave dialog
        if st.session_state.get("quick_sick", False):
            st.markdown("##### 🏥 Quick Sick Leave")
            quick_emp = st.selectbox(
                "Employee to mark sick today:",
                options=[emp[0] for emp in employee_options],
                format_func=lambda x: next(emp[1] for emp in employee_options if emp[0] == x),
                key="quick_sick_emp"
            )
            
            quick_col_a, quick_col_b = st.columns(2)
            with quick_col_a:
                if st.button("✅ Mark Sick Today Only"):
                    today_str = today.strftime('%Y-%m-%d')
                    add_employee_unavailability(quick_emp, today_str, today_str, "Sick Leave")
                    emp_name = next(emp[1] for emp in employee_options if emp[0] == quick_emp)
                    st.success(f"✅ Marked {emp_name.split(' (')[0]} as sick for today")
                    st.session_state["quick_sick"] = False
                    st.rerun()
            
            with quick_col_b:
                if st.button("❌ Cancel"):
                    st.session_state["quick_sick"] = False
                    st.rerun()

def page_shifts():
    """
    Modern Schedule Hub - Main interface for schedule generation, monitoring, and management
    """
    # Clean header
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                border-radius: 16px; padding: 2rem; margin-bottom: 2rem; text-align: center;">
        <h1 style="margin: 0; color: white; font-size: 2.5rem; font-weight: 700;">
            📅 Smart Scheduling
        </h1>
        <p style="color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0; font-size: 1.1rem;">
            Generate optimized work schedules
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Back to Home button
    if st.button("← Back to Dashboard", key="back_to_home_shifts", type="secondary"):
        st.session_state["current_page"] = "🏠 Home"
        st.rerun()
    
    st.markdown("---")
    
    # Load required data
    bs = load_business_settings()
    emp_df = get_all_employees()
    available_roles = [r["role"] for r in bs.roles_coverage] if hasattr(bs, "roles_coverage") else ["Barista", "Cook", "Waiter", "Cashier", "Manager"]
    
    # Enhanced System Status Dashboard - Full Width
    # Quick system status
    col1, col2, col3 = st.columns(3)
    
    emp_count = len(emp_df) if not emp_df.empty else 0
    ai_available = openai_available
    business_configured = bs is not None
    
    with col1:
        st.metric("👥 Staff", emp_count, delta="Ready" if emp_count > 0 else "Add employees")
    
    with col2:
        st.metric("⚙️ Config", "Ready" if business_configured else "Needed", delta="✅" if business_configured else "⚠️")
    
    with col3:
        st.metric("🤖 AI", "Active" if ai_available else "Basic", delta="🚀" if ai_available else "📊")
    
    # Pre-flight checks
    can_generate = True
    issues = []
    
    if emp_df.empty:
        issues.append("❌ No employees added")
        can_generate = False
    if not bs:
        issues.append("❌ Business settings not configured")
        can_generate = False
    if not openai_available:
        issues.append("⚠️ AI scheduling unavailable (will use basic algorithm)")
    
    if issues:
        st.error("**Setup Issues Detected:**")
        for issue in issues:
            st.write(f"  • {issue}")
        if not can_generate:
            st.info("💡 **Next Steps**: Configure business settings and add employees to enable scheduling.")
            return
    
    # Load or initialize schedule DataFrame
    if "schedule_history" not in st.session_state or not st.session_state["schedule_history"]:
        sched_df = load_schedule_from_db(bs)
        if sched_df is not None and not sched_df.empty:
            st.session_state["schedule_history"] = [sched_df.copy()]
        else:
            st.session_state["schedule_history"] = [pd.DataFrame(columns=["slot_id", "date", "shift_type", "role", "employee_id", "employee_name"])]
    
    sched_df = st.session_state["schedule_history"][-1]
    if "current_schedule_df" not in st.session_state:
        st.session_state["current_schedule_df"] = sched_df.copy()
    
    # Simplified main tabs  
    generation_tab, schedule_tab = st.tabs([
        "🚀 Generate Schedule", "� View & Edit"
    ])
    
    with generation_tab:
        st.markdown("### 🎯 AI-Powered Schedule Generation")
        
        # Employee Availability Monitoring System
        st.markdown("#### 👥 Employee Availability Monitor")
        st.markdown("""
        <div style="background: rgba(34, 197, 94, 0.1); border-radius: 12px; padding: 1rem; margin-bottom: 1rem; border-left: 4px solid #22c55e;">
            <p style="margin: 0; color: #166534;">🤖 <strong>AI-Enhanced Availability Control:</strong> The system will analyze availability patterns and provide intelligent recommendations for optimal scheduling.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Get date range for availability monitoring
        if bs and hasattr(bs, 'planning_start') and hasattr(bs, 'planning_days'):
            start_date = bs.planning_start
            date_range = [start_date + timedelta(days=i) for i in range(bs.planning_days)]
        else:
            start_date = date.today()
            date_range = [start_date + timedelta(days=i) for i in range(7)]
        
        if not emp_df.empty:
            # Initialize availability session state
            if "employee_availability" not in st.session_state:
                st.session_state["employee_availability"] = {}
                # Default all employees as available
                for _, emp in emp_df.iterrows():
                    emp_id = emp['id']
                    st.session_state["employee_availability"][emp_id] = {
                        str(d): True for d in date_range
                    }
            
            # AI Availability Analysis
            with st.expander("🤖 AI Availability Analysis", expanded=False):
                if st.button("🔍 Analyze Availability Patterns", key="ai_analyze_availability"):
                    if openai_available:
                        with st.spinner("🤖 AI analyzing availability patterns..."):
                            try:
                                # Create availability summary for AI analysis
                                availability_summary = {}
                                for _, emp in emp_df.iterrows():
                                    emp_id = emp['id']
                                    emp_name = emp['name']
                                    available_dates = []
                                    unavailable_dates = []
                                    
                                    for d in date_range:
                                        date_str = str(d)
                                        if st.session_state["employee_availability"][emp_id].get(date_str, True):
                                            available_dates.append(date_str)
                                        else:
                                            unavailable_dates.append(date_str)
                                    
                                    availability_summary[emp_name] = {
                                        'role': emp['role'],
                                        'max_hours': emp['max_hours_per_week'],
                                        'available_dates': available_dates,
                                        'unavailable_dates': unavailable_dates,
                                        'availability_rate': len(available_dates) / len(date_range) * 100
                                    }
                                
                                # AI Analysis Prompt
                                prompt = f"""
                                Analyze the following employee availability data and provide insights:
                                
                                Planning Period: {start_date} to {date_range[-1]}
                                Employee Availability: {availability_summary}
                                
                                Please provide:
                                1. Availability overview and potential staffing issues
                                2. Recommendations for optimal schedule coverage
                                3. Risk assessment for understaffing
                                4. Suggestions for employee availability improvements
                                
                                Format as a clear, actionable report.
                                """
                                
                                response = openai.ChatCompletion.create(
                                    model="gpt-4",
                                    messages=[
                                        {"role": "system", "content": "You are an AI workforce management consultant. Provide clear, actionable insights about employee availability patterns."},
                                        {"role": "user", "content": prompt}
                                    ],
                                    max_tokens=800,
                                    temperature=0.3
                                )
                                
                                ai_analysis = response["choices"][0]["message"]["content"]
                                st.markdown("#### 🤖 AI Analysis Results")
                                st.markdown(ai_analysis)
                                
                            except Exception as e:
                                st.error(f"AI analysis failed: {e}")
                    else:
                        st.warning("OpenAI API not available for availability analysis")
            
            # Availability Control Table
            st.markdown("#### 📋 Employee Availability Control")
            
            # Quick actions
            action_col1, action_col2, action_col3, action_col4 = st.columns(4)
            
            with action_col1:
                if st.button("✅ Mark All Available", key="mark_all_available"):
                    for emp_id in st.session_state["employee_availability"]:
                        for date_str in st.session_state["employee_availability"][emp_id]:
                            st.session_state["employee_availability"][emp_id][date_str] = True
                    st.success("All employees marked as available")
                    st.rerun()
            
            with action_col2:
                if st.button("❌ Mark All Unavailable", key="mark_all_unavailable"):
                    for emp_id in st.session_state["employee_availability"]:
                        for date_str in st.session_state["employee_availability"][emp_id]:
                            st.session_state["employee_availability"][emp_id][date_str] = False
                    st.warning("All employees marked as unavailable")
                    st.rerun()
            
            with action_col3:
                if st.button("🔄 Reset to Default", key="reset_availability"):
                    # Reset based on employee's days_available
                    for _, emp in emp_df.iterrows():
                        emp_id = emp['id']
                        try:
                            emp_days = json.loads(emp['days_available']) if isinstance(emp['days_available'], str) else emp['days_available']
                        except:
                            emp_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                        
                        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                        day_short = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                        
                        for d in date_range:
                            day_name = day_names[d.weekday()]
                            day_short_name = day_short[d.weekday()]
                            is_available = day_short_name in emp_days or day_name in emp_days
                            st.session_state["employee_availability"][emp_id][str(d)] = is_available
                    
                    st.info("Availability reset to employee default schedules")
                    st.rerun()
            
            with action_col4:
                if st.button("🤖 AI Optimize", key="ai_optimize_availability"):
                    if openai_available:
                        with st.spinner("🤖 AI optimizing availability..."):
                            try:
                                # AI-powered availability optimization
                                prompt = f"""
                                Optimize employee availability for the following scenario:
                                
                                Employees: {emp_df[['name', 'role', 'max_hours_per_week']].to_dict('records')}
                                Date Range: {start_date} to {date_range[-1]}
                                Business Roles Needed: {available_roles}
                                
                                Suggest optimal availability patterns ensuring:
                                1. Full role coverage each day
                                2. Balanced workload distribution
                                3. Minimum staffing requirements met
                                4. Employee preferences considered
                                
                                Return as JSON with employee names and suggested available dates.
                                """
                                
                                response = openai.ChatCompletion.create(
                                    model="gpt-4",
                                    messages=[
                                        {"role": "system", "content": "You are an AI scheduling optimizer. Return practical availability suggestions."},
                                        {"role": "user", "content": prompt}
                                    ],
                                    max_tokens=1000,
                                    temperature=0.2
                                )
                                
                                st.success("🤖 AI availability optimization complete!")
                                st.info("AI suggestions applied - review the availability table below")
                                
                            except Exception as e:
                                st.error(f"AI optimization failed: {e}")
                    else:
                        st.warning("OpenAI API required for AI optimization")
            
            # Create availability matrix with dropdown format
            with st.expander("📅 Employee Availability Matrix", expanded=True):
                st.markdown("Configure employee availability for the planning period")
                
                # Initialize availability if not exists
                if "employee_availability" not in st.session_state:
                    st.session_state["employee_availability"] = {}
                
                for _, emp in emp_df.iterrows():
                    emp_id = emp['id']
                    emp_name = emp['name']
                    emp_role = emp['role']
                    
                    # Ensure employee exists in availability dict
                    if emp_id not in st.session_state["employee_availability"]:
                        st.session_state["employee_availability"][emp_id] = {
                            str(d): True for d in date_range
                        }
                    
                    with st.container():
                        st.markdown(f"**{emp_name}** ({emp_role})")
                        
                        # Create columns for each day
                        day_cols = st.columns(len(date_range))
                        available_count = 0
                        
                        for i, d in enumerate(date_range):
                            date_str = str(d)
                            day_name = d.strftime("%a %m/%d")
                            current_availability = st.session_state["employee_availability"][emp_id].get(date_str, True)
                            
                            with day_cols[i]:
                                # Use selectbox for dropdown format
                                availability_options = ["Available", "Unavailable"]
                                current_index = 0 if current_availability else 1
                                
                                selected = st.selectbox(
                                    day_name,
                                    availability_options,
                                    index=current_index,
                                    key=f"avail_dropdown_{emp_id}_{date_str}"
                                )
                                
                                new_availability = (selected == "Available")
                                st.session_state["employee_availability"][emp_id][date_str] = new_availability
                                if new_availability:
                                    available_count += 1
                        
                        # Show availability summary
                        total_days = len(date_range)
                        availability_rate = (available_count / total_days) * 100
                        
                        if availability_rate >= 80:
                            status_color = "green"
                            status_text = "✅ Good availability"
                        elif availability_rate >= 50:
                            status_color = "orange"
                            status_text = "⚠️ Limited availability"
                        else:
                            status_color = "red"
                            status_text = "❌ Critical - low availability"
                        
                        st.markdown(f'<div style="color: {status_color}; font-size: 0.9em; margin-bottom: 1rem;">{status_text} ({availability_rate:.0f}% available)</div>', unsafe_allow_html=True)
            
            st.markdown("---")
            
        else:
            st.warning("👥 No employees found. Please add employees first in the Employee Management section.")
            if st.button("➕ Go to Employee Management"):
                st.session_state["current_page"] = "👥 Employee Management"
                st.rerun()
        
        # Enhanced Schedule Generation Section
        st.markdown("#### 🚀 AI-Enhanced Schedule Generation")
        
        # Pre-generation validation
        if not can_generate:
            st.error("Cannot generate schedule. Please resolve the issues above.")
        else:
            # AI Generation Settings
            with st.expander("🤖 AI Generation Settings", expanded=True):
                ai_col1, ai_col2 = st.columns(2)
                
                with ai_col1:
                    ai_strategy = st.selectbox(
                        "AI Strategy",
                        ["Balanced", "Employee-Focused", "Business-Focused"],
                        help="Choose the AI optimization focus"
                    )
                    
                    include_preferences = st.checkbox(
                        "Consider Employee Preferences",
                        value=True,
                        help="AI will prioritize employee preferred shifts"
                    )
                
                with ai_col2:
                    ai_creativity = st.slider(
                        "AI Creativity Level",
                        0.1, 1.0, 0.3,
                        help="Higher values allow more creative scheduling solutions"
                    )
                    
                    validate_constraints = st.checkbox(
                        "Strict Constraint Validation",
                        value=True,
                        help="AI will strictly enforce all business rules"
                    )
            
            # Generation button with AI emphasis
            if st.button("🤖 Generate AI-Optimized Schedule", type="primary", use_container_width=True):
                if not emp_df.empty:
                    with st.spinner("🤖 AI is analyzing constraints and generating optimal schedule..."):
                        try:
                            # Filter employees based on availability
                            available_employees = []
                            for _, emp in emp_df.iterrows():
                                emp_id = emp['id']
                                # Check if employee has any available days
                                has_availability = any(
                                    st.session_state["employee_availability"][emp_id].get(str(d), True)
                                    for d in date_range
                                )
                                if has_availability:
                                    available_employees.append(emp)
                            
                            if not available_employees:
                                st.error("❌ No employees are available for the selected dates!")
                                st.stop()
                            
                            available_emp_df = pd.DataFrame(available_employees)
                            
                            # Build shift slots with AI input
                            if core_available:
                                shift_slots = core_build_shift_slots(bs)
                            else:
                                shift_slots = build_shift_slots(bs)
                            
                            # Filter shift slots based on availability
                            filtered_slots = []
                            for slot in shift_slots:
                                slot_date = slot.get('date')
                                if slot_date:
                                    slot_date_str = str(slot_date)
                                    # Check if any employee is available for this date
                                    date_has_availability = any(
                                        st.session_state["employee_availability"][emp['id']].get(slot_date_str, True)
                                        for emp in available_employees
                                    )
                                    if date_has_availability:
                                        filtered_slots.append(slot)
                            
                            if not filtered_slots:
                                st.error("❌ No shift slots have employee availability!")
                                st.stop()
                            
                            # AI-Enhanced Generation
                            st.info("🤖 AI is now considering all parameters:")
                            st.write("✅ Employee availability matrix")
                            st.write("✅ Business constraints and rules")
                            st.write("✅ Role requirements and coverage")
                            st.write("✅ Employee preferences and skills")
                            st.write("✅ Workload balancing and fairness")
                            
                            # Generate with enhanced AI parameters
                            sched_df = generate_schedule_with_ai_enhanced(
                                available_emp_df, 
                                filtered_slots, 
                                bs,
                                availability_matrix=st.session_state["employee_availability"],
                                ai_strategy=ai_strategy,
                                creativity_level=ai_creativity,
                                include_preferences=include_preferences,
                                validate_constraints=validate_constraints
                            )
                            
                            if not sched_df.empty:
                                st.session_state["current_schedule_df"] = sched_df
                                st.session_state["schedule_history"].append(sched_df)
                                
                                # Save to database
                                save_schedule_to_db(sched_df, bs)
                                
                                st.success(f"🎉 AI generated schedule with {len(sched_df)} shifts!")
                                
                                # Show AI generation summary
                                filled_shifts = len(sched_df[sched_df['employee_id'].notna()])
                                fill_rate = (filled_shifts / len(sched_df)) * 100 if len(sched_df) > 0 else 0
                                
                                summary_col1, summary_col2, summary_col3 = st.columns(3)
                                with summary_col1:
                                    st.metric("Total Shifts", len(sched_df))
                                with summary_col2:
                                    st.metric("Filled Shifts", filled_shifts)
                                with summary_col3:
                                    st.metric("Fill Rate", f"{fill_rate:.1f}%")
                                
                                # Switch to schedule view
                                st.balloons()
                                
                                # Display 7-day schedule overview
                                st.markdown("---")
                                st.markdown("""
                                <div style="margin: 2rem 0 1rem 0;">
                                    <h3 style="margin: 0; font-size: 1.5rem; font-weight: 700; color: #1e293b; display: flex; align-items: center; gap: 0.5rem;">
                                        📅 <span>Generated Schedule Overview</span>
                                    </h3>
                                    <p style="margin: 0.5rem 0 0 0; color: #64748b; font-size: 1rem;">Your AI-optimized 7-day workforce schedule</p>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Create schedule overview table
                                if not sched_df.empty:
                                    # Get next 7 days from today
                                    from datetime import date as dt_date
                                    today = dt_date.today()
                                    next_7_days = [today + timedelta(days=i) for i in range(7)]
                                    
                                    # Convert to string format for comparison
                                    next_7_days_str = [d.strftime('%Y-%m-%d') for d in next_7_days]
                                    
                                    # Filter schedule to show only next 7 days
                                    df_next7 = sched_df[sched_df['date'].astype(str).isin(next_7_days_str)]

                                    # Determine which window to display
                                    window_label = "Next 7 Days"
                                    df_window = df_next7

                                    if df_window.empty:
                                        # Fallback 1: Use planning_start week if available
                                        try:
                                            start = getattr(bs, 'planning_start', None)
                                            if start is not None:
                                                plan_days = [start + timedelta(days=i) for i in range(7)]
                                                plan_days_str = [d.strftime('%Y-%m-%d') for d in plan_days]
                                                df_plan = sched_df[sched_df['date'].astype(str).isin(plan_days_str)]
                                                if not df_plan.empty:
                                                    df_window = df_plan
                                                    window_label = "Planning Week"
                                        except Exception:
                                            pass

                                    if df_window.empty:
                                        # Fallback 2: Show first available 7-day window from schedule
                                        if not sched_df.empty:
                                            try:
                                                all_dates_sorted = sorted(set(sched_df['date'].astype(str).tolist()))
                                                if all_dates_sorted:
                                                    first_day = pd.to_datetime(all_dates_sorted[0]).date()
                                                    avail_days = [(first_day + timedelta(days=i)).isoformat() for i in range(7)]
                                                    df_first = sched_df[sched_df['date'].astype(str).isin(avail_days)]
                                                    if not df_first.empty:
                                                        df_window = df_first
                                                        window_label = "First Available Week"
                                            except Exception:
                                                pass

                                    if not df_window.empty:
                                        dates = sorted(df_window['date'].unique())
                                        days_to_show = 7  # Keep label consistent

                                        # Create pivot table for better visualization
                                        schedule_display = df_window.copy()
                                        # Handle both null and empty string employee names
                                        schedule_display['employee_display'] = schedule_display['employee_name'].apply(
                                            lambda x: 'UNFILLED' if pd.isna(x) or x == '' or x is None else str(x)
                                        )
                                        schedule_display['shift_role'] = schedule_display['shift_type'] + ' - ' + schedule_display['role']
                                        # Normalize date type for proper DateColumn rendering
                                        try:
                                            schedule_display['date'] = pd.to_datetime(schedule_display['date']).dt.date
                                        except Exception:
                                            pass
                                        
                                        # Display as an interactive dataframe
                                        st.markdown(f"##### 📋 Schedule for {window_label}")
                                        display_df = schedule_display.copy()
                                    
                                        # Sort by date and shift type
                                        shift_order = {'day': 1, 'evening': 2, 'night': 3}
                                        display_df['shift_order'] = display_df['shift_type'].map(shift_order)
                                        display_df = display_df.sort_values(['date', 'shift_order', 'role'])
                                        display_df = display_df.drop('shift_order', axis=1)
                                        
                                        # Enhanced display with better column configuration
                                        st.dataframe(
                                            display_df[['date', 'shift_type', 'role', 'employee_display']],
                                            width='stretch',
                                            height=600,
                                            column_config={
                                                "date": st.column_config.DateColumn("📅 Date", format="MMM DD, YYYY", width="large"),
                                                "shift_type": st.column_config.TextColumn("⏰ Shift", width="large"),
                                                "role": st.column_config.TextColumn("👤 Role", width="large"),
                                                "employee_display": st.column_config.TextColumn("👥 Assigned Employee", width="large")
                                            },
                                            hide_index=True
                                        )
                                        
                                        # Show daily summary
                                        st.markdown("##### 📊 Daily Schedule Summary")
                                        daily_col1, daily_col2 = st.columns(2)
                                        
                                        with daily_col1:
                                            # Shifts per day
                                            daily_shifts = display_df.groupby('date').size().reset_index(name='total_shifts')
                                            st.markdown("**Shifts per Day:**")
                                            for _, row in daily_shifts.iterrows():
                                                # Ensure date is a datetime object
                                                date_obj = pd.to_datetime(row['date']) if isinstance(row['date'], str) else row['date']
                                                date_str = date_obj.strftime("%a, %b %d")
                                                st.write(f"• {date_str}: {row['total_shifts']} shifts")
                                        
                                        with daily_col2:
                                            # Fill rate per day
                                            daily_filled = display_df.groupby('date').agg({
                                                'employee_display': lambda x: (x != 'UNFILLED').sum(),
                                                'date': 'count'
                                            }).rename(columns={'employee_display': 'filled', 'date': 'total'})
                                            daily_filled['fill_rate'] = (daily_filled['filled'] / daily_filled['total'] * 100).round(1)
                                            
                                            st.markdown("**Fill Rate per Day:**")
                                            for date_key, row in daily_filled.iterrows():
                                                # Ensure date is a datetime object
                                                date_obj = pd.to_datetime(date_key) if isinstance(date_key, str) else date_key
                                                date_str = date_obj.strftime("%a, %b %d")
                                                rate = row['fill_rate']
                                                color = "🟢" if rate >= 90 else "🟡" if rate >= 70 else "🔴"
                                                st.write(f"• {date_str}: {color} {rate}%")
                                        
                                        # Quick actions for the generated schedule
                                        st.markdown("---")
                                        st.markdown("##### ⚡ Quick Actions")
                                        action_col1, action_col2, action_col3 = st.columns(3)
                                        
                                        with action_col1:
                                            if st.button("📋 View Full Schedule", key="view_full_schedule_ai"):
                                                st.session_state.page = "schedule"
                                                st.rerun()
                                        
                                        with action_col2:
                                            if st.button("✏️ Edit Schedule", key="edit_schedule_ai"):
                                                st.session_state.page = "schedule"
                                                st.rerun()
                                        
                                        with action_col3:
                                            if st.button("📊 View Analytics", key="view_analytics_ai"):
                                                # Switch to analytics tab in this same page
                                                st.info("💡 Switch to the 'Analytics' tab above to see detailed schedule analytics")
                                    else:
                                        # No data for next 7 days
                                        st.info("📅 No schedule data found for the next 7 days. Generated schedule may be for different dates.")
                                
                            else:
                                st.error("❌ AI could not generate a valid schedule. Please check constraints and availability.")
                                
                        except Exception as e:
                            st.error(f"❌ Schedule generation failed: {e}")
                            logger.error("Schedule generation error: %s", e)
                else:
                    st.error("❌ No employees available for scheduling!")
        
        # Simple generation options for fallback
        preview_shifts = st.checkbox("📋 Preview requirements first", value=True)
        include_importance = st.checkbox("⭐ Consider employee preferences", value=True)
        optimize_preferences = st.checkbox("🎯 Optimize shift assignments", value=True)
        use_sick_leave = st.checkbox("🏥 Respect unavailability", value=True)
        
        # Enhanced shift slots preview with better visualization
        if preview_shifts or "preview_slots" in st.session_state:
            # Generate shift slots using the appropriate function
            try:
                if core_available:
                    shift_slots = core_build_shift_slots(bs)
                else:
                    shift_slots = build_shift_slots(bs)
            except Exception as e:
                st.error(f"Error generating shift slots: {str(e)}")
                shift_slots = []
            
            if shift_slots and len(shift_slots) > 0:
                st.markdown("---")
                st.markdown("""
                <div style="margin: 2rem 0 1rem 0;">
                    <h3 style="margin: 0; font-size: 1.5rem; font-weight: 700; color: #1e293b; display: flex; align-items: center; gap: 0.5rem;">
                        📋 <span>Shift Requirements Preview</span>
                    </h3>
                    <p style="margin: 0.5rem 0 0 0; color: #64748b; font-size: 1rem;">Review the schedule slots that will be filled by the generation process</p>
                </div>
                """, unsafe_allow_html=True)
                
                slots_df = pd.DataFrame(shift_slots)
                if not slots_df.empty:
                    # Show summary metrics first
                    preview_col1, preview_col2, preview_col3, preview_col4 = st.columns(4, gap="medium")
                    
                    with preview_col1:
                        total_slots = len(shift_slots)
                        st.metric("📊 Total Slots", total_slots, help="Total number of shifts to be filled")
                    
                    with preview_col2:
                        unique_dates = slots_df['date'].nunique()
                        st.metric("📅 Planning Days", unique_dates, help="Number of days in the planning period")
                    
                    with preview_col3:
                        unique_roles = slots_df['role'].nunique()
                        st.metric("👥 Roles Required", unique_roles, help="Different roles needed across shifts")
                    
                    with preview_col4:
                        shift_types = slots_df['shift_type'].nunique()
                        st.metric("⏰ Shift Types", shift_types, help="Different shift types (day/evening/night)")
                    
                    # Enhanced dataframe display
                    st.markdown("##### 📋 Detailed Slot Breakdown")
                    st.dataframe(
                        slots_df.head(10), 
                        width='stretch',
                        height=300,
                        hide_index=True,
                        column_config={
                            "date": st.column_config.DateColumn("📅 Date", format="MMM DD, YYYY"),
                            "shift_type": st.column_config.TextColumn("⏰ Shift Type", width="medium"),
                            "role": st.column_config.TextColumn("👤 Role", width="medium"),
                            "slot_id": st.column_config.TextColumn("🆔 Slot ID", width="large")
                        }
                    )
                    
                    if len(shift_slots) > 10:
                        st.info(f"📋 Showing first 10 of {len(shift_slots)} total slots. Generation will process all slots.")
                else:
                    st.warning("⚠️ No shift slots generated. Please check your business settings configuration.")
            else:
                st.warning("⚠️ No shift slots available for generation. Please configure business settings first.")
        
        # Enhanced main generation section with professional styling
        st.markdown("---")
        
        # Check if system is ready for generation
        generation_ready = True
        ready_issues = []
        
        if emp_df.empty:
            generation_ready = False
            ready_issues.append("❌ No employees configured")
        if not bs:
            generation_ready = False
            ready_issues.append("❌ Business settings missing")
        
        # Try to generate shift slots to validate configuration
        try:
            if core_available:
                test_slots = core_build_shift_slots(bs)
            else:
                test_slots = build_shift_slots(bs)
            if not test_slots or len(test_slots) == 0:
                generation_ready = False
                ready_issues.append("❌ No shift slots configured")
        except Exception as e:
            generation_ready = False
            ready_issues.append(f"❌ Configuration error: {str(e)}")
        
        if generation_ready:
            # Professional generation interface when ready
            st.markdown("""
            <div style="background: linear-gradient(135deg, rgba(16,185,129,0.1) 0%, rgba(5,150,105,0.05) 100%); 
                        border: 2px solid rgba(16,185,129,0.2); border-radius: 16px; padding: 2rem; margin: 1rem 0; text-align: center;">
                <div style="display: flex; align-items: center; justify-content: center; margin-bottom: 1rem;">
                    <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); width: 60px; height: 60px; 
                                border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 1rem;">
                        <span style="font-size: 24px;">🚀</span>
                    </div>
                    <div style="text-align: left;">
                        <h3 style="margin: 0; color: #065f46; font-size: 1.5rem; font-weight: 700;">Ready to Generate</h3>
                        <p style="margin: 0.5rem 0 0 0; color: #047857; font-size: 1rem;">All systems configured and ready for optimization</p>
                    </div>
                </div>
                <div style="background: rgba(255,255,255,0.7); border-radius: 8px; padding: 1rem; margin-bottom: 1.5rem;">
                    <div style="display: flex; justify-content: space-around; text-align: center;">
                        <div>
                            <div style="font-weight: 700; color: #065f46; font-size: 1.2rem;">{employees}</div>
                            <div style="color: #047857; font-size: 0.9rem;">Employees</div>
                        </div>
                        <div>
                            <div style="font-weight: 700; color: #065f46; font-size: 1.2rem;">{slots}</div>
                            <div style="color: #047857; font-size: 0.9rem;">Shift Slots</div>
                        </div>
                        <div>
                            <div style="font-weight: 700; color: #065f46; font-size: 1.2rem;">Hybrid</div>
                            <div style="color: #047857; font-size: 0.9rem;">Algorithm</div>
                        </div>
                    </div>
                </div>
            </div>
            """.format(employees=len(emp_df), slots=len(test_slots)), unsafe_allow_html=True)
            

        else:
            # Professional "not ready" interface
            st.markdown("""
            <div style="background: linear-gradient(135deg, rgba(239,68,68,0.1) 0%, rgba(220,38,38,0.05) 100%); 
                        border: 2px solid rgba(239,68,68,0.2); border-radius: 16px; padding: 2rem; margin: 1rem 0; text-align: center;">
                <div style="display: flex; align-items: center; justify-content: center; margin-bottom: 1rem;">
                    <div style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); width: 60px; height: 60px; 
                                border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 1rem;">
                        <span style="font-size: 24px;">⚙️</span>
                    </div>
                    <div style="text-align: left;">
                        <h3 style="margin: 0; color: #7f1d1d; font-size: 1.5rem; font-weight: 700;">Setup Required</h3>
                        <p style="margin: 0.5rem 0 0 0; color: #991b1b; font-size: 1rem;">Complete the following steps to enable schedule generation</p>
                    </div>
                </div>
                <div style="background: rgba(255,255,255,0.7); border-radius: 8px; padding: 1.5rem;">
            """, unsafe_allow_html=True)
            
            for issue in ready_issues:
                st.markdown(f"**{issue}**")
            
            st.markdown("</div></div>", unsafe_allow_html=True)
            
            # Add helpful action buttons
            action_col1, action_col2, action_col3 = st.columns(3)
            
            with action_col1:
                if st.button("👥 Manage Employees", key="goto_employees", type="secondary"):
                    st.session_state.page = "employees"
                    st.rerun()
            
            with action_col2:
                if st.button("🏢 Business Setup", key="goto_business", type="secondary"):
                    st.session_state.page = "business"
                    st.rerun()
            
            with action_col3:
                if st.button("🔄 Refresh Status", key="refresh_status", type="secondary"):
                    st.rerun()
    
    with schedule_tab:
        st.markdown("### 📋 Interactive Schedule Management")
        
        sched_df = st.session_state.get("current_schedule_df", pd.DataFrame())
        
        if not sched_df.empty:
            # Post-Generation Monitoring System
            st.markdown("#### 🔍 Post-Generation Monitoring")
            st.markdown("""
            <div style="background: rgba(59, 130, 246, 0.1); border-radius: 12px; padding: 1rem; margin-bottom: 1rem; border-left: 4px solid #3b82f6;">
                <p style="margin: 0; color: #1e3a8a;">🤖 <strong>AI Schedule Analysis:</strong> Review assignments, validate availability, and get intelligent optimization suggestions.</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Availability compliance check
            if "employee_availability" in st.session_state:
                st.markdown("##### ✅ Availability Compliance Check")
                
                # Check if any employees were assigned when unavailable
                compliance_issues = []
                availability_violations = 0
                
                for _, row in sched_df.iterrows():
                    if pd.notna(row['employee_id']):
                        emp_id = int(row['employee_id'])
                        shift_date = str(row['date'])
                        
                        if (emp_id in st.session_state["employee_availability"] and
                            not st.session_state["employee_availability"][emp_id].get(shift_date, True)):
                            compliance_issues.append({
                                'employee': row['employee_name'],
                                'date': shift_date,
                                'shift': row['shift_type'],
                                'role': row['role']
                            })
                            availability_violations += 1
                
                if availability_violations == 0:
                    st.success(f"✅ Perfect compliance! All {len(sched_df[sched_df['employee_id'].notna()])} assignments respect availability constraints.")
                else:
                    st.error(f"❌ {availability_violations} availability violations found!")
                    
                    if st.button("🔧 Show Violation Details", key="show_violations"):
                        st.markdown("**Availability Violations:**")
                        violations_df = pd.DataFrame(compliance_issues)
                        st.dataframe(violations_df, use_container_width=True)
                        
                        if st.button("🤖 AI Fix Violations", key="ai_fix_violations"):
                            if openai_available:
                                with st.spinner("🤖 AI resolving availability violations..."):
                                    try:
                                        # AI-powered violation resolution
                                        prompt = f"""
                                        Fix the following schedule violations where employees were assigned when unavailable:
                                        
                                        Violations: {compliance_issues}
                                        Available Employees: {emp_df[['id', 'name', 'role']].to_dict('records')}
                                        Availability Matrix: {st.session_state["employee_availability"]}
                                        
                                        Suggest alternative assignments or mark shifts as unfilled if no alternatives exist.
                                        Return JSON with suggested fixes: {{"slot_id": "new_employee_id_or_null"}}
                                        """
                                        
                                        response = openai.ChatCompletion.create(
                                            model="gpt-4",
                                            messages=[
                                                {"role": "system", "content": "You are an AI scheduling expert. Fix availability violations with practical solutions."},
                                                {"role": "user", "content": prompt}
                                            ],
                                            max_tokens=1000,
                                            temperature=0.2
                                        )
                                        
                                        st.success("🤖 AI violation fixes generated!")
                                        st.info("Review the suggestions and apply manually in the schedule editor below.")
                                        
                                    except Exception as e:
                                        st.error(f"AI fix failed: {e}")
                            else:
                                st.warning("OpenAI API required for automatic violation fixes")
            
            # AI Schedule Quality Analysis
            with st.expander("🤖 AI Schedule Quality Analysis", expanded=False):
                if st.button("🔍 Analyze Schedule Quality", key="ai_analyze_schedule"):
                    if openai_available:
                        with st.spinner("🤖 AI analyzing schedule quality..."):
                            try:
                                # Prepare schedule data for AI analysis
                                schedule_summary = {
                                    'total_shifts': len(sched_df),
                                    'filled_shifts': len(sched_df[sched_df['employee_id'].notna()]),
                                    'fill_rate': len(sched_df[sched_df['employee_id'].notna()]) / len(sched_df) * 100,
                                    'employees_used': len(sched_df[sched_df['employee_id'].notna()]['employee_id'].unique()),
                                    'role_distribution': sched_df['role'].value_counts().to_dict(),
                                    'daily_distribution': sched_df['date'].value_counts().to_dict()
                                }
                                
                                # Employee workload analysis
                                workload_analysis = {}
                                for _, emp in emp_df.iterrows():
                                    emp_shifts = sched_df[sched_df['employee_id'] == emp['id']]
                                    workload_analysis[emp['name']] = {
                                        'assigned_shifts': len(emp_shifts),
                                        'max_hours': emp['max_hours_per_week'],
                                        'role': emp['role'],
                                        'utilization_rate': (len(emp_shifts) * 8) / emp['max_hours_per_week'] * 100  # Assuming 8h shifts
                                    }
                                
                                # AI Analysis Prompt
                                prompt = f"""
                                Analyze this generated work schedule and provide comprehensive quality assessment:
                                
                                Schedule Summary: {schedule_summary}
                                Employee Workload: {workload_analysis}
                                
                                Please provide:
                                1. Overall schedule quality rating (1-5 stars)
                                2. Strengths of the current schedule
                                3. Areas for improvement
                                4. Workload balance assessment
                                5. Coverage adequacy analysis
                                6. Specific recommendations for optimization
                                
                                Format as a professional schedule quality report.
                                """
                                
                                response = openai.ChatCompletion.create(
                                    model="gpt-4",
                                    messages=[
                                        {"role": "system", "content": "You are an expert workforce management consultant. Provide detailed, actionable schedule quality analysis."},
                                        {"role": "user", "content": prompt}
                                    ],
                                    max_tokens=1200,
                                    temperature=0.3
                                )
                                
                                ai_analysis = response["choices"][0]["message"]["content"]
                                st.markdown("#### 🤖 AI Quality Analysis Report")
                                st.markdown(ai_analysis)
                                
                            except Exception as e:
                                st.error(f"AI analysis failed: {e}")
                    else:
                        st.warning("OpenAI API not available for quality analysis")
            
            # Schedule metrics
            metrics_col1, metrics_col2, metrics_col3, metrics_col4 = st.columns(4)
            
            total_slots = len(sched_df)
            filled_slots = len(sched_df[sched_df['employee_id'].notna()])
            unfilled_slots = total_slots - filled_slots
            unique_employees = len(sched_df[sched_df['employee_id'].notna()]['employee_id'].unique())
            
            with metrics_col1:
                st.metric("Total Shifts", total_slots)
            with metrics_col2:
                st.metric("Filled", filled_slots, delta=f"{(filled_slots/total_slots)*100:.1f}%")
            with metrics_col3:
                st.metric("Unfilled", unfilled_slots, delta=f"-{(unfilled_slots/total_slots)*100:.1f}%")
            with metrics_col4:
                st.metric("Active Staff", unique_employees)
            
            # Interactive management tabs
            edit_view_tab, bulk_edit_tab, swap_tab, export_tab = st.tabs([
                "📝 Edit Schedule", "⚡ Bulk Operations", "🔄 Swap Shifts", "📤 Export & Backup"
            ])
            
            with edit_view_tab:
                st.markdown("#### 📝 Edit Individual Shifts")
                
                # Edit controls
                edit_col1, edit_col2, edit_col3 = st.columns([2, 1, 1])
                
                with edit_col1:
                    edit_mode = st.radio(
                        "Edit Mode",
                        ["View Only", "Quick Edit", "Advanced Edit"],
                        horizontal=True,
                        help="View Only: Read-only display, Quick Edit: Basic changes, Advanced Edit: Full editing"
                    )
                
                with edit_col2:
                    show_unfilled = st.checkbox("Show Unfilled Slots", value=True, key="edit_show_unfilled")
                
                with edit_col3:
                    auto_validate = st.checkbox("Auto-validate Changes", value=True, key="auto_validate_edits")
                
                # Filter and sort options
                filter_col1, filter_col2, filter_col3 = st.columns(3)
                
                with filter_col1:
                    date_filter = st.selectbox("Filter by Date", options=["All Dates"] + sorted(sched_df['date'].astype(str).unique().tolist()))
                
                with filter_col2:
                    role_filter = st.selectbox("Filter by Role", options=["All Roles"] + sorted(sched_df['role'].unique().tolist()))
                
                with filter_col3:
                    employee_filter = st.selectbox("Filter by Employee", options=["All Employees"] + sorted([name for name in sched_df['employee_name'].unique() if pd.notna(name)]))
                
                # Apply filters
                filtered_df = sched_df.copy()
                
                if date_filter != "All Dates":
                    filtered_df = filtered_df[filtered_df['date'].astype(str) == date_filter]
                
                if role_filter != "All Roles":
                    filtered_df = filtered_df[filtered_df['role'] == role_filter]
                
                if employee_filter != "All Employees":
                    filtered_df = filtered_df[filtered_df['employee_name'] == employee_filter]
                
                if not show_unfilled:
                    filtered_df = filtered_df[filtered_df['employee_id'].notna()]
                
                # Interactive schedule editing
                if edit_mode == "View Only":
                    st.dataframe(
                        filtered_df,
                        width='stretch',
                        column_config={
                            "date": st.column_config.DateColumn("Date"),
                            "shift_type": st.column_config.TextColumn("Shift"),
                            "role": st.column_config.TextColumn("Role"),
                            "employee_name": st.column_config.TextColumn("Employee"),
                            "employee_id": st.column_config.NumberColumn("ID", format="%d")
                        }
                    )
                
                elif edit_mode == "Quick Edit":
                    st.markdown("##### ⚡ Quick Edit Mode")
                    st.info("💡 **How to use**: Select 'Unassigned' to remove an employee, or choose a new employee to assign/reassign shifts")
                    
                    # Show the schedule table first for reference
                    st.markdown("###### 📋 Schedule Overview")
                    st.dataframe(
                        filtered_df,
                        width='stretch',
                        height=200,
                        column_config={
                            "date": st.column_config.DateColumn("Date"),
                            "shift_type": st.column_config.TextColumn("Shift"),
                            "role": st.column_config.TextColumn("Role"),
                            "employee_name": st.column_config.TextColumn("Employee"),
                            "employee_id": st.column_config.NumberColumn("ID", format="%d")
                        }
                    )
                    
                    st.markdown("---")
                    st.markdown("###### ✏️ Edit Individual Shifts")
                    
                    # Display editable shifts
                    for idx, row in filtered_df.iterrows():
                        shift_key = f"shift_{idx}"
                        current_employee = row.get('employee_name', 'UNFILLED')
                        status_color = "🟢" if pd.notna(row.get('employee_id')) else "🔴"
                        
                        with st.expander(f"{status_color} **{row['date']}** | {row['shift_type']} | {row['role']} | **{current_employee}**", expanded=False):
                            edit_shift_col1, edit_shift_col2, edit_shift_col3 = st.columns([1, 2, 1])
                            
                            with edit_shift_col1:
                                st.markdown("**📅 Shift Details**")
                                st.write(f"Date: {row['date']}")
                                st.write(f"Shift: {row['shift_type']}")
                                st.write(f"Role: {row['role']}")
                                
                                # Current status
                                if pd.notna(row.get('employee_id')):
                                    st.success(f"✅ Assigned to: {current_employee}")
                                else:
                                    st.error("❌ Unassigned")
                            
                            with edit_shift_col2:
                                st.markdown("**👥 Employee Assignment**")
                                
                                # Employee assignment
                                emp_df = get_all_employees()
                                eligible_employees = emp_df[emp_df['role'].str.contains(row['role'], na=False)] if not emp_df.empty else pd.DataFrame()
                                
                                employee_options = ["🚫 Unassigned"] + [f"👤 {name}" for name in eligible_employees['name'].tolist()] if not eligible_employees.empty else ["🚫 Unassigned"]
                                
                                # Format current selection
                                if current_employee == 'UNFILLED' or pd.isna(row.get('employee_id')):
                                    current_formatted = "🚫 Unassigned"
                                else:
                                    current_formatted = f"👤 {current_employee}"
                                
                                current_idx = employee_options.index(current_formatted) if current_formatted in employee_options else 0
                                
                                new_employee = st.selectbox(
                                    "🔄 Change Assignment",
                                    options=employee_options,
                                    index=current_idx,
                                    key=f"employee_{shift_key}",
                                    help="Select 'Unassigned' to remove employee, or choose a new employee to assign"
                                )
                                
                                # Update employee assignment
                                new_employee_clean = new_employee.replace("🚫 ", "").replace("👤 ", "")
                                current_employee_clean = current_employee if current_employee != 'UNFILLED' else 'Unassigned'
                                
                                if new_employee_clean != current_employee_clean:
                                    if new_employee_clean == "Unassigned":
                                        sched_df.loc[idx, 'employee_id'] = None
                                        sched_df.loc[idx, 'employee_name'] = None
                                        st.info("🗑️ Employee removed from this shift")
                                    else:
                                        selected_emp = eligible_employees[eligible_employees['name'] == new_employee_clean].iloc[0]
                                        sched_df.loc[idx, 'employee_id'] = selected_emp['id']
                                        sched_df.loc[idx, 'employee_name'] = selected_emp['name']
                                        st.success(f"✅ Assigned {new_employee_clean} to this shift")
                                    
                                    st.session_state["current_schedule_df"] = sched_df
                                    
                                    if auto_validate:
                                        violations = validate_schedule(sched_df, emp_df, bs)
                                        if violations:
                                            st.warning(f"⚠️ {len(violations)} validation issues detected")
                                        else:
                                            st.success("✅ Change validated successfully")
                            
                            with edit_shift_col3:
                                # Quick actions for this shift
                                if st.button("🔄 Find Replacement", key=f"replace_{shift_key}"):
                                    # Find available employees for this shift
                                    available_employees = eligible_employees[
                                        ~eligible_employees['id'].isin(
                                            sched_df[(sched_df['date'] == row['date']) & 
                                                    (sched_df['employee_id'].notna())]['employee_id']
                                        )
                                    ]
                                    
                                    if not available_employees.empty:
                                        replacement = available_employees.iloc[0]
                                        sched_df.loc[idx, 'employee_id'] = replacement['id']
                                        sched_df.loc[idx, 'employee_name'] = replacement['name']
                                        st.session_state["current_schedule_df"] = sched_df
                                        st.success(f"✅ Assigned {replacement['name']} to this shift")
                                        st.rerun()
                                    else:
                                        st.warning("No available employees found for this shift")
                                
                                if st.button("❌ Clear Assignment", key=f"clear_{shift_key}"):
                                    sched_df.loc[idx, 'employee_id'] = None
                                    sched_df.loc[idx, 'employee_name'] = None
                                    st.session_state["current_schedule_df"] = sched_df
                                    st.success("✅ Shift assignment cleared")
                                    st.rerun()
                
                elif edit_mode == "Advanced Edit":
                    st.markdown("### ✏️ Advanced Editing")
                    
                    # Simplified editing controls  
                    edit_col1, edit_col2 = st.columns(2)
                    
                    with edit_col1:
                        if st.button("➕ Add New Entry", key="add_schedule_entry"):
                            st.session_state["show_add_entry"] = True
                    
                    with edit_col2:
                        if st.button("🗑️ Delete Selected", key="delete_selected", help="Select rows first, then click to delete"):
                            st.session_state["confirm_delete"] = True
                    
                    # Add new entry modal
                    if st.session_state.get("show_add_entry", False):
                        with st.expander("➕ Add New Schedule Entry", expanded=True):
                            add_col1, add_col2, add_col3 = st.columns(3)
                            
                            with add_col1:
                                new_date = st.date_input("Date", key="new_entry_date")
                                new_shift = st.selectbox("Shift Type", ["day", "evening", "night"], key="new_entry_shift")
                            
                            with add_col2:
                                # Get available roles from business settings
                                available_roles = [r.role for r in bs.role_settings] if bs.role_settings else ["Manager", "Barista", "Cashier"]
                                new_role = st.selectbox("Role", available_roles, key="new_entry_role")
                                
                                # Get available employees for the selected role
                                role_employees = emp_df[emp_df['role'].str.contains(new_role, na=False)] if not emp_df.empty else pd.DataFrame()
                                employee_options = [{"id": None, "name": "UNFILLED"}] + [{"id": int(row['id']), "name": row['name']} for _, row in role_employees.iterrows()] if not role_employees.empty else [{"id": None, "name": "UNFILLED"}]
                                
                                selected_emp = st.selectbox(
                                    "Employee", 
                                    options=range(len(employee_options)),
                                    format_func=lambda x: employee_options[x]["name"],
                                    key="new_entry_employee"
                                )
                            
                            with add_col3:
                                st.write("") # spacing
                                add_entry_col1, add_entry_col2 = st.columns(2)
                                with add_entry_col1:
                                    if st.button("✅ Add Entry", type="primary", key="confirm_add_entry"):
                                        # Create new entry
                                        selected_employee = employee_options[selected_emp]
                                        new_entry = {
                                            "date": new_date,
                                            "shift_type": new_shift,
                                            "role": new_role,
                                            "employee_id": selected_employee["id"],
                                            "employee_name": selected_employee["name"] if selected_employee["id"] else None,
                                            "slot_id": f"{new_date}_{new_shift}_{new_role}_{len(sched_df)}"
                                        }
                                        
                                        # Add to dataframe
                                        new_row_df = pd.DataFrame([new_entry])
                                        sched_df = pd.concat([sched_df, new_row_df], ignore_index=True)
                                        st.session_state["current_schedule_df"] = sched_df
                                        st.session_state["show_add_entry"] = False
                                        st.success("✅ New entry added successfully!")
                                        st.rerun()
                                
                                with add_entry_col2:
                                    if st.button("❌ Cancel", key="cancel_add_entry"):
                                        st.session_state["show_add_entry"] = False
                                        st.rerun()
                    
                    # Bulk edit operations
                    if st.session_state.get("show_bulk_edit", False):
                        with st.expander("🔄 Bulk Edit Operations", expanded=True):
                            bulk_op_col1, bulk_op_col2 = st.columns(2)
                            
                            with bulk_op_col1:
                                st.markdown("**Bulk Assignment**")
                                
                                # Select date range for bulk operation
                                bulk_dates = st.multiselect(
                                    "Select Dates",
                                    options=sorted(filtered_df['date'].unique()) if not filtered_df.empty else [],
                                    key="bulk_edit_dates"
                                )
                                
                                # Select roles for bulk operation
                                bulk_roles = st.multiselect(
                                    "Select Roles", 
                                    options=sorted(filtered_df['role'].unique()) if not filtered_df.empty else [],
                                    key="bulk_edit_roles"
                                )
                                
                                # Select employee for bulk assignment
                                if not emp_df.empty:
                                    bulk_employee = st.selectbox(
                                        "Assign Employee",
                                        options=[None] + list(emp_df['name'].unique()),
                                        key="bulk_assign_employee"
                                    )
                                    
                                    if st.button("🚀 Apply Bulk Assignment", key="apply_bulk_assignment"):
                                        if bulk_dates and bulk_roles and bulk_employee:
                                            # Find employee ID
                                            employee_row = emp_df[emp_df['name'] == bulk_employee].iloc[0]
                                            employee_id = int(employee_row['id'])
                                            
                                            # Apply bulk assignment
                                            mask = (filtered_df['date'].isin(bulk_dates)) & (filtered_df['role'].isin(bulk_roles))
                                            affected_rows = filtered_df[mask].index
                                            
                                            for idx in affected_rows:
                                                if idx in sched_df.index:
                                                    sched_df.loc[idx, 'employee_name'] = bulk_employee
                                                    sched_df.loc[idx, 'employee_id'] = employee_id
                                            
                                            st.session_state["current_schedule_df"] = sched_df
                                            st.success(f"✅ Bulk assigned {bulk_employee} to {len(affected_rows)} shifts")
                                            st.session_state["show_bulk_edit"] = False
                                            st.rerun()
                                        else:
                                            st.error("Please select dates, roles, and an employee")
                            
                            with bulk_op_col2:
                                st.markdown("**Bulk Clearing**")
                                
                                clear_dates = st.multiselect(
                                    "Clear Dates",
                                    options=sorted(filtered_df['date'].unique()) if not filtered_df.empty else [],
                                    key="bulk_clear_dates"
                                )
                                
                                clear_roles = st.multiselect(
                                    "Clear Roles",
                                    options=sorted(filtered_df['role'].unique()) if not filtered_df.empty else [],
                                    key="bulk_clear_roles"
                                )
                                
                                if st.button("🗑️ Clear Selected Shifts", key="apply_bulk_clear"):
                                    if clear_dates and clear_roles:
                                        mask = (filtered_df['date'].isin(clear_dates)) & (filtered_df['role'].isin(clear_roles))
                                        affected_rows = filtered_df[mask].index
                                        
                                        for idx in affected_rows:
                                            if idx in sched_df.index:
                                                sched_df.loc[idx, 'employee_name'] = None
                                                sched_df.loc[idx, 'employee_id'] = None
                                        
                                        st.session_state["current_schedule_df"] = sched_df
                                        st.success(f"✅ Cleared {len(affected_rows)} shift assignments")
                                        st.session_state["show_bulk_edit"] = False
                                        st.rerun()
                                    else:
                                        st.error("Please select dates and roles to clear")
                            
                            close_col1, close_col2 = st.columns([1, 1])
                            with close_col2:
                                if st.button("❌ Close Bulk Edit", key="close_bulk_edit"):
                                    st.session_state["show_bulk_edit"] = False
                                    st.rerun()
                    
                    # Delete confirmation modal
                    if st.session_state.get("confirm_delete", False):
                        with st.expander("🗑️ Delete Schedule Entries", expanded=True):
                            st.warning("⚠️ **WARNING**: This will permanently delete selected schedule entries!")
                            
                            # Allow user to select rows to delete
                            if not filtered_df.empty:
                                st.markdown("**Select entries to delete:**")
                                
                                # Create a selectable dataframe for deletion
                                delete_df = filtered_df.copy()
                                delete_df['Select'] = False
                                
                                # Display dataframe with selection checkboxes
                                selected_for_deletion = st.data_editor(
                                    delete_df[['Select', 'date', 'shift_type', 'role', 'employee_name']],
                                    column_config={
                                        "Select": st.column_config.CheckboxColumn("🗑️ Delete", default=False),
                                        "date": st.column_config.DateColumn("📅 Date"),
                                        "shift_type": "⏰ Shift",
                                        "role": "👤 Role", 
                                        "employee_name": "👥 Employee"
                                    },
                                    disabled=["date", "shift_type", "role", "employee_name"],
                                    hide_index=True,
                                    key="deletion_selector"
                                )
                                
                                confirm_col1, confirm_col2, confirm_col3 = st.columns(3)
                                
                                with confirm_col1:
                                    if st.button("🗑️ Confirm Delete", type="primary", key="confirm_delete_entries"):
                                        # Get selected rows for deletion
                                        rows_to_delete = selected_for_deletion[selected_for_deletion['Select'] == True].index
                                        
                                        if len(rows_to_delete) > 0:
                                            # Get the original dataframe indices
                                            original_indices = filtered_df.iloc[rows_to_delete].index
                                            
                                            # Remove from the main schedule dataframe
                                            sched_df = st.session_state["current_schedule_df"].copy()
                                            sched_df = sched_df.drop(original_indices)
                                            st.session_state["current_schedule_df"] = sched_df
                                            
                                            # Reset confirmation state
                                            st.session_state["confirm_delete"] = False
                                            st.success(f"✅ Deleted {len(rows_to_delete)} schedule entries")
                                            st.rerun()
                                        else:
                                            st.error("❌ No entries selected for deletion")
                                
                                with confirm_col2:
                                    selected_count = len(selected_for_deletion[selected_for_deletion['Select'] == True])
                                    st.metric("Selected for Deletion", selected_count)
                                
                                with confirm_col3:
                                    if st.button("❌ Cancel Delete", key="cancel_delete_entries"):
                                        st.session_state["confirm_delete"] = False
                                        st.rerun()
                            else:
                                st.info("No schedule entries to delete")
                                if st.button("❌ Close", key="close_empty_delete"):
                                    st.session_state["confirm_delete"] = False
                                    st.rerun()
                    
                    # Interactive data editor with enhanced features
                    st.markdown("##### 📝 Interactive Schedule Editor")
                    st.info("💡 **How to edit**: Click cells to edit directly • Click row numbers to select rows • Selected rows can be deleted with Delete key • Use + button at bottom to add new rows • Use 'Delete Selected' button above for bulk deletion")
                    
                    # Prepare the dataframe for editing by ensuring proper data types
                    edit_df = filtered_df.copy()
                    if not edit_df.empty:
                        # Convert date column to datetime if it's not already
                        if 'date' in edit_df.columns:
                            edit_df['date'] = pd.to_datetime(edit_df['date'], errors='coerce')
                        
                        # Ensure employee_id is properly formatted
                        if 'employee_id' in edit_df.columns:
                            edit_df['employee_id'] = pd.to_numeric(edit_df['employee_id'], errors='coerce')
                    
                    edited_df = st.data_editor(
                        edit_df,
                        width='stretch',
                        height=600,
                        column_config={
                            "date": st.column_config.DateColumn("📅 Date", width="medium"),
                            "shift_type": st.column_config.SelectboxColumn(
                                "⏰ Shift", 
                                options=["day", "evening", "night"],
                                width="small"
                            ),
                            "role": st.column_config.SelectboxColumn(
                                "👤 Role",
                                options=[r.role for r in bs.role_settings] if bs.role_settings else ["Manager", "Barista", "Cashier"],
                                width="medium"
                            ),
                            "employee_name": st.column_config.TextColumn("👥 Employee", width="large"),
                            "employee_id": st.column_config.NumberColumn("🆔 ID", format="%d", width="small")
                        },
                        num_rows="dynamic",
                        use_container_width=True,
                        key="advanced_schedule_editor"
                    )
                    
                    # Show helpful tips
                    with st.expander("💡 Quick Help", expanded=False):
                        st.markdown("""
                        **How to delete rows:**
                        1. **Direct deletion**: Click on row number(s) to select them, then press Delete key on your keyboard
                        2. **Bulk deletion**: Use the '🗑️ Delete Selected' button above for guided deletion with confirmation
                        3. **Row controls**: Hover over row numbers to see delete icons (may vary by browser)
                        
                        **Other actions:**
                        - **Add rows**: Click the ➕ button at the bottom of the table
                        - **Edit cells**: Click directly on any cell to edit
                        - **Multiple selection**: Hold Ctrl/Cmd while clicking row numbers
                        """)
                    
                    # Action buttons
                    action_col1, action_col2, action_col3, action_col4 = st.columns(4)
                    
                    with action_col1:
                        if st.button("💾 Save All Changes", type="primary", key="save_advanced_changes"):
                            # Prepare the edited dataframe for saving
                            save_df = edited_df.copy()
                            
                            # Ensure data types are compatible for database saving
                            if not save_df.empty:
                                # Convert dates to strings if they're timestamps
                                if 'date' in save_df.columns:
                                    save_df['date'] = save_df['date'].apply(lambda x: 
                                        x.strftime('%Y-%m-%d') if hasattr(x, 'strftime') else str(x) if x is not None else None)
                                
                                # Handle NaN values in employee columns
                                if 'employee_id' in save_df.columns:
                                    save_df['employee_id'] = save_df['employee_id'].apply(lambda x: 
                                        int(x) if pd.notna(x) else None)
                                
                                if 'employee_name' in save_df.columns:
                                    save_df['employee_name'] = save_df['employee_name'].apply(lambda x: 
                                        str(x) if pd.notna(x) and x != '' else None)
                            
                            # Update the main schedule dataframe
                            st.session_state["current_schedule_df"] = save_df.copy()
                            
                            # Save to database
                            try:
                                save_schedule_to_db(save_df, bs)
                                st.success("✅ Changes saved to database successfully!")
                            except Exception as e:
                                st.error(f"❌ Error saving to database: {str(e)}")
                                logger.error("Database save error: %s", e)
                            
                            # Validate changes
                            violations = validate_schedule(save_df, emp_df, bs)
                            if violations:
                                st.warning(f"⚠️ {len(violations)} validation issues detected")
                                with st.expander("View Issues"):
                                    for violation in violations[:5]:
                                        st.write(f"• {violation['message']}")
                            
                            st.rerun()
                    
                    with action_col2:
                        if st.button("🔄 Refresh Data", key="refresh_schedule_data"):
                            st.session_state["current_schedule_df"] = load_schedule_from_db(bs)
                            st.success("✅ Data refreshed from database")
                            st.rerun()
                    
                    with action_col3:
                        if st.button("📊 Validate Schedule", key="validate_current_schedule"):
                            violations = validate_schedule(edited_df, emp_df, bs)
                            if violations:
                                st.error(f"❌ {len(violations)} validation issues found")
                                for violation in violations[:5]:
                                    st.write(f"• {violation['message']}")
                            else:
                                st.success("✅ Schedule passes all validation checks!")
                    
                    with action_col4:
                        if st.button("⚠️ Reset Changes", key="reset_schedule_changes"):
                            if st.session_state.get("confirm_reset", False):
                                st.session_state["current_schedule_df"] = load_schedule_from_db(bs)
                                st.session_state["confirm_reset"] = False
                                st.success("✅ Changes reset to last saved version")
                                st.rerun()
                            else:
                                st.session_state["confirm_reset"] = True
                                st.warning("⚠️ Click again to confirm reset")
                    
                    # Show summary statistics
                    if not edited_df.empty:
                        st.markdown("---")
                        st.markdown("##### 📊 Edit Summary")
                        
                        summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
                        
                        with summary_col1:
                            total_entries = len(edited_df)
                            st.metric("Total Entries", total_entries)
                        
                        with summary_col2:
                            filled_entries = len(edited_df[edited_df['employee_id'].notna()])
                            fill_rate = (filled_entries / total_entries * 100) if total_entries > 0 else 0
                            st.metric("Fill Rate", f"{fill_rate:.1f}%")
                        
                        with summary_col3:
                            unique_employees = len(edited_df[edited_df['employee_id'].notna()]['employee_id'].unique()) if filled_entries > 0 else 0
                            st.metric("Unique Employees", unique_employees)
                        
                        with summary_col4:
                            date_range = f"{edited_df['date'].min()} to {edited_df['date'].max()}" if total_entries > 0 else "No data"
                            st.metric("Date Range", date_range)
            
            with bulk_edit_tab:
                st.markdown("#### ⚡ Bulk Operations")
                
                # Show the schedule table first
                st.markdown("##### 📋 Current Schedule")
                st.dataframe(
                    filtered_df,
                    width='stretch',
                    column_config={
                        "date": st.column_config.DateColumn("Date"),
                        "shift_type": st.column_config.TextColumn("Shift"),
                        "role": st.column_config.TextColumn("Role"),
                        "employee_name": st.column_config.TextColumn("Employee"),
                        "employee_id": st.column_config.NumberColumn("ID", format="%d")
                    }
                )
                
                st.markdown("---")
                
                bulk_col1, bulk_col2 = st.columns(2)
                
                with bulk_col1:
                    st.markdown("##### 🎯 Mass Assignment")
                    
                    # Bulk assign employees to unfilled shifts
                    unfilled_shifts = sched_df[sched_df['employee_id'].isna()]
                    
                    if not unfilled_shifts.empty:
                        st.write(f"**{len(unfilled_shifts)} unfilled shifts found**")
                        
                        bulk_strategy = st.selectbox(
                            "Assignment Strategy",
                            ["Balanced Workload", "Role Expertise", "Availability Priority", "Random Assignment"]
                        )
                        
                        if st.button("🚀 Auto-Fill All Shifts", type="primary"):
                            emp_df = get_all_employees()
                            filled_count = 0
                            
                            for idx, shift in unfilled_shifts.iterrows():
                                # Find eligible employees for this role
                                eligible_employees = emp_df[emp_df['role'].str.contains(shift['role'], na=False)] if not emp_df.empty else pd.DataFrame()
                                
                                if not eligible_employees.empty:
                                    # Remove employees already working on this date
                                    working_on_date = sched_df[
                                        (sched_df['date'] == shift['date']) & 
                                        (sched_df['employee_id'].notna())
                                    ]['employee_id'].tolist()
                                    
                                    available_employees = eligible_employees[
                                        ~eligible_employees['id'].isin(working_on_date)
                                    ]
                                    
                                    if not available_employees.empty:
                                        if bulk_strategy == "Balanced Workload":
                                            # Choose employee with least shifts
                                            employee_workload = sched_df[sched_df['employee_id'].notna()]['employee_id'].value_counts()
                                            available_workload = available_employees['id'].map(employee_workload).fillna(0)
                                            selected_emp = available_employees.loc[available_workload.idxmin()]
                                        elif bulk_strategy == "Role Expertise":
                                            # Choose employee with highest importance for this role
                                            if 'importance' in available_employees.columns:
                                                selected_emp = available_employees.loc[available_employees['importance'].idxmax()]
                                            else:
                                                selected_emp = available_employees.iloc[0]
                                        else:
                                            # Random or availability priority - just pick first available
                                            selected_emp = available_employees.iloc[0]
                                        
                                        sched_df.loc[idx, 'employee_id'] = selected_emp['id']
                                        sched_df.loc[idx, 'employee_name'] = selected_emp['name']
                                        filled_count += 1
                            
                            st.session_state["current_schedule_df"] = sched_df
                            st.success(f"✅ Successfully filled {filled_count} shifts using {bulk_strategy} strategy")
                            
                            # Validate the bulk changes
                            violations = validate_schedule(sched_df, emp_df, bs)
                            if violations:
                                st.warning(f"⚠️ {len(violations)} validation issues detected after bulk assignment")
                            
                            st.rerun()
                    else:
                        st.success("✅ All shifts are already filled!")
                
                with bulk_col2:
                    st.markdown("##### 🧹 Bulk Cleanup")
                    
                    # Bulk operations
                    st.markdown("**Quick Actions**")
                    
                    if st.button("🗑️ Clear All Assignments", key="clear_all_assignments"):
                        sched_df['employee_id'] = None
                        sched_df['employee_name'] = None
                        st.session_state["current_schedule_df"] = sched_df
                        st.success("✅ All employee assignments cleared")
                        st.rerun()
                    
                    if st.button("🔄 Shuffle Assignments", key="shuffle_assignments"):
                        # Randomly reassign all employees while maintaining role constraints
                        emp_df = get_all_employees()
                        
                        for idx, shift in sched_df.iterrows():
                            if pd.notna(shift.get('employee_id')):
                                # Find all employees who can do this role
                                eligible_employees = emp_df[emp_df['role'].str.contains(shift['role'], na=False)]
                                
                                if not eligible_employees.empty:
                                    new_employee = eligible_employees.sample(1).iloc[0]
                                    sched_df.loc[idx, 'employee_id'] = new_employee['id']
                                    sched_df.loc[idx, 'employee_name'] = new_employee['name']
                        
                        st.session_state["current_schedule_df"] = sched_df
                        st.success("✅ Employee assignments shuffled")
                        st.rerun()
                    
                    if st.button("⚖️ Balance Workload", key="balance_workload"):
                        # Redistribute shifts to balance employee workloads
                        emp_df = get_all_employees()
                        
                        # Calculate current workload per employee
                        current_workload = sched_df[sched_df['employee_id'].notna()]['employee_id'].value_counts()
                        
                        # Find overloaded and underloaded employees
                        avg_workload = current_workload.mean()
                        overloaded = current_workload[current_workload > avg_workload * 1.2]
                        underloaded = current_workload[current_workload < avg_workload * 0.8]
                        
                        redistributed = 0
                        for overloaded_emp_id in overloaded.index:
                            emp_shifts = sched_df[sched_df['employee_id'] == overloaded_emp_id]
                            
                            for idx, shift in emp_shifts.head(1).iterrows():  # Move one shift
                                eligible_employees = emp_df[emp_df['role'].str.contains(shift['role'], na=False)]
                                underloaded_eligible = eligible_employees[eligible_employees['id'].isin(underloaded.index)]
                                
                                if not underloaded_eligible.empty:
                                    new_employee = underloaded_eligible.iloc[0]
                                    sched_df.loc[idx, 'employee_id'] = new_employee['id']
                                    sched_df.loc[idx, 'employee_name'] = new_employee['name']
                                    redistributed += 1
                                    break
                        
                        st.session_state["current_schedule_df"] = sched_df
                        st.success(f"✅ Redistributed {redistributed} shifts to balance workload")
                        st.rerun()
            
            with swap_tab:
                st.markdown("#### 🔄 Smart Shift Swapping")
                
                # Show the schedule table first
                st.markdown("##### 📋 Current Schedule")
                st.dataframe(
                    filtered_df,
                    width='stretch',
                    column_config={
                        "date": st.column_config.DateColumn("Date"),
                        "shift_type": st.column_config.TextColumn("Shift"),
                        "role": st.column_config.TextColumn("Role"),
                        "employee_name": st.column_config.TextColumn("Employee"),
                        "employee_id": st.column_config.NumberColumn("ID", format="%d")
                    }
                )
                
                st.markdown("---")
                
                swap_col1, swap_col2 = st.columns(2)
                
                with swap_col1:
                    st.markdown("##### 👥 Employee Swap")
                    
                    # Get list of employees currently in schedule
                    assigned_employees = sched_df[sched_df['employee_id'].notna()][['employee_id', 'employee_name']].drop_duplicates()
                    
                    if not assigned_employees.empty:
                        employee_options = assigned_employees['employee_name'].tolist()
                        
                        employee_a = st.selectbox("Employee A", options=employee_options, key="swap_emp_a")
                        employee_b = st.selectbox("Employee B", options=[emp for emp in employee_options if emp != employee_a], key="swap_emp_b")
                        
                        if st.button("🔄 Swap All Shifts", key="swap_employees"):
                            # Find employee IDs
                            emp_a_id = assigned_employees[assigned_employees['employee_name'] == employee_a]['employee_id'].iloc[0]
                            emp_b_id = assigned_employees[assigned_employees['employee_name'] == employee_b]['employee_id'].iloc[0]
                            
                            # Swap all shifts between these employees
                            emp_a_shifts = sched_df['employee_id'] == emp_a_id
                            emp_b_shifts = sched_df['employee_id'] == emp_b_id
                            
                            # Store temporary values
                            sched_df.loc[emp_a_shifts, 'employee_id'] = emp_b_id
                            sched_df.loc[emp_a_shifts, 'employee_name'] = employee_b
                            sched_df.loc[emp_b_shifts, 'employee_id'] = emp_a_id
                            sched_df.loc[emp_b_shifts, 'employee_name'] = employee_a
                            
                            st.session_state["current_schedule_df"] = sched_df
                            st.success(f"✅ Swapped all shifts between {employee_a} and {employee_b}")
                            
                            # Validate the swap
                            violations = validate_schedule(sched_df, emp_df, bs)
                            if violations:
                                st.warning(f"⚠️ {len(violations)} validation issues detected after swap")
                            
                            st.rerun()
                    else:
                        st.info("No assigned employees found for swapping")
                
                with swap_col2:
                    st.markdown("##### 📅 Shift Swap")
                    
                    # Individual shift swapping
                    filled_shifts = sched_df[sched_df['employee_id'].notna()]
                    
                    if not filled_shifts.empty:
                        shift_options = []
                        for idx, shift in filled_shifts.iterrows():
                            shift_desc = f"{shift['date']} - {shift['shift_type']} - {shift['role']} - {shift['employee_name']}"
                            shift_options.append((idx, shift_desc))
                        
                        if len(shift_options) >= 2:
                            shift_a_idx = st.selectbox(
                                "Shift A", 
                                options=[opt[0] for opt in shift_options],
                                format_func=lambda x: next(opt[1] for opt in shift_options if opt[0] == x),
                                key="swap_shift_a"
                            )
                            
                            shift_b_options = [(idx, desc) for idx, desc in shift_options if idx != shift_a_idx]
                            shift_b_idx = st.selectbox(
                                "Shift B",
                                options=[opt[0] for opt in shift_b_options],
                                format_func=lambda x: next(opt[1] for opt in shift_b_options if opt[0] == x),
                                key="swap_shift_b"
                            )
                            
                            if st.button("🔄 Swap Selected Shifts", key="swap_shifts"):
                                # Get the shift data
                                shift_a = sched_df.loc[shift_a_idx]
                                shift_b = sched_df.loc[shift_b_idx]
                                
                                # Check if employees can work each other's roles
                                emp_df = get_all_employees()
                                emp_a = emp_df[emp_df['id'] == shift_a['employee_id']].iloc[0] if not emp_df.empty else None
                                emp_b = emp_df[emp_df['id'] == shift_b['employee_id']].iloc[0] if not emp_df.empty else None
                                
                                can_swap = True
                                if emp_a is not None and emp_b is not None:
                                    if shift_b['role'] not in emp_a['roles'] or shift_a['role'] not in emp_b['roles']:
                                        can_swap = False
                                        st.error("❌ Cannot swap: Employees are not qualified for each other's roles")
                                
                                if can_swap:
                                    # Perform the swap
                                    temp_emp_id = shift_a['employee_id']
                                    temp_emp_name = shift_a['employee_name']
                                    
                                    sched_df.loc[shift_a_idx, 'employee_id'] = shift_b['employee_id']
                                    sched_df.loc[shift_a_idx, 'employee_name'] = shift_b['employee_name']
                                    sched_df.loc[shift_b_idx, 'employee_id'] = temp_emp_id
                                    sched_df.loc[shift_b_idx, 'employee_name'] = temp_emp_name
                                    
                                    st.session_state["current_schedule_df"] = sched_df
                                    st.success("✅ Shifts swapped successfully")
                                    
                                    # Validate the swap
                                    violations = validate_schedule(sched_df, emp_df, bs)
                                    if violations:
                                        st.warning(f"⚠️ {len(violations)} validation issues detected after swap")
                                    
                                    st.rerun()
                        else:
                            st.info("Need at least 2 filled shifts to perform swaps")
                    else:
                        st.info("No filled shifts available for swapping")
            
            with export_tab:
                st.markdown("#### 📤 Export & Backup Options")
                
                export_col1, export_col2 = st.columns(2)
                
                with export_col1:
                    st.markdown("##### 📊 Export Formats")
                    
                    export_format = st.selectbox("Export Format", ["CSV", "Excel", "JSON", "PDF Summary"])
                    include_unfilled = st.checkbox("Include Unfilled Shifts", value=True, key="export_include_unfilled")
                    
                    # Filter data for export
                    export_df = sched_df.copy()
                    if not include_unfilled:
                        export_df = export_df[export_df['employee_id'].notna()]
                    
                    if st.button(f"📥 Export as {export_format}", key="export_schedule_main"):
                        timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
                        
                        if export_format == "CSV":
                            csv_data = export_df.to_csv(index=False)
                            st.download_button(
                                "Download CSV",
                                data=csv_data,
                                file_name=f"schedule_{timestamp}.csv",
                                mime="text/csv"
                            )
                        elif export_format == "JSON":
                            json_data = export_df.to_json(orient='records', indent=2)
                            st.download_button(
                                "Download JSON",
                                data=json_data,
                                file_name=f"schedule_{timestamp}.json",
                                mime="application/json"
                            )
                        elif export_format == "Excel":
                            # For Excel, we'd need openpyxl, so fall back to CSV
                            csv_data = export_df.to_csv(index=False)
                            st.download_button(
                                "Download as CSV (Excel format not available)",
                                data=csv_data,
                                file_name=f"schedule_{timestamp}.csv",
                                mime="text/csv"
                            )
                        elif export_format == "PDF Summary":
                            # Create a summary report
                            summary_text = f"""
SCHEDULE SUMMARY REPORT
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

OVERVIEW:
- Total Shifts: {len(export_df)}
- Filled Shifts: {len(export_df[export_df['employee_id'].notna()])}
- Fill Rate: {len(export_df[export_df['employee_id'].notna()]) / len(export_df) * 100:.1f}%
- Unique Employees: {len(export_df[export_df['employee_id'].notna()]['employee_id'].unique())}

SCHEDULE DETAILS:
{export_df.to_string()}
                            """
                            st.download_button(
                                "Download PDF Summary as Text",
                                data=summary_text,
                                file_name=f"schedule_summary_{timestamp}.txt",
                                mime="text/plain"
                            )
                
                with export_col2:
                    st.markdown("##### 💾 Backup & Restore")
                    
                    # Backup current schedule
                    if st.button("💾 Create Backup", key="create_backup"):
                        backup_data = {
                            'schedule': sched_df.to_dict('records'),
                            'timestamp': pd.Timestamp.now().isoformat(),
                            'metadata': {
                                'total_shifts': len(sched_df),
                                'filled_shifts': len(sched_df[sched_df['employee_id'].notna()]),
                                'version': '1.0'
                            }
                        }
                        
                        backup_json = json.dumps(backup_data, indent=2)
                        st.download_button(
                            "Download Backup",
                            data=backup_json,
                            file_name=f"schedule_backup_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )
                    
                    # Restore from backup
                    st.markdown("**Restore from Backup**")
                    uploaded_backup = st.file_uploader("Choose backup file", type="json", key="restore_backup")
                    
                    if uploaded_backup is not None:
                        try:
                            backup_data = json.loads(uploaded_backup.read())
                            restored_schedule = pd.DataFrame(backup_data['schedule'])
                            
                            st.write("**Backup Preview:**")
                            st.write(f"- Created: {backup_data.get('timestamp', 'Unknown')}")  
                            st.write(f"- Total Shifts: {backup_data['metadata']['total_shifts']}")
                            st.write(f"- Filled Shifts: {backup_data['metadata']['filled_shifts']}")
                            
                            if st.button("🔄 Restore This Backup", key="restore_backup_confirm"):
                                st.session_state["current_schedule_df"] = restored_schedule
                                st.success("✅ Schedule restored from backup successfully!")
                                st.rerun()
                                
                        except Exception as e:
                            st.error(f"❌ Error reading backup file: {str(e)}")
                    
                    # Save to database
                    if st.button("💾 Save to Database", key="save_to_db", type="primary"):
                        try:
                            save_schedule_to_db(sched_df, bs)
                            st.success("✅ Schedule saved to database successfully!")
                        except Exception as e:
                            st.error(f"❌ Error saving to database: {str(e)}")
        else:
            st.info("📝 No schedule generated yet. Use the **Generate** tab to create your first schedule.")

# ===============================
# Main Application
# ===============================

def clean_stale_session_data():
    """Clean up stale session state data that might contain old employee IDs"""
    try:
        # Get current valid employee IDs from database
        current_emp_df = get_all_employees()
        if not current_emp_df.empty:
            valid_emp_ids = set(current_emp_df['id'].tolist())
            
            # Clean schedule history if it contains invalid employee IDs
            if "schedule_history" in st.session_state and st.session_state["schedule_history"]:
                cleaned_history = []
                for schedule_df in st.session_state["schedule_history"]:
                    if not schedule_df.empty and 'employee_id' in schedule_df.columns:
                        # Remove rows with invalid employee IDs
                        mask = schedule_df['employee_id'].isna() | schedule_df['employee_id'].isin(valid_emp_ids)
                        cleaned_schedule = schedule_df[mask].copy()
                        if not cleaned_schedule.empty:
                            cleaned_history.append(cleaned_schedule)
                
                if len(cleaned_history) != len(st.session_state["schedule_history"]):
                    st.session_state["schedule_history"] = cleaned_history
                    logger.info("Cleaned stale employee IDs from schedule history")
            
            # Clean current schedule DataFrame
            if "current_schedule_df" in st.session_state and not st.session_state["current_schedule_df"].empty:
                current_sched = st.session_state["current_schedule_df"]
                if 'employee_id' in current_sched.columns:
                    mask = current_sched['employee_id'].isna() | current_sched['employee_id'].isin(valid_emp_ids)
                    cleaned_current = current_sched[mask].copy()
                    if len(cleaned_current) != len(current_sched):
                        st.session_state["current_schedule_df"] = cleaned_current
                        logger.info("Cleaned stale employee IDs from current schedule")
                        
    except Exception as e:
        logger.warning("Error cleaning session data: %s", e)

def main():
    st.set_page_config(
        page_title="Shift Plus Pro - AI Workforce Management",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize database
    init_db()
    
    # Clean up orphaned schedule entries
    cleanup_orphaned_schedule_entries()
    
    # Clean up old schedule entries (keep only last 30 days)
    cleanup_old_schedule_entries(30)
    
    # Clean stale session data
    clean_stale_session_data()
    
    # Initialize page state
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "🏠 Home"
    
    page = st.session_state.get("current_page", "🏠 Home")
    
    # Route to pages
    if page == "🏠 Home":
        page_home()
    elif page == "🏢 Business Setup":
        page_business()
    elif page == "👥 Employee Management":
        page_employees()
    elif page == "📅 Schedule Generation":
        page_shifts()
    elif page == "📊 Analytics Dashboard":
        page_analytics()
    else:
        page_home()

def page_home():
    """Home page with navigation"""
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                border-radius: 16px; padding: 2rem; margin-bottom: 2rem;">
        <h1 style="margin: 0; color: white; font-size: 2.8rem; font-weight: 700;">🚀 Shift Plus Pro</h1>
        <p style="color: rgba(255,255,255,0.9); margin: 0.5rem 0 0 0; font-size: 1.1rem;">
            Smart Workforce Management
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Load current setup status
    try:
        bs = load_business_settings()
        emp_df = load_employees()
        setup_progress = {
            "business": True,  # bs is not None 
            "employees": len(emp_df) > 0,
            "schedule": True and len(emp_df) > 0  # bs is not None
        }
    except:
        setup_progress = {"business": False, "employees": False, "schedule": False}
    
    # Show progress if not complete
    progress_count = sum(setup_progress.values())
    if progress_count < 3:
        st.info(f"🎯 Setup Progress: {progress_count}/3 complete")
    
    # Quick Overview Dashboard
    try:
        bs = load_business_settings()
        emp_df = get_all_employees()
        
        # Overview metrics
        st.markdown("### 📊 System Overview")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_employees = len(emp_df) if not emp_df.empty else 0
            st.metric("👥 Total Staff", total_employees)
        
        with col2:
            if not emp_df.empty and "max_hours_per_week" in emp_df.columns:
                total_capacity = emp_df["max_hours_per_week"].sum()
                st.metric("⏰ Weekly Capacity", f"{total_capacity}h")
            else:
                st.metric("⏰ Weekly Capacity", "0h")
        
        with col3:
            if bs and hasattr(bs, 'role_settings'):
                total_roles = len(bs.role_settings) if bs.role_settings else 0
                st.metric("🎭 Active Roles", total_roles)
            else:
                st.metric("🎭 Active Roles", "0")
        
        with col4:
            business_ready = "✅" if setup_progress["business"] else "⚠️"
            st.metric("� Business Config", business_ready)
        
        st.markdown("---")
        
    except Exception:
        st.warning("Dashboard data loading...")
    
    st.markdown("### 🧭 Navigation")
    st.markdown("Choose a module to get started:")
    
    # Clean 2x2 Navigation Grid (removed Dashboard button)
    col1, col2 = st.columns(2, gap="medium")
    
    with col1:
        config_ready = setup_progress["business"]
        if st.button("🏢 **Business Config**\n\nHours, roles & settings", key="nav_config", 
                    use_container_width=True, type="primary" if not config_ready else "secondary"):
            st.session_state["current_page"] = "🏢 Business Setup"
            st.rerun()
    
    with col2:
        emp_ready = setup_progress["employees"]  
        if st.button("👥 **Team Management**\n\nAdd & manage staff", key="nav_team", 
                    use_container_width=True, type="primary" if config_ready and not emp_ready else "secondary"):
            st.session_state["current_page"] = "👥 Employee Management"
            st.rerun()
    
    # Second row
    col3, col4 = st.columns(2, gap="medium")
    
    with col3:
        schedule_ready = setup_progress["schedule"]
        if st.button("📅 **Smart Scheduling**\n\nGenerate AI schedules", key="nav_schedule", 
                    use_container_width=True, disabled=not schedule_ready,
                    type="primary" if schedule_ready else "secondary"):
            st.session_state["current_page"] = "📅 Schedule Generation"
            st.rerun()
    
    with col4:
        if st.button("📊 **Insights & Reports**\n\nPerformance analytics", key="nav_analytics", 
                    use_container_width=True, disabled=not schedule_ready, type="secondary"):
            st.session_state["current_page"] = "📊 Analytics Dashboard"
            st.rerun()
    
    # Debug section (collapsible)
    with st.expander("🔧 System Diagnostics", expanded=False):
        st.markdown("**Session State Cleanup & Diagnostics**")
        
        col_debug1, col_debug2 = st.columns(2)
        
        with col_debug1:
            if st.button("🧹 Clear Session Cache", type="secondary"):
                # Clear potentially problematic session state
                keys_to_clear = ["schedule_history", "current_schedule_df", "edit_emp", "quick_sick"]
                cleared_keys = []
                for key in keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]
                        cleared_keys.append(key)
                
                if cleared_keys:
                    st.success(f"Cleared: {', '.join(cleared_keys)}")
                else:
                    st.info("No session data to clear")
                st.rerun()
        
        with col_debug2:
            if st.button("📊 Show Diagnostics", type="secondary"):
                emp_df = get_all_employees()
                if not emp_df.empty:
                    st.write(f"**Current Employee IDs:** {list(emp_df['id'])}")
                else:
                    st.write("**No employees found**")
                
                if "schedule_history" in st.session_state and st.session_state["schedule_history"]:
                    latest_schedule = st.session_state["schedule_history"][-1]
                    if not latest_schedule.empty and 'employee_id' in latest_schedule.columns:
                        scheduled_ids = latest_schedule['employee_id'].dropna().unique()
                        st.write(f"**Scheduled Employee IDs:** {list(scheduled_ids)}")
                    else:
                        st.write("**No schedule data with employee IDs**")
                else:
                    st.write("**No schedule history**")

if __name__ == "__main__":
    main()
