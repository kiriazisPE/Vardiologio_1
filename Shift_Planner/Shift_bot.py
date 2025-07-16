import streamlit as st
import pandas as pd
from collections import defaultdict
import datetime
from openai import OpenAI
import os
import re
from dotenv import load_dotenv
import json
from pathlib import Path
from difflib import SequenceMatcher



# --- Load .env for API Key ---
load_dotenv()
client = OpenAI()

# Φόρτωση intent_examples.json από τον ίδιο φάκελο με το script
intent_file = Path(__file__).parent / "intent_examples.json"

if not intent_file.exists():
    st.error(f"❌ Το αρχείο {intent_file.name} δεν βρέθηκε στον φάκελο της εφαρμογής.")
    intent_examples = []
else:
    with intent_file.open(encoding="utf-8-sig") as f:
        content = f.read()
        if not content.strip():
            raise ValueError("❌ Το αρχείο intent_examples.json είναι κενό ή περιέχει μόνο κενά.")
        
        try:
            intent_examples = json.loads(content)
        except json.JSONDecodeError as e:
            print("❌ Σφάλμα στο JSON:", e)
            print("➡️ Πρώτα 300 χαρακτήρες:")
            print(content[:300])
            raise e

def classify_intent(user_input: str, examples: dict) -> str:
    try:
        system_prompt = """
        Αναγνώρισε την πρόθεση της εντολής. Πιθανές προθέσεις:
        - remove_from_schedule: Αφαίρεση από το πρόγραμμα
        - add_day_off: Προσθήκη ρεπό
        - availability_change: Αλλαγή διαθεσιμότητας
        - change_shift: Αλλαγή βάρδιας
        - ask_schedule_for_employee: Ερώτηση για πρόγραμμα υπαλλήλου
        - list_day_schedule: Εμφάνιση προγράμματος ημέρας
        
        Απάντησε μόνο με το όνομα της πρόθεσης.
        """

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            temperature=0.3
        )

        return response.choices[0].message.content.strip()
    except:
        return "unknown"


# --- Page Config ---
st.set_page_config(page_title="Βοηθός Προγράμματος Βαρδιών", layout="wide")

# --- Constants ---
DAYS = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]
ALL_SHIFTS = ["Πρωί", "Απόγευμα", "Βράδυ"]
DEFAULT_ROLES = ["Ταμείο", "Σερβιτόρος", "Μάγειρας", "Barista"]
EXTRA_ROLES = ["Υποδοχή", "Καθαριστής", "Λαντζέρης", "Οδηγός", "Manager"]

greek_weekdays = [
    "Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη",
    "Παρασκευή", "Σάββατο", "Κυριακή"
]

unavailability_phrases = [
    r"δε(ν)? μπορεί",
    r"δεν θα δουλέψει",
    r"έχει ρεπό",
    r"λείπει",
    r"δεν είναι διαθέσιμ",
    r"είναι άρρωσ",
    r"χτύπησε",
    r"τραυματίστηκε",
    r"αρρώστησε"
]

relative_keywords = {
    "αύριο": 1,
    "μεθαύριο": 2
}

# Regex που πιάνει και πληθυντικούς
day_pattern = r"(δευτέρα(?:ς|ες)?|τρίτη(?:ς|ες)?|τετάρτη(?:ς|ες)?|πέμπτη(?:ς|ες)?|παρασκευή(?:ς|ες)?|σάββατο(?:υ|α)?|κυριακή(?:ς|ες)?)"
date_pattern = r"\d{2}/\d{2}/\d{4}"
combined_date_pattern = fr"{day_pattern} ({{date_pattern}})"








# --- Session State Initialization ---
def init_session():
    st.session_state.setdefault("page", 0)
    st.session_state.setdefault("business_name", "")
    st.session_state.setdefault("active_shifts", ALL_SHIFTS[:2])
    st.session_state.setdefault("employees", [])
    st.session_state.setdefault("edit_index", None)
    st.session_state.setdefault("requirements", defaultdict(lambda: defaultdict(int)))
    st.session_state.setdefault("schedule", pd.DataFrame())
    st.session_state.setdefault("chat_history", [])
    st.session_state.setdefault("roles", DEFAULT_ROLES + EXTRA_ROLES)
    st.session_state.setdefault("rules", {
        "max_employees_per_shift": 5,
        "max_employees_per_position": {role: 2 for role in DEFAULT_ROLES},
        "min_rest_hours_between_shifts": 12,
        "max_consecutive_work_days": 5,
        "max_weekly_hours": 40,
    })
    st.session_state.setdefault("business_stage", 1)

