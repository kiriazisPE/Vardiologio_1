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
    """📊 Σελίδα Ρυθμίσεων Επιχείρησης"""
    st.header("🏢 Ρυθμίσεις Επιχείρησης")

    # --- Εισαγωγή ονόματος επιχείρησης ---
    with st.container():
        st.subheader("🔖 Όνομα Επιχείρησης")
        st.session_state.business_name = st.text_input(
            "Όνομα επιχείρησης",
            st.session_state.business_name,
            placeholder="π.χ. Καφέ Λιμανάκι",
            help="Προσθέστε το όνομα της επιχείρησής σας."
        )

    # --- Επιλογή ενεργών βαρδιών ---
    with st.container():
        st.subheader("📆 Ενεργές Βάρδιες")
        st.session_state.active_shifts = st.multiselect(
            "Επιλέξτε ποιες βάρδιες χρησιμοποιεί η επιχείρηση",
            ALL_SHIFTS,
            default=st.session_state.active_shifts,
            help="Π.χ. αν δεν έχετε βραδινή, αφαιρέστε τη."
        )

    # --- Επιλογή ρόλων ---
    with st.container():
        st.subheader("👔 Ρόλοι στην Επιχείρηση")
        st.session_state.roles = st.multiselect(
            "Ποιοι ρόλοι απαιτούνται στην επιχείρηση",
            DEFAULT_ROLES + EXTRA_ROLES,
            default=DEFAULT_ROLES,
            help="Επιλέξτε όσους ρόλους χρειάζεστε για το πρόγραμμα βαρδιών."
        )

    # --- Κανόνες ανά βάρδια και ρόλο ---
    st.subheader("⚙️ Κανόνες Βαρδιών & Καθήκοντα")

    with st.expander("👥 Μέγιστος αριθμός υπαλλήλων ανά βάρδια", expanded=True):
        st.session_state.rules["max_employees_per_shift"] = st.slider(
            "Μέγιστος συνολικός αριθμός υπαλλήλων ανά βάρδια",
            min_value=1,
            max_value=20,
            value=st.session_state.rules["max_employees_per_shift"],
            help="Αφορά όλους τους ρόλους μαζί."
        )

    with st.expander("📌 Μέγιστος αριθμός υπαλλήλων ανά ρόλο ανά βάρδια", expanded=False):
        for role in st.session_state.roles:
            st.session_state.rules["max_employees_per_position"][role] = st.number_input(
                f"👤 {role}",
                min_value=0,
                max_value=10,
                value=st.session_state.rules["max_employees_per_position"].get(role, 2),
                key=f"role_{role}",
                help=f"Πόσα άτομα επιτρέπονται το πολύ για τον ρόλο '{role}' ανά βάρδια."
            )

