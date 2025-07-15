import streamlit as st
import pandas as pd
from collections import defaultdict
import datetime
from openai import OpenAI
import os
import re
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

day_pattern = r"(Δευτέρα|Τρίτη|Τετάρτη|Πέμπτη|Παρασκευή|Σάββατο|Κυριακή)"
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

# --- Page 4: Chatbot Commands ---
def extract_name_and_date(cmd):
    import re

    # Μορφή: "βγάλε τον <όνομα> από το πρόγραμμα την <Ημέρα> (<Ημερομηνία>)"
    m1 = re.search(r"βγ(άλε|άζεις)?.*τον\s+(.*?)\s+.*?(Δευτέρα|Τρίτη|Τετάρτη|Πέμπτη|Παρασκευή|Σάββατο|Κυριακή)\s*\((\d{2}/\d{2}/\d{4})\)", cmd, re.IGNORECASE)
    if m1:
        name = m1.group(2).strip()
        day_str = f"{m1.group(3)} ({m1.group(4)})"
        return name, day_str

    # Μορφή: "ο <όνομα> δε μπορεί να δουλέψει την <Ημέρα> (<Ημερομηνία>)"
    m2 = re.search(r"ο\s+(.*?)\s+(δεν|δε)\s+μπορεί\s+να\s+δουλέψει\s+την\s+(Δευτέρα|Τρίτη|Τετάρτη|Πέμπτη|Παρασκευή|Σάββατο|Κυριακή)\s*\((\d{2}/\d{2}/\d{4})\)", cmd, re.IGNORECASE)
    if m2:
        name = m2.group(1).strip()
        day_str = f"{m2.group(3)} ({m2.group(4)})"
        return name, day_str

    # Μορφή: "η <όνομα> έχει ρεπό την <Ημέρα> (<Ημερομηνία>)"
    m3 = re.search(r"η\s+(.*?)\s+έχει\s+ρεπό\s+την\s+(Δευτέρα|Τρίτη|Τετάρτη|Πέμπτη|Παρασκευή|Σάββατο|Κυριακή)\s*\((\d{2}/\d{2}/\d{4})\)", cmd, re.IGNORECASE)
    if m3:
        name = m3.group(1).strip()
        day_str = f"{m3.group(2)} ({m3.group(3)})"
        return name, day_str

    return None, None


def page_chatbot():
    st.title("🍊 Chatbot Εντολές")
    st.markdown("Π.χ. Ο Γιώργος να μην δουλεύει Σάββατο βράδυ")

    command = st.text_input(" ", placeholder="π.χ. Ο Κώστας δε μπορεί να δουλέψει αύριο")

    if st.button("💡 Εκτέλεση Εντολής"):
        if "schedule_df" not in st.session_state:
            st.error("Δεν έχει δημιουργηθεί πρόγραμμα.")
            return

        schedule_df = st.session_state.schedule_df

        name, date_str = extract_name_and_day(command)

        if name is None or date_str is None:
            st.error("❌ Δεν κατάλαβα την εντολή. Χρησιμοποίησε π.χ.: βγάλε τον Γιώργο από το πρόγραμμα την Τρίτη (16/07/2025)")
            return

        mask = (schedule_df['Ημέρα'] == date_str) & (schedule_df['Υπάλληλος'].str.lower() == name.lower())
        if not mask.any():
            st.warning(f"🔍 Ο {name} δεν έχει βάρδια για {date_str} ή το όνομα είναι λάθος.")
        else:
            st.session_state.schedule_df = schedule_df[~mask].reset_index(drop=True)
            st.success(f"✅ Ο {name} αφαιρέθηκε από το πρόγραμμα για {date_str}.")

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

# --- Main ---
def main():
    init_session()
    navigation()
    page_funcs = [page_business, page_employees, page_schedule, page_chatbot]
    page_funcs[st.session_state.page]()

if __name__ == "__main__":
    main()