# --- Navigation ---
def navigation():
    st.sidebar.title("🔁 Πλοήγηση")
    choice = st.sidebar.radio("Μενού", ["1️⃣ Επιχείρηση", "2️⃣ Υπάλληλοι", "3️⃣ Πρόγραμμα", "4️⃣ Chatbot"])
    st.session_state.page = ["1️⃣ Επιχείρηση", "2️⃣ Υπάλληλοι", "3️⃣ Πρόγραμμα", "4️⃣ Chatbot"].index(choice)

# --- Page 1: Business Setup ---
def page_business():
    st.header("🏢 Ρυθμίσεις Επιχείρησης")

    if st.session_state.business_stage == 1:
        st.session_state.business_name = st.text_input("Εισάγετε το όνομα της επιχείρησης", st.session_state.business_name)
        if st.button("➡️ Συνέχεια") and st.session_state.business_name.strip():
            st.session_state.business_stage = 2

    elif st.session_state.business_stage == 2:
        st.markdown("### 📆 Επιλέξτε ενεργές βάρδιες")
        st.session_state.active_shifts = st.multiselect("Βάρδιες που χρησιμοποιεί η επιχείρηση", ALL_SHIFTS, default=st.session_state.active_shifts)

        st.markdown("### 🧱 Επιλογή Ρόλων Επιχείρησης")
        st.session_state.roles = st.multiselect("Επιλέξτε ρόλους που απαιτούνται στην επιχείρηση", DEFAULT_ROLES + EXTRA_ROLES, default=DEFAULT_ROLES)

        st.markdown("### 🛠️ Κανόνες Επιχείρησης")

        with st.expander("👥 Μέγιστος αριθμός υπαλλήλων ανά βάρδια"):
            st.session_state.rules["max_employees_per_shift"] = st.number_input(
                "Μέγιστος αριθμός", min_value=1, max_value=20, value=st.session_state.rules["max_employees_per_shift"]
            )

        for role in st.session_state.roles:
            with st.expander(f"👤 Μέγιστοι {role} ανά βάρδια"):
                st.session_state.rules["max_employees_per_position"][role] = st.number_input(
                    f"{role}", min_value=0, max_value=10, value=st.session_state.rules["max_employees_per_position"].get(role, 2), key=f"role_{role}"
                )

        with st.expander("⏱️ Ελάχιστες ώρες ξεκούρασης μεταξύ βαρδιών"):
            st.session_state.rules["min_rest_hours_between_shifts"] = st.number_input(
                "Ελάχιστες ώρες", min_value=0, max_value=24, value=st.session_state.rules["min_rest_hours_between_shifts"]
            )

        with st.expander("📅 Μέγιστες συνεχόμενες μέρες εργασίας"):
            st.session_state.rules["max_consecutive_work_days"] = st.number_input(
                "Ημέρες", min_value=1, max_value=7, value=st.session_state.rules["max_consecutive_work_days"]
            )

        with st.expander("⏳ Μέγιστες ώρες εργασίας την εβδομάδα"):
            st.session_state.rules["max_weekly_hours"] = st.number_input(
                "Ώρες", min_value=1, max_value=80, value=st.session_state.rules["max_weekly_hours"]
            )

        st.success("✅ Οι ρυθμίσεις αποθηκεύτηκαν.")





day_pattern = r"(δευτέρα(?:ς|ες)?|τρίτη(?:ς|ες)?|τετάρτη(?:ς|ες)?|πέμπτη(?:ς|ες)?|παρασκευή(?:ς|ες)?|σάββατο(?:υ|α)?|κυριακή(?:ς|ες)?)"
date_pattern = r"\d{2}/\d{2}/\d{4}"
combined_date_pattern = fr"{day_pattern} ({{date_pattern}})"

def match_employee_name(user_input: str, schedule_df: pd.DataFrame) -> str:
    all_names = schedule_df['Υπάλληλος'].unique()
    for name in all_names:
        if name.lower() in user_input.lower():
            return name
    return None

