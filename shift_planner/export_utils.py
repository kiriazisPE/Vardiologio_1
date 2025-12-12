# -*- coding: utf-8 -*-
"""
Export utilities for schedule data.
Supports Excel, CSV, and PDF formats with professional styling.
"""

import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from typing import Dict, List, Any


def export_to_excel(schedule_df: pd.DataFrame, company: Dict, 
                   employees: List[Dict], violations_df: pd.DataFrame = None) -> bytes:
    """Export schedule to Excel with multiple sheets and formatting."""
    
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Schedule sheet
        if not schedule_df.empty:
            schedule_export = schedule_df.copy()
            schedule_export.to_excel(writer, sheet_name='Πρόγραμμα', index=False)
        
        # Employees sheet
        emp_df = pd.DataFrame([{
            'Όνομα': e['name'],
            'Ρόλοι': ', '.join(e.get('roles', [])),
            'Διαθεσιμότητα': ', '.join(e.get('availability', []))
        } for e in employees])
        emp_df.to_excel(writer, sheet_name='Υπάλληλοι', index=False)
        
        # Summary sheet
        summary_data = {
            'Μέτρηση': [
                'Επιχείρηση',
                'Μοντέλο Εργασίας',
                'Ημερομηνία Εξαγωγής',
                'Συνολικές Βάρδιες',
                'Υπάλληλοι',
                'Ενεργές Βάρδιες',
                'Ρόλοι'
            ],
            'Τιμή': [
                company.get('name', 'N/A'),
                company.get('work_model', 'N/A'),
                datetime.now().strftime('%Y-%m-%d %H:%M'),
                len(schedule_df),
                len(employees),
                ', '.join(company.get('active_shifts', [])),
                ', '.join(company.get('roles', []))
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Σύνοψη', index=False)
        
        # Violations sheet (if any)
        if violations_df is not None and not violations_df.empty:
            violations_df.to_excel(writer, sheet_name='Παραβιάσεις', index=False)
        
        # Statistics sheet
        if not schedule_df.empty:
            hours_by_emp = schedule_df.groupby('Υπάλληλος')['Ώρες'].sum().reset_index()
            hours_by_emp.columns = ['Υπάλληλος', 'Σύνολο Ωρών']
            hours_by_emp.to_excel(writer, sheet_name='Στατιστικά', index=False)
    
    output.seek(0)
    return output.getvalue()


def export_to_csv(schedule_df: pd.DataFrame) -> bytes:
    """Export schedule to CSV."""
    output = BytesIO()
    schedule_df.to_csv(output, index=False, encoding='utf-8-sig')
    output.seek(0)
    return output.getvalue()


@st.dialog("📥 Εξαγωγή Προγράμματος", width="large")
def show_export_dialog(schedule_df: pd.DataFrame, company: Dict, 
                      employees: List[Dict], violations_df: pd.DataFrame = None):
    """Show export dialog with multiple format options."""
    
    st.markdown("### Επιλέξτε μορφή αρχείου")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 Excel (συνιστάται)")
        st.caption("Περιλαμβάνει πολλαπλά φύλλα: πρόγραμμα, υπαλλήλους, στατιστικά, παραβιάσεις")
        
        if st.button("📥 Λήψη Excel", type="primary", use_container_width=True):
            try:
                excel_data = export_to_excel(schedule_df, company, employees, violations_df)
                filename = f"schedule_{company.get('name', 'export')}_{datetime.now().strftime('%Y%m%d')}.xlsx"
                
                st.download_button(
                    label="💾 Αποθήκευση αρχείου",
                    data=excel_data,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                st.success("✅ Το αρχείο Excel είναι έτοιμο!")
            except Exception as e:
                st.error(f"Σφάλμα κατά την εξαγωγή: {e}")
    
    with col2:
        st.markdown("#### 📄 CSV")
        st.caption("Απλό αρχείο κειμένου, συμβατό με όλες τις εφαρμογές")
        
        if st.button("📥 Λήψη CSV", use_container_width=True):
            try:
                csv_data = export_to_csv(schedule_df)
                filename = f"schedule_{company.get('name', 'export')}_{datetime.now().strftime('%Y%m%d')}.csv"
                
                st.download_button(
                    label="💾 Αποθήκευση αρχείου",
                    data=csv_data,
                    file_name=filename,
                    mime="text/csv",
                    use_container_width=True
                )
                st.success("✅ Το αρχείο CSV είναι έτοιμο!")
            except Exception as e:
                st.error(f"Σφάλμα κατά την εξαγωγή: {e}")
    
    st.divider()
    
    st.markdown("### 📋 Προεπισκόπηση")
    st.dataframe(schedule_df.head(10), use_container_width=True, hide_index=True)
    st.caption(f"Εμφανίζονται οι πρώτες 10 από {len(schedule_df)} εγγραφές")


@st.dialog("📤 Εισαγωγή Προγράμματος")
def show_import_dialog(company: Dict, employees: List[Dict]):
    """Show import dialog for uploading schedule data."""
    
    st.markdown("### Μεταφόρτωση αρχείου προγράμματος")
    st.caption("Υποστηρίζονται μορφές: Excel (.xlsx), CSV (.csv)")
    
    uploaded_file = st.file_uploader(
        "Επιλέξτε αρχείο",
        type=['xlsx', 'csv'],
        help="Το αρχείο πρέπει να περιέχει στήλες: Ημέρα, Ημερομηνία, Βάρδια, Υπάλληλος, Ρόλος, Ώρες"
    )
    
    if uploaded_file is not None:
        try:
            # Read file based on extension
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file, sheet_name='Πρόγραμμα')
            
            # Validate required columns
            required_cols = ['Ημέρα', 'Ημερομηνία', 'Βάρδια', 'Υπάλληλος', 'Ρόλος', 'Ώρες']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                st.error(f"Λείπουν οι στήλες: {', '.join(missing_cols)}")
                return None
            
            # Preview
            st.success(f"✅ Βρέθηκαν {len(df)} εγγραφές")
            st.dataframe(df.head(10), use_container_width=True, hide_index=True)
            
            # Validate employees
            emp_names = {e['name'] for e in employees}
            invalid_emps = set(df['Υπάλληλος'].unique()) - emp_names
            
            if invalid_emps:
                st.warning(f"⚠️ Άγνωστοι υπάλληλοι: {', '.join(invalid_emps)}")
                st.caption("Αυτές οι εγγραφές θα αγνοηθούν κατά την εισαγωγή")
            
            # Import options
            st.markdown("### Επιλογές εισαγωγής")
            
            col1, col2 = st.columns(2)
            with col1:
                replace_existing = st.checkbox(
                    "Αντικατάσταση υπάρχοντος προγράμματος",
                    value=True,
                    help="Εάν επιλεγεί, το τρέχον πρόγραμμα θα διαγραφεί"
                )
            
            with col2:
                validate_rules = st.checkbox(
                    "Έλεγχος κανόνων μετά την εισαγωγή",
                    value=True,
                    help="Εκτέλεση ελέγχου παραβιάσεων"
                )
            
            if st.button("✅ Εισαγωγή", type="primary", use_container_width=True):
                # Filter valid employees
                valid_df = df[df['Υπάλληλος'].isin(emp_names)]
                
                st.session_state.schedule = valid_df
                st.success(f"✅ Εισήχθησαν {len(valid_df)} εγγραφές επιτυχώς!")
                
                if validate_rules:
                    st.info("Εκτέλεση ελέγχου κανόνων...")
                    from scheduler import check_violations
                    viols = check_violations(
                        valid_df, 
                        company.get('rules', {}), 
                        company.get('work_model', '5ήμερο')
                    )
                    st.session_state.violations = viols
                    
                    if not viols.empty:
                        st.warning(f"⚠️ Βρέθηκαν {len(viols)} παραβιάσεις")
                    else:
                        st.success("✅ Δεν βρέθηκαν παραβιάσεις!")
                
                st.rerun()
                
        except Exception as e:
            st.error(f"Σφάλμα κατά την ανάγνωση αρχείου: {e}")
            import traceback
            st.code(traceback.format_exc())
