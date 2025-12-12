# High-Level Architecture - DSPy Shift Scheduler

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Frontend                        │
│  (UI for configuration, employee management, scheduling)     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                   Backend API (backend.py)                   │
│  - generate_schedule()                                       │
│  - analyze_schedule()                                        │
│  - fix_schedule()                                            │
│  - optimize_schedule()                                       │
│  - comprehensive_schedule_pipeline()                         │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│              DSPy Modules (dspy_scheduler.py)                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ SchedulePlanner       → Generate initial schedule   │    │
│  │ ScheduleAnalyzer      → Detect violations          │    │
│  │ ScheduleFixer         → Fix violations             │    │
│  │ ScheduleOptimizer     → Optimize soft constraints  │    │
│  │ ComprehensiveScheduler → Full pipeline             │    │
│  └─────────────────────────────────────────────────────┘    │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│              DSPy Signatures (dspy_scheduler.py)             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ GenerateSchedule  → Strict I/O for generation      │    │
│  │ AnalyzeSchedule   → Strict I/O for analysis        │    │
│  │ FixSchedule       → Strict I/O for fixes           │    │
│  │ OptimizeSchedule  → Strict I/O for optimization    │    │
│  └─────────────────────────────────────────────────────┘    │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                DSPy Configuration (dspy_config.py)           │
│  - configure_dspy() with OpenAI backend                      │
│  - Model: gpt-4o-mini (or gpt-4, gpt-4o)                    │
│  - Temperature: 0.2 (deterministic)                          │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    OpenAI API Backend                        │
│  - GPT-4o-mini / GPT-4 / GPT-4o                             │
│  - All reasoning happens via DSPy → OpenAI                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              Data Models (models.py - Pydantic)              │
│  - Employee, Availability, Constraints                       │
│  - Schedule, ShiftAssignment                                 │
│  - Violation, Suggestion                                     │
│  - Type-safe, validated data structures                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                 Persistence Layer (Future)                   │
│  - SQLite/PostgreSQL for employees, rules, schedules         │
│  - Store corrected schedules for DSPy optimizer training     │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Components

### 1. **Front-end (Streamlit)**

**Purpose**: User interface for all scheduling operations

**Responsibilities**:
- Configure business rules (shifts, hours, rest rules)
- Manage employees & availability
- Trigger schedule generation
- Show & edit generated schedules
- Display violations and suggestions

**Key Files**:
- `main.py` - Main Streamlit app
- `ui_pages.py` - UI components

---

### 2. **Backend API (backend.py)**

**Purpose**: High-level Python API for scheduling operations

**Key Functions**:

```python
# Generate a new schedule
generate_schedule(employees, availability, constraints, week_start, days_count)
  → Returns: {schedule, reasoning}

# Analyze for violations
analyze_schedule(employees, availability, constraints, schedule)
  → Returns: {violations, analysis, quality_score}

# Fix violations
fix_schedule(employees, availability, constraints, schedule, violations)
  → Returns: {suggestions, fixed_schedule, improvement_explanation}

# Optimize for soft constraints
optimize_schedule(employees, constraints, schedule, optimization_goals)
  → Returns: {optimized_schedule, improvements, explanation}

# Complete pipeline (Generate → Analyze → Fix → Optimize)
comprehensive_schedule_pipeline(employees, availability, constraints, week_start)
  → Returns: {initial_schedule, violations, fixed_schedule, final_schedule, ...}
```

**Characteristics**:
- Works with Pydantic models (type-safe)
- Handles JSON conversion automatically
- Provides clean API for Streamlit
- No direct LLM interaction (delegates to DSPy modules)

---

### 3. **DSPy Modules (dspy_scheduler.py)**

**Purpose**: Wrap DSPy Signatures with Chain of Thought reasoning

**Modules**:

1. **SchedulePlanner**
   - Uses `GenerateSchedule` signature
   - Generates initial weekly schedule
   - Respects hard constraints

2. **ScheduleAnalyzer**
   - Uses `AnalyzeSchedule` signature
   - Detects all violations
   - Provides quality score (0-100)

3. **ScheduleFixer**
   - Uses `FixSchedule` signature
   - Suggests specific fixes
   - Produces improved schedule

4. **ScheduleOptimizer**
   - Uses `OptimizeSchedule` signature
   - Optimizes for soft constraints
   - Balances workload, preferences, fairness