def extract_name_and_day(user_input: str, schedule_df: pd.DataFrame):
    text = user_input.lower()
    name = match_employee_name(user_input, schedule_df)
    
    # Check for specific days in plural form first
    day_plural_map = {
        "δευτέρες": "Δευτέρα",
        "τρίτες": "Τρίτη",
        "τετάρτες": "Τετάρτη",
        "πέμπτες": "Πέμπτη",
        "παρασκευές": "Παρασκευή",
        "σάββατα": "Σάββατο",
        "κυριακές": "Κυριακή"
    }
    
    # First check for plural forms
    for plural, singular in day_plural_map.items():
        if plural in text:
            return name, singular
    
    # Then check for singular forms with their variations
    day_pattern = r"(δευτέρα|τρίτη|τετάρτη|πέμπτη|παρασκευή|σάββατο|κυριακή)"
    date_match = re.search(day_pattern, text)
    if date_match:
        day = date_match.group(1)
        day_map = {
            "δευτέρα": "Δευτέρα",
            "τρίτη": "Τρίτη",
            "τετάρτη": "Τετάρτη",
            "πέμπτη": "Πέμπτη",
            "παρασκευή": "Παρασκευή",
            "σάββατο": "Σάββατο",
            "κυριακή": "Κυριακή"
        }
        return name, day_map.get(day, day.capitalize())
    
    # Check for relative days (αύριο, μεθαύριο)
    for word, offset in relative_keywords.items():
        if word in text:
            target_date = datetime.datetime.now() + datetime.timedelta(days=offset)
            weekday = greek_weekdays[target_date.weekday()]
            return name, f"{weekday} ({target_date.strftime('%d/%m/%Y')})"

    return name, None
# --- Page 4: Chatbot Commands --
def page_chatbot():
    st.title("🍊 Chatbot Εντολές")
    
    # Check for schedule first
    if "schedule" not in st.session_state or st.session_state.schedule.empty:
        st.warning("📋 Δεν έχει δημιουργηθεί πρόγραμμα. Πήγαινε στη σελίδα 'Πρόγραμμα' για να δημιουργήσεις.")
        return

    # Initialize variables
    schedule_df = st.session_state.schedule
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 💬 Εντολή")
        st.markdown("Π.χ. _Ο Κώστας δε μπορεί να δουλέψει αύριο_")
        user_input = st.text_input("", placeholder="Γράψε την εντολή σου εδώ...", key="chat_input")
        
        if st.button("💡 Εκτέλεση Εντολής", key="execute_command_intent"):
            if not user_input.strip():
                st.error("❌ Παρακαλώ γράψε μια εντολή πρώτα.")
                return
                
            # Process command
            try:
                intent, name, day, extra_info = process_with_ai(user_input, schedule_df)
                
                if not intent:
                    st.error("❌ Δεν μπόρεσα να καταλάβω την εντολή.")
                    return

                if intent == "remove_from_schedule":
                    if name and day:
                        mask = (schedule_df['Ημέρα'].str.contains(day, case=False)) & \
                               (schedule_df['Υπάλληλος'].str.lower() == name.lower())
                        if not mask.any():
                            st.warning(f"🔍 Ο {name} δεν έχει βάρδια για {day}")
                        else:
                            st.session_state.schedule = schedule_df[~mask].reset_index(drop=True)
                            st.success(f"✅ Ο {name} αφαιρέθηκε από το πρόγραμμα για {day}")
                    else:
                        st.warning("⚠️ Δεν αναγνωρίστηκε ξεκάθαρα όνομα ή ημέρα.")
                
                elif intent == "change_shift":
                    if name and day and "shift" in extra_info:
                        mask = (schedule_df['Ημέρα'].str.contains(day, case=False)) & \
                               (schedule_df['Υπάλληλος'].str.lower() == name.lower())
                        if mask.any():
                            schedule_df.loc[mask, 'Βάρδια'] = extra_info["shift"]
                            st.session_state.schedule = schedule_df
                            st.success(f"✅ Η βάρδια του {name} άλλαξε σε {extra_info['shift']}")
            
            except Exception as e:
                st.error(f"❌ Σφάλμα: {str(e)}")
                return

    with col2:
        st.markdown("### 📋 Πρόγραμμα Βαρδιών")
        st.dataframe(st.session_state.schedule, use_container_width=True)
