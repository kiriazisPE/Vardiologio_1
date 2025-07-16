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
    best_match = ("", 0.0)  # (intent, similarity_score)

    for intent, phrases in examples.items():
        for phrase in phrases:
            score = SequenceMatcher(None, user_input.lower(), phrase.lower()).ratio()
            if score > best_match[1]:
                best_match = (intent, score)

    return best_match[0] if best_match[1] > 0.5 else "unknown"


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

    for word, offset in relative_keywords.items():
        if word in text:
            target_date = datetime.datetime.now() + datetime.timedelta(days=offset)
            weekday = greek_weekdays[target_date.weekday()]
            return name, f"{weekday} ({target_date.strftime('%d/%m/%Y')})"

    match_days = re.search(r"επόμεν(ες|ους)? (\d{1,2}) μέρ", text)
    if match_days:
        num_days = int(match_days.group(2))
        dates = []
        for i in range(num_days):
            target_date = datetime.datetime.now() + datetime.timedelta(days=i)
            weekday = greek_weekdays[target_date.weekday()]
            dates.append(f"{weekday} ({target_date.strftime('%d/%m/%Y')})")
        return name, dates

    date_match = re.search(day_pattern, text)
    if date_match:
        day = date_match.group(1).capitalize()
        return name, day

    return name, None
# --- Page 4: Chatbot Commands --
def page_chatbot():
    st.title("🍊 Chatbot Εντολές")
    st.markdown("Π.χ. Ο Κώστας δε μπορεί να δουλέψει αύριο")
    user_input = st.text_input("Εντολή", placeholder="π.χ. Ο Κώστας δε μπορεί να δουλέψει αύριο", key="chat_input")
    
    # Αρχικοποίηση του intent
    intent = None
    schedule_df = st.session_state.schedule
    name = None
    day = None

    if "schedule" not in st.session_state or st.session_state.schedule.empty:
        st.warning("📋 Δεν έχει δημιουργηθεί πρόγραμμα. Πήγαινε στη σελίδα 'Πρόγραμμα' για να δημιουργήσεις.")
        return

    if st.button("💡 Εκτέλεση Εντολής", key="execute_command_intent"):
        intent = classify_intent(user_input, intent_examples)
        name, day = extract_name_and_day(user_input, schedule_df)

    # Εμφάνιση προγράμματος πάντα κάτω από το bot
    st.markdown("### 📋 Πρόγραμμα Βαρδιών")
    st.dataframe(st.session_state.schedule)

    if intent == "remove_from_schedule":
        if name and day:
            st.success(f"🗓 Ο {name} θα αφαιρεθεί από το πρόγραμμα την {day}")
            mask = (schedule_df['Ημέρα'].str.contains(day)) & (schedule_df['Υπάλληλος'].str.lower() == name.lower())
            if not mask.any():
                st.warning(f"🔍 Ο {name} δεν έχει βάρδια για {day} ή το όνομα είναι λάθος.")
            else:
                st.session_state.schedule = schedule_df[~mask].reset_index(drop=True)
                st.success(f"✅ Ο {name} αφαιρέθηκε από το πρόγραμμα για {day}.")
        else:
            st.warning("⚠️ Δεν αναγνωρίστηκε ξεκάθαρα όνομα ή ημέρα.")

    elif intent == "add_day_off":
        if name and day:
            st.info(f"🛌 Ρεπό καταχωρήθηκε για {name} την {day} (λογική υπό υλοποίηση)")
        else:
            st.warning("⚠️ Δεν αναγνωρίστηκε όνομα ή ημέρα.")

    elif intent == "availability_change":
        st.info(f"🔄 Αλλαγή διαθεσιμότητας για {name} (λειτουργία υπό υλοποίηση)")

    elif intent == "change_shift":
        st.info(f"🔁 Αλλαγή βάρδιας για {name} την {day} (λειτουργία υπό υλοποίηση)")

    elif intent in ["ask_schedule_for_employee", "list_day_schedule"]:
        if name:
            emp_schedule = schedule_df[schedule_df['Υπάλληλος'].str.lower() == name.lower()]
            if emp_schedule.empty:
                st.warning(f"🔍 Δεν βρέθηκε πρόγραμμα για {name}.")
            else:
                if isinstance(day, list):
                    filtered = emp_schedule[emp_schedule['Ημέρα'].apply(lambda d: any(d.startswith(d_) for d_ in day))]
                elif isinstance(day, str):
                    filtered = emp_schedule[emp_schedule['Ημέρα'].str.contains(day)]
                else:
                    filtered = emp_schedule
                if filtered.empty:
                    st.info(f"ℹ️ Ο {name} δεν έχει βάρδια στις ζητούμενες ημέρες.")
                else:
                    st.dataframe(filtered)
        else:
            st.warning("⚠️ Δεν αναγνωρίστηκε υπάλληλος.")

    else:
        st.error("❌ Δεν αναγνωρίστηκε η κατηγορία εντολής.")


