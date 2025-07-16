import streamlit as st
import pandas as pd
from collections import defaultdict
import datetime
import json
from openai import OpenAI
from pathlib import Path
from dotenv import load_dotenv

# --- Load .env for API Key ---
load_dotenv()
client = OpenAI()

# Load intent examples
intent_file = Path(__file__).parent / "intent_examples.json"
if not intent_file.exists():
    st.error(f"❌ Το αρχείο {intent_file.name} δεν βρέθηκε στον φάκελο της εφαρμογής.")
    intent_examples = {}
else:
    with intent_file.open(encoding="utf-8") as f:
        try:
            intent_examples = json.loads(f.read())
        except json.JSONDecodeError as e:
            st.error(f"❌ Σφάλμα στο JSON: {e}")
            intent_examples = {}

# --- Constants ---
DAYS = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]
ALL_SHIFTS = ["Πρωί", "Απόγευμα", "Βράδυ"]
DEFAULT_ROLES = ["Ταμείο", "Σερβιτόρος", "Μάγειρας", "Barista"]
EXTRA_ROLES = ["Υποδοχή", "Καθαριστής", "Λαντζέρης", "Οδηγός", "Manager"]

# --- Session State Initialization ---
def init_session():
    """Initialize session state variables."""
    st.session_state.setdefault("page", 0)
    st.session_state.setdefault("business_name", "")
    st.session_state.setdefault("active_shifts", ALL_SHIFTS)
    st.session_state.setdefault("roles", DEFAULT_ROLES + EXTRA_ROLES)
    st.session_state.setdefault("rules", {
        "max_employees_per_shift": 5,
        "max_employees_per_position": {role: 2 for role in DEFAULT_ROLES},
        "min_rest_hours_between_shifts": 12,
        "max_consecutive_work_days": 5,
        "max_weekly_hours": 40,
    })
    st.session_state.setdefault("employees", [])
    st.session_state.setdefault("schedule", pd.DataFrame())
    st.session_state.setdefault("chat_history", [])

# --- AI Processing ---
def process_with_ai(user_input: str, context: str = "") -> dict:
    """
    Use OpenAI API to analyze the user's command and extract intent, name, day, and extra info.
    """
    try:
        system_prompt = f"""
        Είσαι βοηθός για ένα σύστημα διαχείρισης βαρδιών. Αναλύεις εντολές στα ελληνικά.
        Πρέπει να εξάγεις τις εξής πληροφορίες:
        1. intent: Τύπος εντολής (remove_from_schedule, add_day_off, availability_change, change_shift, ask_schedule_for_employee, list_day_schedule, change_company_settings, employee_interaction_rule)
        2. name: Το όνομα του υπαλλήλου (αν υπάρχει)
        3. day: Η ημέρα/ημερομηνία (αν υπάρχει)
        4. extra_info: Επιπλέον πληροφορίες (π.χ. βάρδια, κανόνες αλληλεπίδρασης, αλλαγές στις ρυθμίσεις)

        Context: {context}
        Απάντησε σε JSON μορφή.
        """
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Ανάλυσε την εξής εντολή: {user_input}"}
            ]
        )
        response_content = response.choices[0].message.content.strip()
        
        # Validate and parse the response
        try:
            result = json.loads(response_content)
            return result
        except json.JSONDecodeError:
            st.warning("⚠️ Η εντολή δεν αναγνωρίστηκε πλήρως. Δοκιμάστε να διατυπώσετε την εντολή διαφορετικά ή να είστε πιο συγκεκριμένοι.")
            return {"error": "Invalid JSON response"}
    except Exception as e:
        st.error("❌ Υπήρξε πρόβλημα κατά την επεξεργασία της εντολής. Παρακαλώ δοκιμάστε ξανά.")
        return {"error": str(e)}

# --- Navigation ---
def navigation():
    """Handle page navigation."""
    st.sidebar.title("🔁 Πλοήγηση")
    choice = st.sidebar.radio("Μενού", ["1️⃣ Επιχείρηση", "2️⃣ Υπαλλήλοι", "3️⃣ Πρόγραμμα", "4️⃣ Chatbot"])
    st.session_state.page = ["1️⃣ Επιχείρηση", "2️⃣ Υπαλλήλοι", "3️⃣ Πρόγραμμα", "4️⃣ Chatbot"].index(choice)

