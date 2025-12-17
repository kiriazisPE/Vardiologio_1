"""
Evaluation Framework - Metrics and scoring for shift scheduling quality.

This module defines how we measure schedule quality for:
- CI/CD gates (must pass before deployment)
- Optimization (guiding DSPy optimization)
- Regression detection (comparing versions)
"""

from typing import List, Dict, Any, Tuple
from collections import defaultdict
from datetime import datetime, timedelta


def score_schedule(
    schedule: List[Dict[str, Any]],
    constraints: Dict[str, Any],
    employees: List[Dict[str, Any]],
    roles_required: Dict[str, Dict[str, int]]
) -> Dict[str, Any]:
    """
    Comprehensive schedule scoring function.
    
    Returns metrics dict with:
        - hard_violations: Must be 0 for valid schedule
        - soft_violations: Lower is better
        - coverage_score: Percentage of required shifts filled
        - fairness_score: Std dev of shift distribution
        - overall_score: Weighted composite score
    
    This is the primary metric used in CI gates.
    """
    
    metrics = {
        "hard_violations": count_hard_violations(schedule, constraints, employees),
        "soft_violations": count_soft_violations(schedule, constraints, employees),
        "coverage_score": calculate_coverage(schedule, roles_required),
        "fairness_score": calculate_fairness(schedule, employees),
        "cost_score": calculate_cost(schedule),
    }
    
    # Overall score (0-100, higher is better)
    # Hard violations are dealbreakers
    if metrics["hard_violations"] > 0:
        metrics["overall_score"] = 0.0
    else:
        # Weight the soft metrics
        metrics["overall_score"] = (
            metrics["coverage_score"] * 0.4 +
            metrics["fairness_score"] * 0.3 +
            max(0, 100 - metrics["soft_violations"] * 5) * 0.2 +
            metrics["cost_score"] * 0.1
        )
    
    metrics["passing"] = (
        metrics["hard_violations"] == 0 and
        metrics["soft_violations"] <= 5 and
        metrics["coverage_score"] >= 95.0
    )
    
    return metrics


def count_hard_violations(
    schedule: List[Dict[str, Any]],
    constraints: Dict[str, Any],
    employees: List[Dict[str, Any]]
) -> int:
    """
    Count violations of hard constraints (must be 0 for valid schedule).
    
    Hard constraints:
    - Employee availability
    - Max daily hours
    - Min rest between shifts
    - Required skills/roles
    """
    violations = 0
    
    # Build employee lookup
    emp_dict = {e["id"]: e for e in employees}
    
    # Group by employee for validation
    by_employee = defaultdict(list)
    for entry in schedule:
        by_employee[entry["employee_id"]].append(entry)
    
    for emp_id, assignments in by_employee.items():
        employee = emp_dict.get(emp_id)
        if not employee:
            violations += len(assignments)  # Unknown employee
            continue
        
        # Check availability
        for entry in assignments:
            date_str = entry["date"]
            shift = entry["shift"]
            availability = employee.get("availability", {})
            
            # Parse date to get day of week
            date_obj = datetime.fromisoformat(date_str)
            day_name = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"][date_obj.weekday()]
            
            if day_name in availability:
                if shift not in availability[day_name]:
                    violations += 1  # Assigned when unavailable
        
        # Check max daily hours
        daily_hours = defaultdict(float)
        for entry in assignments:
            daily_hours[entry["date"]] += entry.get("hours", 8)
        
        max_daily = constraints.get("max_daily_hours_" + constraints.get("work_model", "5ήμερο").replace("ήμερο", "days"), 8)
        for hours in daily_hours.values():
            if hours > max_daily:
                violations += 1
        
        # Check min rest between shifts
        sorted_assignments = sorted(assignments, key=lambda x: x["date"])
        for i in range(len(sorted_assignments) - 1):
            curr = sorted_assignments[i]
            next_assign = sorted_assignments[i + 1]
            
            curr_date = datetime.fromisoformat(curr["date"])
            next_date = datetime.fromisoformat(next_assign["date"])
            
            # Simple check: if consecutive days, ensure not night->morning
            if (next_date - curr_date).days == 1:
                if curr["shift"] == "Βράδυ" and next_assign["shift"] == "Πρωί":
                    violations += 1  # Less than 11h rest
    
    return violations