5. **ComprehensiveScheduler**
   - Combines all 4 modules
   - Complete pipeline in one call
   - Configurable (auto_fix, auto_optimize)

---

### 4. **DSPy Signatures (dspy_scheduler.py)**

**Purpose**: Define strict input/output schemas for LLM reasoning

**Signatures**:

#### GenerateSchedule
```python
Inputs:
  - employees: JSON (with roles, hour limits, preferences)
  - availability: JSON (per day/shift availability)
  - constraints: JSON (hard & soft rules)
  - week_start: ISO date
  - days_count: Number of days

Outputs:
  - schedule_json: Structured JSON with assignments
  - reasoning: Explanation of decisions
```

#### AnalyzeSchedule
```python
Inputs:
  - employees, availability, constraints, schedule_json

Outputs:
  - violations_json: Structured list of violations
  - analysis: Natural language explanation
  - quality_score: 0-100 score
```

#### FixSchedule
```python
Inputs:
  - employees, availability, constraints, schedule_json, violations_json

Outputs:
  - suggestions_json: Specific fix suggestions
  - fixed_schedule_json: Improved schedule
  - improvement_explanation: What was fixed
```

#### OptimizeSchedule
```python
Inputs:
  - employees, constraints, schedule_json, optimization_goals

Outputs:
  - optimized_schedule_json: Optimized schedule
  - improvements_json: List of improvements
  - optimization_explanation: What was optimized
```

---

### 5. **DSPy Configuration (dspy_config.py)**

**Purpose**: Configure DSPy with OpenAI backend

**Key Functions**:

```python
configure_dspy(model="gpt-4o-mini", max_tokens=4000, temperature=0.2)
is_configured() → bool
get_dspy_llm() → DSPy LLM instance
get_openai_client() → OpenAI client
```

**Auto-configuration**: Automatically configures on import if `OPENAI_API_KEY` is set

---

### 6. **Data Models (models.py)**

**Purpose**: Type-safe, validated data structures using Pydantic

**Key Models**:

```python
Employee:
  - id, name, role, roles[]
  - max_hours_per_week, max_hours_per_day
  - min_rest_hours, max_consecutive_days
  - preferred_shifts[], seniority

Availability:
  - employee_id, day, date
  - available_shifts[]
  - unavailable, note

Constraints:
  - min_staff_per_shift{}, max_staff_per_shift{}
  - min_staff_per_role{}
  - max_consecutive_days, max_daily_hours, max_weekly_hours
  - hard_rules[], soft_rules[]
  - business_model

ShiftAssignment:
  - day, date, shift
  - employee_id, employee_name
  - role, hours

Schedule:
  - week_start, week_end
  - assignments[]
  - metadata{}

Violation:
  - type, severity (CRITICAL/HIGH/MEDIUM/LOW)
  - employee_id, day, date, shift
  - description, rule_violated
  - current_value, max_allowed

Suggestion:
  - type (SWAP/REASSIGN/ADD_EMPLOYEE/etc.)
  - priority (HIGH/MEDIUM/LOW)
  - employee_id, employee_id2 (for swaps)
  - description, expected_benefit
  - impact_score (0-100)
```

---

## 🔄 Data Flow

### Example: Generate Schedule

```
1. Streamlit UI
   ↓ (user clicks "Generate Schedule")

2. backend.generate_schedule(employees, availability, constraints, week_start)
   ↓ (converts Pydantic models to JSON)

3. SchedulePlanner.forward(employees_json, availability_json, ...)
   ↓ (uses Chain of Thought)

4. GenerateSchedule Signature
   ↓ (defines strict I/O)

5. DSPy → OpenAI API (gpt-4o-mini)
   ↓ (LLM reasoning)

6. Returns schedule_json + reasoning
   ↓ (parses JSON)

7. backend converts to Schedule object
   ↓

8. Streamlit displays schedule
```

---

## 🎯 Why This Architecture?

### Separation of Concerns
- **UI** (Streamlit) only handles presentation
- **Backend** handles business logic & data conversion
- **DSPy Modules** handle AI reasoning
- **Signatures** define contracts
- **Models** ensure type safety

### Future-Proof
- Swap LLM models in one place (dspy_config.py)
- Add new signatures without changing UI
- Easy to add persistence layer
- Can train DSPy optimizers with examples

### Type-Safe
- Pydantic validation at boundaries
- Structured JSON I/O
- No string parsing errors
- Clear error messages

