# DSPy Signatures for Shift Scheduling

Αυτό το έγγραφο εξηγεί πώς χρησιμοποιείται το DSPy για δομημένες εισόδους/εξόδους στο σύστημα προγραμματισμού βαρδιών.

## 📋 Περιεχόμενα

- [Τι είναι το DSPy](#τι-είναι-το-dspy)
- [Γιατί DSPy για Βάρδιες](#γιατί-dspy-για-βάρδιες)
- [Εγκατάσταση](#εγκατάσταση)
- [Δομημένες Έξοδοι](#δομημένες-έξοδοι)
- [Παραδείγματα Χρήσης](#παραδείγματα-χρήσης)
- [API Reference](#api-reference)

---

## Τι είναι το DSPy

Το **DSPy** είναι ένα framework για προγραμματισμό με LLMs που παρέχει:

- 🎯 **Structured Outputs**: Εγγυημένη δομή JSON με Pydantic
- 🔄 **Signatures**: Σαφείς συμβόλαια εισόδου/εξόδου
- 🧠 **Chain of Thought**: Βελτιωμένη λογική με ενδιάμεσα βήματα
- ⚡ **Predictability**: Προβλέψιμες και αξιόπιστες απαντήσεις

---

## Γιατί DSPy για Βάρδιες

Για ένα πρόγραμμα βαρδιών χρειαζόμαστε **συγκεκριμένη και προβλέψιμη έξοδο**:

### ✅ Πριν το DSPy (Unstructured)
```json
{
  "response": "Φαίνεται ότι χρειάζεσαι 3 άτομα την Δευτέρα και πιθανώς 2 το βράδυ..."
}
```

### ✅ Με DSPy (Structured)
```json
{
  "date": "2025-12-15",
  "day_name": "Monday",
  "shifts": [
    {"shift_type": "day", "required_count": 3, "role": "Barista"},
    {"shift_type": "night", "required_count": 2, "role": "Barista"}
  ],
  "total_staff_needed": 5,
  "is_weekend": false
}
```

---

## Εγκατάσταση

### 1. Εγκατάσταση Dependencies

```bash
pip install -r requirements.txt
```

Το `requirements.txt` περιλαμβάνει:
```
dspy-ai>=2.4.0       # Structured LLM programming
openai>=1.54.0       # OpenAI API
pydantic>=2.0.0      # Data validation
```

### 2. Ρύθμιση API Key

Δημιούργησε ένα `.env` αρχείο:
```bash
OpenAI_API_KEY=sk-your-api-key-here
```

### 3. Έλεγχος Εγκατάστασης

```bash
python shift_planner/dspy_example_usage.py
```

---

## Δομημένες Έξοδοι

Το σύστημα παρέχει **4 κύριες δομημένες εξόδους**:

### 1. 📅 Shifts Per Day

**Τι περιέχει**: Απαιτήσεις βαρδιών ανά ημέρα

```python
from ai_scheduler import get_shifts_per_day_structured

shifts = get_shifts_per_day_structured(
    business_model="5ήμερο",
    start_date=date(2025, 12, 15),
    days_count=7,
    active_shifts=["day", "night"],
    roles=["Manager", "Barista"],
    role_requirements={
        "Manager": {"day": 1, "night": 1},
        "Barista": {"day": 2, "night": 1}
    }
)
```

**Έξοδος**:
```json
[
  {
    "date": "2025-12-15",
    "day_name": "Monday",
    "shifts": [
      {"shift_type": "day", "start_hour": 8, "required_count": 1, "role": "Manager"},
      {"shift_type": "day", "start_hour": 8, "required_count": 2, "role": "Barista"},
      {"shift_type": "night", "start_hour": 20, "required_count": 1, "role": "Manager"}
    ],
    "total_staff_needed": 4,
    "is_weekend": false,
    "special_notes": null
  }
]
```

### 2. 👥 Employee Availability

**Τι περιέχει**: Διαθεσιμότητα και περιορισμοί υπαλλήλων

```python
from ai_scheduler import get_employee_availability_structured

availability = get_employee_availability_structured(
    employees=[
        {"name": "Γιάννης", "roles": ["Manager"], "availability": ["2025-12-15"]}
    ],
    schedule_start=date(2025, 12, 15),
    schedule_days=7,
    current_schedule=pd.DataFrame(),
    work_rules={"max_daily_hours_5days": 8, "weekly_hours_5days": 40}
)
```

**Έξοδος**:
```json
[
  {
    "name": "Γιάννης Παπαδόπουλος",
    "available_dates": ["2025-12-15", "2025-12-16", "2025-12-17"],
    "roles": ["Manager"],
    "preferred_shifts": ["day"],
    "max_weekly_hours": 40.0,
    "current_weekly_hours": 16.0,
    "unavailable_dates": ["2025-12-20"],
    "constraints": "Prefers not to work weekends"
  }
]
```

### 3. ⚠️ Violations

**Τι περιέχει**: Παραβιάσεις κανόνων με σοβαρότητα

```python
from ai_scheduler import get_violations_structured

violations = get_violations_structured(
    schedule_df=current_schedule,
    employees=employees,
    work_rules=work_rules,
    role_requirements=role_requirements
)
```

**Έξοδος**:
```json
[
  {
    "violation_type": "MAX_HOURS_EXCEEDED",
    "severity": "HIGH",
    "employee": "Μαρία Κωνσταντίνου",
    "date": "2025-12-15",
    "shift": "day",
    "description": "Μαρία scheduled for 45 hours this week, exceeds max 40 hours",
    "rule_violated": "max_weekly_hours",
    "current_value": 45.0,
    "max_allowed": 40.0
  },
  {
    "violation_type": "INSUFFICIENT_REST",
    "severity": "CRITICAL",
    "employee": "Νίκος Γεωργίου",
    "date": "2025-12-16",
    "description": "Only 4 hours rest between day and night shift",
    "rule_violated": "min_daily_rest",
    "current_value": 4.0,
    "max_allowed": 11.0
  }
]
```

### 4. 💡 Suggestions

**Τι περιέχει**: Προτάσεις βελτιστοποίησης με προτεραιότητα

```python
from ai_scheduler import get_suggestions_structured

suggestions = get_suggestions_structured(
    schedule_df=current_schedule,
    violations=violations,
    employees=employees,
    roles=["Manager", "Barista"],
    active_shifts=["day", "night"],
    optimization_goals="Fix violations, balance workload"
)
```

**Έξοδος**:
```json
[
  {
    "suggestion_type": "SWAP",
    "priority": "HIGH",
    "employee": "Μαρία",
    "employee2": "Νίκος",
    "date": "2025-12-17",
    "shift": "day",
    "role": "Barista",
    "description": "Swap Μαρία's day shift with Νίκος to reduce Μαρία's hours",
    "expected_benefit": "Reduces Μαρία's weekly hours to 40h and balances workload",
    "impact_score": 85.0
  },
  {
    "suggestion_type": "REASSIGN",
    "priority": "MEDIUM",
    "employee": "Γιάννης",
    "date": "2025-12-16",
    "shift": "night",
    "role": "Manager",
    "description": "Remove Γιάννης from night shift to allow proper rest",
    "expected_benefit": "Ensures 11 hours rest between shifts",
    "impact_score": 75.0
  }
]
```

---

## Παραδείγματα Χρήσης

### Παράδειγμα 1: Comprehensive Analysis

Πάρε όλες τις 4 εξόδους με μια κλήση:

```python
from ai_scheduler import get_comprehensive_analysis_structured
import datetime as dt

analysis = get_comprehensive_analysis_structured(
    business_settings={
        "name": "Καφετέρια Αθήνα",
        "model": "5ήμερο",
        "shifts": ["day", "night"]
    },
    employees=[
        {"name": "Γιάννης", "roles": ["Manager"]},
        {"name": "Μαρία", "roles": ["Barista"]}
    ],
    schedule_params={
        "start_date": dt.date(2025, 12, 15),
        "days_count": 7,
        "active_shifts": ["day", "night"],
        "roles": ["Manager", "Barista"],
        "role_requirements": {
            "Manager": {"day": 1, "night": 1},
            "Barista": {"day": 2, "night": 1}
        }
    },
    current_schedule=pd.DataFrame(),
    work_rules={
        "max_daily_hours_5days": 8,
        "weekly_hours_5days": 40,
        "min_daily_rest": 11
    }
)

# Αποτελέσματα
print(f"Shifts: {len(analysis['shifts_per_day'])} days")
print(f"Availability: {len(analysis['employee_availability'])} employees")
print(f"Violations: {len(analysis['violations'])} found")
print(f"Suggestions: {len(analysis['suggestions'])} recommendations")
print(f"Overall Score: {analysis['overall_score']}")
```

### Παράδειγμα 2: Streamlit Integration

```python
import streamlit as st
from ai_scheduler import get_violations_structured, get_suggestions_structured

# Detect violations
violations = get_violations_structured(
    schedule_df=st.session_state.schedule,
    employees=st.session_state.employees,
    work_rules=st.session_state.rules,
    role_requirements=st.session_state.role_reqs
)

# Show violations grouped by severity
if violations:
    st.error(f"⚠️ {len(violations)} violations detected")
    
    critical = [v for v in violations if v['severity'] == 'CRITICAL']
    high = [v for v in violations if v['severity'] == 'HIGH']
    
    if critical:
        st.subheader("🚨 Critical Violations")
        for v in critical:
            st.warning(f"{v['employee']}: {v['description']}")
    
    # Get suggestions to fix
    suggestions = get_suggestions_structured(
        schedule_df=st.session_state.schedule,
        violations=violations,
        employees=st.session_state.employees,
        roles=st.session_state.roles,
        active_shifts=st.session_state.shifts,
        optimization_goals="Fix all critical violations first"
    )
    
    st.subheader("💡 Suggested Fixes")
    for s in suggestions:
        if s['priority'] == 'HIGH':
            st.info(f"{s['suggestion_type']}: {s['description']}")
```

### Παράδειγμα 3: Batch Processing

```python
from ai_scheduler import get_shifts_per_day_structured
import datetime as dt

# Plan multiple weeks
all_weeks = []
start = dt.date(2025, 12, 15)

for week in range(4):  # 4 weeks
    week_start = start + dt.timedelta(days=week * 7)
    
    shifts = get_shifts_per_day_structured(
        business_model="5ήμερο",
        start_date=week_start,
        days_count=7,
        active_shifts=["day", "night"],
        roles=["Manager", "Barista", "Cashier"],
        role_requirements={
            "Manager": {"day": 1, "night": 1},
            "Barista": {"day": 2, "night": 1},
            "Cashier": {"day": 1, "night": 1}
        }
    )
    
    all_weeks.append({
        "week": week + 1,
        "start_date": week_start,
        "shifts": shifts
    })

# Analyze total staffing needs
total_staff_hours = sum(
    day['total_staff_needed'] * 8  # Assume 8-hour shifts
    for week in all_weeks
    for day in week['shifts']
)

print(f"Total staff hours needed for 4 weeks: {total_staff_hours}")
```

---

## API Reference

### Core Functions

#### `get_shifts_per_day_structured()`

Επιστρέφει δομημένες απαιτήσεις βαρδιών ανά ημέρα.

**Parameters:**
- `business_model` (str): Μοντέλο εργασίας (π.χ. "5ήμερο")
- `start_date` (date): Ημερομηνία έναρξης
- `days_count` (int): Αριθμός ημερών
- `active_shifts` (List[str]): Λίστα βαρδιών
- `roles` (List[str]): Λίστα ρόλων
- `role_requirements` (Dict): Απαιτήσεις ανά ρόλο
- `special_requirements` (str, optional): Ειδικές απαιτήσεις

**Returns:** `List[Dict]` - Λίστα `ShiftPerDay` objects

---

#### `get_employee_availability_structured()`

Επιστρέφει δομημένη διαθεσιμότητα υπαλλήλων.

**Parameters:**
- `employees` (List[dict]): Λίστα υπαλλήλων
- `schedule_start` (date): Αρχή προγράμματος
- `schedule_days` (int): Αριθμός ημερών
- `current_schedule` (DataFrame): Τρέχον πρόγραμμα
- `work_rules` (Dict): Κανόνες εργασίας

**Returns:** `List[Dict]` - Λίστα `EmployeeAvailability` objects

---

#### `get_violations_structured()`

Επιστρέφει δομημένες παραβιάσεις κανόνων.

**Parameters:**
- `schedule_df` (DataFrame): Πρόγραμμα βαρδιών
- `employees` (List[dict]): Υπάλληλοι
- `work_rules` (Dict): Κανόνες εργασίας
- `role_requirements` (Dict): Απαιτήσεις ρόλων
- `business_constraints` (str, optional): Επιχειρηματικοί περιορισμοί

**Returns:** `List[Dict]` - Λίστα `Violation` objects

---

#### `get_suggestions_structured()`

Επιστρέφει δομημένες προτάσεις βελτιστοποίησης.

**Parameters:**
- `schedule_df` (DataFrame): Πρόγραμμα βαρδιών
- `violations` (List[Dict]): Παραβιάσεις
- `employees` (List[dict]): Υπάλληλοι
- `roles` (List[str]): Ρόλοι
- `active_shifts` (List[str]): Βάρδιες
- `optimization_goals` (str): Στόχοι βελτιστοποίησης

**Returns:** `List[Dict]` - Λίστα `Suggestion` objects

---

#### `get_comprehensive_analysis_structured()`

Επιστρέφει ολοκληρωμένη ανάλυση με όλες τις εξόδους.

**Parameters:**
- `business_settings` (Dict): Ρυθμίσεις επιχείρησης
- `employees` (List[dict]): Υπάλληλοι
- `schedule_params` (Dict): Παράμετροι προγράμματος
- `current_schedule` (DataFrame): Τρέχον πρόγραμμα
- `work_rules` (Dict): Κανόνες εργασίας

**Returns:** `Dict` με keys:
- `shifts_per_day`: List of ShiftPerDay
- `employee_availability`: List of EmployeeAvailability
- `violations`: List of Violation
- `suggestions`: List of Suggestion
- `overall_score`: str με βαθμολογία

---

## Pydantic Models

### ShiftPerDay
```python
class ShiftPerDay(BaseModel):
    date: str                    # YYYY-MM-DD
    day_name: str               # Monday, Tuesday, etc.
    shifts: List[dict]          # List of shift details
    total_staff_needed: int     # Total staff for the day
    is_weekend: bool            # Weekend flag
    special_notes: Optional[str]
```

### EmployeeAvailability
```python
class EmployeeAvailability(BaseModel):
    name: str
    available_dates: List[str]
    roles: List[str]
    preferred_shifts: List[str]
    max_weekly_hours: float
    current_weekly_hours: float
    unavailable_dates: List[str]
    constraints: Optional[str]
```

### Violation
```python
class Violation(BaseModel):
    violation_type: str         # MAX_HOURS_EXCEEDED, INSUFFICIENT_REST, etc.
    severity: str              # CRITICAL, HIGH, MEDIUM, LOW
    employee: Optional[str]
    date: Optional[str]
    shift: Optional[str]
    description: str
    rule_violated: str
    current_value: Optional[float]
    max_allowed: Optional[float]
```

### Suggestion
```python
class Suggestion(BaseModel):
    suggestion_type: str        # SWAP, REASSIGN, ADD_EMPLOYEE, etc.
    priority: str              # HIGH, MEDIUM, LOW
    employee: Optional[str]
    employee2: Optional[str]   # For swaps
    date: Optional[str]
    shift: Optional[str]
    role: Optional[str]
    description: str
    expected_benefit: str
    impact_score: Optional[float]  # 0-100
```

---

## Troubleshooting

### DSPy δεν λειτουργεί

1. **Έλεγχος API Key**:
   ```python
   import os
   print(os.getenv("OpenAI_API_KEY"))
   ```

2. **Έλεγχος εγκατάστασης**:
   ```bash
   pip install dspy-ai --upgrade
   ```

3. **Fallback Mode**:
   Αν το DSPy δεν είναι διαθέσιμο, το σύστημα χρησιμοποιεί αυτόματα fallback functions.

### JSON Parse Errors

Αν το LLM επιστρέφει μη-έγκυρο JSON, το σύστημα:
- Χρησιμοποιεί fallback implementations
- Εμφανίζει warning message
- Επιστρέφει basic structured data

---

## Περισσότερες Πληροφορίες

- 📚 [DSPy Documentation](https://dspy-docs.vercel.app/)
- 🔗 [DSPy GitHub](https://github.com/stanfordnlp/dspy)
- 🎓 [DSPy Tutorial](https://dspy-docs.vercel.app/docs/building-blocks/signatures)

---

## Licence

MIT License - Δες LICENSE file για περισσότερες πληροφορίες.