# --- Page 2: Employees ---

def page_employees():
    st.header("👥 Προσθήκη ή Επεξεργασία Υπαλλήλων")

    # Πρώτη χρήση του edit_index
    if "edit_index" not in st.session_state:
        st.session_state.edit_index = None

    is_editing = st.session_state.edit_index is not None

    # Default τιμές
    if is_editing:
        emp = st.session_state.employees[st.session_state.edit_index]
        default_name = emp["name"]
        default_roles = emp["roles"]
        default_days_off = emp["days_off"]
        default_availability = emp["availability"]
    else:
        default_name = ""
        default_roles = []
        default_days_off = 2
        default_availability = []

    with st.form("employee_form"):
        name = st.text_input("Όνομα", value=default_name)
        roles = st.multiselect("Ρόλοι", st.session_state.roles, default=default_roles)
        days_off = st.slider("Ρεπό ανά εβδομάδα", 1, 3, default_days_off)
        availability = st.multiselect("Διαθεσιμότητα για όλες τις ημέρες", st.session_state.active_shifts, default=default_availability)
        submitted = st.form_submit_button("💾 Αποθήκευση")

        if submitted:
            name_lower = name.strip().lower()
            existing_names = [
                e["name"].strip().lower()
                for i, e in enumerate(st.session_state.employees)
                if i != st.session_state.edit_index
            ]

            if name_lower in existing_names:
                st.error(f"⚠️ Ο υπάλληλος '{name}' υπάρχει ήδη.")
            elif name:
                employee_data = {
                    "name": name.strip(),
                    "roles": roles,
                    "days_off": days_off,
                    "availability": availability
                }
                if is_editing:
                    st.session_state.employees[st.session_state.edit_index] = employee_data
                    st.success(f"✅ Ο υπάλληλος '{name}' ενημερώθηκε.")
                else:
                    st.session_state.employees.append(employee_data)
                    st.success(f"✅ Ο υπάλληλος '{name}' προστέθηκε.")
                # Καθαρισμός edit mode
                st.session_state.edit_index = None

    # Αν edit_index είναι None (όχι σε κατάσταση επεξεργασίας)
    if st.session_state.edit_index is None and st.session_state.employees:
        st.markdown("### Εγγεγραμμένοι Υπάλληλοι")
        for i, emp in enumerate(st.session_state.employees):
            with st.expander(f"👤 {emp['name']}"):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"""
                **Ρόλοι:** {', '.join(emp['roles'])}  
                **Ρεπό:** {emp['days_off']}  
                **Διαθεσιμότητα:** {', '.join(emp['availability'])}
                """)

                with col2:
                    if st.button("✏️ Επεξεργασία", key=f"edit_{i}"):
                        st.session_state.edit_index = i
                    if st.button("🗑️ Διαγραφή", key=f"delete_{i}"):
                        del st.session_state.employees[i]
                        st.experimental_set_query_params()  # ασφαλές refresh
                        st.stop()