# --- Page 2: Employees ---
def page_employees():
    """Employee management page."""
    st.header("👥 Προσθήκη ή Επεξεργασία Υπαλλήλων")

    with st.form("employee_form"):
        name = st.text_input("Όνομα", help="Προσθέστε το όνομα του υπαλλήλου.")
        roles = st.multiselect("Ρόλοι", st.session_state.roles, help="Επιλέξτε τους ρόλους που μπορεί να αναλάβει ο υπάλληλος.")
        days_off = st.slider("Ρεπό ανά εβδομάδα", 1, 3, 2, help="Ορίστε τον αριθμό των ρεπό ανά εβδομάδα.")
        availability = st.multiselect("Διαθεσιμότητα για όλες τις ημέρες", st.session_state.active_shifts, help="Επιλέξτε τις βάρδιες που είναι διαθέσιμος ο υπάλληλος.")
        submitted = st.form_submit_button("💾 Αποθήκευση")

        if submitted:
            employee_data = {
                "name": name.strip(),
                "roles": roles,
                "days_off": days_off,
                "availability": availability
            }

            # 🧠 AI validation
            validation = validate_employee_data_with_ai(employee_data)
            if not validation.get("valid", False):
                st.error("❌ Σφάλμα στα δεδομένα:")
                for err in validation.get("errors", []):
                    st.markdown(f"- {err}")
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
                        with st.form(f"edit_form_{index}"):
                            new_name = st.text_input("Όνομα", value=emp["name"])
                            new_roles = st.multiselect("Ρόλοι", st.session_state.roles, default=emp["roles"])
                            new_days_off = st.slider("Ρεπό ανά εβδομάδα", 1, 3, emp["days_off"])
                            new_availability = st.multiselect("Διαθεσιμότητα", st.session_state.active_shifts, default=emp["availability"])
                            save_changes = st.form_submit_button("💾 Αποθήκευση Αλλαγών")
                            if save_changes:
                                new_data = {
                                    "name": new_name.strip(),
                                    "roles": new_roles,
                                    "days_off": new_days_off,
                                    "availability": new_availability
                                }
                                validation = validate_employee_data_with_ai(new_data)
                                if not validation.get("valid", False):
                                    st.error("❌ Σφάλμα στα νέα δεδομένα:")
                                    for err in validation.get("errors", []):
                                        st.markdown(f"- {err}")
                                else:
                                    emp.update(new_data)
                                    st.success(f"✅ Ο υπάλληλος '{new_name}' ενημερώθηκε.")
                with col3:
                    if st.button("🗑️ Διαγραφή", key=f"delete_{index}"):
                        st.session_state.employees.pop(index)
                        st.success(f"✅ Ο υπάλληλος '{emp['name']}' διαγράφηκε.")
        else:
            st.info("Δεν υπάρχουν εγγεγραμμένοι υπάλληλοι.")


def validate_employee_data_with_ai(employee_data: dict) -> dict:
    """
    Validate employee data using AI. Return dictionary with result or error list.
    """
    try:
        prompt = f"""
        Είσαι σύστημα ελέγχου προσωπικού. Σου δίνω δεδομένα υπαλλήλου σε JSON μορφή και πρέπει να ελέγξεις αν είναι σωστά.
        Έλεγξε αν:
        - το όνομα είναι μη κενό string
        - υπάρχουν τουλάχιστον 1 ρόλος
        - υπάρχει διαθεσιμότητα για τουλάχιστον μία βάρδια

        Αν όλα είναι σωστά, απάντησε:
        {{"valid": true}}

        Αν υπάρχουν σφάλματα, απάντησε:
        {{"valid": false, "errors": ["περιγραφή_1", "περιγραφή_2", ...]}}

        Δεδομένα: {json.dumps(employee_data, ensure_ascii=False)}
        """
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"valid": False, "errors": [str(e)]}







