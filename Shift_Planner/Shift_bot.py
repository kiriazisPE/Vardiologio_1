import streamlit as st
import pandas as pd
from collections import defaultdict
import datetime
from openai import OpenAI
import os
from dotenv import load_dotenv

# --- Load .env for API Key ---
load_dotenv()
client = OpenAI()

# --- Page Config ---
st.set_page_config(page_title="Βοηθός Προγράμματος Βαρδιών", layout="wide")

# --- Constants ---
DAYS = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]
ALL_SHIFTS = ["Πρωί", "Απόγευμα", "Βράδυ"]
DEFAULT_ROLES = ["Ταμείο", "Σερβιτόρος", "Μάγειρας", "Barista"]
EXTRA_ROLES = ["Υποδοχή", "Καθαριστής", "Λαντζέρης", "Οδηγός", "Manager"]

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
    st.session_state.setdefault("rules", {
        "max_employees_per_shift": 5,
        "max_employees_per_position": {role: 2 for role in DEFAULT_ROLES + EXTRA_ROLES},
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
# --- Page 2: Employees ---
def page_employees():
    st.header("👥 Προσθήκη Υπαλλήλων")
    with st.form("employee_form"):
        name = st.text_input("Όνομα")
        if "roles" not in st.session_state:
            st.session_state.roles = DEFAULT_ROLES + EXTRA_ROLES
            roles = st.multiselect("Ρόλοι", st.session_state.roles)

        days_off = st.slider("Ρεπό ανά εβδομάδα", 1, 3, 2)
        availability = st.multiselect("Διαθεσιμότητα για όλες τις ημέρες", st.session_state.active_shifts)
        submitted = st.form_submit_button("➕ Προσθήκη")
        if submitted and name:
            st.session_state.employees.append({"name": name, "roles": roles, "days_off": days_off, "availability": availability})
            st.success(f"Ο υπάλληλος {name} προστέθηκε.")

    if st.session_state.employees:
        st.markdown("### Εγγεγραμμένοι Υπάλληλοι")
        for i, emp in enumerate(st.session_state.employees):
            with st.expander(f"👤 {emp['name']}"):
                st.write(emp)
                col1, col2 = st.columns(2)
                if col1.button("✏️ Επεξεργασία", key=f"edit_{i}"):
                    st.session_state.edit_index = i
                if col2.button("🗑️ Διαγραφή", key=f"delete_{i}"):
                    st.session_state.employees.pop(i)
                    st.experimental_rerun()
# --- Page 3: Schedule Generation ---
def page_schedule():
    st.header("🧠 Δημιουργία Προγράμματος")
    if not st.session_state.employees:
        st.warning("Προσθέστε πρώτα υπαλλήλους.")
        return

    if st.button("▶️ Δημιουργία Προγράμματος"):
        data = []
        coverage = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        today = datetime.date.today()
        for i, day in enumerate(DAYS):
            date = (today + datetime.timedelta(days=i)).strftime("%d/%m/%Y")
            for shift in st.session_state.active_shifts:
                for role in st.session_state.roles:
                    count = 0
                    for e in st.session_state.employees:
                        if role in e["roles"] and shift in e["availability"]:
                            data.append({"Ημέρα": f"{day} ({date})", "Βάρδια": shift, "Υπάλληλος": e['name'], "Καθήκοντα": role})
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
# --- Page 4: Chatbot ---
def page_chatbot():
    st.header("💬 Βοηθός Προγράμματος Βαρδιών")
    if st.session_state.schedule.empty:
        st.warning("⚠️ Δημιουργήστε πρώτα πρόγραμμα για να ξεκινήσει η συνομιλία.")
        return

    st.markdown("### 📅 Πρόγραμμα")
    st.dataframe(st.session_state.schedule)

    st.markdown("---")
    st.markdown("### ✍️ Chatbot Εντολές")
    prompt = st.text_input("Π.χ. Ο Γιώργος να μην δουλεύει Σάββατο βράδυ")
    if st.button("💡 Εκτέλεση Εντολής") and prompt:
        with st.spinner("🔍 Επεξεργασία εντολής..."):
            try:
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "system", "content": "Είσαι ένας βοηθός προγραμματισμού βαρδιών που κάνει αλλαγές στο πρόγραμμα."}] + st.session_state.chat_history
                )
                reply = response.choices[0].message.content
                st.session_state.chat_history.append({"role": "assistant", "content": reply})
                st.success("✅ Εντολή ολοκληρώθηκε")
                st.markdown("**Απάντηση:**")
                st.write(reply)
            except Exception as e:
                st.error(f"Σφάλμα κατά την κλήση OpenAI API: {e}")

# --- Main ---
def main():
    init_session()
    navigation()
    page_funcs = [page_business, page_employees, page_schedule, page_chatbot]
    page_funcs[st.session_state.page]()

if __name__ == "__main__":
    main()