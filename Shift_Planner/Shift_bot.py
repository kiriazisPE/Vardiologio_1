import streamlit as st
import pandas as pd
from collections import defaultdict
from datetime import date, datetime, timedelta
import base64
import os
import json
from openai import OpenAI
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError
import csv
import io


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

def page_chatbot():
    """🤖 Smart Assistant Chatbot"""
    st.header("🧠 Βοηθός Βαρδιών (Chatbot)")

    if "schedule" not in st.session_state or st.session_state.schedule.empty:
        st.warning("📋 Δεν υπάρχει πρόγραμμα. Δημιουργήστε πρώτα μέσω 'Πρόγραμμα'.")
        return

    if "history_stack" not in st.session_state:
        st.session_state.history_stack = []

    employees = [e["name"] for e in st.session_state.employees]
    days = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]

    col1, col2 = st.columns(2)

    # --- Quick actions ---
    with col1:
        st.subheader("⚡ Γρήγορες Εντολές")
        if st.button("Ο Κώστας θέλει ρεπό αύριο"):
            st.session_state["last_user_input"] = "Ο Κώστας θέλει ρεπό αύριο"
        if st.button("Ποιοι δουλεύουν την Παρασκευή"):
            st.session_state["last_user_input"] = "Ποιοι δουλεύουν την Παρασκευή"

    # --- Προτεινόμενη autocomplete εντολή ---
    with col2:
        st.subheader("🧩 Δημιουργία Εντολής με Επιλογές")
        emp = st.selectbox("Υπάλληλος", options=employees)
        day = st.selectbox("Ημέρα", options=days)
        action = st.selectbox("Ενέργεια", options=["θέλει ρεπό", "να δουλέψει απόγευμα", "να μην δουλέψει"])

        if st.button("🎯 Δημιουργία Εντολής"):
            st.session_state["last_user_input"] = f"Ο {emp} {action} την {day}"

    # --- Εισαγωγή εντολής ---
    user_input = st.text_input(
        "📨 Ή γράψε την εντολή σου",
        placeholder="Π.χ. Ο Γιώργος δε μπορεί να δουλέψει την Τετάρτη",
        value=st.session_state.get("last_user_input", "")
    )

    # --- Εκτέλεση ---
    if st.button("💡 Εκτέλεση Εντολής") and user_input.strip():
        prev_schedule = st.session_state.schedule.copy()
        result = process_with_ai(user_input, context=json.dumps(st.session_state.schedule.to_dict()))
        intent = result.get("intent")
        name = result.get("name")
        day = result.get("day")
        extra_info = result.get("extra_info", {})

        if not isinstance(extra_info, dict):
            try:
                extra_info = json.loads(extra_info)
            except:
                extra_info = {}

        executed = False

        # --- Example: set_day_unavailable ---
        if intent in ["set_day_unavailable", "temporary_unavailability"]:
            for emp in st.session_state.employees:
                if emp["name"] == name:
                    emp.setdefault("unavailable_days", [])
                    if day not in emp["unavailable_days"]:
                        emp["unavailable_days"].append(day)
                        st.session_state.schedule = st.session_state.schedule[
                            ~((st.session_state.schedule["Υπάλληλος"] == name) & (st.session_state.schedule["Ημέρα"].str.contains(day)))
                        ]
                        executed = True
                        st.success(f"🚫 Ο {name} δεν θα είναι διαθέσιμος τις {day}.")
                        break

        elif intent == "change_shift":
            for i, row in st.session_state.schedule.iterrows():
                if row["Υπάλληλος"] == name and day in row["Ημέρα"]:
                    new_shift = extra_info.get("shift", "Πρωί")
                    st.session_state.schedule.at[i, "Βάρδια"] = new_shift
                    executed = True
                    st.success(f"🔁 Η βάρδια του {name} άλλαξε σε {new_shift} την {day}.")
                    break

        elif intent == "add_day_off":
            for emp in st.session_state.employees:
                if emp["name"] == name:
                    st.session_state.schedule = st.session_state.schedule[
                        ~((st.session_state.schedule["Υπάλληλος"] == name) & (st.session_state.schedule["Ημέρα"].str.contains(day)))
                    ]
                    executed = True
                    st.success(f"🛌 Ο {name} θα έχει ρεπό την {day}.")
                    break

        else:
            st.info("ℹ️ Η εντολή δεν υποστηρίζεται ακόμη.")

        # --- Αν εκτελέστηκε, αποθήκευση ιστορικού & αλλαγής ---
        if executed:
            st.session_state.chat_history.append({
                "user": user_input,
                "ai_response": f"✅ Εντολή: {intent} για {name} την {day}",
                "timestamp": datetime.now().strftime("%d/%m %H:%M")
            })
            st.session_state.history_stack.append(prev_schedule)

    # --- Ιστορικό Εντολών ---
    if st.session_state.get("chat_history"):
        with st.expander("💬 Ιστορικό Εντολών"):
            for entry in reversed(st.session_state.chat_history[-10:]):
                st.markdown(f"🕒 {entry.get('timestamp', '')}")
                st.markdown(f"**👤 {entry['user']}**")
                st.markdown(f"**🤖 {entry['ai_response']}**")
                st.markdown("---")

    # --- Undo τελευταίας αλλαγής ---
    if st.session_state.history_stack:
        if st.button("↩️ Επαναφορά Προηγούμενης Κατάστασης"):
            st.session_state.schedule = st.session_state.history_stack.pop()
            st.success("🔁 Το πρόγραμμα επανήλθε στην προηγούμενη μορφή.")

    # --- Εμφάνιση Τρέχοντος Προγράμματος ---
    st.subheader("📋 Τρέχον Πρόγραμμα")
    st.dataframe(st.session_state.schedule, use_container_width=True)