### Maintainable
- Each component has single responsibility
- Clear interfaces between layers
- Easy to test each layer
- Easy to extend

---

## 🚀 Usage Example

```python
from backend import comprehensive_schedule_pipeline
from models import Employee, Availability, Constraints

# Create employees
employees = [
    Employee(
        id="emp_001",
        name="Γιάννης Παπαδόπουλος",
        role="Manager",
        roles=["Manager", "Barista"],
        max_hours_per_week=40
    ),
    # ... more employees
]

# Define availability
availability = [
    Availability(
        employee_id="emp_001",
        day="Mon",
        available_shifts=["day", "morning"]
    ),
    # ... more availability
]

# Set constraints
constraints = Constraints(
    min_staff_per_shift={"day": 2, "night": 1},
    max_staff_per_shift={"day": 5, "night": 3},
    max_consecutive_days=6,
    max_daily_hours=8,
    max_weekly_hours=40,
    hard_rules=["No overtime", "Respect availability"],
    soft_rules=["Balance workload", "Satisfy preferences"]
)

# Generate complete schedule with pipeline
result = comprehensive_schedule_pipeline(
    employees=employees,
    availability=availability,
    constraints=constraints,
    week_start="2025-12-15",
    days_count=7,
    auto_fix=True,
    auto_optimize=True
)

# Access results
print(f"Quality Score: {result['quality_score']}")
print(f"Violations: {len(result['violations'])}")
print(f"Final Schedule: {len(result['final_schedule'].assignments)} assignments")

# Use final schedule
schedule = result['final_schedule']
for assignment in schedule.assignments:
    print(f"{assignment.employee_name} works {assignment.shift} on {assignment.date}")
```

---

## 📊 Optimization (Future)

### Training DSPy with Examples

```python
from dspy import Example
from dspy.optimizers import BootstrapFewShot

# Collect training examples
train_examples = [
    Example(
        employees=employees_json,
        availability=availability_json,
        constraints=constraints_json,
        week_start="2025-12-08",
        schedule_json=gold_schedule_json  # Your ideal schedule
    ).with_inputs("employees", "availability", "constraints", "week_start")
    for ... in your_training_data
]

# Define metric
def schedule_quality_metric(pred, gold):
    # Compare predicted schedule vs gold standard
    # Return score 0-100
    ...

# Optimize
planner = SchedulePlanner()
optimizer = BootstrapFewShot(
    metric=schedule_quality_metric,
    max_bootstrapped_demos=12
)

optimized_planner = optimizer.compile(planner, train_examples)

# Use optimized planner in production
```

---

## 🗂️ File Structure

```
shift_planner/
├── models.py                   # Pydantic data models
├── dspy_config.py             # DSPy configuration with OpenAI
├── dspy_scheduler.py          # DSPy signatures & modules
├── backend.py                 # High-level API functions
├── main.py                    # Streamlit UI (existing)
├── ui_pages.py                # UI components (existing)
├── requirements.txt           # Dependencies
└── README_ARCHITECTURE.md     # This file
```

---

## 🔧 Configuration

### Environment Variables

```bash
# .env file
OPENAI_API_KEY=sk-your-key-here
```

### DSPy Settings

```python
# In dspy_config.py
configure_dspy(
    model="gpt-4o-mini",      # Or "gpt-4", "gpt-4o"
    max_tokens=4000,          # Adjust as needed
    temperature=0.2           # Low for deterministic scheduling
)
```

---

## ✅ Benefits

1. **Structured Output**: Always get valid JSON
2. **Type Safety**: Pydantic validation
3. **Predictable**: Low temperature + strict schemas
4. **Maintainable**: Clear separation of concerns
5. **Extensible**: Easy to add new features
6. **Testable**: Each layer can be tested independently
7. **Future-Proof**: Can swap models, add training, etc.

---

## 📚 Next Steps

1. ✅ Implement core architecture
2. ✅ Create Pydantic models
3. ✅ Set up DSPy configuration
4. ✅ Implement DSPy signatures & modules
5. ✅ Create backend API
6. ⏳ Update Streamlit UI to use backend
7. ⏳ Add persistence layer (SQLite)
8. ⏳ Collect training examples
9. ⏳ Train DSPy optimizer
10. ⏳ Deploy to production

---

## 📖 References

- [DSPy Documentation](https://dspy-docs.vercel.app/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [OpenAI API](https://platform.openai.com/docs/)
- [Streamlit Documentation](https://docs.streamlit.io/)
