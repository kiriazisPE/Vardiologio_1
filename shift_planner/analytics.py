# -*- coding: utf-8 -*-
"""
Analytics module for advanced data visualization and insights.
Uses Plotly for interactive charts and Streamlit's latest features.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from typing import Dict, List, Any
from constants import DAYS, SHIFT_TIMES


def calculate_employee_metrics(schedule_df: pd.DataFrame, employees: List[Dict]) -> pd.DataFrame:
    """Calculate key metrics per employee."""
    if schedule_df.empty:
        return pd.DataFrame()
    
    metrics = []
    for emp in employees:
        emp_schedule = schedule_df[schedule_df["Υπάλληλος"] == emp["name"]]
        
        if emp_schedule.empty:
            continue
            
        total_hours = emp_schedule["Ώρες"].sum()
        total_shifts = len(emp_schedule)
        
        # Calculate unique days worked
        unique_dates = emp_schedule["Ημερομηνία"].nunique()
        
        # Average hours per shift
        avg_hours = total_hours / total_shifts if total_shifts > 0 else 0
        
        # Shift distribution
        shift_counts = emp_schedule["Βάρδια"].value_counts().to_dict()
        
        metrics.append({
            "Υπάλληλος": emp["name"],
            "Σύνολο Ωρών": total_hours,
            "Σύνολο Βαρδιών": total_shifts,
            "Ημέρες Εργασίας": unique_dates,
            "Μέσος Όρος Ωρών/Βάρδια": round(avg_hours, 2),
            "Κατανομή Βαρδιών": shift_counts
        })
    
    return pd.DataFrame(metrics)


@st.fragment
def render_hours_distribution_chart(schedule_df: pd.DataFrame):
    """Render interactive hours distribution chart using Plotly."""
    if schedule_df.empty:
        st.info("Δεν υπάρχουν δεδομένα για οπτικοποίηση")
        return
    
    # Group by employee and sum hours
    hours_by_emp = schedule_df.groupby("Υπάλληλος")["Ώρες"].sum().reset_index()
    hours_by_emp = hours_by_emp.sort_values("Ώρες", ascending=True)
    
    fig = go.Figure(go.Bar(
        x=hours_by_emp["Ώρες"],
        y=hours_by_emp["Υπάλληλος"],
        orientation='h',
        marker=dict(
            color=hours_by_emp["Ώρες"],
            colorscale='Viridis',
            showscale=True
        ),
        text=hours_by_emp["Ώρες"],
        textposition='auto',
    ))
    
    fig.update_layout(
        title="Κατανομή Ωρών ανά Υπάλληλο",
        xaxis_title="Ώρες",
        yaxis_title="Υπάλληλος",
        height=max(400, len(hours_by_emp) * 40),
        template="plotly_white"
    )
    
    st.plotly_chart(fig, use_container_width=True)


@st.fragment
def render_shift_distribution_chart(schedule_df: pd.DataFrame):
    """Render shift distribution pie chart."""
    if schedule_df.empty:
        st.info("Δεν υπάρχουν δεδομένα για οπτικοποίηση")
        return
    
    shift_counts = schedule_df["Βάρδια"].value_counts()
    
    fig = go.Figure(data=[go.Pie(
        labels=shift_counts.index,
        values=shift_counts.values,
        hole=.3,
        textinfo='label+percent',
        marker=dict(colors=px.colors.qualitative.Set3)
    )])
    
    fig.update_layout(
        title="Κατανομή Βαρδιών",
        template="plotly_white",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)


@st.fragment
def render_timeline_chart(schedule_df: pd.DataFrame):
    """Render Gantt-style timeline of shifts."""
    if schedule_df.empty:
        st.info("Δεν υπάρχουν δεδομένα για οπτικοποίηση")
        return
    
    # Prepare data for Gantt chart
    df = schedule_df.copy()
    df["Ημερομηνία"] = pd.to_datetime(df["Ημερομηνία"])
    
    # Create start and end times for each shift
    gantt_data = []
    for _, row in df.iterrows():
        shift = row["Βάρδια"]
        start_hour, end_hour = SHIFT_TIMES.get(shift, (9, 17))
        
        start = pd.Timestamp.combine(row["Ημερομηνία"].date(), pd.Timestamp(f'{start_hour:02d}:00:00').time())
        
        # Handle overnight shifts
        if end_hour < start_hour:
            end = start + timedelta(hours=(24 - start_hour + end_hour))
        else:
            end = start + timedelta(hours=(end_hour - start_hour))
        
        gantt_data.append({
            "Task": row["Υπάλληλος"],
            "Start": start,
            "Finish": end,
            "Resource": row["Βάρδια"]
        })
    
    gantt_df = pd.DataFrame(gantt_data)
    
    fig = px.timeline(
        gantt_df, 
        x_start="Start", 
        x_end="Finish", 
        y="Task",
        color="Resource",
        title="Χρονοδιάγραμμα Βαρδιών"
    )
    
    fig.update_yaxes(categoryorder="total ascending")
    fig.update_layout(height=max(400, len(gantt_df["Task"].unique()) * 30))
    
    st.plotly_chart(fig, use_container_width=True)


@st.fragment
def render_role_coverage_heatmap(schedule_df: pd.DataFrame, active_shifts: List[str], roles: List[str]):
    """Render heatmap showing role coverage across shifts and dates."""
    if schedule_df.empty:
        st.info("Δεν υπάρχουν δεδομένα για οπτικοποίηση")
        return
    
    df = schedule_df.copy()
    df["Ημερομηνία"] = pd.to_datetime(df["Ημερομηνία"])
    
    # Create pivot table: dates x (shift, role)
    pivot_data = []
    unique_dates = sorted(df["Ημερομηνία"].unique())
    
    for date in unique_dates:
        date_str = date.strftime('%Y-%m-%d')
        row_data = {"Ημερομηνία": date_str}
        
        for shift in active_shifts:
            for role in roles:
                count = len(df[(df["Ημερομηνία"] == date) & 
                              (df["Βάρδια"] == shift) & 
                              (df["Ρόλος"] == role)])
                row_data[f"{shift}_{role}"] = count
        
        pivot_data.append(row_data)
    
    pivot_df = pd.DataFrame(pivot_data)
    
    if len(pivot_df) > 0:
        pivot_df = pivot_df.set_index("Ημερομηνία")
        
        fig = go.Figure(data=go.Heatmap(
            z=pivot_df.values.T,
            x=pivot_df.index,
            y=pivot_df.columns,
            colorscale='RdYlGn',
            text=pivot_df.values.T,
            texttemplate='%{text}',
            textfont={"size": 10},
            colorbar=dict(title="Άτομα")
        ))
        
        fig.update_layout(
            title="Θερμικός Χάρτης Κάλυψης Ρόλων",
            xaxis_title="Ημερομηνία",
            yaxis_title="Βάρδια_Ρόλος",
            height=max(400, len(pivot_df.columns) * 25),
            template="plotly_white"
        )
        
        st.plotly_chart(fig, use_container_width=True)


@st.dialog("📊 Αναλυτικά Στατιστικά")
def show_detailed_analytics(schedule_df: pd.DataFrame, employees: List[Dict], 
                           active_shifts: List[str], roles: List[str]):
    """Show comprehensive analytics in a dialog."""
    
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Ώρες", "🔄 Βάρδιες", "📅 Χρονοδιάγραμμα", "🎯 Κάλυψη"])
    
    with tab1:
        render_hours_distribution_chart(schedule_df)
        
        st.divider()
        metrics_df = calculate_employee_metrics(schedule_df, employees)
        if not metrics_df.empty:
            st.dataframe(
                metrics_df.drop(columns=["Κατανομή Βαρδιών"]),
                use_container_width=True,
                hide_index=True
            )
    
    with tab2:
        render_shift_distribution_chart(schedule_df)
        
        st.divider()
        st.subheader("Κατανομή ανά Υπάλληλο")
        for emp in employees:
            emp_sched = schedule_df[schedule_df["Υπάλληλος"] == emp["name"]]
            if not emp_sched.empty:
                shift_dist = emp_sched["Βάρδια"].value_counts()
                with st.expander(f"👤 {emp['name']}"):
                    cols = st.columns(len(shift_dist))
                    for idx, (shift, count) in enumerate(shift_dist.items()):
                        cols[idx].metric(shift, count)
    
    with tab3:
        render_timeline_chart(schedule_df)
    
    with tab4:
        render_role_coverage_heatmap(schedule_df, active_shifts, roles)


@st.fragment
def render_kpi_cards(schedule_df: pd.DataFrame, employees: List[Dict], 
                    company: Dict, violations_df: pd.DataFrame = None):
    """Render KPI cards with modern styling."""
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Total shifts
    total_shifts = len(schedule_df) if not schedule_df.empty else 0
    col1.metric(
        "📋 Συνολικές Βάρδιες",
        total_shifts,
        help="Συνολικός αριθμός προγραμματισμένων βαρδιών"
    )
    
    # Total employees
    col2.metric(
        "👥 Υπάλληλοι",
        len(employees),
        help="Συνολικός αριθμός υπαλλήλων"
    )
    
    # Total hours
    total_hours = schedule_df["Ώρες"].sum() if not schedule_df.empty else 0
    col3.metric(
        "⏱️ Σύνολο Ωρών",
        f"{total_hours:.1f}h",
        help="Συνολικές ώρες εργασίας"
    )
    
    # Violations
    violation_count = len(violations_df) if violations_df is not None and not violations_df.empty else 0
    col4.metric(
        "⚠️ Παραβιάσεις",
        violation_count,
        delta=f"-{violation_count}" if violation_count > 0 else "0",
        delta_color="inverse",
        help="Αριθμός παραβιάσεων κανόνων"
    )


@st.fragment
def render_employee_workload_comparison(schedule_df: pd.DataFrame, employees: List[Dict]):
    """Render comparison of employee workload."""
    if schedule_df.empty or not employees:
        return
    
    st.subheader("⚖️ Σύγκριση Φόρτου Εργασίας")
    
    workload = schedule_df.groupby("Υπάλληλος")["Ώρες"].sum().reset_index()
    workload = workload.sort_values("Ώρες", ascending=False)
    
    # Calculate statistics
    avg_hours = workload["Ώρες"].mean()
    max_hours = workload["Ώρες"].max()
    min_hours = workload["Ώρες"].min()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Μέσος Όρος", f"{avg_hours:.1f}h")
    col2.metric("Μέγιστο", f"{max_hours:.1f}h")
    col3.metric("Ελάχιστο", f"{min_hours:.1f}h")
    
    # Horizontal bar chart
    fig = go.Figure()
    
    colors = ['#FF6B6B' if h > avg_hours * 1.2 else '#4ECDC4' if h < avg_hours * 0.8 else '#95E1D3' 
              for h in workload["Ώρες"]]
    
    fig.add_trace(go.Bar(
        y=workload["Υπάλληλος"],
        x=workload["Ώρες"],
        orientation='h',
        marker=dict(color=colors),
        text=workload["Ώρες"].apply(lambda x: f"{x:.1f}h"),
        textposition='auto'
    ))
    
    # Add average line
    fig.add_vline(x=avg_hours, line_dash="dash", line_color="red", 
                  annotation_text=f"Μέσος: {avg_hours:.1f}h")
    
    fig.update_layout(
        xaxis_title="Ώρες",
        yaxis_title="",
        height=max(300, len(workload) * 35),
        template="plotly_white",
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Fairness indicator
    variance = workload["Ώρες"].var()
    if variance < 10:
        st.success("✅ Ο φόρτος εργασίας είναι ισορροπημένος")
    elif variance < 25:
        st.warning("⚠️ Υπάρχει μέτρια ανισορροπία στον φόρτο εργασίας")
    else:
        st.error("❌ Ο φόρτος εργασίας χρειάζεται επανακατανομή")