# --- Define structured output with Pydantic ---
class IntentResult(BaseModel):
    intent: str | None
    name: str | None
    day: str | None
    extra_info: dict | None
    intent_score: float | None = None  # optional scoring

# --- Logging (can be turned off in prod) ---
LOG_FILE = "intent_log.jsonl"

def log_to_file(data: dict):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")

# --- Navigation ---
def navigation():
    """Handle page navigation."""
    st.sidebar.title("🔁 Πλοήγηση")
    choice = st.sidebar.radio("Μενού", ["1️⃣ Επιχείρηση", "2️⃣ Υπαλλήλοι", "3️⃣ Πρόγραμμα", "4️⃣ Chatbot"])
    st.session_state.page = ["1️⃣ Επιχείρηση", "2️⃣ Υπαλλήλοι", "3️⃣ Πρόγραμμα", "4️⃣ Chatbot"].index(choice)

# --- Page 1: Business Setup ---
def page_business():
    """📊 Ρυθμίσεις Επιχείρησης"""
    st.header("🏢 Ρυθμίσεις Επιχείρησης")

    col1, col2 = st.columns(2)

    # --- Επιλογή ονόματος επιχείρησης ---
    with col1:
        st.subheader("🔖 Όνομα Επιχείρησης")
        st.session_state.business_name = st.text_input(
            "Όνομα επιχείρησης",
            st.session_state.business_name,
            placeholder="π.χ. Καφέ Λιμανάκι",
            help="Το όνομα θα εμφανίζεται στους υπαλλήλους στο πρόγραμμα."
        )

    with col2:
        st.subheader("🏬 Υποκατάστημα (προαιρετικό)")
        st.text_input("Τοποθεσία / κατάστημα", placeholder="π.χ. Σύνταγμα, Αθήνα")

    st.divider()

    # --- Επιλογή ενεργών βαρδιών ---
    st.subheader("🕒 Ενεργές Βάρδιες")
    shift_cols = st.columns(len(ALL_SHIFTS))
    new_shifts = []
    for i, shift in enumerate(ALL_SHIFTS):
        if shift_cols[i].checkbox(shift, shift in st.session_state.active_shifts):
            new_shifts.append(shift)
    st.session_state.active_shifts = new_shifts

    # --- Επιλογή ρόλων ---
    st.subheader("👔 Ρόλοι στην Επιχείρηση")
    with st.expander("➕ Προσθήκη / Αφαίρεση Ρόλων"):
        selected_roles = st.multiselect(
            "Ενεργοί ρόλοι",
            options=DEFAULT_ROLES + EXTRA_ROLES,
            default=st.session_state.roles,
            help="Οι ρόλοι αυτοί θα χρησιμοποιούνται στο πρόγραμμα."
        )
        st.session_state.roles = selected_roles

    st.divider()

    # --- Κανόνες Βαρδιών ---
    st.subheader("⚙️ Κανόνες Βαρδιών")

    st.markdown("🧮 *Ορισμοί γενικών κανόνων για την κατανομή προσωπικού.*")

    st.slider(
        "👥 Μέγιστος συνολικός αριθμός υπαλλήλων ανά βάρδια",
        min_value=1,
        max_value=20,
        value=st.session_state.rules["max_employees_per_shift"],
        key="max_employees_per_shift_slider",
        help="Αφορά όλους τους υπαλλήλους ανά βάρδια, ανεξαρτήτως ρόλου."
    )
    st.session_state.rules["max_employees_per_shift"] = st.session_state["max_employees_per_shift_slider"]

    with st.expander("📌 Μέγιστος αριθμός υπαλλήλων ανά ρόλο ανά βάρδια"):
        for role in st.session_state.roles:
            default_val = st.session_state.rules["max_employees_per_position"].get(role, 2)
            st.session_state.rules["max_employees_per_position"][role] = st.number_input(
                f"👤 {role}",
                min_value=0,
                max_value=10,
                value=default_val,
                key=f"role_{role}",
                help=f"Πόσα άτομα επιτρέπονται το πολύ για τον ρόλο '{role}' ανά βάρδια."
            )

    st.divider()

    # --- Επισκόπηση ---
    with st.expander("📋 Προεπισκόπηση Ρυθμίσεων", expanded=False):
        st.markdown(f"**📛 Επιχείρηση:** `{st.session_state.business_name}`")
        st.markdown(f"**🕒 Ενεργές Βάρδιες:** {', '.join(st.session_state.active_shifts)}")
        st.markdown(f"**👔 Ρόλοι:** {', '.join(st.session_state.roles)}")
        st.markdown(f"**👥 Max ανά βάρδια:** {st.session_state.rules['max_employees_per_shift']}")
        st.markdown("**📌 Max ανά ρόλο:**")
        st.json(st.session_state.rules["max_employees_per_position"])