# --- Page 1: Business Setup ---
def page_business():
    """Business setup page."""
    st.header("🏢 Ρυθμίσεις Επιχείρησης")
    st.session_state.business_name = st.text_input("Εισάγετε το όνομα της επιχείρησης", st.session_state.business_name, help="Προσθέστε το όνομα της επιχείρησης σας.")

    st.markdown("### 📆 Επιλέξτε ενεργές βάρδιες")
    st.session_state.active_shifts = st.multiselect("Βάρδιες που χρησιμοποιεί η επιχείρηση", ALL_SHIFTS, default=st.session_state.active_shifts, help="Επιλέξτε τις βάρδιες που ισχύουν για την επιχείρησή σας.")

    st.markdown("### 🧱 Επιλογή Ρόλων Επιχείρησης")
    st.session_state.roles = st.multiselect("Επιλέξτε ρόλους που απαιτούνται στην επιχείρηση", DEFAULT_ROLES + EXTRA_ROLES, default=DEFAULT_ROLES, help="Προσθέστε ή αφαιρέστε ρόλους ανάλογα με τις ανάγκες σας.")

    st.markdown("### 🛠️ Κανόνες Επιχείρησης")
    with st.expander("👥 Μέγιστος αριθμός υπαλλήλων ανά βάρδια"):
        st.session_state.rules["max_employees_per_shift"] = st.number_input(
            "Μέγιστος αριθμός", min_value=1, max_value=20, value=st.session_state.rules["max_employees_per_shift"], help="Ορίστε τον μέγιστο αριθμό υπαλλήλων ανά βάρδια."
        )

    for role in st.session_state.roles:
        with st.expander(f"👤 Μέγιστοι {role} ανά βάρδια"):
            st.session_state.rules["max_employees_per_position"][role] = st.number_input(
                f"{role}", min_value=0, max_value=10, value=st.session_state.rules["max_employees_per_position"].get(role, 2), key=f"role_{role}", help=f"Ορίστε τον μέγιστο αριθμό υπαλλήλων για τον ρόλο '{role}'."
            )

    # AI Validation for Business Rules
    if st.button("🔍 Επαλήθευση Ρυθμίσεων"):
        ai_result = process_with_ai("Επαλήθευσε τις ρυθμίσεις επιχείρησης.", context=json.dumps(st.session_state.rules))
        st.json(ai_result)

