import streamlit as st
import pandas as pd
from collections import defaultdict
import datetime
from openai import OpenAI
import os
from dotenv import load_dotenv

# --- Load .env for API Key ---
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Page Config ---
st.set_page_config(page_title="Βοηθός Προγράμματος Βαρδιών", layout="wide")

# --- Constants ---
DAYS = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]
ALL_SHIFTS = ["Πρωί", "Απόγευμα", "Βράδυ"]
ROLES = ["Ταμείο", "Σερβιτόρος", "Μάγειρας", "Barista"]

# --- Session State Initialization ---
def init_session():
    st.session_state.setdefault("page", 0)
    st.session_state.setdefault("business_name", "")
    st.session_state.setdefault("active_shifts", ALL_SHIFTS[:2])
    st.session_state.setdefault("employees", [])
    st.session_state.setdefault("edit_index", None)
    st.session_state.setdefault("requirements", defaultdict(lambda: defaultdict(int)))
    st.session_state.setdefault("schedule", pd.DataFrame())

# --- Navigation ---
def navigation():
    st.sidebar.title("🔁 Πλοήγηση")
    choice = st.sidebar.radio("Μενού", ["1️⃣ Επιχείρηση", "2️⃣ Υπάλληλοι", "3️⃣ Πρόγραμμα", "4️⃣ Chatbot"])
    st.session_state.page = ["1️⃣ Επιχείρηση", "2️⃣ Υπάλληλοι", "3️⃣ Πρόγραμμα", "4️⃣ Chatbot"].index(choice)

# --- Page 1: Business Setup ---
def page_business():
    st.header("🏢 Ρυθμίσεις Επιχείρησης")
    st.session_state.business_name = st.text_input("Όνομα Επιχείρησης", st.session_state.business_name)
    st.markdown("### Επιλέξτε ενεργές βάρδιες")
    st.session_state.active_shifts = st.multiselect("Βάρδιες που χρησιμοποιεί η επιχείρηση", ALL_SHIFTS, default=st.session_state.active_shifts)

# --- Page 2: Employees ---
def page_employees():
    st.header("👥 Προσθήκη Υπαλλήλων")
    with st.form("employee_form"):
        name = st.text_input("Όνομα")
        roles = st.multiselect("Ρόλοι", ROLES)
        days_off = st.slider("Ρεπό ανά εβδομάδα", 1, 3, 2)
        availability = st.multiselect("Διαθεσιμότητα για όλες τις ημέρες", st.session_state.active_shifts)
        submitted = st.form_submit_button("➕ Προσθήκη")
        if submitted and name:
            st.session_state.employees.append({"name": name, "roles": roles, "days_off": days_off, "availability": availability})
            st.success(f"Ο υπάλληλος {name} προστέθηκε.")

    if st.session_state.employees:
        st.markdown("### Εγγεγραμμένοι Υπάλληλοι")
        st.dataframe(pd.DataFrame(st.session_state.employees))

# --- Page 3: Schedule Generation ---
def page_schedule():
    st.header("🧠 Δημιουργία Προγράμματος")
    if not st.session_state.employees:
        st.warning("Προσθέστε πρώτα υπαλλήλους.")
        return

    if st.button("▶️ Δημιουργία Προγράμματος"):
        data = []
        for day in DAYS:
            for shift in st.session_state.active_shifts:
                for e in st.session_state.employees:
                    data.append({"Ημέρα": day, "Βάρδια": shift, "Υπάλληλος": e['name'], "Καθήκοντα": ", ".join(e['roles'])})
        st.session_state.schedule = pd.DataFrame(data)
        st.success("✅ Το πρόγραμμα δημιουργήθηκε!")

    if not st.session_state.schedule.empty:
        st.dataframe(st.session_state.schedule)
        csv = st.session_state.schedule.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Εξαγωγή CSV", csv, file_name="programma.csv", mime="text/csv")

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
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Είσαι ένας βοηθός προγραμματισμού βαρδιών που κάνει αλλαγές στο πρόγραμμα."},
                        {"role": "user", "content": prompt},
                    ]
                )
                reply = response.choices[0].message.content
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