# --- Page 2: Employees ---
def page_employees():
    """👥 Διαχείριση Υπαλλήλων"""
    st.header("👥 Προσωπικό")

    # --- Επιλογή ρόλου για φιλτράρισμα ---
    all_roles = sorted(set(role for emp in st.session_state.employees for role in emp.get("roles", [])))
    role_filter = st.selectbox("Φίλτρο ανά ρόλο", options=["Όλοι"] + all_roles, index=0)

    # --- Εισαγωγή από CSV ---
    with st.expander("📂 Εισαγωγή υπαλλήλων από CSV"):
        uploaded_file = st.file_uploader("Ανέβασε αρχείο CSV", type=["csv"])
        if uploaded_file:
            reader = csv.DictReader(io.StringIO(uploaded_file.getvalue().decode("utf-8")))
            new_employees = []
            for row in reader:
                new_employees.append({
                    "name": row.get("name", ""),
                    "roles": row.get("roles", "").split(","),
                    "availability": row.get("availability", "").split(","),
                    "days_off": int(row.get("days_off", 2)),
                    "avatar": row.get("avatar", "👤")
                })
            st.session_state.employees.extend(new_employees)
            st.success("✅ Εισήχθησαν υπάλληλοι από CSV!")

    # --- Φόρμα προσθήκης υπαλλήλου ---
    with st.expander("➕ Προσθήκη Νέου Υπαλλήλου", expanded=False):
        with st.form("add_employee_form"):
            col1, col2 = st.columns([3, 1])
            with col1:
                name = st.text_input("Όνομα")
                roles = st.multiselect("Ρόλοι", st.session_state.roles)
                availability = st.multiselect("Διαθεσιμότητα (Βάρδιες)", st.session_state.active_shifts)
            with col2:
                avatar = st.selectbox("Avatar", options=["👩‍🍳", "🧑‍💼", "🧑‍🔧", "🧑‍🎓", "🧑‍🏭", "👤"], index=5)
                days_off = st.slider("Ρεπό ανά εβδομάδα", 1, 3, 2)

            submitted = st.form_submit_button("💾 Αποθήκευση")
            if submitted and name.strip():
                st.session_state.employees.append({
                    "name": name.strip(),
                    "roles": roles,
                    "availability": availability,
                    "days_off": days_off,
                    "avatar": avatar
                })
                st.success(f"✅ Ο υπάλληλος '{name}' προστέθηκε.")
                st.rerun()

    st.divider()

    # --- Εμφάνιση υπαλλήλων ---
    filtered_employees = [
        emp for emp in st.session_state.employees
        if role_filter == "Όλοι" or role_filter in emp.get("roles", [])
    ]

    if filtered_employees:
        for emp in filtered_employees:
            with st.expander(f"{emp.get('avatar', '👤')} {emp['name']}"):
                tabs = st.tabs(["👔 Ρόλοι", "🕒 Διαθεσιμότητα", "📆 Ρεπό"])
                with tabs[0]:
                    st.markdown(f"**Ρόλοι:** {', '.join(emp.get('roles', [])) or '—'}")
                with tabs[1]:
                    st.markdown(f"**Διαθέσιμες Βάρδιες:** {', '.join(emp.get('availability', [])) or '—'}")
                with tabs[2]:
                    st.markdown(f"**Ρεπό ανά εβδομάδα:** {emp.get('days_off', 2)}")

    else:
        st.info("Δεν υπάρχουν υπάλληλοι για εμφάνιση.")

    st.divider()

    # --- Εξαγωγή σε CSV ---
    with st.expander("💾 Εξαγωγή υπαλλήλων σε CSV"):
        if st.button("📤 Λήψη αρχείου CSV"):
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=["name", "roles", "availability", "days_off", "avatar"])
            writer.writeheader()
            for emp in st.session_state.employees:
                writer.writerow({
                    "name": emp["name"],
                    "roles": ",".join(emp.get("roles", [])),
                    "availability": ",".join(emp.get("availability", [])),
                    "days_off": emp.get("days_off", 2),
                    "avatar": emp.get("avatar", "👤")
                })
            b64 = base64.b64encode(output.getvalue().encode()).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="employees_{datetime.now().strftime("%Y%m%d")}.csv">📥 Κατέβασε το CSV</a>'
            st.markdown(href, unsafe_allow_html=True)


