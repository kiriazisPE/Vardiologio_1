# Shift Planner - DSPy-Centric AI Architecture

## Overview

This shift scheduling application uses a **Decision Engine architecture** where DSPy becomes a **versioned scheduling policy** that lives inside CI/CD.

The AI is not a chatbot - it's a structured decision engine that:
- ✅ Assigns employees to shifts
- ✅ Respects hard constraints  
- ✅ Minimizes soft violations
- ✅ Produces explainable schedules
- ✅ Can be tested, optimized, and rolled back

## Architecture

```
┌─────────────┐
│   Streamlit │  ← UI Layer (never calls OpenAI directly)
│     UI      │
└──────┬──────┘
       │
       ↓
┌─────────────────┐
│ Planner Service │  ← Service Layer (clean interface)
└──────┬──────────┘
       │
       ↓
┌──────────────────┐
│ DSPy Modules     │  ← Reasoning Layer (versioned artifacts)
│ - ShiftPlanner   │
│ - Analyzer       │
│ - Explainer      │
└──────┬───────────┘
       │
       ↓
┌──────────────────┐
│  Golden Datasets │  ← CI/CD Gates (must pass to deploy)
│  + Evaluation    │
└──────────────────┘
```

## Directory Structure

```
shift_planner/
├── app/
│   ├── streamlit_app.py         # Main UI entry point
│   ├── ui/                       # UI components (pages)
│   └── services/
│       └── planner_service.py    # Service layer (UI ↔ Reasoning)
│
├── reasoning/                    # 🧠 DSPy Decision Engine
│   ├── __init__.py
│   ├── signatures.py             # DSPy Signatures (contracts)
│   ├── modules.py                # DSPy Modules (reasoning logic)
│   ├── evaluation.py             # Metrics & scoring
│   └── optimizers.py             # DSPy optimization logic
│
├── datasets/
│   ├── golden/                   # Test cases for CI gates
│   │   ├── week_simple.json
│   │   ├── week_busy.json
│   │   └── week_edge_cases.json
│   └── live_feedback/            # Real-world data for optimization
│
├── ci/
│   ├── evaluate_reasoning.py     # CI gate - must pass before deploy
│   └── optimize_reasoning.py     # Nightly optimization job
│
└── tests/
    ├── test_hard_constraints.py
    ├── test_soft_constraints.py
    └── test_regressions.py
```

## How It Works

### 1. Reasoning Layer (DSPy)

**Signatures** (`reasoning/signatures.py`):
- Define input/output contracts
- Type-safe interfaces
- Documented expectations

**Modules** (`reasoning/modules.py`):
- `ShiftPlanner`: Main scheduling engine
- `ViolationAnalyzer`: Constraint checking
- `DecisionExplainer`: Transparency & compliance

**Evaluation** (`reasoning/evaluation.py`):
- `score_schedule()`: Comprehensive metrics
- `count_hard_violations()`: Must be 0 for valid schedule
- `detect_regression()`: Compare versions

### 2. Service Layer

**PlannerService** (`app/services/planner_service.py`):
- Clean interface between UI and reasoning
- Handles artifact loading/versioning
- Manages caching and performance
- **UI never calls DSPy directly**

```python
# Streamlit code (simplified)
from app.services.planner_service import get_planner_service

service = get_planner_service()
result = service.generate_weekly_schedule(
    employees=employees,
    active_shifts=shifts,
    roles=roles,
    constraints=constraints,
    week_start="2025-01-06"
)

# result contains:
# - schedule: [{date, shift, employee_id, role}]
# - reasoning: "explanation..."
# - metrics: {hard_violations: 0, soft_violations: 2, ...}
# - recommendations: ["..."]
```

### 3. CI/CD Pipeline

**Evaluation as CI Gate** (`ci/evaluate_reasoning.py`):

```bash
python ci/evaluate_reasoning.py
```

This script:
1. Loads the reasoning artifact
2. Runs it against golden datasets
3. Checks metrics against expected thresholds
4. **Blocks deployment** if hard constraints violated
5. **Warns** if soft constraints regressed

**Exit codes:**
- `0`: ✅ All tests passed - ready for deployment
- `1`: ⚠️ Soft violations - review required
- `2`: 🚨 Hard violations - **BLOCKED**

**Golden Datasets** (`datasets/golden/*.json`):

```json
{
  "name": "week_simple",
  "employees": [...],
  "constraints": {...},
  "expected": {
    "max_hard_violations": 0,
    "max_soft_violations": 2,
    "min_coverage_score": 100.0
  }
}
```

### 4. Deployment & Versioning

**Artifact Versioning:**
```
shift_planner_v1.0.0 → passes CI → production
shift_planner_v1.1.0 → fails CI → blocked
shift_planner_v1.1.1 → passes CI → promotion candidate
```

**Rollback:**
```bash
# Switch artifact version in config
export REASONING_VERSION=1.0.0
# Restart service → instant rollback
```

### 5. Optimization (Controlled)

**Nightly Optimization** (`ci/optimize_reasoning.py`):

```python
from dspy.optimizers import BootstrapFewShot

optimizer = BootstrapFewShot(
    metric=lambda pred, gold: -count_hard_violations(pred)
)

optimized = optimizer.compile(
    ShiftPlanner(),
    load_feedback()
)

optimized.save("reasoning/artifacts/shift_planner_v2")
```

**Rules:**
- ❌ Never runs on PR
- ✅ Runs nightly or manually
- ✅ Produces new artifact
- ✅ New artifact must pass CI before promotion

## Benefits

| Requirement | Solution |
|-------------|----------|
| **Predictability** | Golden datasets + CI gates |
| **Regression Safety** | Version comparison in CI |
| **Explainability** | CoT reasoning + decision explainer |
| **Controlled Evolution** | Versioned artifacts + rollback |
| **Compliance** | Deterministic outputs + audit trail |
| **Testability** | Unit tests for constraints |
| **Deployment Safety** | Can't deploy if CI fails |

## Running Tests

```bash
# Unit tests
pytest tests/

# Reasoning evaluation (CI gate)
python ci/evaluate_reasoning.py

# Optimize (manual/nightly only)
python ci/optimize_reasoning.py
```

## Adding New Test Cases

1. Create `datasets/golden/your_case.json`
2. Define employees, constraints, expected metrics
3. Run `python ci/evaluate_reasoning.py`
4. CI will automatically test on every PR

## Environment Variables

```bash
# Reasoning artifact version
REASONING_VERSION=latest  # or specific version like "1.0.0"

# Reasoning mode
REASONING_MODE=chain_of_thought  # or "react", "basic"

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4
```

## Future Enhancements

- [ ] Artifact storage (S3/Azure Blob)
- [ ] A/B testing framework
- [ ] Real-time feedback loop
- [ ] Multi-model support
- [ ] Cost tracking per artifact
- [ ] Prometheus metrics export

---

**This architecture makes DSPy reasoning:**
- ✅ Testable like code
- ✅ Optimizable like a compiler
- ✅ Deployable like a config
- ✅ Rollbackable like a feature flag
