# -*- coding: utf-8 -*-
"""
Onboarding tour and help system for new users.
Provides interactive guides and tooltips.
"""

import streamlit as st
from typing import Dict, List, Any


def initialize_onboarding():
    """Initialize onboarding state."""
    if "onboarding_completed" not in st.session_state:
        st.session_state.onboarding_completed = False
    if "onboarding_step" not in st.session_state:
        st.session_state.onboarding_step = 0
    if "show_help_panel" not in st.session_state:
        st.session_state.show_help_panel = False


@st.dialog("👋 Καλώς Ήρθατε στο Shift Planner Pro!", width="large")
def show_welcome_tour():
    """Show welcome tour for first-time users."""
    
    st.markdown("""
    # 🎉 Καλώς ήρθατε!
    
    Το **Shift Planner Pro** είναι η πλήρης λύση διαχείρισης προγράμματος εργασίας.
    
    ### ✨ Χαρακτηριστικά
    
    - 📅 **Έξυπνος Προγραμματισμός**: Αυτόματη δημιουργία βαρδιών με τεχνητή νοημοσύνη
    - 👥 **Διαχείριση Προσωπικού**: Ολοκληρωμένη βάση δεδομένων υπαλλήλων
    - 📊 **Αναλυτικά**: Οπτικοποίηση και αναφορές σε πραγματικό χρόνο
    - ⚖️ **Έλεγχος Κανόνων**: Αυτόματος έλεγχος εργατικών κανονισμών
    - 🔄 **Ανταλλαγές Βαρδιών**: Σύστημα αιτημάτων και εγκρίσεων
    - 📥 **Εξαγωγή/Εισαγωγή**: Υποστήριξη Excel, CSV, PDF
    
    ### 📚 Βασικά Βήματα
    
    1. **Επιλέξτε ή Δημιουργήστε Επιχείρηση**
    2. **Προσθέστε Υπαλλήλους** με ρόλους και διαθεσιμότητα
    3. **Δημιουργήστε Πρόγραμμα** αυτόματα ή χειροκίνητα
    4. **Ελέγξτε & Βελτιστοποιήστε** με αναλυτικά εργαλεία
    
    """)
    
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚀 Ξεκινήστε την Ξενάγηση", type="primary", use_container_width=True):
            st.session_state.onboarding_step = 1
            st.session_state.show_interactive_tour = True
            st.rerun()
    
    with col2:
        if st.button("⏭️ Παράλειψη", use_container_width=True):
            st.session_state.onboarding_completed = True
            st.rerun()


def show_contextual_help(page: str):
    """Show contextual help based on current page."""
    
    help_content = {
        "company": {
            "title": "🏢 Βοήθεια: Επιχείρηση",
            "content": """
            ### Ρυθμίσεις Επιχείρησης
            
            Σε αυτή τη σελίδα ρυθμίζετε τις βασικές παραμέτρους της επιχείρησής σας:
            
            - **Όνομα**: Το όνομα της επιχείρησης
            - **Μοντέλο Εργασίας**: 5ήμερο, 6ήμερο ή 7ήμερο
            - **Βάρδιες**: Προσθέστε και διαχειριστείτε τύπους βαρδιών
            - **Ρόλοι**: Ορίστε ρόλους και προτεραιότητες
            - **Κανόνες**: Ορίστε όρια ωρών και ανάπαυσης
            
            💡 **Συμβουλή**: Ξεκινήστε με τις προεπιλεγμένες ρυθμίσεις και προσαρμόστε σταδιακά.
            """
        },
        "employees": {
            "title": "👥 Βοήθεια: Υπάλληλοι",
            "content": """
            ### Διαχείριση Υπαλλήλων
            
            Προσθέστε και διαχειριστείτε το προσωπικό σας:
            
            - **Όνομα**: Πλήρες όνομα υπαλλήλου
            - **Ρόλοι**: Επιλέξτε έναν ή περισσότερους ρόλους
            - **Διαθεσιμότητα**: Ορίστε σε ποιες βάρδιες είναι διαθέσιμος
            
            ⚡ **Γρήγορες Ενέργειες**:
            - Κλικ στο όνομα για επεξεργασία
            - Χρησιμοποιήστε demo δεδομένα για δοκιμή
            """
        },
        "schedule": {
            "title": "📅 Βοήθεια: Πρόγραμμα",
            "content": """
            ### Δημιουργία Προγράμματος
            
            Δύο τρόποι δημιουργίας:
            
            1. **Αυτόματη Δημιουργία**:
               - Επιλέξτε εμβέλεια (εβδομαδιαία/μηνιαία)
               - Κλικ "Δημιουργία"
               - Το σύστημα θα δημιουργήσει βέλτιστο πρόγραμμα
            
            2. **Χειροκίνητη Επεξεργασία**:
               - Χρησιμοποιήστε τον visual builder
               - Επιλέξτε ρόλο για κάθε υπάλληλο ανά βάρδια
               - Αποθηκεύστε τις αλλαγές
            
            📊 **Αναλυτικά**: Κλικ στο κουμπί Αναλυτικά για λεπτομερείς αναφορές
            📥 **Εξαγωγή**: Λήψη σε Excel ή CSV
            """
        }
    }
    
    if page in help_content:
        with st.expander("❓ Βοήθεια", expanded=False):
            content = help_content[page]
            st.markdown(f"## {content['title']}")
            st.markdown(content['content'])