# --- Page 3: Schedule Generation (βελτιωμένη εμπειρία χρήστη & καθαρότητα προβλημάτων) ---
def page_schedule():
    """🧠 Δημιουργία Προγράμματος"""
    st.header("📅 Πρόγραμμα Βαρδιών")

    if not st.session_state.employees:
        st.warning("🚫 Πρέπει πρώτα να προσθέσετε υπαλλήλους.")
        return

    # --- Ημερομηνία έναρξης ---
    start_date = st.date_input("📆 Έναρξη εβδομάδας", value=date.today())
    dates = [start_date + timedelta(days=i) for i in range(7)]
    greek_days = ["Δευ", "Τρι", "Τετ", "Πεμ", "Παρ", "Σαβ", "Κυρ"]

    if st.button("🛠 Δημιουργία Εβδομαδιαίου Προγράμματος"):
        data = []
        for current_date in dates:
            greek_day = greek_days[current_date.weekday()]
            label = f"{greek_day} {current_date.strftime('%d/%m')}"
            for shift in st.session_state.active_shifts:
                for role in st.session_state.roles:
                    eligible = [
                        e for e in st.session_state.employees
                        if role in e["roles"]
                        and shift in e["availability"]
                        and greek_day not in e.get("unavailable_days", [])
                    ]
                    max_needed = st.session_state.rules["max_employees_per_position"].get(role, 1)
                    for e in eligible[:max_needed]:
                        data.append({
                            "Ημέρα": label,
                            "Ημερομηνία": current_date.strftime("%Y-%m-%d"),
                            "Βάρδια": shift,
                            "Υπάλληλος": e["name"],
                            "Ρόλος": role,
                            "⚠️": ""
                        })

        st.session_state.schedule = pd.DataFrame(data)
        st.success("✅ Δημιουργήθηκε πρόγραμμα για 7 ημέρες!")

    # --- Εμφάνιση και επεξεργασία πίνακα ---
    if not st.session_state.schedule.empty:
        st.subheader("📝 Επεξεργασία Προγράμματος")
        
        pivot_df = st.session_state.schedule.pivot_table(
            index="Υπάλληλος", columns="Ημέρα", values="Βάρδια",
            aggfunc="first"  # παίρνει την πρώτη τιμή αν υπάρχουν διπλές
        ).fillna("—").reset_index()


        edited_df = st.data_editor(
            pivot_df,
            num_rows="fixed",
            use_container_width=True,
            column_config={
                col: st.column_config.SelectboxColumn(
                    options=["—"] + st.session_state.active_shifts,
                    required=False
                )
                for col in pivot_df.columns if col != "Υπάλληλος"
            },
            key="schedule_editor"
        )

        # --- Ενημέρωση προγράμματος από τον edited πίνακα ---
        updated_rows = []
        for _, row in edited_df.iterrows():
            for day in edited_df.columns[1:]:
                shift = row[day]
                if shift != "—":
                    updated_rows.append({
                        "Ημέρα": day,
                        "Ημερομηνία": "",  # Προαιρετικό
                        "Βάρδια": shift,
                        "Υπάλληλος": row["Υπάλληλος"],
                        "Ρόλος": "",  # Δεν αλλάζει
                        "⚠️": ""
                    })
        st.session_state.schedule = pd.DataFrame(updated_rows)

        # --- Επισήμανση παραβιάσεων ---
        st.subheader("🚨 Παραβιάσεις Κανόνων")
        warnings = []
        for name in st.session_state.schedule["Υπάλληλος"].unique():
            emp_schedule = st.session_state.schedule[st.session_state.schedule["Υπάλληλος"] == name]
            if len(emp_schedule) > 6:
                warnings.append(f"⚠️ Ο {name} έχει πάνω από 6 βάρδιες την εβδομάδα.")
        if warnings:
            for w in warnings:
                st.error(w)
        else:
            st.success("✅ Δεν εντοπίστηκαν παραβιάσεις.")

        # --- Εξαγωγή ---
        st.subheader("📤 Εξαγωγή Προγράμματος")
        csv = st.session_state.schedule.to_csv(index=False).encode("utf-8")
        st.download_button("💾 Λήψη CSV", csv, file_name="schedule.csv", mime="text/csv")

        with st.expander("🖨 Προεπισκόπηση για Εκτύπωση"):
            st.dataframe(st.session_state.schedule, use_container_width=True)