# --- Page 3: Schedule Generation (βελτιωμένη εμπειρία χρήστη & καθαρότητα προβλημάτων) ---
# --- Page 3: Schedule Generation (βελτιωμένη εμπειρία χρήστη & καθαρότητα προβλημάτων) ---
def page_schedule():
    """Schedule generation page."""
    st.header("🧠 Δημιουργία Προγράμματος")

    if not st.session_state.employees:
        st.warning("🚫 Πρέπει πρώτα να προσθέσετε υπαλλήλους.")
        return

    if st.button("▶️ Δημιουργία Προγράμματος"):
        data = []
        today = datetime.date.today()
        missing_counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

        for i, day in enumerate(DAYS * 4):  # 4 εβδομάδες
            date = (today + datetime.timedelta(days=i)).strftime("%d/%m/%Y")
            for shift in st.session_state.active_shifts:
                for role in st.session_state.roles:
                    eligible_employees = [
                        e for e in st.session_state.employees
                        if role in e["roles"]
                        and shift in e["availability"]
                        and day not in e.get("unavailable_days", [])
                    ]

                    max_needed = st.session_state.rules["max_employees_per_position"].get(role, 1)
                    count_available = len(eligible_employees)

                    if count_available < max_needed:
                        missing = max_needed - count_available
                        missing_counts[f"{day} ({date})"][shift][role] += missing

                    for e in eligible_employees:
                        data.append({
                            "Ημέρα": f"{day} ({date})",
                            "Βάρδια": shift,
                            "Υπάλληλος": e["name"],
                            "Καθήκοντα": role
                        })

        # Εμφάνιση ελλείψεων σε πίνακα
        if missing_counts:
            st.markdown("### ⚠️ Ελλείψεις σε Βάρδιες")
            rows = []
            for day_label, shifts in missing_counts.items():
                for shift, roles_dict in shifts.items():
                    roles_summary = ", ".join([f"{r} ({n})" for r, n in roles_dict.items()])
                    rows.append({"Ημέρα": day_label, "Βάρδια": shift, "Ρόλοι χωρίς κάλυψη (ποσότητα)": roles_summary})

            warning_df = pd.DataFrame(rows)
            st.dataframe(warning_df, use_container_width=True)

        # Αποθήκευση και AI Βελτιστοποίηση
        if data:
            st.session_state.schedule = pd.DataFrame(data)
            ai_result = process_with_ai("Βελτιστοποίησε το πρόγραμμα.", context=json.dumps(data))
            optimized = ai_result.get("optimized_schedule", data)
            st.session_state.schedule = pd.DataFrame(optimized)
            st.success("✅ Το πρόγραμμα δημιουργήθηκε!")
        else:
            st.error("❌ Δεν δημιουργήθηκε πρόγραμμα. Ελέγξτε τις ρυθμίσεις και τους υπαλλήλους.")

    if not st.session_state.schedule.empty:
        st.markdown("### 📋 Πρόγραμμα Βαρδιών")
        st.dataframe(st.session_state.schedule, use_container_width=True)


# --- Page 4: Chatbot Commands ---
def page_chatbot():
    """Chatbot commands page."""
    st.header("🍊 Chatbot Εντολές")

    if "schedule" not in st.session_state or st.session_state.schedule.empty:
        st.warning("📋 Δεν έχει δημιουργηθεί πρόγραμμα. Πήγαινε στη σελίδα ' Πρόγραμμα ' για να δημιουργήσεις.")
        return

    user_input = st.text_input(
        label="Εισάγετε την εντολή σας",
        placeholder="Π.χ. Ο Κώστας δε μπορεί να δουλέψει Δευτέρες",
        help="Προσθέστε μια εντολή για να επεξεργαστεί το πρόγραμμα."
    )

    if st.button("💡 Εκτέλεση Εντολής") and user_input.strip():
        result = process_with_ai(user_input, context=json.dumps(st.session_state.schedule.to_dict()))

        if "error" in result:
            st.error("❌ Δεν μπόρεσα να καταλάβω την εντολή.")
        else:
            intent = result.get("intent")
            name = result.get("name")
            day = result.get("day")
            extra_info = result.get("extra_info")

            if intent == "set_day_unavailable":
                updated = False
                for emp in st.session_state.employees:
                    if emp["name"] == name:
                        emp.setdefault("unavailable_days", [])
                        if day and day not in emp["unavailable_days"]:
                            emp["unavailable_days"].append(day)
                            st.success(f"🚫 Ο υπάλληλος '{name}' δεν θα είναι διαθέσιμος τις {day}.")
                            updated = True
                        elif day:
                            st.info(f"ℹ️ Η ημέρα {day} ήδη προστέθη στις μη διαθέσιμες του '{name}'.")
                if not updated:
                    st.warning(f"⚠️ Δεν βρέθηκε υπάλληλος με όνομα '{name}'.")

    # Avoid duplicate schedule rendering
    if not st.session_state.schedule.empty:
        if st.session_state.get("chatbot_rendered", False):
            return  # already rendered
        st.session_state.chatbot_rendered = True
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