@st.fragment
def render_help_panel():
    """Render floating help panel."""
    
    if st.session_state.get("show_help_panel", False):
        with st.container():
            st.markdown("""
            <style>
            .help-panel {
                position: fixed;
                bottom: 20px;
                right: 20px;
                width: 300px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.15);
                padding: 16px;
                z-index: 1000;
            }
            </style>
            """, unsafe_allow_html=True)
            
            with st.container():
                st.markdown("### 💡 Γρήγορες Συμβουλές")
                
                tips = [
                    "Χρησιμοποιήστε Ctrl+K για γρήγορη αναζήτηση",
                    "Κάντε κλικ στα μετρικά για λεπτομέρειες",
                    "Σύρετε και αφήστε στον πίνακα βαρδιών",
                    "Πατήστε Esc για κλείσιμο διαλόγων"
                ]
                
                import random
                st.info(random.choice(tips))
                
                if st.button("✖️ Κλείσιμο", key="close_help_panel"):
                    st.session_state.show_help_panel = False
                    st.rerun()


def show_feature_highlight(feature_name: str, description: str):
    """Highlight a new or important feature."""
    
    with st.expander(f"✨ Νέο: {feature_name}", expanded=True):
        st.markdown(description)
        if st.button("Δοκιμάστε το!", key=f"try_{feature_name}"):
            st.balloons()
            st.success("Η λειτουργία είναι ενεργή!")


@st.fragment
def render_keyboard_shortcuts():
    """Display available keyboard shortcuts."""
    
    with st.expander("⌨️ Συντομεύσεις Πληκτρολογίου"):
        shortcuts = {
            "Ctrl+K": "Αναζήτηση",
            "Ctrl+S": "Αποθήκευση",
            "Ctrl+Z": "Αναίρεση",
            "Ctrl+Shift+E": "Εξαγωγή",
            "Ctrl+Shift+I": "Εισαγωγή",
            "Esc": "Κλείσιμο διαλόγου",
            "F1": "Βοήθεια"
        }
        
        for key, action in shortcuts.items():
            col1, col2 = st.columns([1, 2])
            col1.code(key)
            col2.write(action)