# --- AI Processor ---
def process_with_ai(user_input: str, context: str = "") -> dict:
    """
    Χρησιμοποιεί OpenAI για intent recognition. Υποστηρίζει πολλαπλά intents,
    scoring, schema validation και logging.
    """
    try:
        system_prompt = f"""
Είσαι βοηθός σε σύστημα διαχείρισης βαρδιών. Αναλύεις ελληνικές εντολές και απαντάς σε JSON.

Μπορείς να επιστρέψεις 1 ή περισσότερα intents.

JSON output: 
[
  {{
    "intent": "set_day_unavailable",
    "name": "Γιώργος",
    "day": "Δευτέρα",
    "extra_info": {{}},
    "intent_score": 0.95
  }},
  ...
]

Αν δεν μπορείς να αναγνωρίσεις τίποτα:
[{{"intent": null, "name": null, "day": null, "extra_info": null, "intent_score": 0.0}}]

Το context αφορά το υπάρχον πρόγραμμα και είναι προαιρετικό:
{context}
        """

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": f"Ανάλυσε την εντολή: {user_input}"}
            ],
            temperature=0.2
        )

        raw = response.choices[0].message.content.strip()

        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                parsed = [parsed]

            validated = []
            for entry in parsed:
                try:
                    validated.append(IntentResult(**entry).dict())
                except ValidationError as ve:
                    validated.append({
                        "intent": None,
                        "name": None,
                        "day": None,
                        "extra_info": None,
                        "intent_score": 0.0,
                        "error": ve.errors()
                    })

            # Log
            log_to_file({
                "timestamp": datetime.now().isoformat(),
                "input": user_input,
                "output": validated
            })

            # Επιστρέφουμε το intent με το υψηλότερο intent_score
            best = max(validated, key=lambda x: x.get("intent_score", 0) or 0)
            return best

        except json.JSONDecodeError:
            st.warning("⚠️ Η απάντηση AI δεν είχε σωστή μορφή JSON.")
            return {"intent": None, "name": None, "day": None, "extra_info": None, "intent_score": 0.0}

    except Exception as e:
        st.error("❌ Σφάλμα κατά την επικοινωνία με το AI.")
        return {"intent": None, "name": None, "day": None, "extra_info": None, "intent_score": 0.0, "error": str(e)}
    
# --- Page 4: Chatbot Commands ---
def main():
    """Main function to run the app."""
    init_session()
    navigation()
    page_funcs = [page_business, page_employees, page_schedule, page_chatbot]
    page_funcs[st.session_state.page]()

if __name__ == "__main__":
    main()