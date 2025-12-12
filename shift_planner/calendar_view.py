# -*- coding: utf-8 -*-
"""
Interactive calendar component with modern UI.
Provides monthly and weekly calendar views with event handling.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date as dt_date
from typing import Dict, List, Any
import calendar
from constants import DAYS, SHIFT_TIMES


def get_month_calendar_data(year: int, month: int, schedule_df: pd.DataFrame) -> Dict:
    """Generate calendar data structure for a month."""
    cal = calendar.monthcalendar(year, month)
    
    # Convert schedule to date-keyed dict
    schedule_dict = {}
    if not schedule_df.empty:
        df = schedule_df.copy()
        df['Ημερομηνία'] = pd.to_datetime(df['Ημερομηνία']).dt.date
        
        for date, group in df.groupby('Ημερομηνία'):
            schedule_dict[date] = group.to_dict('records')
    
    return {
        'calendar': cal,
        'schedule': schedule_dict
    }


@st.fragment
def render_calendar_view(schedule_df: pd.DataFrame, company: Dict, employees: List[Dict]):
    """Render interactive monthly calendar view."""
    
    st.markdown("### 📅 Οπτικοποίηση Ημερολογίου")
    
    # Date navigation
    col1, col2, col3 = st.columns([1, 2, 1])
    
    current_date = st.session_state.get('calendar_date', datetime.now())
    
    with col1:
        if st.button("◀ Προηγούμενος", use_container_width=True):
            if current_date.month == 1:
                current_date = current_date.replace(year=current_date.year - 1, month=12)
            else:
                current_date = current_date.replace(month=current_date.month - 1)
            st.session_state.calendar_date = current_date
            st.rerun()
    
    with col2:
        month_names = [
            'Ιανουάριος', 'Φεβρουάριος', 'Μάρτιος', 'Απρίλιος', 'Μάιος', 'Ιούνιος',
            'Ιούλιος', 'Αύγουστος', 'Σεπτέμβριος', 'Οκτώβριος', 'Νοέμβριος', 'Δεκέμβριος'
        ]
        st.markdown(f"<h3 style='text-align: center;'>{month_names[current_date.month - 1]} {current_date.year}</h3>", 
                   unsafe_allow_html=True)
    
    with col3:
        if st.button("Επόμενος ▶", use_container_width=True):
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
            st.session_state.calendar_date = current_date
            st.rerun()
    
    # Get calendar data
    cal_data = get_month_calendar_data(current_date.year, current_date.month, schedule_df)
    
    # Render calendar grid
    st.markdown("""
    <style>
    .calendar-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 8px;
        margin-top: 20px;
    }
    .calendar-day-header {
        text-align: center;
        font-weight: bold;
        padding: 10px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 8px;
    }
    .calendar-day {
        min-height: 100px;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 8px;
        background: white;
        cursor: pointer;
        transition: all 0.2s;
    }
    .calendar-day:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    .calendar-day-number {
        font-weight: bold;
        font-size: 1.1em;
        margin-bottom: 5px;
    }
    .calendar-day-empty {
        background: #f5f5f5;
    }
    .calendar-shift-badge {
        font-size: 0.75em;
        padding: 2px 6px;
        border-radius: 4px;
        margin: 2px 0;
        display: block;
    }
    .shift-morning {
        background: #FFF9C4;
        color: #F57F17;
    }
    .shift-afternoon {
        background: #FFE0B2;
        color: #E65100;
    }
    .shift-evening {
        background: #B3E5FC;
        color: #01579B;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Day headers
    cols = st.columns(7)
    day_names_short = ["Δευ", "Τρί", "Τετ", "Πέμ", "Παρ", "Σάβ", "Κυρ"]
    for i, day in enumerate(day_names_short):
        cols[i].markdown(f"<div class='calendar-day-header'>{day}</div>", unsafe_allow_html=True)
    
    # Calendar days
    for week in cal_data['calendar']:
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day == 0:
                cols[i].markdown("<div class='calendar-day calendar-day-empty'></div>", unsafe_allow_html=True)
            else:
                date_obj = dt_date(current_date.year, current_date.month, day)
                day_schedule = cal_data['schedule'].get(date_obj, [])
                
                # Count shifts by type
                shift_counts = {}
                for entry in day_schedule:
                    shift = entry['Βάρδια']
                    shift_counts[shift] = shift_counts.get(shift, 0) + 1
                
                # Determine shift class
                shift_classes = {
                    'Πρωί': 'shift-morning',
                    'Απόγευμα': 'shift-afternoon',
                    'Βράδυ': 'shift-evening'
                }
                
                badges = ""
                for shift, count in shift_counts.items():
                    css_class = shift_classes.get(shift, '')
                    badges += f"<span class='calendar-shift-badge {css_class}'>{shift}: {count}</span>"
                
                with cols[i]:
                    st.markdown(
                        f"<div class='calendar-day'>"
                        f"<div class='calendar-day-number'>{day}</div>"
                        f"{badges}"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                    
                    # Add click interaction for day details
                    if st.button(f"📋", key=f"day_{date_obj}", help=f"Δείτε λεπτομέρειες για {date_obj}"):
                        show_day_details_dialog(date_obj, day_schedule, company, employees)


@st.dialog("📅 Λεπτομέρειες Ημέρας", width="large")
def show_day_details_dialog(date: dt_date, day_schedule: List[Dict], company: Dict, employees: List[Dict]):
    """Show detailed view of a specific day's schedule."""
    
    day_name = DAYS[date.weekday()]
    st.markdown(f"### {day_name}, {date.strftime('%d/%m/%Y')}")
    
    if not day_schedule:
        st.info("Δεν υπάρχουν προγραμματισμένες βάρδιες για αυτή την ημέρα")
        return
    
    # Group by shift
    shifts_grouped = {}
    for entry in day_schedule:
        shift = entry['Βάρδια']
        if shift not in shifts_grouped:
            shifts_grouped[shift] = []
        shifts_grouped[shift].append(entry)
    
    # Display each shift
    for shift in company.get('active_shifts', []):
        if shift in shifts_grouped:
            with st.expander(f"🕐 {shift} ({len(shifts_grouped[shift])} άτομα)", expanded=True):
                shift_df = pd.DataFrame(shifts_grouped[shift])
                st.dataframe(
                    shift_df[['Υπάλληλος', 'Ρόλος', 'Ώρες']],
                    use_container_width=True,
                    hide_index=True
                )
                
                # Show shift time
                start_h, end_h = SHIFT_TIMES.get(shift, (0, 0))
                st.caption(f"⏰ Ώρες: {start_h:02d}:00 - {end_h:02d}:00")
    
    st.divider()
    
    # Quick actions
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✏️ Επεξεργασία Ημέρας", use_container_width=True):
            st.info("Η λειτουργία θα προστεθεί σύντομα")
    
    with col2:
        if st.button("📋 Αντιγραφή σε άλλη ημέρα", use_container_width=True):
            st.info("Η λειτουργία θα προστεθεί σύντομα")


@st.fragment
def render_weekly_timeline(schedule_df: pd.DataFrame, start_date: dt_date):
    """Render a weekly timeline view with hour blocks."""
    
    st.markdown("### 📊 Εβδομαδιαία Προβολή")
    
    if schedule_df.empty:
        st.info("Δεν υπάρχουν δεδομένα για προβολή")
        return
    
    # Filter for current week
    end_date = start_date + timedelta(days=6)
    df = schedule_df.copy()
    df['Ημερομηνία'] = pd.to_datetime(df['Ημερομηνία']).dt.date
    week_df = df[(df['Ημερομηνία'] >= start_date) & (df['Ημερομηνία'] <= end_date)]
    
    if week_df.empty:
        st.info(f"Δεν υπάρχουν βάρδιες για την εβδομάδα {start_date} - {end_date}")
        return
    
    # Create timeline grid
    hours = range(6, 24)  # 6 AM to 11 PM
    days = [start_date + timedelta(days=i) for i in range(7)]
    
    # Create grid data
    grid_html = "<div style='overflow-x: auto;'><table style='width: 100%; border-collapse: collapse;'>"
    
    # Header row
    grid_html += "<tr><th style='border: 1px solid #ddd; padding: 8px; background: #f5f5f5;'>Ώρα</th>"
    for day in days:
        day_name = DAYS[day.weekday()][:3]
        grid_html += f"<th style='border: 1px solid #ddd; padding: 8px; background: #f5f5f5;'>{day_name}<br>{day.strftime('%d/%m')}</th>"
    grid_html += "</tr>"
    
    # Hour rows
    for hour in hours:
        grid_html += f"<tr><td style='border: 1px solid #ddd; padding: 8px; font-weight: bold;'>{hour:02d}:00</td>"
        
        for day in days:
            day_shifts = week_df[week_df['Ημερομηνία'] == day]
            
            # Find shifts active during this hour
            active_employees = []
            for _, shift_entry in day_shifts.iterrows():
                shift = shift_entry['Βάρδια']
                start_h, end_h = SHIFT_TIMES.get(shift, (0, 0))
                
                # Handle overnight shifts
                if end_h < start_h:
                    if hour >= start_h or hour < end_h:
                        active_employees.append(f"{shift_entry['Υπάλληλος'][:10]}")
                else:
                    if start_h <= hour < end_h:
                        active_employees.append(f"{shift_entry['Υπάλληλος'][:10]}")
            
            cell_color = "#e8f5e9" if active_employees else "white"
            cell_content = f"<br>".join(active_employees) if active_employees else ""
            grid_html += f"<td style='border: 1px solid #ddd; padding: 4px; font-size: 0.8em; background: {cell_color};'>{cell_content}</td>"
        
        grid_html += "</tr>"
    
    grid_html += "</table></div>"
    
    st.markdown(grid_html, unsafe_allow_html=True)