# --- Page 3: Schedule Generation ---
def page_schedule():
    st.header("🧠 Δημιουργία Προγράμματος")
    if not st.session_state.employees:
        st.warning("Προσθέστε πρώτα υπαλλήλους.")
        return

    if st.button("▶️ Δημιουργία Προγράμματος"):
        data = []
        coverage = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        assigned = defaultdict(lambda: defaultdict(set))
        today = datetime.date.today()
        for i, day in enumerate(DAYS):
            date = (today + datetime.timedelta(days=i)).strftime("%d/%m/%Y")
            for shift in st.session_state.active_shifts:
                for role in st.session_state.roles:
                    count = 0
                    for e in st.session_state.employees:
                        if role in e["roles"] and shift in e["availability"]:
                            if (shift, role) in assigned[day][e["name"]]:
                                continue
                            data.append({"Ημέρα": f"{day} ({date})", "Βάρδια": shift, "Υπάλληλος": e['name'], "Καθήκοντα": role})
                            assigned[day][e["name"]].add((shift, role))
                            count += 1
                            if count >= st.session_state.rules["max_employees_per_position"].get(role, 1):
                                break
                    coverage[day][shift][role] = count
        st.session_state.schedule = pd.DataFrame(data)
        st.session_state.coverage = coverage
        st.success("✅ Το πρόγραμμα δημιουργήθηκε!")

    if not st.session_state.schedule.empty:
        st.dataframe(st.session_state.schedule)
        csv = st.session_state.schedule.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Εξαγωγή CSV", csv, file_name="programma.csv", mime="text/csv")

        st.markdown("### ❗Μη Καλυμμένες Θέσεις")
        uncovered = []
        for day, shifts in st.session_state.coverage.items():
            for shift, roles in shifts.items():
                for role, count in roles.items():
                    needed = st.session_state.rules["max_employees_per_position"].get(role, 1)
                    if count < needed:
                        uncovered.append({"Ημέρα": day, "Βάρδια": shift, "Ρόλος": role, "Ανεπάρκεια": needed - count})
        if uncovered:
            st.dataframe(pd.DataFrame(uncovered))
        else:
            st.success("🎉 Όλες οι θέσεις καλύφθηκαν.")


# Συνάρτηση αλλαγής διαθεσιμότητας στον υπάλληλο ---
def apply_availability_change(name: str, shift_day: str):
    if "employees" not in st.session_state:
        return

    shift_day_clean = shift_day.split(" (")[0] if "(" in shift_day else shift_day

    for emp in st.session_state.employees:
        if emp["name"].lower() == name.lower():
            if shift_day_clean in greek_weekdays:
                if "unavailable_days" not in emp:
                    emp["unavailable_days"] = []
                if shift_day_clean not in emp["unavailable_days"]:
                    emp["unavailable_days"].append(shift_day_clean)
            break

    # --- Αφαίρεση βαρδιών του υπαλλήλου από το πρόγραμμα ---
    if "schedule" in st.session_state and not st.session_state.schedule.empty:
        schedule_df = st.session_state.schedule
        st.session_state.schedule = schedule_df[~(
            (schedule_df['Υπάλληλος'].str.lower() == name.lower()) &
            (schedule_df['Ημέρα'].str.startswith(shift_day_clean))
        )].reset_index(drop=True)

        # --- Εμφάνιση ενημερωμένου προγράμματος κάτω από το chatbot ---
        st.markdown("### 📋 Ενημερωμένο Πρόγραμμα")
        st.dataframe(st.session_state.schedule)

# --- Main ---
def main():
    init_session()
    navigation()
    page_funcs = [page_business, page_employees, page_schedule, page_chatbot]
    page_funcs[st.session_state.page]()

if __name__ == "__main__":
    main()
