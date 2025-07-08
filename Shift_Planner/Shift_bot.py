
import streamlit as st
import pandas as pd
from openai import OpenAI
import os
from copy import deepcopy
from dotenv import load_dotenv

# ----------- ΡΥΘΜΙΣΗ ----------
st.set_page_config(page_title="Βοηθός Προγράμματος Βαρδιών", layout="wide")
st.title("🤖 Βοηθός Προγράμματος Βαρδιών")
st.caption("Πρόγραμμα και μεταβολές σε φυσική γλώσσα με ειδοποιήσεις παραβίασης")

DAYS = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]
SHIFTS = ["Πρωί", "Απόγευμα", "Βράδυ"]
ROLES = ["Ταμείο", "Σερβιτόρος", "Μάγειρας", "Barista"]

# --- CLIENT με νέο API ---
load_dotenv()
client = OpenAI(api_key="OPENAI_API_KEY")  # 🔐 Βάλε εδώ το OpenAI API key σου

# ----------- ΑΡΧΙΚΟΠΟΙΗΣΗ ----------
if "employees" not in st.session_state:
    st.session_state.employees = []
if "schedule" not in st.session_state:
    st.session_state.schedule = pd.DataFrame()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ----------- ΠΡΟΣΘΗΚΗ ΥΠΑΛΛΗΛΟΥ ----------
with st.expander("👥 Προσθήκη Υπαλλήλων", expanded=True):
    name = st.text_input("Όνομα")
    roles = st.multiselect("Ρόλοι", ROLES)
    days_off = st.slider("Ρεπό ανά εβδομάδα", 1, 3, 2)
    availability = st.multiselect("Διαθεσιμότητα για όλες τις ημέρες", SHIFTS)

    if st.button("➕ Προσθήκη"):
        st.session_state.employees.append({
            "name": name,
            "roles": roles,
            "days_off": days_off,
            "availability": {day: availability for day in DAYS}
        })
        st.success(f"Προστέθηκε ο {name}")

# ----------- ΠΡΟΓΡΑΜΜΑ ----------
if st.button("🧠 Δημιουργία Προγράμματος"):
    rows = []
    workdays = {e["name"]: 0 for e in st.session_state.employees}
    for day in DAYS:
        for shift in SHIFTS:
            for role in ROLES:
                for e in st.session_state.employees:
                    if (shift in e["availability"].get(day, [])) and (role in e["roles"]) and workdays[e["name"]] < (7 - e["days_off"]):
                        rows.append({
                            "Ημέρα": day,
                            "Βάρδια": shift,
                            "Υπάλληλος": e["name"],
                            "Καθήκοντα": role
                        })
                        workdays[e["name"]] += 1
                        break
    st.session_state.schedule = pd.DataFrame(rows)
    st.success("✅ Πρόγραμμα δημιουργήθηκε")
    st.dataframe(st.session_state.schedule, use_container_width=True)

# ----------- ΣΥΝΟΜΙΛΙΑ ΜΕ ΒΟΗΘΟ ----------
st.markdown("### 💬 Φυσική Γλώσσα - Βοηθός")

question = st.chat_input("Π.χ. Ο Κώστας την Πέμπτη θα μπει βράδυ")

if not st.session_state.schedule.empty:
    if question:
        schedule_csv = st.session_state.schedule.to_csv(index=False)
        employee_data = pd.DataFrame([{
            "Όνομα": e["name"],
            "Ρόλοι": ", ".join(e["roles"]),
            "Ρεπό": e["days_off"],
            "Διαθεσιμότητα": str(e["availability"])
        } for e in st.session_state.employees]).to_csv(index=False)

        prompt = f"""
Έχεις δύο πίνακες:
1. Πρόγραμμα εργασίας (CSV):
{schedule_csv}

2. Δεδομένα υπαλλήλων:
{employee_data}

Ο χρήστης έδωσε την εξής εντολή:
"{question}"

Απάντησε:
- Τι αλλαγή πρέπει να γίνει
- Αν υπάρχει conflict με τις διαθέσιμες ημέρες ή βάρδιες
- Αν ο υπάλληλος έχει ήδη βάρδια την επόμενη μέρα (π.χ. νυχτερινή-πρωινή)

Απάντησε στα Ελληνικά με σύντομες παρατηρήσεις.
"""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Είσαι βοηθός προγράμματος εργασίας και ελέγχεις αν μια αλλαγή προκαλεί πρόβλημα."},
                {"role": "user", "content": prompt}
            ]
        )
        answer = response.choices[0].message.content.strip()
        st.session_state.chat_history.append(("🧑‍💼", question))
        st.session_state.chat_history.append(("🤖", answer))

    for role, msg in st.session_state.chat_history:
        st.chat_message(role).write(msg)
else:
    st.info("⚠️ Δημιούργησε πρώτα πρόγραμμα για να ξεκινήσεις συνομιλία.")