@st.dialog("📖 Οδηγός Χρήσης")
def show_user_guide():
    """Show comprehensive user guide."""
    
    tabs = st.tabs(["🚀 Ξεκινώντας", "👥 Υπάλληλοι", "📅 Πρόγραμμα", "📊 Αναλυτικά", "⚙️ Ρυθμίσεις"])
    
    with tabs[0]:
        st.markdown("""
        # Ξεκινώντας με το Shift Planner Pro
        
        ## 1. Δημιουργία Επιχείρησης
        
        1. Πηγαίνετε στη σελίδα "Επιλογή"
        2. Κλικ "Δημιουργία Νέας"
        3. Εισάγετε όνομα επιχείρησης
        
        ## 2. Ρύθμιση Παραμέτρων
        
        1. Επιλέξτε μοντέλο εργασίας (5/6/7 ημερών)
        2. Προσθέστε βάρδιες
        3. Ορίστε ρόλους
        4. Προσαρμόστε κανόνες
        
        ## 3. Προσθήκη Προσωπικού
        
        1. Μεταβείτε στη σελίδα "Υπάλληλοι"
        2. Προσθέστε υπαλλήλους έναν-έναν
        3. Ορίστε ρόλους και διαθεσιμότητα
        
        ## 4. Δημιουργία Προγράμματος
        
        1. Πηγαίνετε στη σελίδα "Πρόγραμμα"
        2. Επιλέξτε ημερομηνία έναρξης
        3. Κλικ "Δημιουργία"
        """)
    
    with tabs[1]:
        st.markdown("""
        # Διαχείριση Υπαλλήλων
        
        ## Προσθήκη Υπαλλήλου
        
        Συμπληρώστε τη φόρμα με:
        - **Όνομα**: Πλήρες όνομα
        - **Ρόλοι**: Μπορεί να έχει πολλαπλούς
        - **Διαθεσιμότητα**: Ποιες βάρδιες μπορεί να καλύψει
        
        ## Επεξεργασία
        
        Κλικ σε όνομα υπαλλήλου για επεξεργασία
        
        ## Διαγραφή
        
        ⚠️ Προσοχή: Η διαγραφή είναι μόνιμη
        """)
    
    with tabs[2]:
        st.markdown("""
        # Πρόγραμμα Βαρδιών
        
        ## Αυτόματη Δημιουργία
        
        Το σύστημα λαμβάνει υπόψη:
        - Διαθεσιμότητα υπαλλήλων
        - Προτεραιότητες ρόλων
        - Όρια ωρών και ανάπαυσης
        - Δίκαιη κατανομή φόρτου
        
        ## Visual Builder
        
        Χειροκίνητη επεξεργασία:
        - Επιλέξτε ρόλο από dropdown
        - Αποθηκεύστε εβδομαδιαίο πρόγραμμα
        
        ## Ανταλλαγές Βαρδιών
        
        1. Υποβολή αιτήματος από υπάλληλο
        2. Έγκριση από manager
        3. Αυτόματη ενημέρωση προγράμματος
        """)
    
    with tabs[3]:
        st.markdown("""
        # Αναλυτικά & Αναφορές
        
        ## Διαθέσιμα Γραφήματα
        
        - 📊 Κατανομή ωρών ανά υπάλληλο
        - 🔄 Κατανομή βαρδιών
        - 📅 Χρονοδιάγραμμα
        - 🎯 Θερμικός χάρτης κάλυψης
        
        ## Εξαγωγή Δεδομένων
        
        Διαθέσιμες μορφές:
        - Excel (προτείνεται)
        - CSV
        
        ## KPIs
        
        Παρακολούθηση:
        - Συνολικές βάρδιες
        - Ώρες εργασίας
        - Παραβιάσεις κανόνων
        """)
    
    with tabs[4]:
        st.markdown("""
        # Ρυθμίσεις
        
        ## Επιχείρηση
        
        - Μοντέλο εργασίας
        - Ενεργές βάρδιες
        - Ρόλοι και προτεραιότητες
        
        ## Κανόνες
        
        Προσαρμόστε:
        - Μέγιστες ώρες ημερησίως
        - Ελάχιστη ανάπαυση
        - Εβδομαδιαία όρια
        - Συνεχόμενες ημέρες
        
        ## Θέμα
        
        - Light/Dark mode
        - Προσαρμόσιμα χρώματα
        """)
