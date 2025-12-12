# 🚀 Quick Start Guide - DSPy Scheduler Architecture

## 5-Minute Setup

### 1️⃣ Install Dependencies (1 minute)

```bash
cd shift_planner
pip install -r requirements.txt
```

This installs:
- ✅ `dspy-ai` - DSPy framework
- ✅ `pydantic` - Data validation
- ✅ `openai` - OpenAI API client
- ✅ All other dependencies

---

### 2️⃣ Verify Configuration (30 seconds)

Your API key is already configured in `.env`:
```bash
# Check if configured
python -c "from dspy_config import is_configured; print('✅ Ready!' if is_configured() else '❌ Not configured')"
```

Expected output: `✅ Ready!`

---

### 3️⃣ Run Demo (3 minutes)

```bash
python architecture_demo.py
```

This demonstrates:
1. ✅ Schedule generation
2. ✅ Violation analysis
3. ✅ Complete pipeline

**Interactive**: Press Enter between demos to see each step.

---

## 💡 Quick Examples

### Example 1: Generate Schedule

```python
from backend import generate_schedule
from models import Employee, Availability, Constraints

# Create employees
employees = [
    Employee(
        id="emp_001",
        name="Γιάννης",
        role="Manager",
        max_hours_per_week=40
    )
]

# Define availability
availability = [
    Availability(
        employee_id="emp_001",
        day="Mon",
        available_shifts=["day", "morning"]
    )
]

# Set constraints
constraints = Constraints(
    min_staff_per_shift={"day": 2},
    max_staff_per_shift={"day": 5},
    max_weekly_hours=40,
    hard_rules=["No overtime"],
    soft_rules=["Balance workload"]
)

# Generate!
result = generate_schedule(
    employees=employees,
    availability=availability,
    constraints=constraints,
    week_start="2025-12-15",
    days_count=7
)

# Use results
schedule = result['schedule']
print(f"Generated {len(schedule.assignments)} assignments")
print(f"Reasoning: {result['reasoning']}")
```

---

### Example 2: Complete Pipeline

```python
from backend import comprehensive_schedule_pipeline

# One function call for everything!
result = comprehensive_schedule_pipeline(
    employees=employees,
    availability=availability,
    constraints=constraints,
    week_start="2025-12-15",
    days_count=7,
    auto_fix=True,        # Automatically fix violations
    auto_optimize=True    # Automatically optimize
)

# Get results
final_schedule = result['final_schedule']
violations = result['violations']
quality_score = result['quality_score']
suggestions = result['suggestions']

print(f"Quality: {quality_score}/100")
print(f"Violations: {len(violations)}")
print(f"Suggestions: {len(suggestions)}")
```

---

## 📚 Key Files

### Use These Files:

1. **models.py**
   - Data structures (Employee, Schedule, etc.)
   - Import: `from models import Employee, Schedule, ...`

2. **backend.py**
   - Main API functions
   - Import: `from backend import generate_schedule, ...`

3. **dspy_config.py**
   - Configuration (auto-runs on import)
   - Usually no need to import directly

4. **dspy_scheduler.py**
   - DSPy modules (used internally by backend)
   - Usually no need to import directly

### Read These Files:

1. **README_ARCHITECTURE.md**
   - Complete system documentation
   - Architecture diagrams
   - Data flow explanations

2. **IMPLEMENTATION_COMPLETE.md**
   - What was implemented
   - File overview
   - Migration guide

3. **architecture_demo.py**
   - Working examples
   - Copy-paste code

---

## 🎯 Common Tasks

### Task 1: Create an Employee

```python
from models import Employee

employee = Employee(
    id="emp_001",
    name="Γιάννης Παπαδόπουλος",
    role="Manager",
    roles=["Manager", "Barista"],
    max_hours_per_week=40,
    max_hours_per_day=8,
    min_rest_hours=11,
    preferred_shifts=["day", "morning"],
    seniority="senior"
)

# Employee is validated by Pydantic
print(employee.dict())  # Convert to dict
```

---

### Task 2: Define Constraints

```python
from models import Constraints

constraints = Constraints(
    min_staff_per_shift={
        "morning": 2,
        "day": 3,
        "afternoon": 2,
        "evening": 1,
        "night": 1
    },
    max_staff_per_shift={
        "morning": 5,
        "day": 8,
        "afternoon": 5,
        "evening": 3,
        "night": 2
    },
    min_staff_per_role={
        "Manager": {"day": 1, "night": 1},
        "Barista": {"day": 2, "night": 1}
    },
    max_consecutive_days=6,
    max_daily_hours=8,
    max_weekly_hours=40,
    min_rest_hours=11,
    respect_roles=True,
    hard_rules=[
        "No employee works more than max_hours_per_week",
        "Respect employee availability",
        "Each shift must have minimum required staff"
    ],
    soft_rules=[
        "Balance workload across employees",
        "Satisfy preferred shifts",
        "Fair weekend distribution"
    ],
    business_model="5ήμερο"
)
```

---

### Task 3: Analyze Existing Schedule

```python
from backend import analyze_schedule

result = analyze_schedule(
    employees=employees,
    availability=availability,
    constraints=constraints,
    schedule=existing_schedule  # Your Schedule object
)

violations = result['violations']
quality_score = result['quality_score']

# Group violations by severity
critical = [v for v in violations if v.severity == "CRITICAL"]
high = [v for v in violations if v.severity == "HIGH"]

print(f"Quality: {quality_score}/100")
print(f"Critical violations: {len(critical)}")
print(f"High violations: {len(high)}")

for v in critical:
    print(f"- {v.description}")
```

---

### Task 4: Fix Violations

```python
from backend import fix_schedule

result = fix_schedule(
    employees=employees,
    availability=availability,
    constraints=constraints,
    schedule=schedule_with_violations,
    violations=detected_violations
)

suggestions = result['suggestions']
fixed_schedule = result['fixed_schedule']

# Show suggestions
for s in suggestions:
    if s.priority == "HIGH":
        print(f"Priority: {s.priority}")
        print(f"Type: {s.type}")
        print(f"Description: {s.description}")
        print(f"Benefit: {s.expected_benefit}")
        print()

# Use fixed schedule
print(f"Fixed schedule has {len(fixed_schedule.assignments)} assignments")
```

---

## 🔧 Troubleshooting

### Issue: "DSPy not configured"

**Solution**:
```python
from dspy_config import configure_dspy

configure_dspy()  # Manually configure
```

---

### Issue: "OpenAI API key not found"

**Solution**: Check `.env` file has:
```
OPENAI_API_KEY='your-key-here'
```

Or set environment variable:
```bash
export OPENAI_API_KEY='your-key-here'
```

---

### Issue: Import errors

**Solution**: Install dependencies:
```bash
pip install -r requirements.txt
```

---

## 📖 Next Steps

1. ✅ **Run demo**: `python architecture_demo.py`
2. ✅ **Read docs**: `README_ARCHITECTURE.md`
3. ✅ **Try examples**: Copy from `architecture_demo.py`
4. ⏳ **Integrate with Streamlit**: Update `main.py`
5. ⏳ **Add persistence**: SQLite database
6. ⏳ **Train optimizer**: Collect examples, train DSPy

---

## 💬 Support

- **Architecture docs**: `README_ARCHITECTURE.md`
- **Implementation details**: `IMPLEMENTATION_COMPLETE.md`
- **Code examples**: `architecture_demo.py`
- **Original DSPy docs**: `DSPY_README.md`

---

## ✅ You're Ready!

The complete architecture is implemented and working. Start with:

```bash
python architecture_demo.py
```

Then integrate into your Streamlit app using the `backend.py` API!