def count_soft_violations(
    schedule: List[Dict[str, Any]],
    constraints: Dict[str, Any],
    employees: List[Dict[str, Any]]
) -> int:
    """
    Count violations of soft constraints (minimize but not blocking).
    
    Soft constraints:
    - Consecutive days > 5
    - Uneven distribution
    - Non-preferred shifts
    - Weekend assignments
    """
    violations = 0
    
    by_employee = defaultdict(list)
    for entry in schedule:
        by_employee[entry["employee_id"]].append(entry)
    
    for emp_id, assignments in by_employee.items():
        # Check consecutive days
        dates = sorted([datetime.fromisoformat(a["date"]) for a in assignments])
        consecutive = 1
        max_consecutive = constraints.get("max_consecutive_days", 6)
        
        for i in range(1, len(dates)):
            if (dates[i] - dates[i-1]).days == 1:
                consecutive += 1
                if consecutive > max_consecutive:
                    violations += 1
            else:
                consecutive = 1
    
    return violations


def calculate_coverage(
    schedule: List[Dict[str, Any]],
    roles_required: Dict[str, Dict[str, int]]
) -> float:
    """
    Calculate what percentage of required roles are filled.
    
    Returns: 0-100 (percentage)
    """
    if not roles_required:
        return 100.0
    
    # Count filled roles
    filled = defaultdict(lambda: defaultdict(int))
    for entry in schedule:
        shift_key = f"{entry['date']}_{entry['shift']}"
        filled[shift_key][entry.get("role", "unknown")] += 1
    
    # Count required vs filled
    total_required = 0
    total_filled = 0
    
    for shift_key, roles in roles_required.items():
        for role, count in roles.items():
            total_required += count
            total_filled += min(count, filled[shift_key].get(role, 0))
    
    if total_required == 0:
        return 100.0
    
    return (total_filled / total_required) * 100.0


def calculate_fairness(
    schedule: List[Dict[str, Any]],
    employees: List[Dict[str, Any]]
) -> float:
    """
    Calculate fairness of shift distribution.
    
    Returns: 0-100 (100 = perfectly fair, lower = more uneven)
    """
    if not employees:
        return 100.0
    
    # Count assignments per employee
    assignment_counts = defaultdict(int)
    for entry in schedule:
        assignment_counts[entry["employee_id"]] += 1
    
    # Include employees with 0 assignments
    for emp in employees:
        if emp["id"] not in assignment_counts:
            assignment_counts[emp["id"]] = 0
    
    counts = list(assignment_counts.values())
    if not counts:
        return 100.0
    
    # Calculate standard deviation
    mean = sum(counts) / len(counts)
    variance = sum((x - mean) ** 2 for x in counts) / len(counts)
    std_dev = variance ** 0.5
    
    # Convert to 0-100 score (lower std dev = higher score)
    # Perfect fairness (std_dev=0) = 100
    # std_dev >= 5 = 0
    score = max(0, 100 - (std_dev * 20))
    
    return score


def calculate_cost(schedule: List[Dict[str, Any]]) -> float:
    """
    Calculate cost efficiency (overtime, night shifts, weekends).
    
    Returns: 0-100 (100 = lowest cost)
    """
    if not schedule:
        return 100.0
    
    total_shifts = len(schedule)
    premium_shifts = 0
    
    for entry in schedule:
        shift = entry.get("shift", "")
        date_obj = datetime.fromisoformat(entry["date"])
        
        # Night shift premium
        if shift == "Βράδυ":
            premium_shifts += 0.5
        
        # Weekend premium
        if date_obj.weekday() >= 5:  # Saturday or Sunday
            premium_shifts += 0.3
    
    # Lower premium percentage = higher score
    premium_ratio = premium_shifts / total_shifts if total_shifts > 0 else 0
    score = max(0, 100 - (premium_ratio * 100))
    
    return score


# Regression detection
def detect_regression(
    current_metrics: Dict[str, Any],
    baseline_metrics: Dict[str, Any],
    tolerance: float = 0.05
) -> Tuple[bool, List[str]]:
    """
    Detect if current schedule regressed vs baseline.
    
    Args:
        current_metrics: Metrics from current reasoning artifact
        baseline_metrics: Metrics from baseline (e.g., production)
        tolerance: Allowed degradation (5% default)
    
    Returns:
        (is_regression, [list of degraded metrics])
    """
    regressed_metrics = []
    
    # Check key metrics
    for metric in ["overall_score", "coverage_score", "fairness_score"]:
        current_val = current_metrics.get(metric, 0)
        baseline_val = baseline_metrics.get(metric, 0)
        
        # Allow small degradation within tolerance
        if current_val < baseline_val * (1 - tolerance):
            regressed_metrics.append(
                f"{metric}: {current_val:.2f} < {baseline_val:.2f} (baseline)"
            )
    
    # Hard violations must not increase
    if current_metrics.get("hard_violations", 0) > baseline_metrics.get("hard_violations", 0):
        regressed_metrics.append("hard_violations increased")
    
    is_regression = len(regressed_metrics) > 0
    
    return is_regression, regressed_metrics