# --- Page 2: Employees ---
def page_employees():
    """Employee management page."""
    st.header("👥 Προσθήκη ή Επεξεργασία Υπαλλήλων")

    # Form for adding new employees
    with st.form("employee_form"):
        name = st.text_input("Όνομα", help="Προσθέστε το όνομα του υπαλλήλου.")
        roles = st.multiselect("Ρόλοι", st.session_state.roles, help="Επιλέξτε τους ρόλους που μπορεί να αναλάβει ο υπάλληλος.")
        days_off = st.slider("Ρεπό ανά εβδομάδα", 1, 3, 2, help="Ορίστε τον αριθμό των ρεπό ανά εβδομάδα.")
        availability = st.multiselect("Διαθεσιμότητα για όλες τις ημέρες", st.session_state.active_shifts, help="Επιλέξτε τις βάρδιες που είναι διαθέσιμος ο υπάλληλος.")
        submitted = st.form_submit_button("💾 Αποθήκευση")

        if submitted:
            if not availability:
                st.warning("⚠️ Παρακαλώ επιλέξτε τουλάχιστον μία βάρδια για τη διαθεσιμότητα του υπαλλήλου.")
            elif not name.strip():
                st.warning("⚠️ Το όνομα του υπαλλήλου δεν μπορεί να είναι κενό.")
            else:
                employee_data = {
                    "name": name.strip(),
                    "roles": roles,
                    "days_off": days_off,
                    "availability": availability
                }
                ai_result = process_with_ai("Επαλήθευσε τα δεδομένα υπαλλήλου.", context=json.dumps(employee_data))
                if "error" in ai_result:
                    st.error("❌ Σφάλμα κατά την επαλήθευση των δεδομένων.")
                else:
                    st.session_state.employees.append(employee_data)
                    st.success(f"✅ Ο υπάλληλος '{name}' προστέθηκε.")

    st.markdown("### Εγγεγραμμένοι Υπάλληλοι")
    with st.expander("📋 Δείτε τους εγγεγραμμένους υπαλλήλους"):
        if st.session_state.employees:
            for index, emp in enumerate(st.session_state.employees):
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.markdown(f"**{emp['name']}** - Ρόλοι: {', '.join(emp['roles'])}, Ρεπό: {emp['days_off']}, Διαθεσιμότητα: {', '.join(emp['availability']) if emp['availability'] else 'Δεν μπορεί'}")
                with col2:
                    if st.button("✏️ Επεξεργασία", key=f"edit_{index}"):
                        # Edit employee logic
                        with st.form(f"edit_form_{index}"):
                            new_name = st.text_input("Όνομα", value=emp["name"])
                            new_roles = st.multiselect("Ρόλοι", st.session_state.roles, default=emp["roles"])
                            new_days_off = st.slider("Ρεπό ανά εβδομάδα", 1, 3, emp["days_off"])
                            new_availability = st.multiselect("Διαθεσιμότητα", st.session_state.active_shifts, default=emp["availability"])
                            save_changes = st.form_submit_button("💾 Αποθήκευση Αλλαγών")
                            if save_changes:
                                if not new_availability:
                                    st.warning("⚠️ Παρακαλώ επιλέξτε τουλάχιστον μία βάρδια για τη διαθεσιμότητα του υπαλλήλου.")
                                elif not new_name.strip():
                                    st.warning("⚠️ Το όνομα του υπαλλήλου δεν μπορεί να είναι κενό.")
                                else:
                                    emp["name"] = new_name.strip()
                                    emp["roles"] = new_roles
                                    emp["days_off"] = new_days_off
                                    emp["availability"] = new_availability
                                    st.success(f"✅ Ο υπάλληλος '{new_name}' ενημερώθηκε.")
                with col3:
                    if st.button("🗑️ Διαγραφή", key=f"delete_{index}"):
                        st.session_state.employees.pop(index)
                        st.success(f"✅ Ο υπάλληλος '{emp['name']}' διαγράφηκε.")
        else:
            st.info("Δεν υπάρχουν εγγεγραμμένοι υπάλληλοι. Προσθέστε έναν υπάλληλο για να ξεκινήσετε.")

# --- Page 3: Schedule Generation ---
def page_schedule():
    """Schedule generation page."""
    st.header("🧠 Δημιουργία Προγράμματος")

    if not st.session_state.employees:
        st.warning("Προσθέστε πρώτα υπαλλήλους.")
        return

    if st.button("▶️ Δημιουργία Προγράμματος"):
        data = []
        today = datetime.date.today()

        for i, day in enumerate(DAYS * 4):  # Generate for 4 weeks (1 month)
            date = (today + datetime.timedelta(days=i)).strftime("%d/%m/%Y")
            for shift in st.session_state.active_shifts:
                for role in st.session_state.roles:
                    eligible_employees = [
                        e for e in st.session_state.employees
                        if role in e["roles"] and shift in e["availability"]
                    ]
                    if not eligible_employees:
                        st.warning(f"⚠️ Δεν υπάρχουν διαθέσιμοι υπάλληλοι για τον ρόλο '{role}' στη βάρδια '{shift}' την ημέρα '{day}'.")
                    for e in eligible_employees:
                        data.append({
                            "Ημέρα": f"{day} ({date})",
                            "Βάρδια": shift,
                            "Υπάλληλος": e["name"],
                            "Καθήκοντα": role
                        })

        if data:
            st.session_state.schedule = pd.DataFrame(data)
            ai_result = process_with_ai("Βελτιστοποίησε το πρόγραμμα.", context=json.dumps(data))
            st.session_state.schedule = pd.DataFrame(ai_result.get("optimized_schedule", data))
            st.success("✅ Το πρόγραμμα δημιουργήθηκε!")
        else:
            st.error("❌ Δεν δημιουργήθηκε πρόγραμμα. Ελέγξτε τις ρυθμίσεις και τους υπαλλήλους.")

    if not st.session_state.schedule.empty:
        st.markdown("### 📋 Πρόγραμμα Βαρδιών")
        st.dataframe(st.session_state.schedule)

