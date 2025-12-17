"""
DSPy Signatures for Shift Scheduling Decision Engine.

Signatures define the input/output contracts for reasoning tasks.
These are versioned and tested against golden datasets.
"""

import dspy
from typing import List, Dict, Any


class GenerateWeeklySchedule(dspy.Signature):
    """
    Generate a weekly shift schedule that satisfies hard constraints
    and minimizes soft constraint violations.
    
    Hard Constraints (must satisfy):
    - Employee availability
    - Max daily hours
    - Min rest between shifts
    - Required roles per shift
    
    Soft Constraints (minimize violations):
    - Fair distribution of shifts
    - Preferred shifts
    - Consecutive days limits
    """
    
    employees: List[Dict[str, Any]] = dspy.InputField(
        desc="List of employees with {id, name, roles, availability, preferences}"
    )
    
    shifts_required: Dict[str, List[str]] = dspy.InputField(
        desc="Required shifts per day: {day: [shift_names]}"
    )
    
    roles_required: Dict[str, Dict[str, int]] = dspy.InputField(
        desc="Roles needed per shift: {shift: {role: count}}"
    )
    
    constraints: Dict[str, Any] = dspy.InputField(
        desc="Scheduling constraints: {max_daily_hours, min_rest, max_consecutive_days, work_model}"
    )
    
    week_start: str = dspy.InputField(
        desc="Start date of the week (ISO format: YYYY-MM-DD)"
    )
    
    schedule: List[Dict[str, Any]] = dspy.OutputField(
        desc="Generated schedule: [{date, shift, employee_id, role, hours}]"
    )
    
    reasoning: str = dspy.OutputField(
        desc="Explanation of key scheduling decisions and trade-offs made"
    )


class AnalyzeScheduleViolations(dspy.Signature):
    """
    Analyze a schedule for constraint violations and provide recommendations.
    """
    
    schedule: List[Dict[str, Any]] = dspy.InputField(
        desc="Schedule to analyze: [{date, shift, employee_id, role, hours}]"
    )
    
    constraints: Dict[str, Any] = dspy.InputField(
        desc="Constraints to check against"
    )
    
    employees: List[Dict[str, Any]] = dspy.InputField(
        desc="Employee data for validation"
    )
    
    violations: List[Dict[str, Any]] = dspy.OutputField(
        desc="List of violations: [{type, severity, employee, date, details}]"
    )
    
    recommendations: List[str] = dspy.OutputField(
        desc="Actionable recommendations to fix violations"
    )


class OptimizeAssignment(dspy.Signature):
    """
    Optimize a single shift assignment to minimize violations while maintaining coverage.
    """
    
    shift_date: str = dspy.InputField(desc="Date of the shift")
    shift_name: str = dspy.InputField(desc="Name of the shift (e.g., 'Πρωί')")
    role_needed: str = dspy.InputField(desc="Role required for this assignment")
    
    available_employees: List[Dict[str, Any]] = dspy.InputField(
        desc="Employees who can work this shift"
    )
    
    current_schedule: List[Dict[str, Any]] = dspy.InputField(
        desc="Current schedule context for fairness analysis"
    )
    
    constraints: Dict[str, Any] = dspy.InputField(desc="Scheduling constraints")
    
    best_employee_id: int = dspy.OutputField(
        desc="ID of the best employee for this assignment"
    )
    
    justification: str = dspy.OutputField(
        desc="Why this employee was chosen (fairness, availability, skills)"
    )


class ExplainScheduleDecision(dspy.Signature):
    """
    Explain why a specific scheduling decision was made.
    """
    
    assignment: Dict[str, Any] = dspy.InputField(
        desc="Assignment to explain: {date, shift, employee_id, role}"
    )
    
    alternatives: List[Dict[str, Any]] = dspy.InputField(
        desc="Other employees who could have been assigned"
    )
    
    schedule_context: List[Dict[str, Any]] = dspy.InputField(
        desc="Full schedule for context"
    )
    
    constraints: Dict[str, Any] = dspy.InputField(desc="Constraints applied")
    
    explanation: str = dspy.OutputField(
        desc="Human-readable explanation of why this decision was optimal"
    )
    
    trade_offs: List[str] = dspy.OutputField(
        desc="List of trade-offs considered in this decision"
    )