# --- Page 4: Chatbot Commands ---
def page_chatbot():
    """Chatbot commands page."""
    st.header("🍊 Chatbot Εντολές")

    if "schedule" not in st.session_state or st.session_state.schedule.empty:
        st.warning("📋 Δεν έχει δημιουργηθεί πρόγραμμα. Πήγαινε στη σελίδα 'Πρόγραμμα' για να δημιουργήσεις.")
        return

    user_input = st.text_input("Γράψε την εντολή σου εδώ...", placeholder="Π.χ. Υπάρχει πάρτι αύριο, πρόσθεσε 2 μάγειρες και 1 μπάρμαν", help="Προσθέστε μια εντολή για να επεξεργαστεί το πρόγραμμα.")
    if st.button("💡 Εκτέλεση Εντολής"):
        result = process_with_ai(user_input, context=json.dumps(st.session_state.schedule.to_dict()))
        if "error" in result:
            st.error("❌ Δεν μπόρεσα να καταλάβω την εντολή.")
        else:
            # Process the extracted intent and update the schedule or settings
            intent = result.get("intent")
            name = result.get("name")
            day = result.get("day")
            extra_info = result.get("extra_info")

            if intent == "change_company_settings":
                # Update company settings dynamically
                settings_update = json.loads(extra_info)  # Parse the settings update
                for role, count in settings_update.items():
                    st.session_state.rules["max_employees_per_position"][role] += count
                st.success(f"✅ Οι ρυθμίσεις της εταιρείας ενημερώθηκαν: {settings_update}")

            elif intent == "employee_interaction_rule":
                # Add interaction rules between employees
                interaction_rule = json.loads(extra_info)  # Parse the interaction rule
                st.session_state.rules.setdefault("employee_interactions", []).append(interaction_rule)
                st.success(f"✅ Προστέθηκε κανόνας αλληλεπίδρασης: {interaction_rule}")

            elif intent == "remove_from_schedule":
                st.session_state.schedule = st.session_state.schedule[
                    ~((st.session_state.schedule["Υπάλληλος"] == name) & (st.session_state.schedule["Ημέρα"].str.contains(day)))
                ]
                st.success(f"✅ Ο υπάλληλος '{name}' αφαιρέθηκε από το πρόγραμμα για την ημέρα '{day}'.")

            elif intent == "add_day_off":
                st.session_state.schedule = st.session_state.schedule[
                    ~((st.session_state.schedule["Υπάλληλος"] == name) & (st.session_state.schedule["Ημέρα"].str.contains(day)))
                ]
                st.success(f"✅ Προστέθηκε ρεπό για τον υπάλληλο '{name}' την ημέρα '{day}'.")

            elif intent == "availability_change":
                for emp in st.session_state.employees:
                    if emp["name"] == name:
                        emp["availability"] = extra_info.split(",")
                        st.success(f"✅ Η διαθεσιμότητα του υπαλλήλου '{name}' ενημερώθηκε σε '{extra_info}'.")

            elif intent == "change_shift":
                st.session_state.schedule.loc[
                    (st.session_state.schedule["Υπάλληλος"] == name) & (st.session_state.schedule["Ημέρα"].str.contains(day)),
                    "Βάρδια"
                ] = extra_info
                st.success(f"✅ Η βάρδια του υπαλλήλου '{name}' ενημερώθηκε σε '{extra_info}' για την ημέρα '{day}'.")

            elif intent == "ask_schedule_for_employee":
                employee_schedule = st.session_state.schedule[st.session_state.schedule["Υπάλληλος"] == name]
                st.markdown(f"### Πρόγραμμα για τον υπάλληλο '{name}'")
                st.dataframe(employee_schedule)

            elif intent == "list_day_schedule":
                day_schedule = st.session_state.schedule[st.session_state.schedule["Ημέρα"].str.contains(day)]
                st.markdown(f"### Πρόγραμμα για την ημέρα '{day}'")
                st.dataframe(day_schedule)

            else:
                st.warning("⚠️ Η εντολή δεν αναγνωρίστηκε.")

    # Display the updated schedule
    if not st.session_state.schedule.empty:
        st.markdown("### 📋 Ενημερωμένο Πρόγραμμα Βαρδιών")
        st.dataframe(st.session_state.schedule)

# --- Main ---
def main():
    """Main function to run the app."""
    init_session()
    navigation()
    page_funcs = [page_business, page_employees, page_schedule, page_chatbot]
    page_funcs[st.session_state.page]()

if __name__ == "__main__":
    main()

